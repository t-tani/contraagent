"""Write the docs' live-demo data: the demo pipeline's run, as the monitor serves it.

    uv run python web/apps/docs/scripts/fixture.py

Runs the demo pipeline (`contraagent.docs.examples.demo`) with its demo agent
in a temporary directory, reads the run through `Monitor` (the same views the
HTTP API returns) and writes
`src/fixtures/demo-run.json`, with the temporary path replaced by `/work` and
the directory contraagent is installed in (where the demo's flow code is) by
`/site-packages`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import contraagent
from contraagent.docs.examples.demo import run as demo
from contraagent.monitor import Monitor

OUT = Path(__file__).resolve().parents[1] / "src" / "fixtures" / "demo-run.json"
TRANSCRIPT = "summarize-delta"  # two rounds: sent back once by a validator


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = Path.cwd()
        os.chdir(tmp)
        try:
            demo.main(["--no-serve", "--fast"])
        finally:
            os.chdir(old)
        mon = Monitor(Path(tmp) / "demo-runs")
        run = "docs"
        data = {
            "run": run,
            "journal": mon.journal(run)[0],
            "plan": mon.plan(run),
            "outputs": mon.outputs(run),
            "transcript": mon.stream(run, TRANSCRIPT, 0)[0]["events"],
        }
        text = json.dumps(data, indent=1, ensure_ascii=False, default=str)
        text = text.replace(str(Path(tmp).resolve()), "/work").replace(tmp, "/work")
        text = text.replace(str(Path(contraagent.__file__).resolve().parents[1]), "/site-packages")
    OUT.write_text(text + "\n")
    sys.stdout.write(f"wrote {OUT} ({len(text) // 1024} KiB)\n")


if __name__ == "__main__":
    main()
