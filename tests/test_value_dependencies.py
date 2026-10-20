"""A task is given values. A task call copies its params as JSON at the call; a `Pending`
among them, at any depth, and a value that is not JSON raise `TypeError` there. A received
output is a value like any other: a copy of it or a field of it is the same value. Where a
task's params came from (`given_from`) is recorded beside its fingerprint and never changes
what a resume skips; a task nothing used is recorded as unawaited."""

import asyncio
import copy
import json
from typing import Any

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, Rows, agent_task, python_task
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


class Holder(BaseModel):
    """A params model with a field of any type: a type checker lets a `Pending` in."""

    doc: Any
    depth: int = 1


class Given(BaseModel):
    """The params of `check` given a document: a field of any type, so a type checker lets
    a `Pending` or a value that is not JSON in."""

    doc: Any


class Loose(BaseModel):
    """The params of `check` for a flow that gives it a document, documents or a text."""

    doc: Any = None
    docs: Any = None
    text: Any = None


write = agent_task("write", instructions="Write.", output=Doc, max_turns=3, timeout_s=30)
check = agent_task("check", instructions="Check.", output=Doc, max_turns=3, timeout_s=30)
check_doc = agent_task("check", instructions="Check.", params=Given, output=Doc, max_turns=3, timeout_s=30)
check_any = agent_task("check", instructions="Check.", params=Loose, output=Doc, max_turns=3, timeout_s=30)
hold = agent_task("hold", instructions="Hold.", params=Holder, output=Doc, max_turns=3, timeout_s=30)


@python_task
def count(doc: Doc, scale: int = 1) -> int:
    return len(doc.text) * scale


class Agent(StubAgent):
    """A stub whose `write` writes `text`, which a test changes between runs."""

    def __init__(self) -> None:
        self.text = "first"
        reply = {"unit": "u", "text": "checked"}
        super().__init__(
            {
                "write": lambda launch: {"unit": launch.unit, "text": self.text},
                "check": lambda launch: reply,
                "hold": lambda launch: reply,
                "collect": lambda launch: [{"unit": "u", "text": "a"}, {"unit": "u", "text": "b"}],
            }
        )


def pipeline(tmp_path, agent) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)


def plan(rep) -> dict[str, dict[str, Any]]:
    return {r["key"]: r for r in map(json.loads, (rep.run_dir / "plan.jsonl").read_text().splitlines())}


def flow_call_ends(rep) -> dict[str, dict[str, Any]]:
    rows = map(json.loads, (rep.run_dir / "flow_calls.jsonl").read_text().splitlines())
    return {r["id"]: r for r in rows if r["event"] == "end"}


# --- a Pending is never a param ---------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "where"),
    [
        (lambda p: Loose(doc=p), "doc is the Pending of write-u"),
        (lambda p: Loose(docs=[1, p]), "docs[1] is the Pending of write-u"),
        (lambda p: Loose(docs={"first": p}), "docs['first'] is the Pending of write-u"),
        (lambda p: Loose(docs={"first": (p,)}), "docs['first'][0] is the Pending of write-u"),
    ],
)
def test_a_pending_among_the_params_raises_at_the_call_and_says_how_to_write_it(tmp_path, given, where):
    def flow():
        check_any("u", given(write("u")))

    with pytest.raises(TypeError) as raised:
        pipeline(tmp_path, Agent()).run(flow)
    message = str(raised.value)
    assert message.startswith(f"check(): {where}, the future output of a task call")
    assert "await the task call and pass its output" in message and ".options(after=[...])" in message


def test_a_pending_inside_a_model_raises_at_the_call(tmp_path):
    async def flow():
        hold("u", Holder(doc=Holder(doc=write("u"))))  # the field takes any value

    rep = pipeline(tmp_path, Agent()).run(flow)
    [error] = rep.flow_errors
    assert isinstance(error.error, TypeError) and "doc.doc is the Pending of write-u" in str(error.error)
    assert "hold-u" not in rep.results


def test_a_python_task_refuses_a_pending_too(tmp_path):
    with pytest.raises(TypeError, match=r"count\(\): doc is the Pending of write-u"):
        pipeline(tmp_path, Agent()).run(lambda: count(doc=write("u")))


def test_a_pending_is_given_in_after_for_an_order_with_no_output(tmp_path):
    def flow():
        check.options(after=[write("u")])("u")

    agent = Agent()
    rep = pipeline(tmp_path, agent).run(flow)
    assert rep.ok and [launch.key for launch in agent.launches] == ["write-u", "check-u"]
    assert plan(rep)["check-u"]["after"] == ["write-u"] and plan(rep)["check-u"]["given_from"] == []


# --- params are JSON, copied at the call ---------------------------------------------------


class Opaque:
    pass


@pytest.mark.parametrize(
    ("value", "says"),
    [
        (Opaque(), "params hold a value that is not JSON or not of its field's type: .*Opaque"),
        (float("nan"), "params hold a value that is not JSON"),
    ],
)
def test_a_param_that_is_not_json_raises_at_the_call(tmp_path, value, says):
    with pytest.raises(TypeError, match=says):
        pipeline(tmp_path, Agent()).run(lambda: check_doc("u", Given(doc=value)))


def test_a_python_tasks_default_that_is_not_json_raises_at_the_call(tmp_path):
    @python_task
    def opaque(unit: str, thing: Any = Opaque()) -> None:
        pass

    with pytest.raises(TypeError, match=r"opaque\(\): the default of thing is a Opaque, which is not JSON"):
        pipeline(tmp_path, Agent()).run(lambda: opaque("u"))


def test_the_call_file_holds_the_value_the_flow_passed_at_the_call(tmp_path):
    async def flow():
        doc = await write("u")
        out = tmp_path / "runs" / "flow" / "out" / "write" / "u.json"
        out.write_text(json.dumps({"unit": "u", "text": "changed on disk"}))  # after the flow received it
        given = Given(doc=doc.model_dump())
        call = check_doc("u", given)
        given.doc["text"] = "changed by the flow"  # after the call
        await call

    agent = Agent()
    assert pipeline(tmp_path, agent).run(flow).ok
    [launch] = agent.launches_of("check-u")
    assert launch.params == {"doc": {"unit": "u", "text": "first"}}


def test_a_default_given_and_a_default_left_out_have_one_fingerprint(tmp_path):
    def flow():
        count.options(key="left-out")(doc={"unit": "u", "text": "t"})
        count.options(key="given")(doc={"unit": "u", "text": "t"}, scale=1)
        hold.options(key="model-left-out")("u", Holder(doc="d"))
        hold.options(key="model-given")("u", Holder(doc="d", depth=1))

    rep = pipeline(tmp_path, Agent()).run(flow)
    tasks = {k: r.task for k, r in rep.results.items()}
    assert tasks["left-out"].fingerprint_parts["params"] == tasks["given"].fingerprint_parts["params"]
    assert tasks["model-left-out"].fingerprint_parts["params"] == tasks["model-given"].fingerprint_parts["params"]


# --- a received output is a value ------------------------------------------------------------


def test_a_copy_of_an_output_is_the_same_value_and_given_from_it(tmp_path):
    async def flow():
        doc = await write("u")
        check_any.options(key="whole")("u", Loose(doc=doc))
        check_any.options(key="copy")("u", Loose(doc=copy.deepcopy(doc)))
        check_any.options(key="dumped")("u", Loose(doc=doc.model_dump()))
        check_any.options(key="typed")("u", Loose(doc=Doc(unit="u", text="first")))
        check_any.options(key="field")("u", Loose(text=doc.text))
        check_any.options(key="literal")("u", Loose(text="first"))
        check_any.options(key="built")("u", Loose(text=doc.text.upper()))

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    params = {k: r.task.fingerprint_parts["params"] for k, r in rep.results.items()}
    assert params["whole"] == params["copy"] == params["dumped"] == params["typed"]
    assert params["field"] == params["literal"] != params["built"]
    given = {k: r["given_from"] for k, r in plan(rep).items()}
    assert given["whole"] == given["copy"] == given["dumped"] == given["typed"] == ["write-u"]
    assert given["field"] == given["literal"] == given["built"] == []  # a field of an output is no output
    assert given["write-u"] == []
    assert plan(rep)["field"]["created_from"] == ["write-u"]  # what it came after, all the same


def test_a_whole_row_of_a_rows_output_records_the_edge(tmp_path):
    collect = agent_task("collect", instructions="Collect.", output=Rows[Doc], max_turns=3, timeout_s=30)

    async def flow():
        rows = await collect("u")
        for i, row in enumerate(rows):
            check_any.options(key=f"row-{i}")("u", Loose(doc=row))
        check_any.options(key="all")("u", Loose(docs=list(rows)))
        check_any.options(key="text")("u", Loose(text=rows[0].text))

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok, rep.failed
    given = {k: r["given_from"] for k, r in plan(rep).items()}
    assert given["row-0"] == given["row-1"] == given["all"] == ["collect-u"]
    assert given["text"] == []


def test_given_from_never_changes_what_a_resume_skips(tmp_path):
    async def from_output():
        await check_any("u", Loose(text=(await write("u")).text))

    async def from_literal():
        await write("u")
        await check_any("u", Loose(text="first"))

    agent = Agent()
    assert pipeline(tmp_path, agent).run(from_output, run_id="r").ok
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(from_literal, run_id="r", resume=True)
    assert rep.ok and agent.launches == []  # the same params: skipped, wherever they came from


def test_an_upstream_task_that_runs_again_with_the_same_output_leaves_its_reader_skipped(tmp_path):
    def flow(instructions):
        writer = agent_task("write", instructions=instructions, output=Doc, max_turns=3, timeout_s=30)

        async def run():
            await check_doc("u", Given(doc=await writer("u")))

        return run

    agent = Agent()
    assert pipeline(tmp_path, agent).run(flow("Write."), run_id="r").ok
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(flow("Write more."), run_id="r", resume=True)
    assert [launch.key for launch in agent.launches] == ["write-u"] and rep.results["check-u"].stop == "skipped"


# --- unawaited tasks ---------------------------------------------------------------------------


def test_a_task_nothing_used_is_unawaited_and_runs_all_the_same(tmp_path):
    async def flow():
        write.options(key="forgotten")("u")  # never awaited
        ordered = write.options(key="ordered")("u")
        check.options(after=[ordered])("u")  # check itself is never awaited
        await write.options(key="awaited")("u")
        return write.options(key="returned")("u")

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok and rep.results["forgotten"].ok
    assert flow_call_ends(rep)["0"]["unawaited"] == ["forgotten", "check-u"]


def test_a_flow_call_that_outlives_its_parent_is_counted_before_the_parents_end_is_recorded(tmp_path):
    started = asyncio.Event()

    async def child(pending):
        started.set()
        await asyncio.sleep(0)
        await check_doc("u", Given(doc=await pending))  # after the parent returned

    async def flow():
        pending = write("u")
        asyncio.get_running_loop().create_task(child(pending))
        await started.wait()

    rep = pipeline(tmp_path, Agent()).run(flow)
    ends = flow_call_ends(rep)
    assert rep.ok and "unawaited" not in ends["0"]  # the child awaited it, and its own task
    rows = [json.loads(line) for line in (rep.run_dir / "flow_calls.jsonl").read_text().splitlines()]
    assert [(r["id"], r["event"]) for r in rows][-2:] == [("0.1", "end"), ("0", "end")]
    assert ends["0"]["ts"] <= ends["0.1"]["ts"]  # the time the top flow call ended itself


def test_a_flow_that_does_not_wait_lists_its_unawaited_tasks(tmp_path):
    def flow():
        first = write.options(key="first")("u")
        check.options(after=[first])("u")
        return write.options(key="returned")("u")

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert flow_call_ends(rep)["0"]["unawaited"] == ["check-u"]


# --- given from: the causal past of the creating flow call ----------------------------------


def test_equal_outputs_of_sibling_flow_calls_do_not_cross(tmp_path):
    async def unit(u):
        doc = await write.options(key=f"write-{u}")("same")  # each unit's output is equal
        await check_any.options(key=f"before-{u}")("same", Loose())
        await check_any.options(key=f"check-{u}")("same", Loose(doc=doc))

    async def flow():
        await asyncio.gather(unit("a"), unit("b"))

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    given = {k: r["given_from"] for k, r in plan(rep).items()}
    assert given["check-a"] == ["write-a"] and given["check-b"] == ["write-b"]


def test_a_value_passed_to_a_child_and_one_returned_by_a_child_count(tmp_path):
    async def child(u, doc):
        await check_any.options(key=f"check-{u}")("same", Loose(doc=doc))  # given as an argument
        return await write.options(key=f"again-{u}")("same")

    async def flow():
        docs = await asyncio.gather(*[write.options(key=f"write-{u}")("same") for u in ("a", "b")])
        returned = await asyncio.gather(*[child(u, d) for u, d in zip(("a", "b"), docs, strict=True)])
        await check_any.options(key="all")("same", Loose(docs=list(returned)))  # returned by the children

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    given = {k: r["given_from"] for k, r in plan(rep).items()}
    # Both writes reached the parent before it created the children, and their outputs are equal: both named.
    assert given["check-a"] == given["check-b"] == ["write-a", "write-b"]
    assert given["all"][:2] == ["write-a", "write-b"] and sorted(given["all"][2:]) == ["again-a", "again-b"]  # in creation order


@pytest.mark.parametrize("awaits", [False, True])
def test_a_childs_results_reach_its_parent_only_when_the_parent_awaits_it(tmp_path, awaits):
    async def child():
        return await write.options(key="write-child")("same")

    async def flow():
        started = asyncio.get_running_loop().create_task(child())
        if awaits:
            await started  # resumed by the child's end
        else:
            await check_any.options(after=["write-child"], key="later")("same", Loose())  # the child's result is given before
        await check_any.options(key="final")("same", Loose(doc={"unit": "same", "text": "first"}))  # equal to the child's output

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    assert plan(rep)["final"]["given_from"] == (["write-child"] if awaits else [])


async def _child():
    return await write.options(key="write-child")("same")


async def _child_ended():
    """A child flow call, started and left to end: a task ordered after its write is awaited."""
    started = asyncio.get_running_loop().create_task(_child())
    await check_any.options(after=["write-child"], key="later")("same", Loose())
    assert started.done()
    return started


@pytest.mark.parametrize("how", ["await", "gather", "taskgroup"])
def test_a_child_that_ended_before_it_is_awaited_reaches_its_parent(tmp_path, how):
    async def flow():
        if how == "taskgroup":
            async with asyncio.TaskGroup() as group:
                started = group.create_task(_child())
                await check_any.options(after=["write-child"], key="later")("same", Loose())
            doc = await started  # ended within the group
        else:
            started = await _child_ended()
            doc = await started if how == "await" else (await asyncio.gather(started))[0]
        await check_any.options(key="final")("same", Loose(doc=doc))

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    final = plan(rep)["final"]
    assert final["given_from"] == ["write-child"]
    assert "write-child" in final["created_from"]
    if how == "await":  # the await resumes the flow call at once, by the child's frontier
        assert final["created_from"] == ["write-child"]


def test_a_childs_end_seen_without_its_value_reaches_no_one(tmp_path):
    async def flow():
        started = await _child_ended()
        assert started.done() and started.exception() is None  # neither gives its value
        await check_any.options(key="final")("same", Loose(doc={"unit": "same", "text": "first"}))
        await started

    rep = pipeline(tmp_path, Agent()).run(flow)
    assert rep.ok
    final = plan(rep)["final"]
    assert final["given_from"] == [] and final["created_from"] == ["later"]
