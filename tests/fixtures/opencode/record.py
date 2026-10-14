"""Record one launch of the installed opencode into `tests/fixtures/opencode/<version>/json.jsonl`.

    uv run python tests/fixtures/opencode/record.py     # a free OpenCode Zen model: no cost
    CONTRAAGENT_OPENCODE_MODEL=provider/model uv run python tests/fixtures/opencode/record.py

The same prompt every time: read a file, run `echo hi`, reply "done". Long strings are cut and
local paths replaced, so a recording holds the wire's shape, not its content.
`tests/test_opencode_wire.py` reads every recording; `tests/live/test_live_agents.py` records
into a temporary directory and reads that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent import Launch, Limits, OpencodeBackend

PROMPT = (
    "Do these two steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`. "
    "Then reply with the single word done."
)
MODEL = os.environ.get("CONTRAAGENT_OPENCODE_MODEL", "opencode/muse-spark-1.3-contributor-free")


def record(cwd: Path) -> list[dict]:
    """The events of one launch, as opencode printed them."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n")
    launch = Launch(prompt=PROMPT, label="rec", model=MODEL, cwd=cwd, limits=Limits(timeout_s=180, max_turns=8))
    backend = OpencodeBackend()
    out = subprocess.run(backend.argv(launch), cwd=cwd, env=backend.env(launch), capture_output=True, timeout=200).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip().startswith(b"{")]


def slim(value, cwd: str):
    """Long strings cut at 160 characters, the working directory and home replaced."""
    if isinstance(value, dict):
        return {k: slim(v, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [slim(v, cwd) for v in value]
    if isinstance(value, str):
        value = value.replace(cwd, "/work").replace(cwd.lstrip("/"), "work").replace(str(Path.home()), "/home/user")
        return value if len(value) <= 160 else value[:160] + "…"
    return value


def main() -> int:
    version = subprocess.run(["opencode", "--version"], capture_output=True, text=True).stdout.strip()
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(Path(tmp).resolve())
        events = record(Path(cwd))
        (target / "json.jsonl").write_text("".join(json.dumps(slim(e, cwd), ensure_ascii=False) + "\n" for e in events))
    print(f"recorded opencode {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
