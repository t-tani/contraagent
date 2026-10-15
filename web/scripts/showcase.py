"""The runs the root README's screenshots show (`screenshots.mjs` calls it).

    uv run python web/scripts/showcase.py        # writes inputs/ and demo-runs/ in the current directory

The demo pipeline on its demo agent (no coding agent, nothing spent), with units
that all finish: every task is done. `beta`'s summary is rate limited on its first
model and done after a model switch; `alpha`'s note and `delta`'s summary fail
their checks once and are done after a correction in the same session; `gamma`'s
first review does not approve, so its review loop runs a second pass. Then the
nested `analyse` flow (three layers of flow calls, a loop inside a loop).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from contraagent import Overrides, Pipeline
from contraagent.docs.examples.analysis.flow import analyse
from contraagent.docs.examples.demo.run import HERE, DemoAgent
from contraagent.docs.examples.demo.tasks import docs

UNITS = ("alpha", "beta", "gamma", "delta", "eta", "theta", "iota", "kappa")


def main() -> None:
    inputs = Path("inputs")
    inputs.mkdir(exist_ok=True)
    for u in UNITS:
        (inputs / f"{u}.md").write_text(f"# {u}\nThe {u} component parses a config file, validates it and reports errors.\n")
    for run_id in ("analyse", "docs"):
        shutil.rmtree(Path("demo-runs", run_id), ignore_errors=True)

    nested = Pipeline(None, runs_dir="demo-runs", backends={"stub": DemoAgent()}, overrides=Overrides(agent="stub"))
    nested.run(analyse, bundles=["east", "west", "south"])

    agent = DemoAgent()
    # The demo's review of gamma fails twice before it succeeds (retries); the showcase
    # starts it at its third round, so its first review completes (and does not approve).
    agent.rounds["review-gamma"] = 2
    report = Pipeline(HERE / "pipeline.toml", runs_dir="demo-runs", backends={"stub": agent}).run(docs, units=list(UNITS))
    if report.failed or report.partial:
        raise SystemExit(f"the showcase run has tasks not done: {[r.task.key for r in (*report.failed, *report.partial)]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
