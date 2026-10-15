"""Loops and passes (`contraagent._internal.pipeline.loops`), and fingerprints.

A pass is one iteration of one loop of flow code, counted from the loop's back edges
(`sys.monitoring`). Bytecode differs between Python versions; run this on each one
`requires-python` admits (`uv run --python 3.12 pytest tests/test_passes.py`, ... 3.14)."""

import importlib.util
import inspect
import json
import sys
import textwrap

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, TooManyPasses, agent_task, python_task
from contraagent._internal.pipeline import loops
from contraagent.testing import StubAgent

# --- counting, against counters the flows keep themselves ------------------------------
#
# Each generator yields the passes it expects at that point, outermost loop first.


def nested(n, m):
    a = 0
    for _ in range(n):
        a += 1
        b = 0
        for _ in range(m):
            b += 1
            yield [a, b]
        yield [a]


def while_true_starting_with_a_for(ys):
    a = 0
    while True:
        a += 1
        b = 0
        for _ in ys:
            b += 1
            yield [a, b]
        if a == 3:
            break


def while_true_starting_with_a_while(n):
    a = 0
    while True:
        a += 1
        b = k = 0
        while k < n:
            b += 1
            k += 1
            yield [a, b]
        if a == 3:
            break
    yield []


def a_yield_in_a_while_test(n):
    a = 1
    while (yield [a]) is None and a < n:
        yield [a]
        a += 1


def branches(n):
    a = 0
    for k in range(n):
        a += 1
        if k % 2 == 0:
            yield [a]
        else:
            yield [a]


def continue_and_break():
    a = 0
    while True:
        a += 1
        if a % 3 == 0:
            continue  # an iteration that yields nothing
        if a > 10:
            break
        yield [a]
    yield []


def comprehensions_in_a_loop(n):
    a = 0
    for _ in range(n):
        a += 1
        _ = [y for y in range(5) if y]
        yield [a]
        yield [[a] for _ in range(3)][0]
    yield [[] for _ in range(2)][0]


def helper(n):
    a = 0
    for _ in range(n):
        a += 1
        yield [a]


def a_loop_through_yield_from(n):
    a = 0
    for _ in range(n):
        a += 1
        yield [a]
        yield from helper(2)


def exceptions_in_a_loop(n):
    a = 0
    for i in range(n):
        a += 1
        try:
            if i % 2:
                raise ValueError
            yield [a]
        except ValueError:
            continue
        finally:
            pass


def while_with_else(n):
    a = k = 0
    while k < n:
        a += 1
        k += 1
        b = 0
        for _ in range(2):
            b += 1
            yield [a, b]
    else:
        yield []


def for_with_else(n):
    a = 0
    for _ in range(n):
        a += 1
        yield [a]
    else:
        yield []
    yield []


SHAPES = [
    (nested, (4, 3)),
    (while_true_starting_with_a_for, ([1, 2],)),
    (while_true_starting_with_a_while, (2,)),
    (a_yield_in_a_while_test, (3,)),
    (branches, (4,)),
    (continue_and_break, ()),
    (comprehensions_in_a_loop, (3,)),
    (a_loop_through_yield_from, (3,)),
    (exceptions_in_a_loop, (5,)),
    (while_with_else, (3,)),
    (for_with_else, (2,)),
]


def observed(gen, counter):
    """At each yield: (what the flow expected, the passes counted for its innermost frame)."""
    out = []
    try:
        expected = next(gen)
        while True:
            inner = gen
            while inner.gi_yieldfrom is not None:
                inner = inner.gi_yieldfrom
            out.append((expected, [loop.pass_ for loop in counter.loops(inner.gi_frame)]))
            expected = gen.send(None)
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
        gen = nested(2, 2)
        next(gen)
        assert [(loop.line, loop.pass_) for loop in counter.loops(gen.gi_frame)] == [
            (line_of(nested, "for _ in range(n)"), 1),
            (line_of(nested, "for _ in range(m)"), 1),
        ]


def test_code_with_no_source_falls_back_to_its_backward_jumps():
    scope: dict = {}
    exec(compile("def made(n):\n    for u in range(n):\n        yield u\n", "<made>", "exec"), scope)
    counter = loops.LoopCounter()
    with loops.counting(counter):
        gen = scope["made"](3)
        got = [[(loop.line, loop.pass_) for loop in counter.loops(gen.gi_frame)] for _ in gen]
    assert got == [[(2, 1)], [(2, 2)], [(2, 3)]]
    exec(compile("def made_while(n):\n    while n:\n        n -= 1\n        yield n\n", "<made_while>", "exec"), scope)
    with loops.counting(counter):
        assert len(list(scope["made_while"](3))) == 3
    assert not loops.is_while("<made>", 2) and loops.is_while("<made_while>", 3)  # a `for` heads at its FOR_ITER


def test_outside_counting_or_with_no_free_tool_id_a_pass_is_none():
    gen = nested(1, 1)
    next(gen)
    assert [loop.pass_ for loop in loops.LoopCounter().loops(gen.gi_frame)] == [None, None]
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


def grid(cols, rows_):
    for c in range(cols):
        for r in range(rows_):
            yield step(f"c{c}r{r}", n=c)


def test_nested_loops_record_the_outer_and_inner_pass_and_4_by_3_is_not_too_many(tmp_path):
    def flow():
        for c in range(4):
            for r in range(3):
                yield step("u", key=f"cell-{c}-{r}", n=c)

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
    def flow():
        for k in range(4):
            if k % 2 == 0:
                yield step("u", n=k)
            else:
                yield step("u", n=-k)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [passes(plan[k]) for k in ("python:step-u", "python:step-u~2", "python:step-u~3", "python:step-u~4")] == [[1], [2], [3], [4]]


def test_continue_break_and_iterations_that_create_nothing_still_count(tmp_path):
    def flow():
        k = 0
        while True:
            k += 1
            if k % 2 == 0:
                continue  # creates nothing
            if k > 7:
                break
            yield step("u", n=k)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [passes(r) for r in plan.values()] == [[1], [3], [5], [7]]


def test_a_comprehension_fan_out_has_no_pass_and_no_limit(tmp_path):
    def flow():
        return (yield [step(f"u{i}", n=i) for i in range(12)])

    rep = pipeline(tmp_path).run(flow)
    assert rep.ok and not rep.flow_errors and rep.value == list(range(1, 13))
    assert all(r["flow"][-1]["loops"] == [] for r in plan_of(rep).values())


def test_a_loop_inside_yield_from_is_counted_in_its_own_frame(tmp_path):
    def inner(u):
        for i in range(3):
            yield step(u, n=i)

    def flow():
        for u in ("a", "b"):
            yield from inner(u)

    rep = pipeline(tmp_path).run(flow)
    plan = plan_of(rep)
    assert [(passes(plan["python:step-b~3"], 0), passes(plan["python:step-b~3"], 1))] == [([2], [3])]
    assert passes(plan["python:step-a"], 0) == [1] and passes(plan["python:step-a"], 1) == [1]


def test_sibling_flow_calls_of_the_same_code_count_on_their_own(tmp_path):
    def per_unit(u, until):
        n = 0
        while True:
            n = yield step(u, n=n)
            if n >= until:
                return n

    def flow():
        return (yield [per_unit("a", 4), per_unit("b", 2), per_unit("c", 3)])

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
    def child(u):
        return (yield step(u))

    def flow():
        for r in range(2):
            yield [child(f"u{r}{i}") for i in range(2)]

    rep = pipeline(tmp_path).run(flow)
    starts = {r["id"]: r for r in rows(rep, "flow_calls.jsonl") if r["event"] == "start"}
    assert starts["0"]["flow"] == []
    assert [passes(starts[c]) for c in ("0.1", "0.2", "0.3", "0.4")] == [[1], [1], [2], [2]]
    assert starts["0.3"]["flow"][0]["loops"][0]["line"] == line_of(flow, "for r in range(2)")
    assert plan_of(rep)["python:step-u10"]["flow"][0] == starts["0.3"]["flow"][0]  # the child's tasks start with it


def test_max_passes_bounds_each_while_loop_and_names_it(tmp_path):
    def flow():
        for c in range(5):
            r = 0
            while r < 5:
                yield step(f"u{c}", key=f"cell-{c}-{r}")
                r += 1

    rep = pipeline(tmp_path, max_passes=4).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, TooManyPasses)
    assert f"cell-0-4: pass 5 of the loop at {__file__}:{line_of(flow, 'while r < 5')}" in str(call.error)
    assert "max_passes=4" in str(call.error)


def test_a_for_loop_has_no_limit(tmp_path):
    def flow():
        for u in range(25):
            yield step(f"u{u}")

    rep = pipeline(tmp_path, max_passes=2).run(flow)
    assert rep.ok and not rep.flow_errors and len(rep.results) == 25
    assert passes(plan_of(rep)["python:step-u24"]) == [25]


def test_max_passes_bounds_a_while_loop_that_yields_child_flow_calls(tmp_path):
    def child(u):
        return (yield step(u))

    def flow():
        r = 0
        while r < 4:
            yield [child(f"u{r}")]
            r += 1

    rep = pipeline(tmp_path, max_passes=2).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, TooManyPasses) and "flow call 0.3" in str(call.error) and "pass 3 of the loop" in str(call.error)
    ends = {r["id"]: r for r in rows(rep, "flow_calls.jsonl") if r["event"] == "end"}
    assert ends["0.3"]["state"] == "raised" and "TooManyPasses" in ends["0.3"]["error"]
    assert sorted(rep.results) == ["python:step-u0", "python:step-u1"]


def test_resume_of_nested_loops_skips_finished_tasks_with_the_same_keys_and_passes(tmp_path):
    def flow():
        c = 0
        while c < 3:
            n = 0
            while n < 2:
                n = yield step(f"u{c}", n=n)
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

        def flow():
            doc = yield write("u")
            return (yield check("u", doc=doc))

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
        "def flow():\n    return (yield add(n=1))\n"
    )
    rep = pipeline(tmp_path).run(load(first), run_id="r")
    assert rep.value == 2
    rep = pipeline(tmp_path).run(load(first), run_id="r", resume=True)
    assert rep.results["python:add"].stop == "skipped"
    rep = pipeline(tmp_path).run(load(first.replace("n + 1", "n + 10")), run_id="r", resume=True)
    assert rep.results["python:add"].stop == "completed" and rep.value == 11


def test_renaming_a_wrapper_function_does_not_rerun(tmp_path):
    def body():
        n = yield step("u")
        return (yield step("v", n=n))

    def wrapper():
        return (yield from body())

    def renamed():
        return (yield from body())

    assert pipeline(tmp_path).run(wrapper, run_id="r").value == 2
    rep = pipeline(tmp_path).run(renamed, run_id="r", resume=True)
    assert {r.stop for r in rep.results.values()} == {"skipped"}
