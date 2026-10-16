"""Record one launch of the installed pi into `tests/fixtures/pi/<version>/json.jsonl`.

    uv run python tests/fixtures/pi/record.py      # spends a fraction of a cent (GPT-5.6 Luna)

The same prompt every time: read a file, run `echo hi`, reply "done", on the user's own
pi logins (`ambient`). Long strings are cut and local paths replaced, so a recording
holds the wire's shape, not its content. `tests/test_pi_wire.py` reads every recording.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent.backends import Launch, PiBackend
from contraagent.config import Limits

PROMPT = (
    "Do these two steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`. "
    "Then reply with the single word done."
)
MODEL = "openai/gpt-5.6-luna"


def record(cwd: Path) -> list[dict]:
    """The events of one launch, as pi sent them."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n", encoding="utf-8", newline="\n")
    launch = Launch(prompt=PROMPT, label="rec", model=MODEL, effort="low", cwd=cwd, limits=Limits(timeout_s=180))
    backend = PiBackend()
    out = subprocess.run(
        backend.argv(launch), cwd=cwd, env=backend.env(launch), capture_output=True, stdin=subprocess.DEVNULL, timeout=200
    ).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip().startswith(b"{")]


def slim(value, cwd: str):
    """Long strings cut at 160 characters, the working directory and home replaced."""
    if isinstance(value, dict):
        return {k: slim(v, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [slim(v, cwd) for v in value]
    if isinstance(value, str):
        value = value.replace(cwd, "/work").replace(str(Path.home()), "/home/user")
        return value if len(value) <= 160 else value[:160] + "…"
    return value


def main() -> int:
    version = subprocess.run(["pi", "--version"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        events = record(Path(tmp))
        (target / "json.jsonl").write_text(
            "".join(json.dumps(slim(e, tmp), ensure_ascii=False) + "\n" for e in events), encoding="utf-8", newline="\n"
        )
    print(f"recorded pi {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
