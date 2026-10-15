"""Writes `v1/review/`: a run directory of format 1, from a stub run, which
`tests/test_run_format.py` holds the monitor to reading. It is written once and kept as it
is; a new format gets a fixture of its own beside it.

    uv run python tests/fixtures/runs/make_v1.py

The run's working directory becomes `/work/review` and its host `host-1`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.testing import StubAgent, fails, writes_smallest

HERE = Path(__file__).resolve().parent
CWD = "/work/review"


class Finding(BaseModel):
    line: int = Field(ge=1)
    text: str


class Review(BaseModel):
    verdict: Literal["approve", "change"]
    findings: list[Finding] = Field(default_factory=list)


review = agent_task("review", instructions="Review the file in params.path.", output=Review, max_turns=5, timeout_s=60, retries=0)


@python_task
def fetch(unit: str) -> str:
    return f"src/{unit}.py"


@python_task
def summary(reviews: list[Review]) -> int:
    return sum(len(r.findings) for r in reviews)


def flow(units: list[str]):
    paths = yield [fetch(u) for u in units]
    reviews = []
    for unit, path in zip(units, paths, strict=True):
        try:
            reviews.append((yield review(unit, path=path)))
        except Exception:
            continue
    return (yield summary(reviews=reviews))


def main() -> None:
    out = HERE / "v1" / "review"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        script = {"review-gamma": fails(reason="stub: the review stopped")}
        stub = StubAgent(script, default=writes_smallest(), execute=["fetch", "summary"])
        config = PipelineConfig({"defaults": {"agent": "claude", "model": "claude-sonnet-5-5"}})
        report = Pipeline(config, runs_dir=work / "runs", cwd=work, stub=stub).run(flow, run_id="review", units=["alpha", "beta", "gamma"])
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(report.run_dir, out)
        for path in out.rglob("*"):
            if path.is_file():
                path.write_text(path.read_text().replace(str(work), CWD))
    info = json.loads((out / "run.json").read_text())
    info.update(host_id="host-1", pid=1, start_ticks=1, argv=["flow.py"])
    (out / "run.json").write_text(json.dumps(info))


if __name__ == "__main__":
    main()
