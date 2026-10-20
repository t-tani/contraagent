"""Record two launches of the installed codex into `tests/fixtures/codex/<version>/`.

    uv run python tests/fixtures/codex/record.py      # spends a fraction of a cent

The same prompts every time, on the user's own codex login (`ambient`): one launch reads a
file, runs `echo hi` and replies "done" (`json.jsonl`, its `codex exec --json` events), then
one resumes its thread with one more prompt (`resume.jsonl`). `rollout.jsonl` is the thread's
rollout file after both. Long strings are cut and local paths replaced, so a recording holds
the shapes, not the content. `tests/test_codex_wire.py` reads every recording.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent._internal.backends.codex import wire
from contraagent.backends import CodexBackend, Launch
from contraagent.config import Limits

PROMPT = (
    "Do these two steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`. "
    "Then reply with the single word done."
)
RESUME_PROMPT = "Now reply with the single word again, nothing else."
MODEL = "gpt-5.6-luna"


def record(cwd: Path) -> dict[str, list[dict]]:
    """The events of both launches, as codex printed them, and the thread's rollout lines."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n", encoding="utf-8", newline="\n")
    backend = CodexBackend()
    events: list[dict] = []
    feed = wire.EventReader.feed

    def keep(self, ev):
        events.append(ev)
        return feed(self, ev)

    wire.EventReader.feed = keep  # type: ignore[method-assign]
    try:
        launch = Launch(prompt=PROMPT, label="rec", model=MODEL, effort="low", cwd=cwd, limits=Limits(timeout_s=180), persist_session=True)
        first = backend.run(launch)
        fresh, events[:] = list(events), []
        backend.run(Launch(**{**launch.__dict__, "prompt": RESUME_PROMPT, "resume": first.session_id}))
        resumed = list(events)
    finally:
        wire.EventReader.feed = feed  # type: ignore[method-assign]
    found = wire.find_rollout(backend.codex_home(launch), first.session_id)
    if found is None:
        raise SystemExit(f"no rollout file for thread {first.session_id}")
    rollout = [json.loads(line) for line in found.read_text(encoding="utf-8").splitlines() if line.strip()]
    found.unlink()
    return {"json": fresh, "resume": resumed, "rollout": rollout}


#: Keys whose values name the account or a request: replaced.
PRIVATE = frozenset({"creator_user_id", "creator_account_id", "response_id"})


def slim(value, cwd: str):
    """Long strings cut at 160 characters, the working directory and home replaced, the
    account's and the requests' ids (`PRIVATE`) removed."""
    if isinstance(value, dict):
        return {k: "x" if k in PRIVATE else slim(v, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [slim(v, cwd) for v in value]
    if isinstance(value, str):
        value = value.replace(cwd, "/work").replace(str(Path.home()), "/home/user")
        return value if len(value) <= 160 else value[:160] + "…"
    return value


def main() -> int:
    said = subprocess.run(["codex", "--version"], capture_output=True, text=True, encoding="utf-8").stdout
    version = said.strip().rsplit(" ", 1)[-1]
    target = Path(__file__).parent / version
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(Path(tmp).resolve())
        for name, lines in record(Path(cwd)).items():
            (target / f"{name}.jsonl").write_text(
                "".join(json.dumps(slim(e, cwd), ensure_ascii=False) + "\n" for e in lines), encoding="utf-8", newline="\n"
            )
    print(f"recorded codex {version} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
