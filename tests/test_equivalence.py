"""The example flows do on the current tree what they did on 0.6.2, but for the listed differences.

`tests/equivalence/record.py` recorded each flow of `FLOWS` on the 0.6.2 release into
`tests/fixtures/equivalence/0.6.2/`: the tasks it creates (key, kind, unit, final stop),
the content of each output file, the `RunReport` counts and the flow's value. Here the
same recorder runs each flow on the current tree, and every difference from the
baseline must be one that `DIFFERENCES` allows for that flow. An allowed difference
names the row of the migration table it comes from (`ROWS`): 0.7.0 keeps the result of
a flow on the success path, and changes it only where a row says so.

A flow whose difference waits for a pull request still to land is in `PENDING`, a
strict xfail: it fails once the flow matches again, so the entry is removed then. The
0.7.0 release removes `PENDING` and checks that every entry of `DIFFERENCES` still
occurs. A flow that 0.6.2 did not have is in `NEW`.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).parent
BASELINE = HERE / "fixtures" / "equivalence" / "0.6.2"


def _recorder() -> Any:
    spec = importlib.util.spec_from_file_location("equivalence_record", HERE / "equivalence" / "record.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # the dataclasses find their module
    spec.loader.exec_module(module)
    return module


record = _recorder()

#: The rows of the migration table (0.6.1 → 0.7.0) that let a result change. Each
#: allowed difference names one.
ROWS = {
    "pending-to-await": (
        "A flow that does not wait passes a task call (a Pending) to another task: it becomes an async def that "
        "awaits and passes the output. Same result on the success path; when the input's writer fails or is "
        "deferred, the tasks that read it are not created, so no invalid_input row is written and "
        "RunReport.failed and deferred count fewer."
    ),
    "keep-going": (
        "One task fails (keep going): the other flow calls and tasks go on, and the run ends not ok. Each flow "
        "call that raises an exception of its own is a flow error, even when a parent catches it."
    ),
    "unit-flow-calls": (
        "Work on each unit in one flow call goes on past a failure of another: it becomes a child flow call per "
        "unit under asyncio.gather(..., return_exceptions=True). Same result for the units that got through; "
        "the work after the gather runs on them."
    ),
}


@dataclass(frozen=True)
class Allowed:
    """A difference from the baseline that the table allows: the paths it may touch
    (`fnmatch` patterns over `tasks/<key>`, `outputs/<file>`, `report/<count>`, `value`),
    the row of `ROWS` and why the flow differs there."""

    paths: tuple[str, ...]
    row: str
    why: str


DIFFERENCES: dict[str, list[Allowed]] = {
    "review.docs": [
        Allowed(
            ("tasks/python:report", "outputs/report/*", "value"),
            "unit-flow-calls",
            "On the stub no review approves, so both review loops stop at their pass limit (TooManyPasses). "
            "`docs` now gathers the loops with return_exceptions=True, so it still runs `report`, on no summary; "
            "on 0.6.2 the gather raised and `report` was never created.",
        ),
        Allowed(
            ("report/flow_errors",),
            "keep-going",
            "Both loops' TooManyPasses are flow errors; on 0.6.2 only the top flow call that raised one was.",
        ),
    ],
    "demo.docs.demo": [
        Allowed(
            ("tasks/summarize-zeta", "report/failed"),
            "pending-to-await",
            "zeta's `prepare` fails. On 0.6.2 `review_loop` passed the prepare call to `summarize`, which was "
            "created and refused (invalid_input); now it awaits `prepare`, so zeta's summary is not created and "
            "does not count as failed.",
        ),
    ],
    "demo.docs_one_review.demo": [
        Allowed(
            (
                "tasks/summarize-zeta",
                "tasks/python:score-zeta",
                "tasks/review-zeta",
                "tasks/write_note-zeta",
                "tasks/python:report",
            ),
            "pending-to-await",
            "zeta's `prepare` fails. On 0.6.2 the flow does not wait, so zeta's summary, score, review and note "
            "and the report are created and refused (invalid_input); awaited, zeta's are not created, and the "
            "report runs over the other units.",
        ),
        Allowed(
            ("report/failed", "report/ok", "outputs/report/*", "value"),
            "pending-to-await",
            "The refused tasks no longer count as failed, and the report over the other units is written.",
        ),
    ],
}

#: Flows that differ from the baseline in a way a pull request still to land allows: the
#: flow, and which change. A strict xfail each.
PENDING: dict[str, str] = {}

#: Flows that 0.6.2's examples do not have, and why they were added.
NEW = {
    "cancel.review": "the example of cancellable tasks: probes whose answers stop being needed (.options(cancellable=True))",
    "review.publish.approve": "the all-or-nothing example of keep going: one report only when every unit's loop got through (TaskGroup)",
}

BASELINED = sorted(p.stem for p in BASELINE.glob("*.json"))


def differences(baseline: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """The paths where `now` differs from `baseline`: a task, an output file or a count by
    name, the value whole, a field of the flow's call by name."""
    found = [name for name in ("call", "kwargs", "config", "scenario") if baseline[name] != now[name]]
    for section in ("tasks", "outputs", "report"):
        before, after = baseline[section], now[section]
        found += [f"{section}/{k}" for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
    if baseline["value"] != now["value"]:
        found.append("value")
    return found


def unexplained(flow: str, paths: list[str]) -> list[str]:
    allowed = [pattern for a in DIFFERENCES.get(flow, []) for pattern in a.paths]
    return [p for p in paths if not any(fnmatch.fnmatchcase(p, pattern) for pattern in allowed)]


def _param(flow: str) -> Any:
    if flow in PENDING:
        return pytest.param(flow, marks=pytest.mark.xfail(reason=PENDING[flow], strict=True))
    return flow


@pytest.mark.parametrize("flow", [_param(f) for f in BASELINED])
def test_the_flow_does_what_it_did_on_0_6_2(flow, tmp_path):
    baseline = json.loads((BASELINE / f"{flow}.json").read_text(encoding="utf-8"))
    (spec,) = [f for f in record.FLOWS if f.id == flow]
    now = record.summary(spec, tmp_path)
    left = unexplained(flow, differences(baseline, now))
    assert not left, f"{flow} differs from 0.6.2 where no row of the migration table allows it: {left}"


def test_every_flow_has_a_baseline_or_is_new():
    ids = [f.id for f in record.FLOWS]
    assert len(ids) == len(set(ids))
    assert set(ids) - set(BASELINED) == set(NEW)
    assert set(BASELINED) <= set(ids)


def test_every_example_with_a_flow_is_recorded():
    examples = HERE.parent / "src" / "contraagent" / "docs" / "examples"
    with_flows = {p.parent.name for name in ("flow.py", "tasks.py") for p in examples.glob(f"*/{name}")}
    assert with_flows == {f.example for f in record.FLOWS}


def test_every_allowed_difference_names_a_row_and_a_recorded_flow():
    for flow, allowed in DIFFERENCES.items():
        assert flow in BASELINED, flow
        assert all(a.row in ROWS and a.paths and a.why for a in allowed), flow
    assert set(PENDING) <= set(BASELINED)


def test_the_comparison_names_each_difference():
    base = {"call": "c", "kwargs": {}, "config": False, "scenario": "stub", "value": 1}
    before = {**base, "tasks": {"a": {"stop": "completed"}}, "outputs": {"x": "1"}, "report": {"ok": True}}
    after = {**base, "tasks": {"b": {"stop": "completed"}}, "outputs": {"x": "2"}, "report": {"ok": True}, "value": 2}
    assert differences(before, after) == ["tasks/a", "tasks/b", "outputs/x", "value"]
    assert unexplained("review.docs", ["tasks/python:report", "tasks/review-alpha", "outputs/report/report.json"]) == ["tasks/review-alpha"]
