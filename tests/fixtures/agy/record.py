"""Record three launches of the installed agy into `tests/fixtures/agy/<version>/`.

    uv run python tests/fixtures/agy/record.py [model]    # spends a little of the login's quota

The same prompts every time, on the user's own Google login (`ambient`): one launch reads a
file, runs `echo hi` and replies "done" (`json.jsonl`, its `agy -p --output-format
stream-json` events), then one resumes its conversation with one more prompt
(`resume.jsonl`), and one is asked for a command its task denies (`denied.jsonl`). Long
strings are cut and local paths replaced, so a recording holds the shapes, not the content.
`tests/test_agy_wire.py` reads every recording.

`model` is one `agy models` lists for the login (default `MODEL`); the plan's quota is by
group of models, so a recording is made on a model whose group has some left.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from contraagent._internal.backends.agy import wire
from contraagent.backends import AgyBackend, Launch
from contraagent.config import Limits

PROMPT = (
    "Do these two steps, one tool call each: 1) read the file note.txt; 2) run the shell command `echo hi`. "
    "Then reply with the single word done."
)
RESUME_PROMPT = "Now reply with the single word again, nothing else."
DENIED_PROMPT = "Run the shell command `ls` with a tool. Then reply with the single word done."
MODEL = "gemini-3.8-flash-low"


def record(cwd: Path, model: str) -> dict[str, list[dict]]:
    """The events of the three launches, as agy printed them."""
    (cwd / "note.txt").write_text("The retry queue holds failed jobs.\n", encoding="utf-8", newline="\n")
    backend = AgyBackend()
    events: list[dict] = []
    feed = wire.StreamReader.feed

    def keep(self, ev):
        events.append(ev)
        return feed(self, ev)

    wire.StreamReader.feed = keep  # type: ignore[method-assign]
    try:
        launch = Launch(prompt=PROMPT, label="rec", model=model, cwd=cwd, limits=Limits(timeout_s=180), persist_session=True)
        first = backend.run(launch)
        fresh, events[:] = list(events), []
        backend.run(Launch(**{**launch.__dict__, "prompt": RESUME_PROMPT, "resume": first.session_id}))
        resumed, events[:] = list(events), []
        limits = Limits(timeout_s=180, disallowed_tools=("Bash(ls:*)",))
        backend.run(Launch(prompt=DENIED_PROMPT, label="rec-denied", model=model, cwd=cwd, limits=limits))
        denied = list(events)
    finally:
        wire.StreamReader.feed = feed  # type: ignore[method-assign]
        backend.discard_session(Launch(prompt="", label="rec"), first.session_id)
    if first.stop.value != "completed":
        raise SystemExit(f"the first launch ended {first.stop.value}: {first.stderr_tail.strip()}")
    return {"json": fresh, "resume": resumed, "denied": denied}


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
    model = sys.argv[1] if len(sys.argv) > 1 else MODEL
    version = subprocess.run(["agy", "--version"], capture_output=True, text=True, encoding="utf-8").stdout.strip().split()[-1]
    target = Path(__file__).parent / version
    with tempfile.TemporaryDirectory() as tmp:
        cwd = str(Path(tmp).resolve())
        recorded = record(Path(cwd), model)
        target.mkdir(exist_ok=True)
        for name, lines in recorded.items():
            (target / f"{name}.jsonl").write_text(
                "".join(json.dumps(slim(e, cwd), ensure_ascii=False) + "\n" for e in lines), encoding="utf-8", newline="\n"
            )
    print(f"recorded agy {version} on {model} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
