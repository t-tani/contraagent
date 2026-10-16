"""Write the docs' live-demo data: the showcase runs, as the monitor serves them.

    uv run python web/apps/docs/scripts/fixture.py

Runs the showcase (`web/scripts/showcase.py`: the demo pipeline on its demo agent,
every task done, the runs the packages' screenshots show) in a temporary
directory, then writes

- `src/fixtures/demo-run.json`: its `docs` run through `Monitor` (the same views
  the HTTP API returns), the data a `ca-*` view takes as properties;
- `public/demo/data/`: an export of both runs (`contraagent monitor export`),
  what `<ca-monitor export="/demo/data/">` and an export client read, with each
  task's transcript beside it, which an export holds none of
  (`runs/<run>/streams/<file>.json`, a `StreamPage`, named as `tasks/<file>.json`:
  `file_name(key)`).

In every file the temporary path is replaced by `/work` and the directory
contraagent is installed in (where the demo's flow code is) by `/site-packages`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import contraagent
from contraagent._internal.cli import main as cli
from contraagent._internal.runs.layout import file_name
from contraagent.monitor import Monitor

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "src" / "fixtures" / "demo-run.json"
EXPORT = HERE / "public" / "demo"
SHOWCASE = HERE.parents[1] / "scripts" / "showcase.py"
TRANSCRIPT = "summarize-delta"  # two rounds: sent back once by a validator


def showcase() -> None:
    spec = importlib.util.spec_from_file_location("showcase", SHOWCASE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = Path.cwd()
        os.chdir(tmp)
        try:
            showcase()
            cli(["monitor", "export", "--runs-dir", "demo-runs", "--out", "export", "--runs", "0", "--title", "contraagent demo"])
        finally:
            os.chdir(old)

        def clean(text: str) -> str:
            text = text.replace(str(Path(tmp).resolve()), "/work").replace(tmp, "/work")
            installed = Path(contraagent.__file__).resolve().parents[1]
            # The export writes a path under the home directory as `~/...`.
            home = f"~/{installed.relative_to(Path.home())}" if installed.is_relative_to(Path.home()) else None
            text = text.replace(str(installed), "/site-packages")
            return text.replace(home, "/site-packages") if home else text

        mon = Monitor(Path(tmp) / "demo-runs")
        run = "docs"
        data = {
            "run": run,
            "journal": mon.journal(run)[0],
            "plan": mon.plan(run),
            "outputs": mon.outputs(run),
            "transcript": mon.stream(run, TRANSCRIPT, 0)[0]["events"],
        }
        OUT.write_text(clean(json.dumps(data, indent=1, ensure_ascii=False, default=str)) + "\n", encoding="utf-8", newline="\n")

        shutil.rmtree(EXPORT, ignore_errors=True)
        shutil.copytree(Path(tmp) / "export" / "data", EXPORT / "data")
        for r in ("docs", "analyse"):
            streams = EXPORT / "data" / "runs" / r / "streams"
            streams.mkdir(parents=True, exist_ok=True)
            for key in sorted({row["key"] for row in mon.journal(r)[0]}):
                page = mon.stream(r, key, 0)[0]
                if page["events"]:
                    name = file_name(key)
                    (streams / f"{name}.json").write_text(json.dumps(page, ensure_ascii=False, default=str), encoding="utf-8", newline="\n")
                    # The task's detail names its transcript, as the server's does.
                    task = EXPORT / "data" / "runs" / r / "tasks" / f"{name}.json"
                    task.write_text(
                        json.dumps({**json.loads(task.read_text(encoding="utf-8")), "stream": key}, ensure_ascii=False),
                        encoding="utf-8",
                        newline="\n",
                    )
        size = 0
        for file in (EXPORT / "data").rglob("*.json"):
            file.write_text(clean(file.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
            size += file.stat().st_size
    sys.stdout.write(f"wrote {OUT} ({OUT.stat().st_size // 1024} KiB) and {EXPORT / 'data'} ({size // 1024} KiB)\n")


if __name__ == "__main__":
    main()
