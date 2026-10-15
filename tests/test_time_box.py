"""Time boxes: a flow call with a deadline of its own (`time_box`), over the tasks it and
its child flow calls create, beside the run's own deadline."""

import json
import threading
import time
from types import SimpleNamespace

import pytest

from contraagent import Pipeline, PipelineConfig, python_task, time_box
from contraagent.dispatch import FlowDriver, Task, TaskDeferred, TaskResult, WorkQueue, result_or_raise
from contraagent.monitor import Monitor


class Runner:
    """Runs a task by sleeping `params["sleep"]`; records the keys it launched."""

    def __init__(self) -> None:
        self.launched: list[str] = []
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        with self._lock:
            self.launched.append(task.key)
        time.sleep(task.params.get("sleep", 0.0))
        return TaskResult(task=task, ok=True, stop="completed")


def t(key: str, **params) -> Task:
    return Task(key.split("-")[0], key=key, params=params)


def drive(*flows, wait_s: float = 0.0, **queue_options):
    """Run `flows` on a fresh queue, `wait_s` after making it (past a short run deadline)."""
    deferred: list[dict] = []

    def on_event(event, task, **fields):
        if event == "deferred":
            deferred.append({"key": task.key, **fields, "cause": fields["cause"].to_dict()})

    runner = Runner()
    driver = FlowDriver(answer=result_or_raise)
    queue = WorkQueue(runner, max_concurrent=4, on_event=on_event, **queue_options)
    time.sleep(wait_s)
    driver.run(queue, *flows)
    return runner, driver, {d["key"]: d for d in deferred}


# --- the queue's rules, per box ---------------------------------------------------


def test_past_its_deadline_a_box_launches_only_its_finishing_kinds_and_the_tasks_outside_go_on():
    seen: list[str] = []

    def inner():
        yield t("slow-1", sleep=0.3)  # runs past the box's deadline
        try:
            yield t("work-1")  # created past it: deferred
        except TaskDeferred as exc:
            seen.append(exc.key)
        yield t("report-1")  # a finishing kind: launches in the grace window
        return "inner"

    def flow():
        value = yield time_box(inner(), deadline_s=0.1, grace_s=30, finishing_kinds=["report"])
        yield t("publish-1")  # outside the box: launches though its deadline has passed
        return value

    runner, driver, deferred = drive(flow())
    assert runner.launched == ["slow-1", "report-1", "publish-1"]
    assert seen == ["work-1"] and driver.calls["0"].value == "inner"
    assert deferred["work-1"]["cause"] == {"cause": "deadline", "flow_call": "0.1"}
    assert "time box of flow call 0.1" in deferred["work-1"]["reason"]
    box = driver.calls["0.1"].time_box
    assert box is not None and box.deadline_s == 0.1 and box.flow_call == "0.1"
    assert driver.calls["0"].time_box is None


def test_past_its_grace_window_a_box_launches_nothing_and_its_flow_receives_task_deferred():
    def inner():
        yield t("slow-1", sleep=0.2)
        yield t("report-1")

    def flow():
        try:
            yield time_box(inner(), deadline_s=0.05, grace_s=0.0, finishing_kinds=["report"])
        except TaskDeferred as exc:
            yield t("publish-1")
            return exc.key

    runner, driver, deferred = drive(flow())
    assert runner.launched == ["slow-1", "publish-1"]
    assert driver.calls["0"].value == "report-1"  # the box's flow raised; its parent caught it
    assert deferred["report-1"]["cause"] == {"cause": "grace_window", "flow_call": "0.1"}


def test_nested_boxes_the_earliest_deadline_stops_a_task_and_names_its_box():
    def innermost():
        yield t("slow-1", sleep=0.3)
        yield t("work-1")  # past the outer box's deadline, inside the inner's

    def outer():
        yield time_box(innermost(), deadline_s=60)
        yield t("work-2")

    def other():
        try:
            yield time_box(t_gen("in-1"), deadline_s=0.1)  # an inner box earlier than its outer one
        except TaskDeferred:
            pass
        yield t("after-1")  # in the outer box only: its deadline is a minute away

    def flow():
        try:
            yield time_box(outer(), deadline_s=0.1)
        except TaskDeferred:
            pass
        yield time_box(other(), deadline_s=60)

    runner, driver, deferred = drive(flow())
    assert deferred["work-1"]["cause"] == {"cause": "deadline", "flow_call": "0.1"}  # the outer box, the earlier
    assert "work-2" not in runner.launched
    assert "in-2" in deferred and deferred["in-2"]["cause"]["flow_call"] == "0.2.1"
    assert "after-1" in runner.launched
    assert driver.calls["0.1.1"].time_box.deadline_s == 60  # type: ignore[union-attr]


def t_gen(key):
    yield t(key, sleep=0.25)
    yield t(key.replace("-1", "-2"))


def test_in_a_box_s_endgame_a_task_that_cannot_finish_is_deferred_at_once():
    def inner():
        yield Task("long", key="long-1", estimate_s=1000)

    def flow():
        try:
            yield time_box(inner(), deadline_s=5, slack_s=5)
        except TaskDeferred:
            pass
        yield t("publish-1")

    runner, _, deferred = drive(flow())
    assert runner.launched == ["publish-1"]
    cause = deferred["long-1"]["cause"]
    assert cause["cause"] == "cannot_finish" and cause["flow_call"] == "0.1" and cause["need_s"] == 1000


def test_the_run_s_own_deadline_is_unchanged_and_names_no_flow_call():
    def flow():
        try:
            yield t("scan-1")
        except TaskDeferred:
            yield t("report-1")

    runner, _, deferred = drive(flow(), wait_s=0.01, deadline_s=0.001, finishing_kinds=("report",))
    assert runner.launched == ["report-1"]
    assert deferred["scan-1"]["cause"] == {"cause": "deadline"}


def test_time_box_takes_a_generator_and_a_positive_deadline():
    with pytest.raises(TypeError, match="takes a generator"):
        time_box(t("a-1"), deadline_s=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="deadline_s must be a positive"):
        time_box(t_gen("a-1"), deadline_s=0)
    with pytest.raises(TypeError, match="not the string"):
        time_box(t_gen("a-1"), deadline_s=1, finishing_kinds="report")
    assert time_box(t_gen("a-1"), deadline_s=100).slack_s == 25  # a quarter, as the run's


# --- a pipeline: the record, the monitor, resume --------------------------------------

slept: list[str] = []


#: The clock `slow` spends on: the test's `clock`.
spent: list["FakeTime"] = []


@python_task
def slow(unit: str) -> str:
    slept.append(unit)
    spent[-1].spend(0.3)  # past the box's 0.15 s
    return unit


@python_task
def late(unit: str) -> str:
    return unit


@python_task
def publish(unit: str) -> str:
    return unit


def work(unit):
    yield slow(unit)
    try:
        yield late(unit)
    except TaskDeferred:
        return "cut"
    return "whole"


def cycle(unit: str):
    done = yield time_box(work(unit), deadline_s=0.15, grace_s=60, finishing_kinds=["publish"])
    yield publish(unit)
    return done


class FakeTime:
    """The queue's and the flow driver's clock (`time.monotonic`), moved only by `spend`: a
    deadline is crossed by the work a test says took time, never by how loaded the machine
    is. `sleep` and `time` stay real."""

    def __init__(self) -> None:
        self.now = 1000.0
        self._lock = threading.Lock()

    def monotonic(self) -> float:
        with self._lock:
            return self.now

    def spend(self, seconds: float) -> None:
        with self._lock:
            self.now += seconds

    sleep = staticmethod(time.sleep)
    time = staticmethod(time.time)


@pytest.fixture
def clock(monkeypatch):
    import contraagent.dispatch.flow as flow_module
    import contraagent.dispatch.queue as queue_module

    fake = FakeTime()
    monkeypatch.setattr(queue_module, "time", fake)
    monkeypatch.setattr(flow_module, "time", fake)
    return fake


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_pipeline_records_the_box_and_a_resume_starts_its_clock_again(tmp_path, clock):
    slept.clear()
    spent[:] = [clock]
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None)
    first = pipeline.run(cycle, run_id="c", unit="a")
    assert first.value == "cut"
    starts = [r for r in rows(first.run_dir / "flow_calls.jsonl") if r["event"] == "start" and r["id"] == "0.1"]
    box = starts[-1]["time_box"]
    assert box["deadline_s"] == 0.15 and box["grace_s"] == 60 and box["finishing_kinds"] == ["publish"] and box["started_at"]
    [deferral] = rows(first.run_dir / "deferred.jsonl")
    assert deferral["key"] == "python:late-a" and deferral["cause"] == {"cause": "deadline", "flow_call": "0.1"}

    mon = Monitor(tmp_path / "runs")
    plan = mon.plan("c")
    [call] = [c for c in plan["flow_calls"] if c["id"] == "0.1"]
    assert call["time_box"]["deadline_s"] == 0.15
    [node] = [n for n in plan["nodes"] if n["key"] == "python:late-a"]
    assert node["deferred_cause"]["flow_call"] == "0.1"

    # Resumed, the box counts from its flow call's start in this run start: `slow` is
    # skipped at once, so `late` now starts before the deadline.
    second = pipeline.run(cycle, run_id="c", unit="a", resume=True)
    assert second.value == "whole" and slept == ["a"]


def test_the_time_box_example_cuts_the_writes_and_still_summarizes_and_publishes(tmp_path, clock):
    from contraagent.docs.examples.time_box.flow import cycle as topics_cycle
    from contraagent.testing import StubAgent

    def write(launch):
        clock.spend(0.25)  # each write takes a quarter second: a and b start before 0.4 s, c after
        return {"topic": launch.unit, "summary": "s"}

    agent = StubAgent({"write": write, "summarize": {"text": "t"}})
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, backends=agent.backends(), log=lambda line: None)
    report = pipeline.run(topics_cycle, topics=["a", "b", "c", "d"], deadline_s=0.4)
    assert report.value == ["a", "b"]  # c was created past the deadline
    assert [launch.key for launch in agent.launches] == ["write-a", "write-b", "summarize"]
    assert report.results["python:publish"].ok
    [deferral] = rows(report.run_dir / "deferred.jsonl")
    assert deferral["key"] == "write-c" and deferral["cause"] == {"cause": "deadline", "flow_call": "0.1"}
