"""A reader of a run record ignores a field it does not know (`docs/compatibility.md`): this
release reads the records a later release of the same run format writes, with new fields at
any depth, while its writers write only the fields declared."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

from contraagent._internal.contracts.calls import CallFile, validate_call
from contraagent._internal.dispatch.records import RecordModel
from contraagent._internal.execution import file_schemas
from contraagent._internal.monitor import api
from contraagent._internal.monitor.views import VIEWS, serialize
from contraagent._internal.runs import layout
from contraagent.monitor import Monitor, Period

FIXTURE = Path(__file__).parent / "fixtures" / "runs" / "v1" / "review"

#: The field a later release adds, at every depth.
LATER = "added_later"

#: Keys whose value is a map of names a pipeline or a coding agent chose (or a document of
#: the pipeline's own: params, a JSON Schema), not a record's fields.
FREE = {
    "params",
    "json_schema",
    "schema",
    "tool_uses",
    "unread_events",
    "retry_errors",
    "tool_args",
    "quota_caps",
    "markers",
    "units",
    "windows",
    "reading",
}


def _later(value: Any) -> Any:
    """`value` with a field `LATER` added to every JSON object in it but the free maps."""
    if isinstance(value, dict):
        return {**{k: v if k in FREE else _later(v) for k, v in value.items()}, LATER: {"x": [1]}}
    if isinstance(value, list):
        return [_later(v) for v in value]
    return value


def _rewrite(path: Path) -> None:
    if path.suffix == ".jsonl":
        rows = [_later(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    else:
        path.write_text(json.dumps(_later(json.loads(path.read_text()))))


#: Rows of the records the fixture does not hold, each with nested records in it.
EXTRA_ROWS = {
    layout.FLOW_CALLS: [
        {
            "ts": "2026-10-15T10:47:45+00:00",
            "id": "0.1",
            "event": "start",
            "parent": "0",
            "function": "__main__.boxed",
            "flow": [{"function": "__main__.flow", "file": "/work/flow/make_v1.py", "line": 60, "loops": [{"line": 58, "pass": 1}]}],
            "time_box": {"started_at": "2026-10-15T10:47:45+00:00", "deadline_s": 60.0, "grace_s": 0.0, "slack_s": 0.0},
        },
        {"ts": "2026-10-15T10:47:45+00:00", "id": "0.1", "event": "end", "state": "returned", "error": None},
    ],
    layout.DEFERRED: [
        {
            "ts": "2026-10-15T10:47:45+00:00",
            "key": "review-delta",
            "kind": "review",
            "unit": "delta",
            "reason": "its credentials rest",
            "cause": {
                "cause": "rest",
                "rests": [{"credential": "personal", "window": "five_hour", "pct": 93.0, "cap": 90.0, "route": "claude"}],
            },
        },
        {
            "ts": "2026-10-15T10:47:45+00:00",
            "key": "review-epsilon",
            "reason": "deadline",
            "cause": {"cause": "deadline", "flow_call": "0.1"},
        },
    ],
    layout.RESTS: [
        {"ts": "2026-10-15T10:47:45+00:00", "event": "start", "credential": "personal", "window": "five_hour", "pct": 93.0, "cap": 90.0},
    ],
    layout.SERVICES: [
        {"ts": "2026-10-15T10:47:45+00:00", "event": "start", "name": "db", "key": "review-alpha", "address": "localhost:5432"},
    ],
}


@pytest.fixture
def later_run(tmp_path: Path) -> Path:
    """The run format fixture as a later release would write it: every row and every object
    in it has a field this release does not know, and so do the records added to it."""
    runs = tmp_path / "runs"
    run_dir = runs / "review"
    shutil.copytree(FIXTURE, run_dir)
    for name, rows in EXTRA_ROWS.items():
        with (run_dir / name).open("a") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    info = json.loads((run_dir / layout.RUN_INFO).read_text())
    info["preflight"] = {
        "policy": "substitute",
        "dropped": [{"agent": "claude", "model": "m1", "credential": "personal", "reason": "rate limited", "kinds": ["review"]}],
        "substituted": [{"kind": "review", "from_agent": "claude", "from_model": "m1", "to_agent": "codex", "to_model": "m2"}],
        "kept": [{"kind": "fetch", "agent": "claude", "model": "m1", "reason": "no route"}],
    }
    info["quota_caps"] = {"personal": {"five_hour_pct": 90.0}}
    (run_dir / layout.RUN_INFO).write_text(json.dumps(info))
    for path in run_dir.rglob("*.json*"):
        if path.relative_to(run_dir).parts[0] not in ("out", layout.STREAMS):
            _rewrite(path)
    return runs


def test_every_model_of_a_run_record_ignores_or_keeps_an_unknown_field():
    models = [*file_schemas.RECORDS.values(), CallFile]
    assert all(issubclass(m, RecordModel) for m in models)
    seen: set[type[BaseModel]] = set()
    stack: list[type[BaseModel]] = [RecordModel]
    while stack:
        model = stack.pop()
        seen.add(model)
        stack += model.__subclasses__()
    # Those of the monitor's API extend a record with fields of the monitor's own.
    for model in seen:
        assert model.model_config.get("extra") in ("ignore", "allow"), model


CURSOR_ROW = {
    "schema_version": "1",
    "run": "review",
    "stage": "review",
    "history": [{"name": "review", "at": "2026-10-15T10:47:45Z"}],
    "units": {"alpha": {"stage": "review", "inflight": {"item_ids": ["a"], "since": "2026-10-15T10:47:45Z", "pid": 1}}},
    "updated_at": "2026-10-15T10:47:45Z",
}


def _rows(name: str) -> list[dict]:
    """The fixture's rows of record `name`, and the rows of `EXTRA_ROWS`."""
    path = FIXTURE / name
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() and name.endswith(".jsonl") else []
    if path.exists() and not name.endswith(".jsonl"):
        rows = [json.loads(path.read_text())]
    return [*rows, *EXTRA_ROWS.get(name, []), *([CURSOR_ROW] if name == layout.CURSOR else [])]


def _without_later(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_later(v) for k, v in value.items() if k != LATER}
    if isinstance(value, list):
        return [_without_later(v) for v in value]
    return value


@pytest.mark.parametrize("name", sorted(file_schemas.RECORDS))
def test_a_record_reader_ignores_a_later_field_and_keeps_the_rest(name):
    model = file_schemas.RECORDS[name]
    rows = _rows(name)
    assert rows
    for row in rows:
        known = model.model_validate(row).model_dump(mode="json", by_alias=True)
        later = model.model_validate(_later(row)).model_dump(mode="json", by_alias=True)
        # A model that keeps extras (a journal row's) keeps it; every other drops it.
        assert _without_later(later) == known


def test_a_call_file_reader_ignores_a_later_field():
    row = json.loads((FIXTURE / layout.CALLS / "review-alpha.json").read_text())
    later = CallFile.model_validate(_later(row))
    assert later == CallFile.model_validate(row)
    assert LATER not in later.model_dump_json()


def test_the_monitor_reads_a_later_run(later_run):
    mon = Monitor(later_run)
    (summary,) = TypeAdapter(list[api.RunSummary]).validate_python(mon.runs())
    assert summary.run == "review" and not summary.running
    for view in VIEWS.values():
        serialize(view.model, view.read(mon, "review"))
    plan = mon.plan("review")
    states = {n["key"]: n["state"] for n in plan["nodes"]}
    assert states["review-alpha"] == "done" and states["review-gamma"] == "failed"
    assert {c["id"] for c in plan["flow_calls"]} >= {"0", "0.1"}
    for key in states:
        TypeAdapter(api.TaskDetail).validate_python(mon.task_detail("review", key))
    day = date.fromisoformat(json.loads((FIXTURE / layout.RUN_INFO).read_text())["started_at"][:10])
    TypeAdapter(api.Trends).validate_python(mon.trends(Period(day, day), stub=True))


def test_a_call_file_with_a_later_field_is_read_and_checked(later_run, tmp_path):
    call_path = later_run / "review" / layout.CALLS / "review-alpha.json"
    out = tmp_path / "alpha.json"
    data = json.loads(call_path.read_text())
    data["output"]["path"] = str(out)
    data["cwd"] = str(tmp_path)
    call_path.write_text(json.dumps(data))
    call = CallFile.read(call_path)
    assert call.params == {"path": "src/alpha.py"}
    assert call.output is not None and call.output.from_ == "file"
    out.write_text("{}")
    assert validate_call(call_path) == (0, "")  # no importable schema: the JSON parses
    # Written again, a call file holds only the fields this release declares.
    again = json.loads(call.write(tmp_path / "again.json").read_text())
    assert LATER not in again and LATER not in again["output"]
