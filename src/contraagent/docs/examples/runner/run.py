"""Run `reviews` from a program: what `contraagent run` takes, and what only Python can pass.

    python -m contraagent.docs.examples.runner.run alpha beta --config pipeline.toml
    python -m contraagent.docs.examples.runner.run alpha beta gamma --resume

`contraagent run` takes the flow, its arguments (`--kwargs`), the config, an agent or
model override, the run id, `--resume`, the runs directory, the preflight policy, and
the stub, record and replay options. A function or an object cannot be given on a
command line, so these `Pipeline` arguments need a program: `row_extras` (a journal
column of the pipeline's own), `quota_rule`, `scopes`, `enrichers`, `backends`, `env`,
`services`, `mcp_servers`, `log`, a credential override (`Overrides(credential=)`), `max_concurrent`, `cwd`,
`keep_transcripts` and the queue's options (`deadline_s`, ...).
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from contraagent import Pipeline, RunReport, TaskResult
from contraagent.backends import Backend
from contraagent.config import QuotaReading
from contraagent.docs.examples.runner.flow import reviews


def severity_column(runs_dir: Path, run_id: str) -> Callable[[TaskResult], dict[str, Any]]:
    """`row_extras`: a `severity` column in each `review` attempt's journal row. A result
    carries no output, so the column reads the task's output file, under the run's `out/`
    at the path its kind's `output_name` gives (`{kind}/{unit}.json` by default)."""

    def row_extras(result: TaskResult) -> dict[str, Any]:
        task = result.task
        path = runs_dir / run_id / "out" / task.kind / f"{task.unit}.json"
        if task.kind != "review" or not result.ok or not path.is_file():
            return {}
        return {"severity": json.loads(path.read_text(encoding="utf-8"))["severity"]}

    return row_extras


def rest_past_80(credential: str, reading: QuotaReading) -> str | tuple[str, datetime] | None:
    """`quota_rule`: the credential named `credential` rests once its 5-hour usage passes
    80%, until its 5-hour window resets (the config's caps rest it at their own limits)."""
    if reading.five_hour_pct is None or reading.five_hour_pct <= 80:
        return None
    reason = f"5-hour usage {reading.five_hour_pct:.0f}% is past 80%"
    resets = reading.five_hour_resets_at
    return (reason, datetime.fromisoformat(resets)) if resets else reason


def main(argv: list[str] | None = None, *, backends: Mapping[str, Backend] | None = None) -> RunReport:
    ap = argparse.ArgumentParser(description="Review each unit's release notes, in/<unit>.md.")
    ap.add_argument("units", nargs="+")
    ap.add_argument("--config", default=None, help="the pipeline's TOML file")
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--run-id", default="reviews")
    ap.add_argument("--resume", action="store_true", help="skip the reviews the run already finished")
    args = ap.parse_args(argv)

    runs_dir = Path(args.runs_dir)
    pipeline = Pipeline(
        args.config,
        runs_dir=runs_dir,
        backends=backends,
        row_extras=severity_column(runs_dir, args.run_id),
        quota_rule=rest_past_80,
        max_concurrent=2,
    )
    report = pipeline.run(reviews, units=args.units, run_id=args.run_id, resume=args.resume)
    for key, result in report.results.items():
        print(f"{key}: {result.stop} {result.reason}".rstrip())
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    raise SystemExit(0 if main().ok else 1)
