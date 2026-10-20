"""Call options (`AgentTask.options`, `PythonTask.options`) and cancellation: by default a task
runs to its end whatever happens to the flow call that created it; one called with
`.options(cancellable=True)` is cancelled (stop `cancelled`) once every flow call that
created it or waited for it was closed."""

import asyncio
import json
import os
import sys
import threading
import time

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, TaskFailed, agent_task, python_task
from contraagent.backends import ClaudeBackend
from contraagent.config import Limits
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent
from fake_cli import write_fake_cli


class Answer(BaseModel):
    text: str


def answered(launch):
    return {"text": launch.unit}


probe = agent_task("probe", instructions="Answer the question.", output=Answer, max_turns=1, timeout_s=30)


def pipeline(tmp_path, agent, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


@python_task
def gate(unit: str) -> None:
    raise RuntimeError(f"{unit} is closed")


# --- options ---------------------------------------------------------------------------------


def test_options_returns_the_same_declaration_with_its_options(tmp_path):
    keyed = probe.options(key="first", priority=2).options(cancellable=True)
    assert type(keyed) is type(probe) and keyed is not probe
    assert keyed.kind == probe.kind and keyed.digest() == probe.digest() and probe.differences(keyed) == []
    again = keyed.options(priority=5)  # what is not given keeps its value

    seen: list[tuple] = []

    def flow():
        for task, unit in ((probe, "a"), (keyed, "b"), (again, "c")):
            pending = task(unit)
            seen.append((pending.key, pending._node.priority, pending._node.cancellable, pending._node.spec is probe))

    report = pipeline(tmp_path, StubAgent({"probe": answered})).run(flow)
    assert report.ok, report.failed
    assert seen == [("probe-a", 0.0, False, True), ("first", 2.0, True, True), ("first~2", 5.0, True, True)]


def test_the_graph_computes_the_digest_of_one_declaration_once(tmp_path, monkeypatch):
    calls: list[str] = []
    digest = type(probe).digest

    def counted(self):
        calls.append(self.kind)
        return digest(self)

    monkeypatch.setattr(type(probe), "digest", counted)

    def flow():
        probe("a")
        probe.options(key="k1")("b")
        probe.options(key="k2", priority=1)("c")

    report = pipeline(tmp_path, StubAgent({"probe": answered})).run(flow)
    assert report.ok, report.failed
    assert calls.count("probe") == 1


def test_an_option_not_given_keeps_its_value_and_none_clears_it(tmp_path):
    keyed = probe.options(key="x", credential="team", priority=2)
    kept = keyed.options(cancellable=True)  # key, credential and priority not given: kept
    cleared = kept.options(key=None, credential=None)
    assert kept._options.key == "x" and kept._options.credential == "team" and kept._options.priority == 2.0
    assert cleared._options.key is None and cleared._options.credential == "" and cleared._options.priority == 2.0

    keys: list[str] = []

    def flow():
        keys.append(kept.options(credential=None)("a").key)
        keys.append(cleared("a").key)

    report = pipeline(tmp_path, StubAgent({"probe": answered})).run(flow)
    assert report.ok, report.failed
    assert keys == ["x", "probe-a"]


def test_options_of_a_python_task_keep_its_parameter_types_and_take_no_credential():
    @python_task
    def tally(n: int) -> int:
        return n

    ranked = tally.options(priority=3)
    assert ranked._param_types is tally._param_types  # built once, at the declaration
    with pytest.raises(TypeError):
        ranked.options(credential="team")  # type: ignore[call-arg]


@pytest.mark.parametrize("word", ["key", "after", "priority", "credential", "cancellable"])
def test_a_call_option_given_to_the_call_names_options(word):
    with pytest.raises(TypeError, match=rf"{word}= is a call option.*probe\.options\({word}=\.\.\.\)"):
        probe("a", **{word: "x"})


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ({"key": 3}, "probe.options(...): key must be a string or None, not 3"),
        ({"priority": "high"}, "probe.options(...): priority must be a finite number"),
        ({"after": "other"}, "probe.options(...): after takes a list of tasks"),
        ({"credential": " team"}, "probe.options(...): credential must name a [credentials.<name>]"),
        ({"cancellable": 1}, "probe.options(...): cancellable must be True or False"),
    ],
)
def test_options_are_checked_where_they_are_given(given, says):
    with pytest.raises(TypeError) as caught:
        probe.options(**given)
    assert says in str(caught.value)


# --- cancellation ----------------------------------------------------------------------------


def closing_flow(task):
    """A flow whose TaskGroup closes the flow call that created `task` (held back by
    `after=` until the gate fails), and catches the failure."""

    async def asks(gated):
        return await task.options(after=[gated])("q")

    async def fails(gated):
        await gated

    async def flow():
        gated = gate("door")
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(asks(gated))
                group.create_task(fails(gated))
        except* TaskFailed:
            pass
        return "closed"

    return flow


def test_by_default_a_task_of_a_closed_flow_call_runs_to_its_end_and_is_journaled(tmp_path):
    agent = StubAgent({"probe": answered})
    report = pipeline(tmp_path, agent).run(closing_flow(probe))
    assert report.value == "closed"
    assert report.results["probe-q"].ok and [launch.unit for launch in agent.launches] == ["q"]
    assert [row["stop"] for row in journal(report) if row["key"] == "probe-q"] == ["completed"]
    assert report.cancelled == []
    calls = [json.loads(line) for line in (report.run_dir / "flow_calls.jsonl").read_text().splitlines()]
    assert any(row.get("state") == "closed" for row in calls)


def test_a_queued_cancellable_task_is_cancelled_and_never_launched(tmp_path):
    agent = StubAgent({"probe": answered})
    report = pipeline(tmp_path, agent).run(closing_flow(probe.options(cancellable=True)), run_id="r")
    assert report.value == "closed"
    assert agent.launches == []
    result = report.results["probe-q"]
    assert result.stop == "cancelled" and not result.ok
    assert report.cancelled == [result] and result not in report.failed
    [row] = [row for row in journal(report) if row["key"] == "probe-q"]
    assert row["stop"] == "cancelled" and not row["ok"]
    assert row["fingerprint"] == result.task.fingerprint and row["fingerprint_parts"] == result.task.fingerprint_parts
    assert row["fingerprint_parts"]  # journaled as any attempt is: a resume compares it part by part
    assert report.summary["by_stop"].get("cancelled") == 1
    monitor = Monitor(tmp_path / "runs")
    [node] = [n for n in monitor.plan("r")["nodes"] if n["key"] == "probe-q"]
    assert node["state"] == "cancelled"
    [run] = monitor.runs()
    assert run["tasks"]["cancelled"] == 1 and run["tasks"]["failed"] == 1  # the gate failed

    async def calm():  # the resume runs it again: a cancelled task is not ok
        return await probe.options(cancellable=True)("q")

    again = pipeline(tmp_path, agent).run(calm, run_id="r", resume=True)
    assert again.ok and again.results["probe-q"].stop == "completed"  # not skipped: run again, as a failed task is
    assert [launch.unit for launch in agent.launches] == ["q"]


def test_a_task_a_live_flow_call_waits_for_is_not_cancelled(tmp_path):
    shared = []

    async def maker(gated):
        shared.append(pending := probe.options(cancellable=True, after=[gated])("q"))
        await pending

    async def fails(gated):
        await gated

    async def watcher():
        while not shared:
            await asyncio.sleep(0)
        return await shared[0]

    async def flow():
        watching = asyncio.create_task(watcher())
        gated = gate("door")
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(maker(gated))
                group.create_task(fails(gated))
        except* TaskFailed:
            pass
        return (await watching).text

    agent = StubAgent({"probe": answered})
    report = pipeline(tmp_path, agent).run(flow)
    assert report.value == "q"
    assert report.results["probe-q"].stop == "completed" and report.cancelled == []


def test_a_running_python_task_runs_to_its_end_when_it_is_cancelled(tmp_path, monkeypatch):
    from contraagent.engine import WorkQueue

    started, release = threading.Event(), threading.Event()
    cancelled: list[str] = []

    @python_task
    def slow(unit: str) -> int:
        started.set()
        assert release.wait(30), "cancel was never asked"
        return 7

    @python_task
    def door(unit: str) -> None:
        assert started.wait(30)
        raise RuntimeError("closed")

    cancel = WorkQueue.cancel

    def cancel_then_release(self, key):
        done = cancel(self, key)
        cancelled.append(key)
        release.set()
        return done

    monkeypatch.setattr(WorkQueue, "cancel", cancel_then_release)

    async def runs():
        return await slow.options(cancellable=True)("s")

    async def fails():
        await door("d")

    async def flow():
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(runs())
                group.create_task(fails())
        except* TaskFailed:
            pass
        return "closed"

    report = pipeline(tmp_path, StubAgent()).run(flow)
    assert report.value == "closed" and cancelled == ["python:slow-s"]
    result = report.results["python:slow-s"]
    assert result.ok and result.stop == "completed" and report.cancelled == []


SLOW_CLAUDE = r"""
import os, pathlib, sys, time
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)"); sys.exit(0)
pathlib.Path("notes").mkdir(exist_ok=True)
pathlib.Path("notes/q.md").write_text("half a thought\n")
pathlib.Path("started").write_text(str(os.getpid()))
time.sleep(600)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="a fake coding agent is a #! script")
def test_a_running_cancellable_agent_task_has_its_launch_stopped_and_is_not_retried(tmp_path):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "claude", SLOW_CLAUDE)
    work = tmp_path / "work"
    work.mkdir()
    marker = work / "started"
    thinker = agent_task(
        "think",
        instructions="Think it over.",
        output=Answer,
        changes=["notes/{unit}.md"],
        max_turns=1,
        timeout_s=120,
        retries=2,
    )

    @python_task
    def door(unit: str) -> None:
        deadline = time.monotonic() + 60
        while not marker.exists():  # the launch is running
            assert time.monotonic() < deadline, "the launch never started"
            time.sleep(0.02)
        raise RuntimeError("closed")

    async def thinks():
        return await thinker.options(cancellable=True)("q")

    async def fails():
        await door("d")

    async def flow():
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(thinks())
                group.create_task(fails())
        except* TaskFailed:
            pass
        return "closed"

    backend = ClaudeBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path)})
    t0 = time.monotonic()
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", backends={"claude": backend}, cwd=work, preflight="off", log=lambda line: None)
    report = pipeline.run(flow)
    assert time.monotonic() - t0 < 60
    assert report.value == "closed"
    result = report.results["think-q"]
    assert result.stop == "cancelled" and report.cancelled == [result]
    rows = [row for row in journal(report) if row["key"] == "think-q"]
    assert len(rows) == 1 and rows[0]["stop"] == "cancelled"  # one attempt: not retried
    assert rows[0]["changes"]["removed"] == ["notes/q.md"] and not (work / "notes" / "q.md").exists()
    assert result.wall_s < Limits(timeout_s=120).timeout_s


def test_the_example_s_first_blocking_finding_cancels_the_probes_still_queued(tmp_path):
    """The tasks topic's example: one slot, so the security probe runs first; its blocking
    finding closes the other flow calls, and their probes are cancelled, never launched."""
    from contraagent.docs.examples.cancel import flow

    agent = StubAgent(
        {
            "probe-c1-security": {"blocking": True, "note": "the token is in the query string"},
            "probe": {"blocking": False, "note": "nothing found"},
        }
    )
    report = pipeline(tmp_path, agent, max_concurrent=1).run(flow.review, "c1")
    assert report.value == "blocked: the token is in the query string"
    assert [launch.key for launch in agent.launches] == ["probe-c1-security"]
    assert sorted(r.task.key for r in report.cancelled) == ["probe-c1-data", "probe-c1-license"]
    assert report.ok

    clear = pipeline(tmp_path / "clear", StubAgent({"probe": {"blocking": False, "note": "nothing found"}})).run(flow.review, "c2")
    assert clear.value == "clear" and clear.cancelled == []
