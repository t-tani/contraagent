"""Record one launch of the installed omp on each wire into `tests/fixtures/omp/<version>/`.

    uv run python tests/fixtures/omp/record.py [json] [rpc] [stop]   # spends a few cents (Haiku)

The same prompt every time on `json` and `rpc`: read a file, run `echo hi`, one
`web_search`, reply "done". `stop` is one `--mode json` launch whose plugin's stop hook
objects once and whose task denies `Bash(rm:*)` (`STOP_PROMPT`). Long strings are cut and
local paths replaced, so a recording holds the wire's shape, not its content. `tests/test_omp_wire.py` reads every recording;
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


#: The prompt of the stop hook's recording: the plugin's stop hook objects once, and the task
#: denies `Bash(rm:*)`, so the recording holds a continued session and a blocked call.
STOP_PROMPT = "Write the word APPLE to the file out.txt, then run the shell command `rm -f none.txt`, then reply with the single word done."
#: The stop hook of that recording: it objects once (exit 2), as `contraagent call validate` does.
ONCE = """#!/usr/bin/env bash
if grep -q '"stop_hook_active": *true' <(cat); then exit 0; fi
echo "The output file does not pass its checks:" >&2
echo "- out.txt: must hold the word BANANA, not APPLE" >&2
exit 2
"""


def record_stop(cwd: Path) -> list[dict]:
    """The `--mode json` events of one launch whose plugin's stop hook objects once and whose
    task denies `Bash(rm:*)`: the plugin is rendered for omp (`omp/index.ts`, `omp/hooks.json`)."""
    from contraagent._internal.plugins import hooks
    from contraagent._internal.plugins.plugin import Plugin
    from contraagent._internal.plugins.scaffold import new_plugin

    plug = cwd / "plug"
    new_plugin(plug, "rec")
    (plug / "hooks.toml").write_text('[[hooks]]\non = "stop"\nscript = "hooks/once.sh"\n', encoding="utf-8", newline="\n")
    script = plug / "hooks" / "once.sh"
    script.write_text(ONCE, encoding="utf-8", newline="\n")
    script.chmod(0o755)
    hooks.write(Plugin.load(plug), ["omp"])
    limits = Limits(timeout_s=180, max_turns=8, disallowed_tools=("Bash(rm:*)",))
    launch = Launch(prompt=STOP_PROMPT, label="rec", model=MODEL, cwd=cwd, plugin_dirs=(str(plug),), limits=limits)
    backend = OmpBackend()
    out = subprocess.run(backend.argv(launch), cwd=cwd, env=backend.env(launch), capture_output=True, timeout=200).stdout
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


def main(wanted: list[str]) -> int:
    """Record the wires `wanted` names (`json`, `rpc`, `stop`; all by default)."""
    wanted = wanted or ["json", "rpc", "stop"]
    version = subprocess.run(["omp", "--version"], capture_output=True, text=True, encoding="utf-8").stdout.strip().removeprefix("omp/")
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        recorded = record(Path(tmp)) if {"json", "rpc"} & set(wanted) else {}
        if "stop" in wanted:
            recorded["stop"] = record_stop(Path(tmp))
        for wire, evs in recorded.items():
            if wire not in wanted:
                continue
            text = "".join(json.dumps(slim(e, tmp), ensure_ascii=False) + "\n" for e in evs)
            (target / f"{wire}.jsonl").write_text(text, encoding="utf-8", newline="\n")
    print(f"recorded omp {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
