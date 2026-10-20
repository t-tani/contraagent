"""Async flows in `Pipeline`: what an `await` receives, the recorded origin of each task,
key and file numbering, failures at the `await`, late kinds, resume, a generator flow
refused, a coroutine never awaited, and one run per event loop. Passes and fingerprints:
`test_passes.py`."""

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import (
    Pipeline,
    PipelineConfig,
    RoutingError,
    TaskDeferred,
    TaskFailed,
    TextOutput,
    TooManyPasses,
    agent_task,
    python_task,
)
from contraagent._internal.cli import main
from contraagent.docs.examples.review import flow as example
from contraagent.testing import StubAgent, fails, writes_nothing


class Summary(BaseModel):
    unit: str
    points: list[str]


class Verdict(BaseModel):
    approved: bool
    note: str = ""


def budget(**kw):
    return {"max_turns": 5, "timeout_s": 60, **kw}


summarize = agent_task("summarize", instructions="s", output=Summary, **budget())
review = agent_task("review", instructions="r", output=Verdict, **budget())
revise = agent_task("revise", instructions="v", output=Summary, **budget())
write_doc = agent_task("write_doc", instructions="w", output=str, **budget())
nothing = agent_task("nothing", instructions="n", **budget())


@python_task
def count(summary: Summary) -> int:
    return len(summary.points)


@python_task
def sections(unit: str) -> list[str]:
    return [f"{unit}-{i}" for i in range(3 if unit == "big" else 1)]


def summary_of(launch):
    """A summary of one point; a revision adds one to the summary it was given."""
    points = launch.params["summary"]["points"] + ["more"] if launch.kind == "revise" else ["a"]
    return {"unit": launch.unit, "points": points}


def approves_at(passes: dict[str, int]):
    """A review that approves unit u at pass passes[u] (1 when not named)."""

    def reply(launch):
        n = int(launch.key.rpartition("~")[2]) if "~" in launch.key else 1
        return {"approved": n >= passes.get(launch.unit, 1), "note": "more"}

    return reply


def stub(passes: dict[str, int] | None = None, **script) -> StubAgent:
    return StubAgent({"summarize": summary_of, "revise": summary_of, "review": approves_at(passes or {}), **script})


def pipeline(tmp_path, agent, **kw):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def plan_rows(report):
    return [json.loads(line) for line in (report.run_dir / "plan.jsonl").read_text().splitlines()]


def journal_rows(report):
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def flow_call_rows(report):
    return [json.loads(line) for line in (report.run_dir / "flow_calls.jsonl").read_text().splitlines()]


def passes(row, depth=-1):
    """The passes of the loops around a plan row's call site at `depth` of its flow path."""
    return [loop["pass"] for loop in row["flow"][depth]["loops"]]


def structure(report):
    """Per key: what must be the same in every run of the same flow."""
    return {
        r["key"]: ([(f["function"], f["line"], f["loops"]) for f in r["flow"]], r["created_from"], r["flow_call"])
        for r in plan_rows(report)
    }


# --- the documented example --------------------------------------------------


def test_the_review_loop_converges_at_pass_2_and_the_report_joins_every_unit(tmp_path):
    agent = stub({"b": 2})
    rep = pipeline(tmp_path, agent).run(example.docs, units=["a", "b"])
    assert rep.ok and not rep.flow_errors, rep.failed
    assert sorted(rep.results) == ["python:report", "review-a", "review-b", "review-b~2", "revise-b", "summarize-a", "summarize-b"]
    assert rep.value.splitlines() == ["a: 1 points", "b: 2 points"]  # the top flow call's return value
    plan = {r["key"]: r for r in plan_rows(rep)}
    # a received output passed on is the dependency, as a Pending is
    assert plan["review-b~2"]["after"] == ["revise-b"]
    assert plan["revise-b"]["after"] == ["summarize-b", "review-b"]
    assert plan["python:report"]["after"] == ["summarize-a", "revise-b"]  # through each child's return value
    # the loop's review is in its pass 1, then 2; revise in pass 1
    assert (passes(plan["review-b"]), passes(plan["review-b~2"]), passes(plan["revise-b"])) == ([1], [2], [1])
    # created from: the keys the flow call had received
    assert plan["review-b~2"]["created_from"] == ["revise-b"]
    assert plan["python:report"]["created_from"] == ["review-a", "review-b~2"]
    # each unit's loop is its own flow call; the report is the top's
    assert {plan[k]["flow_call"] for k in ("summarize-a", "review-a")} == {"0.1"}
    assert plan["python:report"]["flow_call"] == "0"
    # the flow path, outermost first, with the loop around the review's call site
    flow = plan["review-b~2"]["flow"]
    assert [f["function"] for f in flow] == [f"{example.__name__}.docs", f"{example.__name__}.review_loop"]
    [loop] = flow[1]["loops"]
    assert loop["line"] < flow[1]["line"] and flow[0]["loops"] == []
    assert plan["summarize-b"]["flow"][1]["loops"] == []  # before the loop
    # output files are numbered like the keys
    assert (rep.run_dir / "out/review/b~2.json").is_file() and (rep.run_dir / "out/review/b.json").is_file()


def test_a_task_with_no_plugin_may_write_its_output_in_claude_code(tmp_path):
    """Headless Claude Code denies a `Write` its settings do not allow: a task with no plugin
    runs with the template's permissions (found against the real CLI: every such task ended
    `invalid_output`, its file never written)."""
    agent = stub()
    rep = pipeline(tmp_path, agent).run(example.docs, units=["a"])
    assert rep.ok
    for launch in agent.launches:
        settings = json.loads(launch.launch.settings or "{}")
        assert {"Read", "Write", "Edit"} <= set(settings["permissions"]["allow"]), launch.key


def test_two_runs_of_the_same_flow_record_the_same_structure_and_fingerprints(tmp_path):
    runs = [pipeline(tmp_path, stub({"b": 3})).run(example.docs, units=["a", "b"], run_id=f"r{i}") for i in (1, 2)]
    assert structure(runs[0]) == structure(runs[1])
    fingerprints = [{r["key"]: r["fingerprint"] for r in journal_rows(rep)} for rep in runs]
    assert fingerprints[0] == fingerprints[1] and len(set(fingerprints[0].values())) == len(fingerprints[0])
    calls = [{(r["id"], r.get("parent"), r.get("function"), r.get("state")) for r in flow_call_rows(rep)} for rep in runs]
    assert calls[0] == calls[1]  # the same flow calls (they end in the order their tasks finish)


# --- what is recorded ---------------------------------------------------------------


def test_a_static_flow_keeps_its_keys_and_files_and_is_flow_call_0(tmp_path):
    def flow(units):
        for u in units:
            review(u, summary=summarize(u, path=u))

    rep = pipeline(tmp_path, stub()).run(flow, units=["a", "b"])
    assert rep.ok and sorted(rep.results) == ["review-a", "review-b", "summarize-a", "summarize-b"]
    assert (rep.run_dir / "out/summarize/a.json").is_file()
    row = next(r for r in plan_rows(rep) if r["key"] == "review-a")
    assert (row["created_from"], row["flow_call"]) == ([], "0")
    assert [(f["function"], f["loops"]) for f in row["flow"]] == [(f"{__name__}.{flow.__qualname__}", [])]
    assert row["flow"][0]["file"] == __file__
    calls = flow_call_rows(rep)
    assert [(c["id"], c["event"], c.get("state")) for c in calls] == [("0", "start", None), ("0", "end", "returned")]
    assert calls[0]["function"] == f"{__name__}.{flow.__qualname__}" and calls[0]["parent"] is None and calls[0]["flow"] == []
    rows = journal_rows(rep)
    assert {r["flow_call"] for r in rows} == {"0"} and all(len(r["fingerprint"]) == 64 for r in rows)


def test_the_same_task_twice_in_one_flow_call_is_numbered(tmp_path):
    def flow():
        first = summarize("u", path="x")
        return summarize("u", path="y"), first

    rep = pipeline(tmp_path, stub()).run(flow)
    second, first = rep.value
    assert (first.key, second.key) == ("summarize-u", "summarize-u~2")
    assert (first.path.name, second.path.name) == ("u.json", "u~2.json")


def test_flow_calls_record_parent_flow_path_and_end(tmp_path):
    rep = pipeline(tmp_path, stub({"b": 2})).run(example.docs, units=["a", "b"])
    starts = {c["id"]: c for c in flow_call_rows(rep) if c["event"] == "start"}
    ends = {c["id"]: c for c in flow_call_rows(rep) if c["event"] == "end"}
    assert sorted(starts) == ["0", "0.1", "0.2"] and set(ends) == set(starts)
    child = starts["0.2"]
    assert child["parent"] == "0" and child["function"] == f"{example.__name__}.review_loop"
    [frame] = child["flow"]  # where docs created it: outside any loop (a comprehension is none)
    assert (frame["function"], frame["file"], frame["loops"]) == (f"{example.__name__}.docs", example.__file__, [])
    assert {e["state"] for e in ends.values()} == {"returned"} and {e["error"] for e in ends.values()} == {None}


def test_nesting_at_any_depth_records_the_whole_flow_path(tmp_path):
    async def leaf(u):
        return await summarize(u, path=u)

    async def middle(u):
        first = await leaf(u)  # the same flow call
        return await asyncio.gather(leaf_review(u, first))

    async def leaf_review(u, s):
        return await review(u, summary=s)

    async def top():
        return await asyncio.gather(middle("a"))

    rep = pipeline(tmp_path, stub()).run(top)
    assert rep.ok, rep.failed
    plan = {r["key"]: r for r in plan_rows(rep)}
    assert plan["summarize-a"]["flow_call"] == "0.1" and plan["review-a"]["flow_call"] == "0.1.1"
    names = [f["function"].rpartition(".")[2] for f in plan["review-a"]["flow"]]
    assert names == ["top", "middle", "leaf_review"]
    assert [f["function"].rpartition(".")[2] for f in plan["summarize-a"]["flow"]] == ["top", "middle", "leaf"]
    assert plan["review-a"]["after"] == ["summarize-a"]


# --- shapes ---------------------------------------------------------------------


def test_a_branch_and_a_fan_out_sized_by_a_result(tmp_path):
    async def per_unit(u):
        parts = await sections(u)
        summaries = await asyncio.gather(*[summarize(u, key=f"summarize-{p}", path=p) for p in parts])
        if len(summaries) > 1:  # a branch on a result
            return await write_doc(u, summaries=summaries)
        return None

    async def flow(units):
        return await asyncio.gather(*[per_unit(u) for u in units])

    agent = stub(write_doc=lambda launch: f"# {len(launch.params['summaries'])}\n")
    rep = pipeline(tmp_path, agent).run(flow, units=["big", "small"])
    assert rep.ok, rep.failed
    keys = sorted(rep.results)
    assert keys == [
        "python:sections-big",
        "python:sections-small",
        "summarize-big-0",
        "summarize-big-1",
        "summarize-big-2",
        "summarize-small-0",
        "write_doc-big",
    ]
    doc, none = rep.value
    assert doc == "# 3\n" and isinstance(doc, TextOutput) and none is None
    plan = {r["key"]: r for r in plan_rows(rep)}
    assert all(plan[f"summarize-big-{i}"]["flow"][-1]["loops"] == [] for i in range(3))  # a fan-out, not a loop
    assert plan["write_doc-big"]["after"] == ["summarize-big-0", "summarize-big-1", "summarize-big-2"]
    assert plan["summarize-big-0"]["after"] == []  # a list of str a Python task returned: values, not files


def test_keyed_tasks_on_one_unit_each_keep_their_own_output(tmp_path):
    async def flow():
        return await asyncio.gather(*[summarize("u", key=f"part-{i}", path=f"p{i}") for i in range(3)])

    agent = stub(summarize=lambda launch: {"unit": launch.unit, "points": [launch.params["path"]]})
    rep = pipeline(tmp_path, agent).run(flow)
    assert rep.ok and [s.points for s in rep.value] == [["p0"], ["p1"], ["p2"]]
    out = rep.run_dir / "out" / "summarize"
    assert sorted(p.name for p in out.iterdir()) == ["part-0.json", "part-1.json", "part-2.json"]
    assert [json.loads((out / f"part-{i}.json").read_text())["points"] for i in range(3)] == [["p0"], ["p1"], ["p2"]]


def test_a_python_task_in_the_loop_and_text_outputs_passed_on(tmp_path):
    async def flow():
        summary = await summarize("u", path="x")
        while (await count("u", summary=summary)) < 3:
            summary = await revise("u", summary=summary)
        doc = await write_doc("u", summary=summary)
        built = "# built here\n"  # a str the flow built is a value
        await write_doc("v", doc=doc, title=built)

    agent = stub(write_doc=lambda launch: "# doc\n")
    rep = pipeline(tmp_path, agent).run(flow)
    assert rep.ok, rep.failed
    plan = {r["key"]: r for r in plan_rows(rep)}
    assert [passes(plan[k]) for k in ("python:count-u", "python:count-u~2", "python:count-u~3")] == [[1], [2], [3]]
    assert plan["python:count-u~3"]["after"] == ["revise-u~2"]
    assert (rep.run_dir / "out/count/u~3.json").read_text() == "3"
    assert plan["write_doc-v"]["after"] == ["write_doc-u"]  # the text output, recognized
    [launch] = agent.launches_of("write_doc-v")
    assert launch.params == {"doc": "# doc\n", "title": "# built here\n"}


def test_a_task_with_no_output_answers_none(tmp_path):
    async def flow():
        return await nothing("u")

    rep = pipeline(tmp_path, StubAgent({"nothing": writes_nothing()})).run(flow)
    assert rep.ok and rep.value is None


# --- failures at the await -------------------------------------------------------


def test_failed_and_refused_tasks_raise_task_failed_at_the_await(tmp_path):
    seen = {}

    async def flow():
        try:
            await summarize("a", path="x")
        except TaskFailed as exc:
            seen["failed"] = (exc.stop, exc.key, exc.item.key)
        s = summarize("b", path="x")  # not awaited: review waits for it and is refused
        try:
            await review("b", summary=s)
        except TaskFailed as exc:
            seen["refused"] = (exc.stop, exc.key)
        return "went on"

    agent = stub(**{"summarize-a": fails(), "summarize-b": fails()})
    rep = pipeline(tmp_path, agent).run(flow)
    assert seen == {"failed": ("error", "summarize-a", "summarize-a"), "refused": ("invalid_input", "review-b")}
    assert rep.value == "went on" and not rep.flow_errors and not rep.ok  # failed tasks still fail the run


def test_a_deferred_task_raises_task_deferred_and_a_finishing_task_still_runs(tmp_path):
    async def flow():
        try:
            await summarize("u", path="x")
        except TaskDeferred as exc:
            return await write_doc("u", note=exc.stop)

    agent = stub(write_doc=lambda launch: f"# {launch.params['note']}\n")
    rep = pipeline(tmp_path, agent, deadline_s=1e-6, finishing_kinds=("write_doc",)).run(flow)
    assert rep.value == "# deferred\n"
    assert rep.results["summarize-u"].stop == "deferred" and rep.results["write_doc-u"].ok


def test_an_uncaught_exception_after_work_started_is_a_flow_error(tmp_path):
    async def flow():
        s = await summarize("u", path="x")
        raise RuntimeError(f"stop after {s.unit}")

    rep = pipeline(tmp_path, stub()).run(flow)
    assert not rep.ok and rep.results["summarize-u"].ok
    [call] = rep.flow_errors
    assert call.id == "0" and isinstance(call.error, RuntimeError)
    assert flow_call_rows(rep)[-1] == {**flow_call_rows(rep)[-1], "state": "raised", "error": "RuntimeError: stop after u"}


def test_a_flow_raising_before_its_first_task_raises(tmp_path):
    async def flow():
        raise ValueError("bad arguments")
        await summarize("u", path="x")

    with pytest.raises(ValueError, match="bad arguments"):
        pipeline(tmp_path, stub()).run(flow)


def test_too_many_passes_raises_at_the_call(tmp_path):
    rep = pipeline(tmp_path, stub({"u": 99}), max_passes=3).run(example.review_loop, "u")
    [call] = rep.flow_errors
    loop = 1 + next(i for i, line in enumerate(Path(example.__file__).read_text().splitlines()) if line.strip() == "while True:")
    assert isinstance(call.error, TooManyPasses) and f"review-u: pass 4 of the loop at {example.__file__}:{loop}" in str(call.error)
    assert sorted(k for k in rep.results if k.startswith("review")) == ["review-u", "review-u~2", "review-u~3"]


def test_max_passes_comes_from_the_config_defaults(tmp_path):
    agent = stub()
    config = PipelineConfig({"defaults": {"max_passes": 2}})
    assert Pipeline(config, backends=agent.backends()).max_passes == 2
    assert Pipeline(None, backends=agent.backends()).max_passes == 10
    with pytest.raises(ValueError, match="max_passes = 0 is not a positive integer"):
        PipelineConfig({"defaults": {"max_passes": 0}}).defaults()


def test_a_key_created_by_two_flow_calls_needs_key(tmp_path):
    async def part(u):
        await summarize(u, path=u)
        return await write_doc()  # no unit: the same key in both flow calls

    async def flow():
        return await asyncio.gather(part("a"), part("b"))

    rep = pipeline(tmp_path, stub(write_doc="# d\n")).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, ValueError) and "pass key=" in str(call.error) and "write_doc" in str(call.error)


def test_a_reachable_kind_is_routed_before_the_first_launch(tmp_path):
    late = agent_task("late", instructions="l", output=Summary)  # no budget, here or in the config

    async def flow():
        s = await summarize("u", path="x")
        return await late("u", summary=s)

    agent = stub()
    with pytest.raises(RoutingError, match="kind late has no budget"):
        pipeline(tmp_path, agent).run(flow)
    assert not agent.launches


def test_a_kind_declared_while_the_flow_runs_is_routed_when_created(tmp_path):
    async def flow():
        s = await summarize("u", path="x")
        late = agent_task("late", instructions="l", output=Summary)  # unreachable from the code: routed now
        return await late("u", summary=s)

    rep = pipeline(tmp_path, stub()).run(flow)
    [call] = rep.flow_errors
    assert "late" in str(call.error) and "budget" in str(call.error)
    assert f'{__file__}", line' in "".join(__import__("traceback").format_exception(call.error))  # the author's call line
    agent = stub(late=summary_of)
    config = PipelineConfig({"tasks": {"late": {"max_turns": 3, "timeout_s": 30, "model": "m-late"}}})
    rep = Pipeline(config, runs_dir=tmp_path / "runs2", backends=agent.backends(), cwd=tmp_path, log=lambda line: None).run(flow)
    assert rep.ok and agent.launches_of("late-u")[0].model == "m-late"


revise_v2 = agent_task("revise", instructions="v2", output=Summary, **budget(model="m-v2"))  # revise, declared otherwise


async def revise_loop(unit, revise=revise):  # the default: a declaration the caller may replace
    summary = await summarize(unit, path="x")
    while not (await review(unit, summary=summary)).approved:
        summary = await revise(unit, summary=summary)
    return summary


def test_a_default_argument_the_caller_replaces_is_a_candidate_not_a_conflict(tmp_path):
    async def flow():
        return await revise_loop("u", revise=revise_v2)

    agent = stub({"u": 2})
    rep = pipeline(tmp_path, agent).run(flow)
    assert rep.ok, rep.flow_errors
    # revise was routed as first reached (the default), and again as revise_v2 created it
    assert agent.launches_of("revise-u")[0].model == "m-v2"
    definition = json.loads((rep.run_dir / "definitions/revise.json").read_text())
    assert definition["files"][0]["text"] == "v2"


def test_two_different_declarations_of_one_kind_both_created_raise_at_the_second(tmp_path):
    again = agent_task("revise", instructions="v", output=Summary, **budget())  # declared the same way: one kind

    async def flow():
        s = await summarize("u", path="x")
        s = await asyncio.gather(revise("u", summary=s), again("w", summary=s))
        return await revise_v2("z", summary=s[0])

    rep = pipeline(tmp_path, stub()).run(flow)
    [call] = rep.flow_errors
    assert isinstance(call.error, ValueError)
    assert str(call.error) == (
        "kind 'revise' is declared by two agent_task calls with different instructions, config: "
        "one kind is one definition and one [tasks.revise] table; give one of them another kind"
    )
    assert f'{__file__}", line' in "".join(__import__("traceback").format_exception(call.error))  # the author's call line
    assert sorted(rep.results) == ["revise-u", "revise-w", "summarize-u"]


def test_a_slow_step_is_logged(tmp_path, caplog):
    async def flow():
        await summarize("u", path="x")
        time.sleep(1.1)

    with caplog.at_level("WARNING", logger="contraagent"):
        pipeline(tmp_path, stub()).run(flow)
    assert "heavy work belongs in a Python task" in caplog.text


def test_contraagent_run_exits_1_on_a_flow_error(tmp_path, capsys, monkeypatch):
    (tmp_path / "steps.py").write_text(
        "from contraagent import python_task\n"
        "@python_task\ndef double(n: int) -> int:\n    return 2 * n\n"
        "async def flow(n):\n    m = await double(n=n)\n    raise ValueError(f'got {m}')\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    try:
        assert main(["run", "steps.py:flow", "--kwargs", '{"n": 2}']) == 1
    finally:
        sys.modules.pop("steps", None)
    out = capsys.readouterr().out
    assert "1/1 tasks done" in out and "flow call 0 (steps.flow) at steps.py:7: ValueError: got 4" in out


# --- resume -----------------------------------------------------------------------


def test_resume_after_pass_1_launches_only_pass_2_onward_and_a_changed_param_reruns(tmp_path):
    agent = stub({"u": 2})
    first = pipeline(tmp_path, agent, max_passes=1).run(example.review_loop, "u", run_id="r")
    assert isinstance(first.flow_errors[0].error, TooManyPasses)  # stopped where pass 2 began
    assert sorted(first.results) == ["review-u", "revise-u", "summarize-u"]

    agent.launches.clear()
    again = pipeline(tmp_path, agent).run(example.review_loop, "u", run_id="r", resume=True)
    assert again.ok and again.value.unit == "u"
    assert [launch.key for launch in agent.launches] == ["review-u~2"]  # pass 2 only
    assert {k: r.stop for k, r in again.results.items() if r.stop == "skipped"} == {
        "summarize-u": "skipped",
        "review-u": "skipped",
        "revise-u": "skipped",
    }

    agent.launches.clear()

    summarize_, review_, revise_ = example.summarize, example.review, example.revise

    async def changed(unit):  # the same tasks, another path param for summarize
        summary = await summarize_(unit, path=f"elsewhere/{unit}.md")
        while True:
            verdict = await review_(unit, summary=summary)
            if verdict.approved:
                return summary
            summary = await revise_(unit, summary=summary, verdict=verdict)

    pipeline(tmp_path, agent).run(changed, "u", run_id="r", resume=True)
    # summarize's params changed: it runs again, and writes the same output, so what received it does not
    assert [launch.key for launch in agent.launches] == ["summarize-u"]


def test_resume_reads_numbered_outputs_and_an_off_contract_one_fails_at_the_await(tmp_path):
    rep = pipeline(tmp_path, stub({"u": 2})).run(example.review_loop, "u", run_id="r")
    assert rep.ok
    (rep.run_dir / "out/revise/u.json").write_text("{}")
    agent = stub({"u": 2})
    again = pipeline(tmp_path, agent).run(example.review_loop, "u", run_id="r", resume=True)
    [call] = again.flow_errors
    assert isinstance(call.error, TaskFailed) and call.error.stop == "invalid_output" and call.error.key == "revise-u"
    assert agent.launches == []


def test_a_resumed_chain_of_skipped_tasks_uses_no_recursion(tmp_path):
    @python_task
    def step(i: int) -> int:
        return i + 1

    async def chain(n):
        i = 0
        for k in range(n):
            i = await step(key=f"step-{k}", i=i)
        return i

    agent = stub()
    assert pipeline(tmp_path, agent).run(chain, 400, run_id="c").value == 400
    rep = pipeline(tmp_path, agent).run(chain, 400, run_id="c", resume=True)
    assert rep.value == 400 and {r.stop for r in rep.results.values()} == {"skipped"}


_running: list[int] = [0, 0]  # now, most at once
_running_changed = threading.Condition()


@python_task(claims=["heavy"])
def heavy(unit: str, meet: int = 1) -> int:
    """Waits until `meet` of its kind ran at once (10 s at most)."""
    with _running_changed:
        _running[0] += 1
        _running[1] = max(_running[1], _running[0])
        _running_changed.notify_all()
        _running_changed.wait_for(lambda: _running[1] >= meet, timeout=10)
    time.sleep(0.05)
    with _running_changed:
        _running[0] -= 1
    return 1


def test_a_claiming_kind_runs_within_its_claim_capacity(tmp_path):
    async def flow(meet):
        return await asyncio.gather(*[heavy(u, meet=meet) for u in "abcd"])

    _running[:] = [0, 0]
    rep = pipeline(tmp_path, StubAgent()).run(flow, 1)
    assert rep.ok and rep.value == [1, 1, 1, 1]
    assert _running[1] == 1  # four ready at once, one at a time
    _running[:] = [0, 0]
    assert pipeline(tmp_path, StubAgent(), claim_capacity={"heavy": 4}).run(flow, 2, run_id="free").ok
    assert _running[1] > 1  # a capacity of 4: they overlap


# --- what an async flow is ----------------------------------------------------------


def test_awaits_deliver_typed_answers_and_gather_keeps_their_order(tmp_path):
    async def flow():
        summary = await summarize("u", path="x")
        n, doc = await asyncio.gather(count("u", summary=summary), write_doc("u", summary=summary))
        return summary, n, doc

    rep = pipeline(tmp_path, stub(write_doc="# d\n")).run(flow)
    summary, n, doc = rep.value
    assert isinstance(summary, Summary) and summary.points == ["a"]
    assert n == 1 and doc == "# d\n" and isinstance(doc, TextOutput)


def test_the_frontier_is_the_union_a_gather_received_whatever_order_its_tasks_end_in(tmp_path):
    async def flow():
        await asyncio.gather(summarize("a", path="a"), summarize("b", path="b"), summarize("c", path="c"))
        review("u")  # created from all three
        await summarize("d", path="d")
        review("v")  # created from the last await only

    for order in ("abc", "cba"):
        ended = {u: threading.Event() for u in "abc"}

        def in_order(launch, order=order, ended=ended):
            """Ends the summaries of a, b and c in `order`."""
            if launch.unit in order:
                for u in order[: order.index(launch.unit)]:
                    ended[u].wait(timeout=10)
            reply = summary_of(launch)
            if launch.unit in ended:
                ended[launch.unit].set()
            return reply

        agent = stub(summarize=in_order, review={"approved": True})
        rep = pipeline(tmp_path, agent, max_concurrent=4).run(flow, run_id=f"r-{order}")
        plan = {r["key"]: r for r in plan_rows(rep)}
        assert plan["review-u"]["created_from"] == ["summarize-a", "summarize-b", "summarize-c"]
        assert plan["review-v"]["created_from"] == ["summarize-d"]


def test_a_generator_flow_is_refused_with_its_rewrite(tmp_path):
    def flow():
        yield summarize("u", path="x")

    for given in (flow, lambda: flow()):
        with pytest.raises(TypeError) as caught:
            pipeline(tmp_path, stub()).run(given)
        message = str(caught.value)
        assert "generator flow" in message and "`def` -> `async def`" in message
        for rewrite in (
            "`yield x` -> `await x`",
            "`yield [a, b]` -> `await asyncio.gather(a, b)`",
            "`yield from sub()` -> `await sub()`",
            "`yield time_box(g, ...)` -> `await time_box(c, ...)`",
        ):
            assert rewrite in message


def test_a_coroutine_never_awaited_is_a_warning_line(tmp_path):
    async def sub(u):
        return await summarize(u, path=u)

    async def flow():
        sub("a")  # pyright: ignore[reportUnusedCoroutine]  # the await forgotten: it never runs
        return await summarize("b", path="b")

    lines: list[str] = []
    agent = stub()
    rep = Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lines.append).run(flow)
    assert rep.ok and sorted(rep.results) == ["summarize-b"]
    [line] = [line for line in lines if "never awaited" in line]
    assert "sub" in line and "await sub(...)" in line and __file__ in line


def test_one_run_per_event_loop_at_a_time(tmp_path):
    release = threading.Event()

    @python_task
    def hold(unit: str) -> int:
        release.wait(timeout=10)
        return 1

    async def flow():
        return await hold("u")

    async def main():
        first = asyncio.ensure_future(pipeline(tmp_path, StubAgent()).run_async(flow, run_id="first"))
        while not (tmp_path / "runs" / "first").exists():
            await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="one event loop runs one run at a time"):
            await pipeline(tmp_path, StubAgent()).run_async(flow, run_id="second")
        release.set()
        return await first

    assert asyncio.run(main()).value == 1
    assert not (tmp_path / "runs" / "second").exists()


def test_a_flow_that_awaits_a_clock_or_a_thread_fails_at_that_await(tmp_path):
    async def flow():
        first = await summarize("a", path="a")
        try:
            await asyncio.to_thread(len, "x")
        except TypeError as exc:
            thread = str(exc)
        await asyncio.sleep(1)  # not caught: it ends the flow
        return first, thread

    rep = pipeline(tmp_path, stub()).run(flow)
    assert not rep.ok and sorted(rep.results) == ["summarize-a"]
    [top] = rep.flow_errors
    assert isinstance(top.error, TypeError) and "needs a clock" in str(top.error) and "time_box()" in str(top.error)
    [row] = [r for r in flow_call_rows(rep) if r["event"] == "end"]
    assert row["state"] == "raised" and "needs a clock" in row["error"]


def test_a_flow_that_waits_for_what_nothing_answers_ends_the_run_with_the_place(tmp_path):
    never = asyncio.Event()

    async def flow():
        await summarize("a", path="a")
        await never.wait()

    started = time.monotonic()
    rep = pipeline(tmp_path, stub()).run(flow)  # no deadline: it would have waited forever
    assert time.monotonic() - started < 60
    assert not rep.ok and rep.value is None
    [top] = rep.flow_errors
    assert top.state == "closed" and isinstance(top.error, RuntimeError)
    assert f"waits at {__file__}:{flow.__code__.co_firstlineno + 2}" in str(top.error)
    [row] = [r for r in flow_call_rows(rep) if r["event"] == "end"]
    assert row["state"] == "closed" and "for what nothing will answer" in row["error"]


def test_run_async_drives_the_flows_from_a_loop_of_the_callers_own(tmp_path):
    async def flow():
        a, b = await asyncio.gather(summarize("a", path="a"), summarize("b", path="b"))
        return a.unit + b.unit

    async def main():
        loop = asyncio.get_running_loop()
        report = await pipeline(tmp_path, stub()).run_async(flow)
        assert asyncio.get_running_loop() is loop
        return report

    rep = asyncio.run(main())
    assert rep.ok and rep.value == "ab"


def test_a_flow_call_is_on_record_once_it_creates_something(tmp_path):
    async def helper(pending):
        return await pending  # waits for its parent's task call: no record

    async def sub(u):
        return await summarize(u, path=u)  # creates a task: on record

    async def flow():
        first = summarize("a", path="a")
        await asyncio.gather(first, summarize("b", path="b"))  # 0.1 and 0.2 wait only
        await asyncio.create_task(helper(first))  # 0.3
        done = await asyncio.gather(sub("c"))  # 0.4
        follow = await write_doc("d", path="d")
        return done, follow

    rep = pipeline(tmp_path, stub(write_doc=lambda launch: "text")).run(flow)
    assert rep.ok
    rows = flow_call_rows(rep)
    assert [r["id"] for r in rows if r["event"] == "start"] == ["0", "0.4"]
    assert [r["id"] for r in rows if r["event"] == "end"] == ["0.4", "0"]
    plan = {r["key"]: r for r in plan_rows(rep)}
    assert {key: r["flow_call"] for key, r in plan.items()} == {
        "summarize-a": "0",
        "summarize-b": "0",
        "summarize-c": "0.4",
        "write_doc-d": "0",
    }
    # What the Tasks that left no record received reached the flow all the same.
    assert plan["write_doc-d"]["created_from"] == ["summarize-c"]


def test_a_task_failure_passing_through_a_flow_call_puts_it_on_no_record(tmp_path):
    async def passes(pending):
        return await pending  # the task's TaskFailed passes through unchanged

    async def own(pending):
        try:
            await pending
        except TaskFailed as exc:
            raise ValueError(f"no summary: {exc.key}") from exc

    async def flow():
        bad = summarize("a", path="a")
        caught = []
        for awaited in (asyncio.gather(bad), asyncio.create_task(passes(bad)), asyncio.create_task(own(bad))):
            try:
                await awaited  # 0.1 (asyncio's Task around the task call), 0.2, 0.3
            except (TaskFailed, ValueError) as exc:
                caught.append(type(exc).__name__)
        return caught

    rep = pipeline(tmp_path, stub(**{"summarize-a": fails()})).run(flow)
    assert rep.value == ["TaskFailed", "TaskFailed", "ValueError"]
    rows = flow_call_rows(rep)
    assert [r["id"] for r in rows if r["event"] == "start"] == ["0", "0.3"]
    [end] = [r for r in rows if r["event"] == "end" and r["id"] == "0.3"]
    assert end["state"] == "raised" and end["error"] == "ValueError: no summary: summarize-a"
