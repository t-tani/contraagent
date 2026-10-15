"""Claims: the names a task holds while it runs, filled in per task, and their capacities."""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from contraagent import ConfigError, Pipeline, PipelineConfig, RoutingError, Task, TaskResult, agent_task, python_task
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


class Spans:
    """Runs a task by sleeping `params["sleep"]`; records each task's (start, end)."""

    def __init__(self) -> None:
        self.spans: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        time.sleep(task.params.get("sleep", 0.0))
        with self._lock:
            self.spans[task.key] = (t0, time.monotonic())
        return TaskResult(task=task, ok=True, stop="completed")

    def overlap(self, a: str, b: str) -> bool:
        (a0, a1), (b0, b1) = self.spans[a], self.spans[b]
        return a0 < b1 and b0 < a1


# --- the queue -----------------------------------------------------------------------


def test_one_task_at_a_time_holds_a_name_across_kinds_and_within_one():
    runner = Spans()
    q = WorkQueue(runner, max_concurrent=4)
    q.add(Task("style", key="style-a", unit="a", claims=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("terms", key="terms-a", unit="a", claims=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("terms", key="terms-a~2", unit="a", claims=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("terms", key="terms-b", unit="b", claims=("topic:b",), params={"sleep": 0.15}))
    q.run()
    writes = ["style-a", "terms-a", "terms-a~2"]
    assert not any(runner.overlap(a, b) for a in writes for b in writes if a < b)
    assert any(runner.overlap(w, "terms-b") for w in writes)  # topic:b is another name
    assert q._held == {}  # every claim released


def test_tasks_that_claim_nothing_run_together_whatever_their_kind_and_unit():
    runner = Spans()
    q = WorkQueue(runner, max_concurrent=4)
    q.add(Task("write", key="write-a", unit="a", claims=("topic:a",), params={"sleep": 0.15}))
    q.add(Task("triage", key="triage-a", unit="a", params={"sleep": 0.15}))
    q.add(Task("triage", key="triage-a~2", unit="a", params={"sleep": 0.15}))
    q.run()
    assert runner.overlap("write-a", "triage-a") and runner.overlap("triage-a", "triage-a~2")


def test_a_pattern_caps_each_name_it_matches_on_its_own():
    runner = Spans()
    q = WorkQueue(runner, max_concurrent=4, claim_capacity={"heavy:*": 2})
    for key in ("x1", "x2", "x3"):
        q.add(Task("parse", key=key, claims=("heavy:x",), params={"sleep": 0.15}))
    q.add(Task("parse", key="y1", claims=("heavy:y",), params={"sleep": 0.15}))
    q.run()
    xs = ["x1", "x2", "x3"]
    pairs = [runner.overlap(a, b) for a in xs for b in xs if a < b]
    assert any(pairs) and not all(pairs)  # two at a time, never three
    assert any(runner.overlap(x, "y1") for x in xs)  # heavy:y has places of its own


def test_a_name_s_own_entry_outranks_a_pattern_and_the_longest_pattern_wins():
    q = WorkQueue(Spans(), claim_capacity={"topic:*": 2, "topic:big*": 3, "topic:bigger": 0, "*": 5})
    assert q.capacity("topic:a") == 2
    assert q.capacity("topic:big-one") == 3
    assert q.capacity("topic:bigger") == 0
    assert q.capacity("heavy") == 5
    assert WorkQueue(Spans()).capacity("heavy") == 1  # no entry: one at a time


def test_a_capacity_of_0_never_starts_the_task():
    seen: list[str] = []
    q = WorkQueue(Spans(), claim_capacity={"off": 0}, follow_up=lambda res: seen.append(res.stop) or [])
    q.add(Task("t", key="t", claims=("off",)))
    q.run()
    assert seen == ["deferred"]


def test_an_overdue_task_keeps_a_name_it_still_needs():
    """The starvation guard: `head` claims `topic:a` and `topic:b`; while `topic:a` is held,
    later tasks claiming `topic:b` do not take it from an overdue `head`."""
    starts: list[str] = []
    q = WorkQueue(
        Spans(),
        max_concurrent=4,
        overdue_s=0.0,
        on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None,
    )
    q.add(Task("hold", key="hold", claims=("topic:a",), params={"sleep": 0.2}))
    q.add(Task("kick", key="kick"))

    def follow_up(res: TaskResult) -> list[Task]:
        if res.task.key != "kick":
            return []
        head = Task("head", key="head", claims=("topic:a", "topic:b"), estimate_s=5000)
        return [head] + [Task("filler", key=f"b{i}", claims=("topic:b",), estimate_s=10, params={"sleep": 0.05}) for i in range(3)]

    q.follow_up = follow_up
    q.run()
    assert starts == ["hold", "kick", "head", "b0", "b1", "b2"]


def test_an_overdue_task_leaves_a_name_with_room_for_both_to_others():
    """The starvation guard takes no place a later task leaves room for: `heavy` holds two,
    so while an overdue `head` waits for `x`, a filler may hold the other place of `heavy`,
    one at a time, never the last one."""
    runner = Spans()
    starts: list[str] = []
    q = WorkQueue(
        runner,
        max_concurrent=4,
        overdue_s=0.0,
        claim_capacity={"heavy": 2},
        on_event=lambda event, task, **f: starts.append(task.key) if event == "start" else None,
    )
    q.add(Task("hold", key="hold", claims=("x",), params={"sleep": 0.3}))
    q.add(Task("kick", key="kick"))

    def follow_up(res: TaskResult) -> list[Task]:
        if res.task.key != "kick":
            return []
        head = Task("head", key="head", claims=("x", "heavy"), estimate_s=5000)
        return [head] + [Task("filler", key=f"f{i}", claims=("heavy",), estimate_s=10, params={"sleep": 0.05}) for i in range(4)]

    q.follow_up = follow_up
    q.run()
    assert starts.index("f0") < starts.index("head")  # `heavy` had room for both
    before = [k for k in starts[: starts.index("head")] if k.startswith("f")]
    assert not any(runner.overlap(a, b) for a in before for b in before if a < b)  # never the last place


# --- declarations: templates filled in per task --------------------------------------


class Written(BaseModel):
    path: str


def written(launch):
    return {"path": f"topics/{launch.unit}.md"}


def run(tmp_path, flow, agent, **options):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **options).run(flow)


def plan_rows(report) -> dict[str, dict]:
    return {row["key"]: row for row in map(json.loads, (report.run_dir / "plan.jsonl").read_text().splitlines())}


def test_claims_are_filled_in_from_the_unit_the_key_the_kind_and_the_params(tmp_path):
    merge = agent_task(
        "merge", instructions="Merge.", output=Written, claims=["topic:{params.topics}", "kind:{kind}", "{key}"], max_turns=3, timeout_s=60
    )

    @python_task(claims=["topic:{unit}", "batch:{params.batch}"])
    def count(unit: str, batch: int) -> int:
        return 1

    def flow():
        merge("a", topics=["a", "b", "a"])
        count("d", batch=7)

    report = run(tmp_path, flow, StubAgent({"merge": written}))
    assert report.ok, report.failed
    rows = plan_rows(report)
    assert rows["merge-a"]["claims"] == ["topic:a", "topic:b", "kind:merge", "merge-a"]
    assert rows["python:count-d"]["claims"] == ["topic:d", "batch:7"]


def test_claim_templates_are_checked_where_they_are_declared_and_called(tmp_path):
    with pytest.raises(ValueError, match="names topic; it may name unit, key, kind and params.<name>"):
        agent_task("bad", instructions="x", claims=["{topic}"], max_turns=1, timeout_s=1)
    with pytest.raises(TypeError, match="list of names"):
        agent_task("bad", instructions="x", claims="topic:{unit}", max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match="takes no format"):
        python_task(claims=["{unit:>4}"])(lambda: None)
    lonely = agent_task("lonely", instructions="x", output=Written, claims=["topic:{unit}"], max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match="names \\{unit\\}, and the task has no unit"):
        run(tmp_path / "1", lambda: lonely(), StubAgent({"lonely": written}))
    by_param = agent_task("by_param", instructions="x", output=Written, claims=["topic:{params.topic}"], max_turns=1, timeout_s=1)
    with pytest.raises(ValueError, match="the call gives no topic"):
        run(tmp_path / "2", lambda: by_param("a"), StubAgent({"by_param": written}))
    with pytest.raises(TypeError, match="a claim takes strings and numbers"):
        run(tmp_path / "3", lambda: by_param("a", topic={"x": 1}), StubAgent({"by_param": written}))
    with pytest.raises(ValueError, match="an empty list; the task would claim nothing"):
        run(tmp_path / "4", lambda: by_param("a", topic=[]), StubAgent({"by_param": written}))


def test_a_claim_of_the_key_names_each_task_of_one_key_apart(tmp_path):
    own = agent_task("own", instructions="x", output=Written, claims=["{key}"], max_turns=1, timeout_s=1)

    def flow():
        own("a")
        own("a")

    report = run(tmp_path, flow, StubAgent({"own": written}))
    assert report.ok, report.failed
    rows = plan_rows(report)
    assert rows["own-a"]["claims"] == ["own-a"] and rows["own-a~2"]["claims"] == ["own-a~2"]


def test_claims_leave_the_fingerprint_alone(tmp_path):
    def fingerprint(claims):
        task = agent_task("same", instructions="x", output=Written, claims=claims, max_turns=1, timeout_s=1)
        report = run(tmp_path / str(len(claims)), lambda: task("a"), StubAgent({"same": written}))
        return json.loads((report.run_dir / "journal.jsonl").read_text().splitlines()[0])["fingerprint"]

    assert fingerprint([]) == fingerprint(["topic:{unit}"])


def test_the_config_holds_claim_capacities_and_the_pipeline_outranks_it(tmp_path):
    config = PipelineConfig({"defaults": {"claim_capacity": {"topic:*": 1, "heavy": 2}}})
    assert config.claim_capacity() == {"topic:*": 1, "heavy": 2}
    p = Pipeline(config, runs_dir=tmp_path, backends=StubAgent().backends(), claim_capacity={"heavy": 3})
    assert p.queue_options["claim_capacity"] == {"topic:*": 1, "heavy": 3}
    with pytest.raises(ConfigError, match="is not a non-negative integer"):
        PipelineConfig({"defaults": {"claim_capacity": {"topic:*": -1}}}).claim_capacity()
    bad = PipelineConfig({"defaults": {"claim_capacity": {"topic:*": "one"}}})
    task = agent_task("t", instructions="x", output=Written, max_turns=1, timeout_s=1)
    with pytest.raises(RoutingError, match="claim_capacity"):
        Pipeline(bad, runs_dir=tmp_path / "r", backends=StubAgent({"t": written}).backends()).run(lambda: task("a"))


def test_the_claims_example_writes_each_topic_one_task_at_a_time(tmp_path):
    from contraagent.docs.examples.claims import flow as example

    spans: dict[str, tuple[float, float]] = {}

    def timed(answer):
        def reply(launch):
            t0 = time.monotonic()
            time.sleep(0.1)
            spans[launch.key] = (t0, time.monotonic())
            return answer(launch)

        return reply

    agent = StubAgent(
        {"style": timed(written), "terms": timed(written), "merge": timed(written), "triage": timed(lambda launch: {"relevant": True})}
    )
    pipe = Pipeline(
        None,
        runs_dir=tmp_path / "runs",
        cwd=tmp_path,
        backends=agent.backends(),
        log=lambda line: None,
        max_concurrent=8,
        claim_capacity=example.CLAIM_CAPACITY,
    )
    report = pipe.run(example.topics, names=["alpha", "beta"])
    assert report.ok, report.failed

    def overlap(a: str, b: str) -> bool:
        (a0, a1), (b0, b1) = spans[a], spans[b]
        return a0 < b1 and b0 < a1

    for topic in ("alpha", "beta"):
        writes = [f"style-{topic}", f"terms-{topic}", "merge"]
        assert not any(overlap(a, b) for a in writes for b in writes if a < b)
    assert overlap("triage-alpha", "style-alpha") or overlap("triage-alpha", "terms-alpha")  # claims nothing
    assert overlap("style-alpha", "style-beta")  # each topic is a name of its own
