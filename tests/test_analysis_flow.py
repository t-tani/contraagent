"""The nested example flow (`contraagent.docs.examples.analysis`) on the stub agent:
three layers of flow calls, nested loops, a fan-out sized at run time, and a kind
chosen at run time. It checks clean (both parser kinds reachable), runs end to end,
and the recorded origins match its structure."""

from __future__ import annotations

import json
from pathlib import Path

from contraagent import Overrides, Pipeline
from contraagent.docs.examples.analysis import flow as example
from contraagent.testing import StubAgent

HERE = Path(example.__file__).resolve().parents[1]  # the run's working directory holds the flow's file


def classify(launch):
    name = launch.params["file"]["name"]
    return {"name": name, "format": "json" if name.endswith("1") else "csv", "data": True}


def table(launch):
    return {"columns": [{"name": "id", "nulls": 0}, {"name": "amount", "nulls": 1}, {"name": "note", "nulls": 9}]}


def propose(launch):
    # one column's first reading is too short, so `verify` sends it back once (the inner loop's pass 2).
    short = launch.key == "propose-east-0-id" and launch.n == 1
    col = launch.params["column"]["name"]
    return {"column": col, "reads": "value" if short else f"The {col} column."}


def refine(launch):
    return {"column": launch.params["meaning"]["column"], "reads": f"The {launch.params['meaning']['column']} column, in words."}


def stub() -> StubAgent:
    return StubAgent({"classify": classify, "parse_csv": table, "parse_json": table, "propose": propose, "refine": refine})


def pipeline(runs, agent=None):
    backends = (agent or stub()).backends()
    return Pipeline(
        None,
        runs_dir=runs,
        backends=backends,
        cwd=HERE,
        overrides=Overrides(agent="stub"),
        log=lambda line: None,
    )


def test_the_flow_checks_clean_and_both_parser_kinds_are_reachable():
    report = Pipeline(None, backends=stub().backends(), cwd=HERE, overrides=Overrides(agent="stub")).check(
        example.analyse, bundles=["east", "west"]
    )
    assert report.ok, report
    # Only what the flow creates before its first wait is built; the rest is found in the code it reaches.
    assert {"parse_csv", "parse_json"} <= set(report.later_kinds)  # the kind is chosen at run time; both are reachable


def test_it_runs_end_to_end_and_records_its_structure(tmp_path):
    agent = stub()
    report = pipeline(tmp_path / "runs", agent).run(example.analyse, bundles=["east", "west", "south"], run_id="analyse")
    assert report.ok, report.failed
    assert report.value == "east: 4 columns\nwest: 2 columns\nsouth: 2 columns"  # the summary task's output

    plan = {json.loads(line)["key"]: json.loads(line) for line in (report.run_dir / "plan.jsonl").read_text().splitlines()}

    # Three layers of flow calls: analyse (0), analyse_bundle (0.N), analyse_file (0.N.M).
    assert plan["python:summary"]["flow_call"] == "0"
    assert plan["classify-east-0"]["flow_call"] == "0.1" and plan["python:report-east"]["flow_call"] == "0.1"
    assert plan["parse_csv-east-0"]["flow_call"] == "0.1.1" and plan["parse_json-east-1"]["flow_call"] == "0.1.2"
    names = [f["function"].rsplit(".", 1)[1] for f in plan["propose-east-0-id"]["flow"]]
    assert names == ["analyse", "analyse_bundle", "analyse_file"]

    # The kind chosen at run time, from the format: east-0 is CSV, east-1 is JSON.
    assert "parse_csv-east-0" in plan and "parse_json-east-1" in plan

    # Nested loops in analyse_file, by their first lines: `propose` is in the `for` only,
    # `verify` and `refine` in the `while` inside it too.
    source = Path(example.__file__).read_text().splitlines()
    outer = 1 + next(i for i, line in enumerate(source) if line.strip() == "for column in ranked.top:")
    inner = 1 + next(i for i, line in enumerate(source) if line.strip() == "while True:")

    def loops(key):
        return [(loop["line"], loop["pass"]) for loop in plan[key]["flow"][2]["loops"]]

    assert loops("parse_csv-east-0") == []
    # east-0's first column (id): its reading was sent back once, so verify ran in passes 1
    # and 2 of the `while`, and refine in pass 1; all in pass 1 of the `for`.
    assert loops("propose-east-0-id") == [(outer, 1)]
    assert loops("python:verify-east-0-id") == [(outer, 1), (inner, 1)]
    assert loops("refine-east-0-id") == [(outer, 1), (inner, 1)]
    assert loops("python:verify-east-0-id~2") == [(outer, 1), (inner, 2)]
    # its second column (amount): pass 2 of the `for`, and the `while` entered again at pass 1.
    assert loops("propose-east-0-amount") == [(outer, 2)]
    assert loops("python:verify-east-0-amount") == [(outer, 2), (inner, 1)]
    assert len(agent.launches_of("propose-east-0-id")) == 1 and len(agent.launches_of("refine-east-0-id")) == 1
