"""`benchmarks/schedule.py`, the scheduling benchmark, still runs on this tree: one scenario
quickly in every test run, every scenario under `-m bench`. Its figures are not checked:
they are the benchmark's results, not a test's."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "benchmarks" / "schedule.py"


def bench(tmp_path: Path, *args: str) -> dict:
    out = tmp_path / "result"
    command = [sys.executable, str(TOOL), "run", "--out", str(out), "--seeds", "1", *args]
    subprocess.run(command, check=True, capture_output=True, timeout=900)
    assert out.with_name(f"{out.name}.md").read_text(encoding="utf-8").startswith("# Scheduling benchmark")
    return json.loads(out.with_name(f"{out.name}.json").read_text(encoding="utf-8"))


def test_a_scenario_runs_twice_and_reports_its_figures(tmp_path):
    result = bench(tmp_path, "--scenarios", "demo-deadline", "--scale", "0.02", "--jobs", "1")
    runs = result["scenarios"]["demo-deadline"]["runs"]
    for run in ("first", "second"):
        (figures,) = runs[run]
        assert figures["launches"] > 0 and figures["failed"] == 0
        assert {"makespan", "idle", "deferred", "done_by_deadline", "cost_after_deadline", "deferred_would_fit"} <= set(figures)


@pytest.mark.bench
def test_every_scenario_runs(tmp_path):
    result = bench(tmp_path, "--scale", "0.05")
    for name, scenario in result["scenarios"].items():
        # No task fails. A flow may end in an error: past the grace window of `time-box`,
        # a topic's `finish` is deferred, and nothing catches it.
        for run in ("first", "second"):
            (figures,) = scenario["runs"][run]
            assert figures["launches"] > 0 and figures["failed"] == 0, name
