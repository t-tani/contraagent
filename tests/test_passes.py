"""Loops and passes (`contraagent._internal.pipeline.loops`), and fingerprints.

A pass is one iteration of one loop of flow code, counted from the loop's back edges
(`sys.monitoring`). Bytecode differs between Python versions; run this on each one
`requires-python` admits (`uv run --python 3.12 pytest tests/test_passes.py`, ... 3.14)."""

import asyncio
import importlib.util
import inspect
import json
import sys
import textwrap

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, TooManyPasses, agent_task, max_passes, python_task
from contraagent._internal.pipeline import loops
from contraagent.testing import StubAgent

# --- counting, against counters the flows keep themselves ------------------------------
#
# Each flow awaits `at(...)`: the passes it expects at that point, outermost loop first.


class at:
    """What a shape expects where it awaits: the driver (`observed`) receives the passes."""

    def __init__(self, *passes: int) -> None:
        self.passes = list(passes)

    def __await__(self):
        yield self.passes


async def nested(n, m):
    a = 0
    for _ in range(n):
        a += 1
        b = 0
        for _ in range(m):
            b += 1
            await at(a, b)
        await at(a)


async def while_true_starting_with_a_for(ys):
    a = 0
    while True:
        a += 1
        b = 0
        for _ in ys:
            b += 1
            await at(a, b)
        if a == 3:
            break


async def while_true_starting_with_a_while(n):
    a = 0
    while True:
        a += 1
        b = k = 0
        while k < n:
            b += 1
            k += 1
            await at(a, b)
        if a == 3:
            break
    await at()


async def an_await_in_a_while_test(n):
    a = 1
    while (await at(a)) is None and a < n:
        await at(a)
        a += 1


async def branches(n):
    a = 0
    for k in range(n):
        a += 1
        if k % 2 == 0:
            await at(a)
        else:
            await at(a)


async def continue_and_break():
    a = 0
    while True:
        a += 1
        if a % 3 == 0:
            continue  # an iteration that awaits nothing
        if a > 10:
            break
        await at(a)
    await at()


async def comprehensions_in_a_loop(n):
    a = 0
    for _ in range(n):
        a += 1
        _ = [y for y in range(5) if y]
        await at(a)
        await at(*[[a] for _ in range(3)][0])
    await at(*[[] for _ in range(2)][0])


async def helper(n):
    a = 0
    for _ in range(n):
        a += 1
        await at(a)


async def a_loop_through_an_awaited_helper(n):
    a = 0
    for _ in range(n):
        a += 1
        await at(a)
        await helper(2)


async def exceptions_in_a_loop(n):
    a = 0
    for i in range(n):
        a += 1
        try:
            if i % 2:
                raise ValueError
            await at(a)
        except ValueError:
            continue
        finally:
            pass


async def while_with_else(n):
    a = k = 0
    while k < n:
        a += 1
        k += 1
        b = 0
        for _ in range(2):
            b += 1
            await at(a, b)
    else:
        await at()


async def for_with_else(n):
    a = 0
    for _ in range(n):
        a += 1
        await at(a)
    else:
        await at()
    await at()


SHAPES = [
    (nested, (4, 3)),
    (while_true_starting_with_a_for, ([1, 2],)),
    (while_true_starting_with_a_while, (2,)),
    (an_await_in_a_while_test, (3,)),
    (branches, (4,)),
    (continue_and_break, ()),
    (comprehensions_in_a_loop, (3,)),
    (a_loop_through_an_awaited_helper, (3,)),
    (exceptions_in_a_loop, (5,)),
    (while_with_else, (3,)),
    (for_with_else, (2,)),
]


def innermost(coro):
    """The frame where `coro` waits: the last coroutine of its `cr_await` chain."""
    while getattr(coro.cr_await, "cr_frame", None) is not None:
        coro = coro.cr_await
    return coro.cr_frame


def observed(coro, counter):
    """At each await of `at`: (what the flow expected, the passes counted for its innermost frame)."""
    out = []
    try:
        expected = coro.send(None)
        while True:
            out.append((expected, [loop.pass_ for loop in counter.loops(innermost(coro))]))
            expected = coro.send(None)
    except StopIteration:
        pass
    return out


@pytest.mark.parametrize("flow, args", SHAPES, ids=[f.__name__ for f, _ in SHAPES])
def test_the_passes_counted_are_the_iterations_the_flow_made(flow, args):
    counter = loops.LoopCounter()
    with loops.counting(counter):
        seen = observed(flow(*args), counter)
    assert seen and all(expected == got for expected, got in seen), seen


def line_of(fn, text: str) -> int:
    lines, first = inspect.getsourcelines(fn)
    return first + next(i for i, line in enumerate(lines) if text in line)


def test_loops_are_named_by_their_first_lines_outermost_first():
    counter = loops.LoopCounter()
    with loops.counting(counter):
        coro = nested(2, 2)
        coro.send(None)
        assert [(loop.line, loop.pass_) for loop in counter.loops(coro.cr_frame)] == [
            (line_of(nested, "for _ in range(n)"), 1),
            (line_of(nested, "for _ in range(m)"), 1),
        ]
        coro.close()


def test_code_with_no_source_falls_back_to_its_backward_jumps():
    scope: dict = {"at": at}
    exec(compile("async def made(n):\n    for u in range(n):\n        await at(u)\n", "<made>", "exec"), scope)
    counter = loops.LoopCounter()
    with loops.counting(counter):
        got = [passes for _, passes in observed(scope["made"](3), counter)]
    assert got == [[1], [2], [3]]
    assert [loop.line for loop in loops.loops_of(scope["made"].__code__).loops.values()] == [2]
    exec(compile("async def made_while(n):\n    while n:\n        n -= 1\n        await at(n)\n", "<made_while>", "exec"), scope)
    with loops.counting(counter):
        assert len(observed(scope["made_while"](3), counter)) == 3
    assert not loops.is_while("<made>", 2) and loops.is_while("<made_while>", 2)  # each named by its first line
    src = "async def made_continue(n):\n    while n:\n        n -= 1\n        if n == 2:\n            continue\n        await at(n)\n"
    exec(compile(src, "<made_continue>", "exec"), scope)
    with loops.counting(counter):
        got = [passes for _, passes in observed(scope["made_continue"](4), counter)]
    assert got == [[1], [3], [4]]  # `continue` goes back to the same loop


def test_outside_counting_or_with_no_free_tool_id_a_pass_is_none():
    coro = nested(1, 1)
    coro.send(None)
    assert [loop.pass_ for loop in loops.LoopCounter().loops(coro.cr_frame)] == [None, None]
    coro.close()
    mon = sys.monitoring
    taken = [t for t in loops.TOOL_IDS if mon.get_tool(t) is None]
    for t in taken:
        mon.use_tool_id(t, "another tool")
    try:
        counter = loops.LoopCounter()
        with loops.counting(counter):
            assert [p for _, p in observed(nested(2, 1), counter)] == [[None, None], [None], [None, None], [None]]
    finally:
        for t in taken:
            mon.free_tool_id(t)


def test_the_tool_id_is_freed_when_counting_ends_and_another_tool_keeps_its_own():
    mon = sys.monitoring
    before = {t: mon.get_tool(t) for t in loops.TOOL_IDS}
    mon.use_tool_id(loops.TOOL_IDS[0], "another tool")
    try:
        counter = loops.LoopCounter()
        with loops.counting(counter):
            assert mon.get_tool(loops.TOOL_IDS[1]) == loops.TOOL_NAME
            assert all(e == g for e, g in observed(nested(2, 2), counter))
        assert mon.get_tool(loops.TOOL_IDS[1]) is None
    finally:
        mon.free_tool_id(loops.TOOL_IDS[0])
    assert {t: mon.get_tool(t) for t in loops.TOOL_IDS} == before


def jumps_seen_by_a_later_tool(fn) -> list[str]:
    """The functions whose back edges a tool that takes contraagent's id after it sees."""
    mon = sys.monitoring
    tool = next(t for t in loops.TOOL_IDS if mon.get_tool(t) is None)
    seen: list[str] = []
    mon.use_tool_id(tool, "a later tool")
    try:
        mon.register_callback(tool, mon.events.JUMP, lambda code, src, dst: seen.append(code.co_name) if dst < src else None)
        mon.set_events(tool, mon.events.JUMP)
        fn()
    finally:
        mon.set_events(tool, 0)
        mon.register_callback(tool, mon.events.JUMP, None)
        mon.free_tool_id(tool)
    return seen


def test_a_tool_that_takes_the_id_after_counting_receives_every_jump():
    """`DISABLE` outlives `free_tool_id` (and 3.14's `clear_tool_id`): the counter turns the
    locations it disabled back on as it frees the id (`restart_events`)."""

    def plain():  # not flow code's loop (not an async def): disabled at its first jump
        total = 0
        for i in range(3):
            total += i
        return total

    with loops.counting(loops.LoopCounter()):
        plain()
    assert "plain" in jumps_seen_by_a_later_tool(plain)


def test_with_both_tool_ids_taken_a_run_counts_nothing_and_ends_as_any_other(tmp_path):
    mon = sys.monitoring
    taken = [t for t in loops.TOOL_IDS if mon.get_tool(t) is None]
    for t in taken:
        mon.use_tool_id(t, "another tool")
    try:

        async def flow():
            for k in range(3):
                await step("u", n=k)

        rep = pipeline(tmp_path).run(flow)
    finally:
        for t in taken:
            mon.free_tool_id(t)
    assert rep.ok and not rep.flow_errors
    assert [passes(r) for r in plan_of(rep).values()] == [[None], [None], [None]]


def test_where_the_callback_cannot_find_the_jumping_frame_nothing_is_counted(tmp_path, monkeypatch):
    """Off CPython (no `sys.monitoring`, or a callback not run on the jumping frame): the
    tool is not taken."""
    monkeypatch.setattr(loops, "_monitoring", lambda: None)

    async def flow():
        for k in range(2):
            await step("u", n=k)

    rep = pipeline(tmp_path).run(flow)
    assert rep.ok and [passes(r) for r in plan_of(rep).values()] == [[None], [None]]
    assert all(sys.monitoring.get_tool(t) != loops.TOOL_NAME for t in loops.TOOL_IDS)


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="a code object is freed when its last reference goes")
def test_the_analysis_of_a_code_object_goes_with_it():
    """Code made anew at each call (`exec`) does not make the analyses grow."""
    before = len(loops._codes)
    for i in range(20):
        module = compile(f"async def made_{i}(n):\n    while n:\n        n -= 1\n", f"<made_{i}>", "exec")
        code = next(c for c in module.co_consts if isinstance(c, type(module)))
        assert loops.loops_of(code).loops  # analysed: one `while`
        assert len(loops._codes) == before + 1
        del module, code
        assert len(loops._codes) == before


# --- in a pipeline ----------------------------------------------------------------------


class Doc(BaseModel):
    unit: str
    text: str


@python_task
def step(unit: str, n: int = 0) -> int:
    return n + 1


@python_task
def accept(unit: str, n: int = 0) -> bool:
    return n >= 3


def pipeline(tmp_path, agent=None, **kw):
    agent = agent or StubAgent({})
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def rows(rep, name):
    return [json.loads(line) for line in (rep.run_dir / name).read_text().splitlines()]


def plan_of(rep):
    return {r["key"]: r for r in rows(rep, "plan.jsonl")}


def passes(row, depth=-1):
    return [loop["pass"] for loop in row["flow"][depth]["loops"]]


async def grid(cols, rows_):
    for c in range(cols):
        for r in range(rows_):
            await step(f"c{c}r{r}", n=c)


def test_nested_loops_record_the_outer_and_inner_pass_and_4_by_3_is_not_too_many(tmp_path):
    async def flow():
        for c in range(4):
            for r in range(3):
                await step("u", key=f"cell-{c}-{r}", n=c)

    rep = pipeline(tmp_path).run(flow)
    assert rep.ok and not rep.flow_errors
    plan = plan_of(rep)
    assert {k: passes(plan[k]) for k in ("cell-0-0", "cell-1-2", "cell-3-0", "cell-3-2")} == {
        "cell-0-0": [1, 1],
        "cell-1-2": [2, 3],
        "cell-3-0": [4, 1],
        "cell-3-2": [4, 3],
    }


def test_a_branch_in_a_loop_counts_every_iteration(tmp_path):
    async def flow():
        for k in range(4):
            if k % 2 == 0:
                await step("u", n=k)
            else:
                await step("u", n=-k)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [passes(plan[k]) for k in ("python:step-u", "python:step-u~2", "python:step-u~3", "python:step-u~4")] == [[1], [2], [3], [4]]


def test_continue_break_and_iterations_that_create_nothing_still_count(tmp_path):
    async def flow():
        k = 0
        while True:
            k += 1
            if k % 2 == 0:
                continue  # creates nothing
            if k > 7:
                break
            await step("u", n=k)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [passes(r) for r in plan.values()] == [[1], [3], [5], [7]]


def test_a_comprehension_fan_out_has_no_pass_and_no_limit(tmp_path):
    async def flow():
        return await asyncio.gather(*[step(f"u{i}", n=i) for i in range(12)])

    rep = pipeline(tmp_path).run(flow)
    assert rep.ok and not rep.flow_errors and rep.value == list(range(1, 13))
    assert all(r["flow"][-1]["loops"] == [] for r in plan_of(rep).values())


def test_a_loop_inside_an_awaited_helper_is_counted_in_its_own_frame(tmp_path):
    async def inner(u):
        for i in range(3):
            await step(u, n=i)

    async def flow():
        for u in ("a", "b"):
            await inner(u)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [(passes(plan["python:step-b~3"], 0), passes(plan["python:step-b~3"], 1))] == [([2], [3])]
    assert passes(plan["python:step-a"], 0) == [1] and passes(plan["python:step-a"], 1) == [1]


def test_sibling_flow_calls_of_the_same_code_count_on_their_own(tmp_path):
    async def per_unit(u, until):
        n = 0
        while True:
            n = await step(u, n=n)
            if n >= until:
                return n

    async def flow():
        return await asyncio.gather(per_unit("a", 4), per_unit("b", 2), per_unit("c", 3))

    rep = pipeline(tmp_path).run(flow)
    assert rep.value == [4, 2, 3]
    plan = plan_of(rep)
    by_unit: dict[str, list] = {}
    for r in plan.values():
        by_unit.setdefault(r["unit"], []).append((r["flow_call"], passes(r)))
    assert by_unit == {
        "a": [("0.1", [1]), ("0.1", [2]), ("0.1", [3]), ("0.1", [4])],
        "b": [("0.2", [1]), ("0.2", [2])],
        "c": [("0.3", [1]), ("0.3", [2]), ("0.3", [3])],
    }


def test_a_child_flow_call_starts_with_its_parents_frames_and_passes(tmp_path):
    async def child(u):
        return await step(u)

    async def flow():
        for r in range(2):
            await asyncio.gather(*[child(f"u{r}{i}") for i in range(2)])

    rep = pipeline(tmp_path).run(flow)
    starts = {r["id"]: r for r in rows(rep, "flow_calls.jsonl") if r["event"] == "start"}
    assert starts["0"]["flow"] == []
    assert [passes(starts[c]) for c in ("0.1", "0.2", "0.3", "0.4")] == [[1], [1], [2], [2]]
    assert starts["0.3"]["flow"][0]["loops"][0]["line"] == line_of(flow, "for r in range(2)")
    assert plan_of(rep)["python:step-u10"]["flow"][0] == starts["0.3"]["flow"][0]  # the child's tasks start with it


def test_max_passes_bounds_each_while_loop_and_names_it(tmp_path):
    async def flow():
        for c in range(5):
            r = 0
            while r < 5:
                await step(f"u{c}", key=f"cell-{c}-{r}")
                r += 1

    rep = pipeline(tmp_path, max_passes=4).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, TooManyPasses)
    assert f"cell-0-4: pass 5 of the loop at {__file__}:{line_of(flow, 'while r < 5')}" in str(call.error)
    assert "max_passes=4" in str(call.error)


def test_a_function_bound_takes_the_place_of_the_runs_for_its_own_while_loops(tmp_path):
    @max_passes(6)
    async def converge(u):
        r = 0
        while r < 5:
            await step(u, key=f"{u}-{r}")
            r += 1

    @max_passes(2)
    async def short(u):
        r = 0
        while r < 5:
            await step(u, key=f"{u}-{r}")
            r += 1

    async def unbounded(u):
        r = 0
        while r < 5:
            await step(u, key=f"{u}-{r}")
            r += 1

    async def flow():
        for name, child in (("long", converge), ("short", short), ("plain", unbounded)):
            try:
                await asyncio.gather(child(name))
            except TooManyPasses as exc:
                await step(f"failed-{name}", key=f"failed-{name}", n=len(str(exc)))

    rep = pipeline(tmp_path, max_passes=3).run(flow)
    # A broken bound is a flow error even where the flow catches it: the run is not ok.
    assert not rep.ok and not rep.failed
    assert [c.function.rpartition(".")[2] for c in rep.flow_errors] == ["short", "unbounded"]
    assert all(isinstance(c.error, TooManyPasses) for c in rep.flow_errors)
    assert sorted(k for k in rep.results if k.startswith("long")) == [f"long-{r}" for r in range(5)]  # 5 passes, under 6
    assert sorted(k for k in rep.results if k.startswith("short")) == ["short-0", "short-1"]
    assert sorted(k for k in rep.results if k.startswith("plain")) == ["plain-0", "plain-1", "plain-2"]  # the run's 3
    assert "failed-short" in rep.results and "failed-plain" in rep.results and "failed-long" not in rep.results


def test_a_function_bound_names_itself_and_holds_in_an_awaited_helper(tmp_path):
    @max_passes(2)
    async def inner(u):
        r = 0
        while r < 5:
            await step(u, key=f"{u}-{r}")
            r += 1

    async def flow():
        await inner("u")

    rep = pipeline(tmp_path).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, TooManyPasses)
    message = str(call.error)
    assert f"pass 3 of the loop at {__file__}:{line_of(inner, 'while r < 5')}" in message
    assert "max_passes=2 of test_passes." in message and "a larger @max_passes(n) on test_passes." in message


def test_max_passes_refuses_what_it_cannot_bound():
    with pytest.raises(ValueError, match="positive integer"):
        max_passes(0)
    with pytest.raises(TypeError, match="async def function"):

        @max_passes(3)
        def plain():
            return 1

    with pytest.raises(TypeError, match="no `while` loop"):

        @max_passes(3)
        async def only_for():
            for u in range(3):
                await step(f"u{u}")


def test_a_for_loop_has_no_limit(tmp_path):
    async def flow():
        for u in range(25):
            await step(f"u{u}")

    rep = pipeline(tmp_path, max_passes=2).run(flow)
    assert rep.ok and not rep.flow_errors and len(rep.results) == 25
    assert passes(plan_of(rep)["python:step-u24"]) == [25]


def test_max_passes_bounds_a_while_loop_that_creates_child_flow_calls(tmp_path):
    async def child(u):
        return await step(u)

    async def flow():
        r = 0
        while r < 4:
            await asyncio.gather(child(f"u{r}"))
            r += 1

    rep = pipeline(tmp_path, max_passes=2).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, TooManyPasses) and "flow call 0.3" in str(call.error) and "pass 3 of the loop" in str(call.error)
    ends = {r["id"]: r for r in rows(rep, "flow_calls.jsonl") if r["event"] == "end"}
    assert ends["0.3"]["state"] == "raised" and "TooManyPasses" in ends["0.3"]["error"]
    assert sorted(rep.results) == ["python:step-u0", "python:step-u1"]


def test_resume_of_nested_loops_skips_finished_tasks_with_the_same_keys_and_passes(tmp_path):
    async def flow():
        c = 0
        while c < 3:
            n = 0
            while n < 2:
                n = await step(f"u{c}", n=n)
            c += 1

    first = pipeline(tmp_path, max_passes=2).run(flow, run_id="r")
    assert isinstance(first.flow_errors[0].error, TooManyPasses)  # at the outer loop's pass 3
    assert sorted(first.results) == ["python:step-u0", "python:step-u0~2", "python:step-u1", "python:step-u1~2"]
    before = {k: r["flow"] for k, r in plan_of(first).items()}
    again = pipeline(tmp_path).run(flow, run_id="r", resume=True)
    assert again.ok
    assert {k: r.stop for k, r in again.results.items()} == {
        "python:step-u0": "skipped",
        "python:step-u0~2": "skipped",
        "python:step-u1": "skipped",
        "python:step-u1~2": "skipped",
        "python:step-u2": "completed",
        "python:step-u2~2": "completed",
    }
    resumed = [r for r in rows(again, "plan.jsonl")][len(before) :]
    assert {r["key"]: r["flow"] for r in resumed if r["key"] in before} == before
    assert passes(next(r for r in resumed if r["key"] == "python:step-u2~2")) == [3, 2]


# --- fingerprints -----------------------------------------------------------------------


def summary_of(launch):
    return {"unit": launch.unit, "text": "same"}


def test_an_edited_instruction_reruns_and_what_received_the_same_output_does_not(tmp_path):
    def build(instructions):
        write = agent_task("write", instructions=instructions, output=Doc, max_turns=3, timeout_s=30)
        check = agent_task("check", instructions="c", output=Doc, max_turns=3, timeout_s=30)

        async def flow():
            doc = await write("u")
            return await check("u", doc=doc)

        return flow

    agent = StubAgent({"write": summary_of, "check": summary_of})
    assert pipeline(tmp_path, agent).run(build("first"), run_id="r").ok
    agent.launches.clear()
    pipeline(tmp_path, agent).run(build("first"), run_id="r", resume=True)
    assert agent.launches == []
    pipeline(tmp_path, agent).run(build("edited"), run_id="r", resume=True)
    assert [launch.key for launch in agent.launches] == ["write-u"]  # check received the same output


def test_an_edited_python_function_reruns(tmp_path):
    def load(source: str):
        path = tmp_path / "steps_src.py"
        path.write_text(textwrap.dedent(source))
        spec = importlib.util.spec_from_file_location("steps_src", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.flow

    first = (
        "from contraagent import python_task\n"
        "@python_task\ndef add(n: int) -> int:\n    return n + 1\n"
        "async def flow():\n    return await add(n=1)\n"
    )
    rep = pipeline(tmp_path).run(load(first), run_id="r")
    assert rep.value == 2
    rep = pipeline(tmp_path).run(load(first), run_id="r", resume=True)
    assert rep.results["python:add"].stop == "skipped"
    rep = pipeline(tmp_path).run(load(first.replace("n + 1", "n + 10")), run_id="r", resume=True)
    assert rep.results["python:add"].stop == "completed" and rep.value == 11


def test_renaming_a_wrapper_function_does_not_rerun(tmp_path):
    async def body():
        n = await step("u")
        return await step("v", n=n)

    async def wrapper():
        return await body()

    async def renamed():
        return await body()

    assert pipeline(tmp_path).run(wrapper, run_id="r").value == 2
    rep = pipeline(tmp_path).run(renamed, run_id="r", resume=True)
    assert {r.stop for r in rep.results.values()} == {"skipped"}
