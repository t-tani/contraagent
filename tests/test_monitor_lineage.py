"""The monitor's forecast (the tasks a run is expected to create, from an earlier run of
the same flow), the lineage of a task's earlier and later tasks, and its input files."""

import json
from pathlib import Path

from contraagent._internal.contracts.contract import input_files_of
from contraagent._internal.monitor.core import lineage_of
from contraagent.monitor import Monitor

FLOW = "flows.review"


def frame(function: str, *passes: int) -> dict:
    return {"function": function, "file": "flows.py", "line": 3, "loops": [{"line": 5 + i, "pass": p} for i, p in enumerate(passes)]}


def task(key: str, kind: str, *frames: dict, **extra) -> dict:
    return {"ts": "", "key": key, "kind": kind, "unit": key.rsplit("-", 1)[-1], "after": [], "flow": list(frames), **extra}


def attempt(key: str, kind: str, wall: float, cost: float | None) -> dict:
    return {"ts": "2026-10-01T00:00:00+00:00", "key": key, "kind": kind, "ok": True, "stop": "completed", "wall_s": wall, "cost_usd": cost}


def write_run(
    root: Path, run: str, plan: list[dict], journal: list[dict] = (), *, flow=FLOW, started: str, finished: str | None = None
) -> Path:
    d = root / run
    d.mkdir(parents=True)
    info = {"run_id": run, "run_uid": run, "host_id": "h1", "run_group": run, "started_at": started}
    if flow is not None:
        info["flow"] = flow
    if finished is not None:
        info["finished_at"] = finished
    (d / "run.json").write_text(json.dumps(info))
    (d / "plan.jsonl").write_text("".join(json.dumps(r) + "\n" for r in plan))
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in journal))
    return d


TOP = frame("flows.review")
LOOP = (frame("flows.review"), frame("flows.one", 1))


def earlier_plan(units: str) -> tuple[list[dict], list[dict]]:
    """Per unit: a summary, then a review in pass 1 of the unit's loop."""
    plan, journal = [], []
    for u in units:
        plan += [task(f"summarize-{u}", "summarize", TOP), task(f"review-{u}", "review", *LOOP)]
        journal += [attempt(f"summarize-{u}", "summarize", 10.0, 0.2), attempt(f"review-{u}", "review", 4.0, None)]
    return plan, journal


def test_a_run_records_its_top_flow(demo_runs):
    info = json.loads((demo_runs / "docs" / "run.json").read_text())
    assert info["flow"] == "contraagent.docs.examples.demo.tasks.docs"


def test_the_forecast_reads_the_run_of_the_same_flow_that_finished_last_before(tmp_path):
    plan, journal = earlier_plan("abcd")
    write_run(tmp_path, "earlier", plan, journal, started="2026-10-01T00:00:00+00:00", finished="2026-10-01T01:00:00+00:00")
    # Older, another flow, and one that finished after this run started: none of them is read.
    older, older_journal = earlier_plan("abcdefgh")
    write_run(tmp_path, "older", older, older_journal, started="2026-09-01T00:00:00+00:00", finished="2026-09-01T01:00:00+00:00")
    write_run(
        tmp_path,
        "other",
        older,
        older_journal,
        flow="flows.other",
        started="2026-10-01T02:00:00+00:00",
        finished="2026-10-01T03:00:00+00:00",
    )
    write_run(tmp_path, "later", older, older_journal, started="2026-10-02T00:00:00+00:00", finished="2026-10-02T01:00:00+00:00")
    now = write_run(tmp_path, "now", [task("summarize-a", "summarize", TOP)], started="2026-10-01T05:00:00+00:00")

    mon = Monitor(tmp_path)
    got = mon.forecast("now")
    assert (got["flow"], got["earlier_run"], got["earlier_finished_at"]) == (FLOW, "earlier", "2026-10-01T01:00:00+00:00")
    summarize, review = got["entries"]
    assert (summarize["kind"], summarize["group"], summarize["flow"], summarize["passes"]) == (
        "summarize",
        "summarize",
        ["flows.review"],
        [],
    )
    assert (summarize["expected"], summarize["created"], summarize["remaining"]) == (4, 1, 3)
    assert (summarize["wall_s"], summarize["cost_usd"]) == (30.0, 0.6)
    assert (review["flow"], review["passes"], review["expected"], review["remaining"]) == (["flows.review", "flows.one"], [1], 4, 4)
    assert (review["wall_s"], review["cost_usd"]) == (16.0, None)  # the earlier run reported no cost for it
    assert (got["remaining"], got["wall_s"], got["cost_usd"]) == (7, 46.0, 0.6)

    # Each task the run creates takes one off; a run that creates more is no error.
    rows = [task(f"summarize-{u}", "summarize", TOP) for u in "bcdef"]
    with (now / "plan.jsonl").open("a") as f:
        f.write("".join(json.dumps(r) + "\n" for r in rows))
    summarize = mon.forecast("now")["entries"][0]
    assert (summarize["expected"], summarize["created"], summarize["remaining"], summarize["wall_s"]) == (4, 6, 0, 0.0)


def test_a_run_with_no_flow_or_no_earlier_run_has_no_forecast(tmp_path):
    plan, journal = earlier_plan("ab")
    write_run(tmp_path, "earlier", plan, journal, started="2026-10-01T00:00:00+00:00", finished="2026-10-01T01:00:00+00:00")
    write_run(tmp_path, "old-release", [], flow=None, started="2026-10-01T05:00:00+00:00")
    write_run(tmp_path, "first", [], flow="flows.first", started="2026-10-01T05:00:00+00:00")
    write_run(tmp_path, "unfinished", plan, journal, flow="flows.first", started="2026-10-01T00:00:00+00:00")
    mon = Monitor(tmp_path)
    for run, flow in (("old-release", ""), ("first", "flows.first")):
        assert mon.forecast(run) == {
            "flow": flow,
            "earlier_run": "",
            "earlier_finished_at": "",
            "entries": [],
            "remaining": 0,
            "wall_s": 0.0,
            "cost_usd": None,
        }


def test_the_lineage_of_a_task_tells_data_from_order_and_from_creation():
    node = {"given_from": ["a"], "after": ["a", "b"], "created_from": ["a", "c"]}
    assert lineage_of(node) == {"a": ["given_from", "created_from"], "b": ["after"], "c": ["created_from"]}


def test_earlier_and_later_tasks_carry_their_lineage(tmp_path):
    plan = [
        task("prepare-u", "prepare", TOP),
        task("summarize-u", "summarize", TOP, given_from=["prepare-u"], after=["prepare-u"], created_from=["prepare-u"]),
        task("index-u", "index", TOP, after=["prepare-u"]),
        task("review-u", "review", TOP, created_from=["summarize-u"]),
    ]
    write_run(tmp_path, "r", plan, started="2026-10-01T00:00:00+00:00")
    mon = Monitor(tmp_path)
    down = {d["key"]: d["lineage"] for d in mon.task_detail("r", "prepare-u")["io"]["downstream"]}
    assert down == {"summarize-u": ["given_from", "created_from"], "index-u": ["after"]}
    up = {u["key"]: u["lineage"] for u in mon.task_detail("r", "review-u")["io"]["upstream"]}
    assert up == {"summarize-u": ["created_from"]}


def test_input_files_are_found_among_the_params_at_any_depth():
    sha = "a" * 64
    params = {"note": {"path": "out/a.md", "sha256": sha}, "notes": [{"path": "in/b.md", "sha256": sha}], "other": {"path": "x"}}
    assert input_files_of(params) == [
        {"param": "note", "path": "out/a.md", "sha256": sha},
        {"param": "notes/0", "path": "in/b.md", "sha256": sha},
    ]


def test_an_input_file_names_the_task_that_wrote_it_and_its_check(tmp_path):
    sha = "b" * 64
    plan = [task("write-u", "write", TOP), task("count-u", "count", TOP, given_from=["write-u"]), task("lint-u", "lint", TOP)]
    d = write_run(tmp_path, "r", plan, [attempt("write-u", "write", 1.0, None)], started="2026-10-01T00:00:00+00:00")
    contracts = d / "contracts"
    contracts.mkdir()
    out = {"io": "output", "path": "/work/runs/r/out/write/u.md", "schema_name": "text"}
    files = [{"param": "note", "path": "out/write/u.md", "sha256": sha}, {"param": "spec", "path": "in/spec.md", "sha256": sha}]
    for rec in (
        {"key": "write-u", "outputs": [out]},
        {"key": "count-u", "input_files": files},
        {"key": "lint-u", "input_files": files[1:]},
    ):
        (contracts / f"{rec['key']}.json").write_text(json.dumps({"outputs": [], "inputs": [], **rec}))
    mon = Monitor(tmp_path)
    got = mon.task_detail("r", "count-u")["io"]["input_files"]
    assert [(f["param"], f["writer"], f["check"]) for f in got] == [("note", "write-u", "not_checked"), ("spec", None, "not_checked")]

    refusal = "input file in/spec.md changed after the task call: sha256 bbbbbbbbbbbb at the call, cccccccccccc now"
    with (d / "journal.jsonl").open("a") as f:
        f.write(json.dumps({**attempt("count-u", "count", 1.0, None), "ok": False, "stop": "invalid_input", "reason": refusal}) + "\n")
        f.write(json.dumps(attempt("lint-u", "lint", 1.0, None)) + "\n")
    got = mon.task_detail("r", "count-u")["io"]["input_files"]
    assert [(f["check"], f["reason"]) for f in got] == [("not_checked", ""), ("refused", refusal)]
    assert mon.task_detail("r", "lint-u")["io"]["input_files"][0]["check"] == "passed"
