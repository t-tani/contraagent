"""Record one launch of the installed Claude Code into `tests/fixtures/claude/<version>/json.jsonl`.

    uv run python tests/fixtures/claude/record.py      # spends a fraction of a cent (Haiku)

The same prompt every time: read a file, run `echo hi`, reply "done", on the user's own
Claude Code login (`ambient`), launched as `ClaudeBackend` launches a task. Long strings are
cut, local paths replaced and the account's ids removed, so a recording holds the wire's
shape, not its content. `tests/test_claude_wire.py` reads every recording.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent.backends import ClaudeBackend, Launch
from contraagent.config import Limits

PROMPT = (
    "Do these two steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`. "
    "Then reply with the single word done."
)
MODEL = "claude-haiku-5-5"


def record(cwd: Path) -> list[dict]:
    """The events of one launch, as Claude Code printed them."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n", encoding="utf-8", newline="\n")
    launch = Launch(prompt=PROMPT, label="rec", model=MODEL, cwd=cwd, allowed_tools=("Read", "Bash(echo:*)"), limits=Limits(timeout_s=180))
    backend = ClaudeBackend()
    out = subprocess.run(
        backend.argv(launch), cwd=cwd, env=backend.env(launch), capture_output=True, stdin=subprocess.DEVNULL, timeout=200
    ).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip().startswith(b"{")]


#: Keys whose values name the account, the organization or a path of the host: replaced.
PRIVATE = frozenset({"account_uuid", "organization_uuid", "organization_id", "user_id", "email", "messaging_socket_path"})
#: Keys of `system/init` that list what the host has installed: emptied.
INSTALLED = frozenset({"skills", "slash_commands", "terminal_slash_commands", "agents", "plugins", "mcp_servers"})


def slim(value, cwd: str):
    """Long strings cut at 160 characters, the working directory and home replaced, the
    account's ids and the host's paths (`PRIVATE`) removed, what the host has installed
    (`INSTALLED`) emptied."""
    if isinstance(value, dict):
        return {k: "x" if k in PRIVATE else [] if k in INSTALLED else slim(v, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [slim(v, cwd) for v in value]
    if isinstance(value, str):
        value = value.replace(cwd, "/work").replace(str(Path.home()), "/home/user")
        return value if len(value) <= 160 else value[:160] + "…"
    return value


def main() -> int:
    said = subprocess.run(["claude", "--version"], capture_output=True, text=True, encoding="utf-8").stdout
    version = said.split()[0]
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(Path(tmp).resolve())
        events = record(Path(cwd))
        (target / "json.jsonl").write_text(
            "".join(json.dumps(slim(e, cwd), ensure_ascii=False) + "\n" for e in events), encoding="utf-8", newline="\n"
        )
    print(f"recorded claude {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
