"""`JournalEstimates`: a kind's median wall time, and the tail after a task, from recent runs and this one."""

import json
import os

from contraagent import Frame, Loop, Origin, Pipeline, Task
from contraagent._internal.execution.estimates import run_tails
from contraagent._internal.pipeline.graph import Graph
from contraagent.docs.examples.review import flow as example
from contraagent.engine import JournalEstimates
from contraagent.testing import StubAgent

DOCS = "flows.docs"
LOOP = "flows.review_loop"


def plan_row(key, kind, flow=(DOCS, LOOP), after=(), created_from=(), passes=(), flow_call="0"):
    """`passes`: the passes of the loops around the call site in the last frame."""
    frames = [{"function": f, "file": "flows.py", "line": 1, "loops": []} for f in flow]
    frames[-1]["loops"] = [{"line": 10 + i, "pass": p} for i, p in enumerate(passes)]
    return {
        "key": key,
        "kind": kind,
        "flow": frames,
        "after": list(after),
        "created_from": list(created_from),
        "flow_call": flow_call,
    }


def journal_row(key, kind, wall_s, stop="completed"):
    return {"key": key, "kind": kind, "wall_s": wall_s, "stop": stop, "ok": stop == "completed"}


def write_run(runs, run_id, plan, journal, calls=None, mtime=None):
    d = runs / run_id
    d.mkdir(parents=True)
    (d / "plan.jsonl").write_text("".join(json.dumps(r) + "\n" for r in plan))
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in journal))
    if calls is not None:
        (d / "flow_calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in calls))
    if mtime is not None:
        os.utime(d / "journal.jsonl", (mtime, mtime))


def review_run(review_s: float, revise_s: float):
    """summarize -> review -> revise -> review~2, then a report created from the last review."""
    plan = [
        plan_row("summarize-a", "summarize"),
        plan_row("review-a", "review", after=["summarize-a"], created_from=["summarize-a"], passes=[1]),
        plan_row("revise-a", "revise", after=["summarize-a", "review-a"], created_from=["review-a"], passes=[1]),
        plan_row("review-a~2", "review", after=["revise-a"], created_from=["revise-a"], passes=[2]),
        plan_row("python:report", "report", flow=(DOCS,), created_from=["review-a~2"]),
    ]
    journal = [
        journal_row("summarize-a", "summarize", 10),
        journal_row("review-a", "review", review_s),
        journal_row("revise-a", "revise", revise_s),
        journal_row("review-a~2", "review", review_s),
        journal_row("python:report", "report", 1),
    ]
    return plan, journal


def task(kind, flow=(DOCS, LOOP), passes=()):
    frames = [Frame(function=f, file="flows.py", line=1) for f in flow]
    frames[-1] = Frame(function=flow[-1], file="flows.py", line=1, loops=tuple(Loop(line=10 + i, pass_=p) for i, p in enumerate(passes)))
    return Task(kind, unit="z", origin=Origin(flow=tuple(frames)))


def test_a_tail_is_the_longest_chain_after_a_task_along_after_and_created_from():
    tails = dict(((k, round(t, 3)) for k, t in run_tails(*review_run(review_s=4, revise_s=6))))
    # after summarize: review 4 + revise 6 + review~2 4 + report 1
    assert tails[((DOCS, LOOP), "summarize", ())] == 15
    assert tails[((DOCS,), "report", ())] == 0
    # one sample per task, told apart by the loop's pass: review-a (6 + 4 + 1) and review-a~2 (1)
    assert tails[((DOCS, LOOP), "review", (1,))] == 11 and tails[((DOCS, LOOP), "review", (2,))] == 1


def test_the_estimate_is_the_median_over_runs_per_flow_path_and_kind(tmp_path):
    for i, (review_s, revise_s) in enumerate([(4, 6), (2, 2), (8, 30)]):
        write_run(tmp_path, f"r{i}", *review_run(review_s, revise_s))
    est = JournalEstimates(tmp_path)
    assert est.tail(task("summarize")) == 15  # 15, 7, 47
    assert est.tail(task("review", passes=[1])) == 11  # 11, 5, 39
    assert est.tail(task("review", passes=[2])) == 1
    assert est.tail(task("summarize", flow=("other.flow",))) is None  # another flow path: no history
    assert est.tail(task("report", flow=(DOCS,))) == 0
    assert est.estimate(task("review")) == 4  # the median wall time per kind is unchanged


def test_a_chain_cut_short_by_a_failure_or_a_deferral_is_not_sampled():
    plan = [plan_row("summarize-a", "summarize"), plan_row("review-a", "review", after=["summarize-a"])]
    plan += [plan_row("revise-a", "revise", after=["review-a"])]  # queued, never journaled: deferred
    plan += [plan_row("summarize-b", "summarize"), plan_row("review-b", "review", after=["summarize-b"])]
    journal = [journal_row("summarize-a", "summarize", 10), journal_row("review-a", "review", 5)]
    journal += [journal_row("summarize-b", "summarize", 10), journal_row("review-b", "review", 5, stop="timeout")]
    assert run_tails(plan, journal) == []  # a: revise never ran; b: the review failed


def test_a_chain_from_a_flow_call_that_did_not_return_is_not_sampled():
    plan = [plan_row("summarize-a", "summarize", flow_call="0.1"), plan_row("review-a", "review", after=["summarize-a"], flow_call="0.1")]
    plan += [plan_row("summarize-b", "summarize", flow_call="0.2"), plan_row("review-b", "review", after=["summarize-b"], flow_call="0.2")]
    journal = [journal_row(k, k.split("-")[0], 5) for k in ("summarize-a", "review-a", "summarize-b", "review-b")]
    calls = [{"id": "0.1", "event": "end", "state": "returned"}, {"id": "0.2", "event": "end", "state": "raised"}]
    assert {k[1]: t for k, t in run_tails(plan, journal, calls + [{"id": "0", "event": "end", "state": "returned"}])} == {
        "summarize": 5.0,
        "review": 0.0,
    }
    assert run_tails(plan, journal, calls) == []  # flow call 0 never ended: the run was cut short


def test_only_the_most_recent_runs_are_read(tmp_path):
    for i, (review_s, revise_s) in enumerate([(4, 6), (2, 2), (8, 30)]):
        write_run(tmp_path, f"r{i}", *review_run(review_s, revise_s), mtime=1_000_000 + (2 - i) * 100)  # r0 the newest
    assert JournalEstimates(tmp_path, recent=1).tail(task("summarize")) == 15
    assert JournalEstimates(tmp_path, recent=2).tail(task("summarize")) == 11  # 15 and 7
    assert JournalEstimates(tmp_path, recent=1).estimate(task("revise")) == 6


def test_the_most_recent_runs_go_by_their_journals_last_time_not_the_files_time(tmp_path):
    """A copy of the runs directory that did not keep the files' times keeps their rows' times."""
    for i, (review_s, revise_s) in enumerate([(4, 6), (2, 2), (8, 30)]):
        plan, journal = review_run(review_s, revise_s)
        journal = [{**row, "ts": f"2026-10-{20 - i:02d}T09:00:00+00:00"} for row in journal]  # r0 the newest
        write_run(tmp_path, f"r{i}", plan, journal, mtime=1_000_000 + i * 100)  # r2 the newest file
    assert JournalEstimates(tmp_path, recent=1).estimate(task("revise")) == 6


def test_this_runs_attempts_and_flow_calls_update_the_estimates(tmp_path):
    write_run(tmp_path, "old", *review_run(4, 6))
    est = JournalEstimates(tmp_path)
    assert est.estimate(task("review")) == 4 and est.tail(task("review", passes=[1])) == 11
    for r in [plan_row("review-b", "review", passes=[1], flow_call="0.1")]:
        est.observe_plan(r)
    est.observe_plan(plan_row("revise-b", "revise", after=["review-b"], created_from=["review-b"], passes=[1], flow_call="0.1"))
    est.observe_plan(plan_row("review-b~2", "review", after=["revise-b"], created_from=["revise-b"], passes=[2], flow_call="0.1"))
    for key, kind, wall in (("review-b", "review", 30), ("revise-b", "revise", 50), ("review-b~2", "review", 20)):
        est.observe_attempt(journal_row(key, kind, wall))
    assert est.estimate(task("review")) == 25  # this run's attempts replace the past ones
    assert est.tail(task("review", passes=[1])) == 11  # not until its flow call returns
    est.flow_call_ended("0.1", "returned")
    # the chain inside it (50 + 20), then what the past says follows its last task (1)
    assert est.tail(task("review", passes=[1])) == 71
    assert est.tail(task("review", passes=[2])) == 1  # a last task is not sampled from itself
    est.observe_plan(plan_row("review-c", "review", passes=[1], flow_call="0.2"))
    est.observe_plan(plan_row("revise-c", "revise", after=["review-c"], passes=[1], flow_call="0.2"))
    est.observe_attempt(journal_row("review-c", "review", 30))
    est.flow_call_ended("0.2", "raised")  # no sample from a flow call that raised
    assert est.tail(task("review", passes=[1])) == 71


def test_a_long_chain_costs_no_stack():
    n = 3000
    plan = [plan_row(f"t{i}", "step", after=[f"t{i - 1}"] if i else []) for i in range(n)]
    journal = [journal_row(f"t{i}", "step", 1) for i in range(n)]
    tails = [t for _, t in run_tails(plan, journal)]
    assert tails[0] == n - 1 and tails[-1] == 0


def test_the_graph_sets_each_tasks_tail_from_its_estimator(tmp_path):
    graph = Graph(tmp_path / "out")
    graph.tail = lambda t: 7.0 if t.kind == "summarize" else None
    with graph.building():
        example.summarize("a", path="x")
        example.report(summaries=[])
    assert [t.tail_s for t in graph.tasks()] == [7.0, None]


def test_a_past_run_of_an_async_flow_gives_its_first_tasks_a_tail(tmp_path):
    agent = StubAgent(
        {
            "summarize": lambda launch: {"unit": launch.unit, "points": ["p"]},
            "review": {"approved": True, "note": ""},
        }
    )
    rep = Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None).run(
        example.docs, units=["a"]
    )
    journal = rep.run_dir / "journal.jsonl"  # the stub takes no time: give each attempt 2 s
    journal.write_text("".join(json.dumps({**json.loads(line), "wall_s": 2.0}) + "\n" for line in journal.read_text().splitlines()))
    est = JournalEstimates(tmp_path / "runs")
    summarize = task("summarize", flow=(f"{example.__name__}.docs", f"{example.__name__}.review_loop"))
    assert est.tail(summarize) == 4.0  # the review, then the report created from it
    review = task("review", flow=(f"{example.__name__}.docs", f"{example.__name__}.review_loop"), passes=[1])
    assert est.tail(review) == 2.0  # pass 1 of the review loop: the report
