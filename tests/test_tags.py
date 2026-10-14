"""Tags: templates filled in per task, and capacities by name or by pattern."""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.dispatch import Task, TaskResult, WorkQueue
from contraagent.routing.config import ConfigError
from contraagent.routing.plan import RoutingError
from contraagent.testing import StubAgent


class Spans:
    """Runs a task by sleeping `params["sleep"]`; records each task's (start, end)."""

    def __init__(self) -> None:
        self.spans: dict[str, tuple[float, float]] = {}
        self.starts: list[str] = []
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        with self._lock:
            self.starts.append(task.key)
        time.sleep(task.params.get("sleep", 0.0))
        self.spans[task.key] = (t0, time.monotonic())
        return TaskResult(task=task, ok=True, stop="completed")

    def overlap(self, a: str, b: str) -> bool:
        (a0, a1), (b0, b1) = self.spans[a], self.spans[b]
        return a0 < b1 and b0 < a1


# --- the queue: capacities by name and by pattern ------------------------------------


def test_a_tag_keeps_tasks_of_one_kind_on_one_unit_apart():
    """The unit lock lets two tasks of one kind on one unit overlap; a tag capped at 1 does not."""
    runner = Spans()
    q = WorkQueue(runner, max_concurrent=4, tag_capacity={"topic:a": 1})
    q.add(Task("fix", key="fix-1", unit="a", tags=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("fix", key="fix-2", unit="a", tags=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("fix", key="fix-3", unit="a", params={"sleep": 0.15}))  # no tag: the unit lock alone
    q.run()
    assert not runner.overlap("fix-1", "fix-2")
    assert runner.overlap("fix-1", "fix-3") or runner.overlap("fix-2", "fix-3")


def test_a_pattern_caps_each_tag_it_matches_on_its_own():
    runner = Spans()
    q = WorkQueue(runner, max_concurrent=4, tag_capacity={"topic:*": 1})
    for key, topic in (("a1", "a"), ("a2", "a"), ("b1", "b")):
        q.add(Task("write", key=key, unit=key, tags=(f"topic:{topic}",), params={"sleep": 0.15}))
    q.run()
    assert not runner.overlap("a1", "a2")
    assert runner.overlap("a1", "b1") or runner.overlap("a2", "b1")  # topic:b is not topic:a's place


def test_a_tag_s_name_outranks_a_pattern_and_the_longest_pattern_wins():
    q = WorkQueue(Spans(), tag_capacity={"topic:*": 1, "topic:big*": 3, "topic:bigger": 0, "*": 2})
    assert q.capacity("topic:a") == 1
    assert q.capacity("topic:big-one") == 3
    assert q.capacity("topic:bigger") == 0
    assert q.capacity("heavy") == 2
    assert WorkQueue(Spans(), tag_capacity={"topic:*": 1}).capacity("heavy") is None  # no entry: no limit


def test_an_overdue_task_keeps_a_pattern_tag_it_needs():
    """The starvation guard: `head` needs `topic:a` and `topic:b`, capped by a pattern; while
    `topic:a` is held, later tasks wanting `topic:b` do not take it from an overdue `head`."""
    starts: list[str] = []
    runner = Spans()
    q = WorkQueue(
        runner,
        max_concurrent=4,
        tag_capacity={"topic:*": 1},
        overdue_s=0.0,
        on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None,
    )
    q.add(Task("hold", key="hold", tags=("topic:a",), params={"sleep": 0.2}))
    q.add(Task("kick", key="kick"))

    def follow_up(res: TaskResult) -> list[Task]:
        if res.task.key != "kick":
            return []
        head = Task("head", key="head", tags=("topic:a", "topic:b"), estimate_s=5000)
        return [head] + [Task("filler", key=f"b{i}", tags=("topic:b",), estimate_s=10, params={"sleep": 0.05}) for i in range(3)]

    q.follow_up = follow_up
    q.run()
    assert starts == ["hold", "kick", "head", "b0", "b1", "b2"]


# --- declarations: templates filled in per task --------------------------------------


class Written(BaseModel):
    path: str


def written(launch):
    return {"path": f"topics/{launch.unit}.md"}


def run(tmp_path, flow, agent, **options):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **options).run(flow)


def plan_rows(report) -> dict[str, dict]:
    return {row["key"]: row for row in map(json.loads, (report.run_dir / "plan.jsonl").read_text().splitlines())}


def test_a_tag_naming_unit_is_held_once_per_unit_the_task_locks(tmp_path):
    audit = agent_task("audit", instructions="Audit.", output=Written, tags=["topic:{unit}", "kind:{kind}"], max_turns=3, timeout_s=60)

    @python_task(tags=["topic:{unit}"])
    def count(unit: str) -> int:
        return 1

    def flow():
        audit("a", extra_units=["b", "c"])
        count("d")

    report = run(tmp_path, flow, StubAgent({"audit": written}))
    assert report.ok, report.failed
    rows = plan_rows(report)
    assert rows["audit-a"]["tags"] == ["topic:a", "topic:b", "topic:c", "kind:audit"]
    assert rows["python:count-d"]["tags"] == ["topic:d"]


def test_tag_templates_are_checked_where_they_are_declared_and_called(tmp_path):
    with pytest.raises(ValueError, match="names topic; it may name unit, key and kind"):
        agent_task("bad", instructions="x", tags=["{topic}"], max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="list of tags"):
        agent_task("bad", instructions="x", tags="topic:{unit}", max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match="names topic"):
        python_task(tags=["{topic}"])(lambda: None)
    lonely = agent_task("lonely", instructions="x", output=Written, tags=["topic:{unit}"], max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match="names \\{unit\\}, and the task has no unit"):
        run(tmp_path, lambda: lonely(), StubAgent({"lonely": written}))


def test_tags_leave_the_fingerprint_alone(tmp_path):
    def fingerprint(tags):
        task = agent_task("same", instructions="x", output=Written, tags=tags, max_turns=1, timeout_s=1)
        report = run(tmp_path / str(len(tags)), lambda: task("a"), StubAgent({"same": written}))
        return json.loads((report.run_dir / "journal.jsonl").read_text().splitlines()[0])["fingerprint"]

    assert fingerprint([]) == fingerprint(["topic:{unit}"])


def test_the_config_holds_tag_capacities_and_the_pipeline_outranks_it(tmp_path):
    config = PipelineConfig({"defaults": {"tag_capacity": {"topic:*": 1, "heavy": 2}}})
    assert config.tag_capacity() == {"topic:*": 1, "heavy": 2}
    p = Pipeline(config, runs_dir=tmp_path, backends=StubAgent().backends(), tag_capacity={"heavy": 1})
    assert p.queue_options["tag_capacity"] == {"topic:*": 1, "heavy": 1}
    with pytest.raises(ConfigError, match="is not a non-negative integer"):
        PipelineConfig({"defaults": {"tag_capacity": {"topic:*": -1}}}).tag_capacity()
    bad = PipelineConfig({"defaults": {"tag_capacity": {"topic:*": "one"}}})
    task = agent_task("t", instructions="x", output=Written, max_turns=1, timeout_s=1)
    with pytest.raises(RoutingError, match="tag_capacity"):
        Pipeline(bad, runs_dir=tmp_path / "r", backends=StubAgent({"t": written}).backends()).run(lambda: task("a"))


def test_the_tags_example_writes_each_topic_one_task_at_a_time(tmp_path):
    from contraagent.docs.examples.tags import flow as example

    spans: dict[str, tuple[float, float]] = {}

    def timed(answer):
        def reply(launch):
            t0 = time.monotonic()
            time.sleep(0.1)
            spans[launch.key] = (t0, time.monotonic())
            return answer(launch)

        return reply

    agent = StubAgent({"draft": timed(written), "fix": timed(written), "triage": timed(lambda launch: {"relevant": True})})
    pipe = example.pipeline(runs_dir=tmp_path / "runs", cwd=tmp_path, backends=agent.backends(), log=lambda line: None, max_concurrent=8)
    report = pipe.run(example.topics, names=["alpha", "beta"])
    assert report.ok, report.failed

    def overlap(a: str, b: str) -> bool:
        (a0, a1), (b0, b1) = spans[a], spans[b]
        return a0 < b1 and b0 < a1

    for topic in ("alpha", "beta"):
        writes = [f"draft-{topic}", f"fix-{topic}-style", f"fix-{topic}-terms"]
        assert not any(overlap(a, b) for a in writes for b in writes if a < b)
        assert overlap(f"triage-{topic}-security", f"triage-{topic}-privacy")  # no tag: they share the topic
    fixes = {t: [f"fix-{t}-style", f"fix-{t}-terms"] for t in ("alpha", "beta")}
    assert any(overlap(a, b) for a in fixes["alpha"] for b in fixes["beta"])  # each topic has its own place
