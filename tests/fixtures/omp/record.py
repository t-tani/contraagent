"""Record one launch of the installed omp on each wire into `tests/fixtures/omp/<version>/`.

    uv run python tests/fixtures/omp/record.py      # spends a few cents (Haiku)

The same prompt every time: read a file, run `echo hi`, one `web_search`, reply "done".
Long strings are cut and local paths replaced, so a recording holds the wire's shape,
not its content. `tests/test_omp_wire.py` reads every recording;
`tests/live/test_live_agents.py` records into a temporary directory and reads that.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent._internal.backends.omp import rpc
from contraagent.backends import Launch, OmpBackend, OmpRpcBackend
from contraagent.config import Limits

PROMPT = (
    "Do these three steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`; "
    '3) call web_search once with the query "oh-my-pi coding agent". Then reply with the single word done.'
)
MODEL = "anthropic/claude-haiku-5-5"


def record(cwd: Path) -> dict[str, list[dict]]:
    """Both wires' events of one launch each, as omp sent them."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n", encoding="utf-8", newline="\n")
    launch = Launch(prompt=PROMPT, label="rec", model=MODEL, cwd=cwd, limits=Limits(timeout_s=180, max_turns=8))
    backend = OmpBackend()
    out = subprocess.run(backend.argv(launch), cwd=cwd, env=backend.env(launch), capture_output=True, timeout=200).stdout
    lines = [json.loads(line) for line in out.splitlines() if line.strip().startswith(b"{")]
    frames: list[dict] = []
    feed = rpc.RpcReader.feed

    def keep(self, frame):
        frames.append(frame)
        return feed(self, frame)

    rpc.RpcReader.feed = keep  # type: ignore[method-assign]
    try:
        OmpRpcBackend().run(launch)
    finally:
        rpc.RpcReader.feed = feed  # type: ignore[method-assign]
    return {"json": lines, "rpc": frames}


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
    version = subprocess.run(["omp", "--version"], capture_output=True, text=True, encoding="utf-8").stdout.strip().removeprefix("omp/")
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for wire, evs in record(Path(tmp)).items():
            text = "".join(json.dumps(slim(e, tmp), ensure_ascii=False) + "\n" for e in evs)
            (target / f"{wire}.jsonl").write_text(text, encoding="utf-8", newline="\n")
    print(f"recorded omp {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
