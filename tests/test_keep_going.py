"""Keep going: a failed task stops only the code that awaits its output, and the flow
calls that await that code; every other flow call and every queued or running task goes
on, and the run ends not ok once it has done all it can. Where a flow call stopped and
because of which failure: `FlowCall.raised_at` and `raised_by`, `flow_calls.jsonl`.

A task that must still run when the failure reaches the flow waits for `gate`, which the
flow sets where it receives the failure: it runs while the failure passes, by construction."""

import asyncio
import inspect
import json
import threading

import pytest
from pydantic import BaseModel, ValidationError

from contraagent import Pipeline, TaskFailed, agent_task
from contraagent.testing import StubAgent, fails
from test_flow_loop import run

step = agent_task("step", instructions="s", output=str, max_turns=5, timeout_s=60)
slow = agent_task("slow", instructions="w", output=str, max_turns=5, timeout_s=60)


def line_of(function, marker: str) -> int:
    """The line of `function`'s source that holds `marker`."""
    lines, first = inspect.getsourcelines(function)
    [n] = [i for i, text in enumerate(lines) if text.rstrip().endswith(marker)]
    return first + n


def gated(gate: threading.Event):
    """A reply that waits for `gate` before it writes its text."""

    def reply(launch):
        assert gate.wait(60), "the flow never received the failure"
        return f"{launch.key} after the failure"

    return reply


def stub(gate: threading.Event, **script) -> StubAgent:
    return StubAgent({"step": lambda launch: launch.key, "slow": gated(gate), **script})


def pipeline(tmp_path, agent, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def ends(report) -> dict[str, dict]:
    rows = [json.loads(line) for line in (report.run_dir / "flow_calls.jsonl").read_text().splitlines()]
    return {r["id"]: r for r in rows if r["event"] == "end"}


async def unit(u: str):
    await step(u)  # FIRST
    await step(u)
    return await step(u)


async def slow_unit(u: str):
    await slow(u)
    return await step(u)  # created after the failure


def test_one_failing_unit_stops_neither_its_sibling_units_nor_their_running_tasks(tmp_path):
    gate = threading.Event()

    async def flow():
        try:
            return await asyncio.gather(unit("bad"), unit("good"), slow_unit("s"))  # GATHER
        except TaskFailed:
            gate.set()
            raise

    agent = stub(gate, **{"step-bad": fails()})
    rep = pipeline(tmp_path, agent).run(flow)
    assert not rep.ok and rep.value is None
    assert [k for k, r in rep.results.items() if not r.ok] == ["step-bad"]
    assert {k for k, r in rep.results.items() if r.ok} == {"step-good", "step-good~2", "step-good~3", "slow-s", "step-s"}
    assert rep.results["slow-s"].ok and (tmp_path / "runs" / rep.run_id / "out" / "slow" / "s.md").exists()
    [top] = rep.flow_errors
    assert top.raised_by == "step-bad" and top.raised_at is not None
    assert (top.raised_at.function.rpartition(".")[2], top.raised_at.line) == ("flow", line_of(flow, "# GATHER"))
    rows = ends(rep)
    assert {cid: r["state"] for cid, r in rows.items()} == {"0": "raised", "0.1": "raised", "0.2": "returned", "0.3": "returned"}
    assert rows["0.1"]["raised_by"] == rows["0"]["raised_by"] == "step-bad"  # the same key wherever it passes
    assert rows["0.1"]["raised_at"]["line"] == line_of(unit, "# FIRST")
    assert rows["0"]["raised_at"]["line"] == line_of(flow, "# GATHER")
    assert "raised_at" not in rows["0.2"] and "raised_by" not in rows["0.2"]


def test_a_resume_runs_only_the_failed_task_and_what_awaits_it(tmp_path):
    gate = threading.Event()
    gate.set()

    async def flow():
        done = await asyncio.gather(unit("bad"), unit("good"), return_exceptions=True)
        return [d for d in done if isinstance(d, str)]

    agent = stub(gate, **{"step-bad": fails()})
    first = pipeline(tmp_path, agent).run(flow, run_id="r")
    assert not first.ok and not first.flow_errors and first.value == ["step-good~3"]

    agent = stub(gate)
    again = pipeline(tmp_path, agent).run(flow, run_id="r", resume=True)
    assert again.ok and again.value == ["step-bad~3", "step-good~3"]
    assert [launch.key for launch in agent.launches] == ["step-bad", "step-bad~2", "step-bad~3"]


def test_a_parent_that_raises_does_not_close_its_children(tmp_path):
    gate = threading.Event()

    async def flow():
        child = asyncio.create_task(slow_unit("c"))  # never awaited: it goes on without its parent
        try:
            await step("bad")
        except TaskFailed:
            gate.set()
            raise
        return await child

    agent = stub(gate, **{"step-bad": fails()})
    rep = pipeline(tmp_path, agent).run(flow)
    assert not rep.ok and [call.id for call in rep.flow_errors] == ["0"]
    assert rep.results["slow-c"].ok and rep.results["step-c"].ok  # created after its parent ended
    assert {cid: r["state"] for cid, r in ends(rep).items()} == {"0": "raised", "0.1": "returned"}


def test_a_task_group_closes_its_other_flow_calls_and_their_agent_tasks_run_to_their_end(tmp_path):
    gate = threading.Event()

    async def failing():
        await step("bad")

    async def sibling():
        await slow("s")
        await step("never")  # its flow call is closed before

    async def flow():
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(failing())
                tg.create_task(sibling())
        except* TaskFailed:
            gate.set()
            raise

    agent = stub(gate, **{"step-bad": fails()})
    rep = pipeline(tmp_path, agent).run(flow)
    assert not rep.ok
    assert rep.results["slow-s"].ok and "step-never" not in rep.results
    rows = ends(rep)
    assert {cid: r["state"] for cid, r in rows.items()} == {"0": "raised", "0.1": "raised", "0.2": "closed"}
    [top] = rep.flow_errors
    assert isinstance(top.error, ExceptionGroup) and top.raised_by == "step-bad"  # the group's failed task
    assert rows["0"]["raised_by"] == "step-bad" and "raised_by" not in rows["0.2"]


def test_the_review_examples_publish_is_all_or_nothing(tmp_path):
    from contraagent.docs.examples.review import flow as example

    gate = threading.Event()

    async def flow():
        try:
            return await example.publish(["a", "b"])
        except* TaskFailed:
            gate.set()
            raise

    agent = StubAgent(
        {
            "summarize-a": fails(),
            "summarize": gated_summary(gate),
            "review": {"approved": True},
            "revise": lambda launch: launch.params["summary"],
        }
    )
    rep = pipeline(tmp_path, agent).run(flow)
    assert not rep.ok and rep.results["summarize-b"].ok  # it ran to its end after its flow call was closed
    assert "review-b" not in rep.results and "python:report" not in rep.results
    [top] = rep.flow_errors
    assert top.raised_by == "summarize-a"
    assert {cid: r["state"] for cid, r in ends(rep).items()} == {"0": "raised", "0.1": "raised", "0.2": "closed"}


def gated_summary(gate: threading.Event):
    def reply(launch):
        assert gate.wait(60), "the flow never received the failure"
        return {"unit": launch.unit, "points": ["p"]}

    return reply


def test_an_exception_of_flow_code_has_its_line_and_no_task(tmp_path):
    async def flow():
        try:
            await step("bad")
        except TaskFailed as exc:
            raise ValueError(f"no {exc.key}") from exc  # OWN

    rep = pipeline(tmp_path, stub(threading.Event(), **{"step-bad": fails()})).run(flow)
    [top] = rep.flow_errors
    assert top.raised_by is None and top.raised_at is not None and top.raised_at.line == line_of(flow, "# OWN")
    assert "raised_by" not in ends(rep)["0"]


def test_an_exception_of_flow_code_a_parent_tolerates_is_still_a_flow_error(tmp_path):
    async def broken(u: str):
        await step(u)
        raise ValueError(f"bug in {u}")  # BUG

    async def flow():
        done = await asyncio.gather(broken("a"), unit("b"), return_exceptions=True)
        return [d for d in done if isinstance(d, str)]

    rep = pipeline(tmp_path, stub(threading.Event())).run(flow)
    assert rep.value == ["step-b~3"] and not rep.failed  # every task succeeded, and the flow returned
    assert not rep.ok
    [call] = rep.flow_errors
    assert call.id == "0.1" and isinstance(call.error, ValueError) and call.raised_by is None
    assert call.raised_at is not None and call.raised_at.line == line_of(broken, "# BUG")


class Found(BaseModel):
    text: str


class Review(BaseModel):
    found: Found


find = agent_task("find", instructions="f", output=Found, max_turns=5, timeout_s=60)
review = agent_task("review", instructions="r", params=Review, output=str, max_turns=5, timeout_s=60)


def check_text(text: str) -> None:
    raise ValueError(f"no {text}")


def test_an_exception_raised_below_flow_code_is_at_the_flow_s_line(tmp_path):
    """A library (pydantic refusing a `Pending` as a field's value) or a helper that is not
    a coroutine raises below the flow's line: `raised_at` is that line, not theirs."""

    async def library():
        pending = find("a")
        await review("a", Review(found=pending))  # type: ignore[arg-type]  # LIBRARY

    async def helper():
        found = await find("b")
        check_text(found.text)  # HELPER

    agent = StubAgent({"find": lambda launch: {"text": launch.key}})
    for flow, marker, error in ((library, "# LIBRARY", ValidationError), (helper, "# HELPER", ValueError)):
        rep = pipeline(tmp_path, agent).run(flow, run_id=flow.__name__)
        [call] = rep.flow_errors
        assert isinstance(call.error, error) and call.raised_at is not None
        assert (call.raised_at.function.rpartition(".")[2], call.raised_at.line) == (flow.__name__, line_of(flow, marker))
        assert ends(rep)["0"]["raised_at"]["line"] == line_of(flow, marker)


def test_a_task_failure_a_parent_tolerates_fails_the_run_only_as_a_failed_task(tmp_path):
    async def flow():
        done = await asyncio.gather(unit("bad"), unit("good"), return_exceptions=True)
        return [d for d in done if isinstance(d, str)]

    rep = pipeline(tmp_path, stub(threading.Event(), **{"step-bad": fails()})).run(flow)
    assert rep.value == ["step-good~3"] and not rep.flow_errors
    assert not rep.ok and [r.task.key for r in rep.failed] == ["step-bad"]


# --- the driver alone ----------------------------------------------------------


def test_raised_at_is_where_the_exception_left_each_flow_calls_own_code():
    """A helper awaited in the flow call is its own code; a child's frames are not, even
    when the child runs the same function (recursion)."""

    async def top(d):
        async def leaf(k):
            await d.wait("ok-" + k)
            await d.wait(k)  # LEAF

        async def helper(k):
            return await leaf(k)

        async def mid():
            await asyncio.gather(helper("fail-1"))  # MID

        async def nest(n):
            if n == 0:
                await d.wait("fail-2")  # DEEPEST
            await asyncio.gather(nest(n - 1))  # NESTED

        async def own():
            await d.wait("y")
            raise ValueError("own")  # OWN

        await asyncio.gather(mid(), nest(2), own(), return_exceptions=True)

    driver, _ = run(top)

    def at(marker: str) -> int:
        return line_of(test_raised_at_is_where_the_exception_left_each_flow_calls_own_code, f"# {marker}")

    got = {c.id: (c.function.rpartition(".")[2], c.raised_at.line if c.raised_at else None, c.raised_by) for c in driver.calls.values()}
    assert got == {
        "0": ("top", None, None),
        "0.1": ("mid", at("MID"), "fail-1"),
        "0.2": ("nest", at("NESTED"), "fail-2"),
        "0.3": ("own", at("OWN"), None),
        "0.1.1": ("helper", at("LEAF"), "fail-1"),
        "0.2.1": ("nest", at("NESTED"), "fail-2"),
        "0.2.1.1": ("nest", at("DEEPEST"), "fail-2"),
    }


@pytest.mark.parametrize("closing", [False, True])
def test_a_returned_or_closed_flow_call_has_no_raised_at(closing):
    async def top(d):
        async def bad():
            await d.wait("fail-x")

        async def other():
            await d.wait("y")
            await d.wait("z")

        if closing:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(bad())
                tg.create_task(other())
        return await d.wait("after")

    driver, _ = run(top)
    for call in driver.calls.values():
        if call.state != "raised":
            assert call.raised_at is None and call.raised_by is None, call
