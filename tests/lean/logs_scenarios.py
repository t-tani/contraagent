"""Scenarios of a run's log, played on `append_lines` and the readers of `runs/files.py`
and on the Lean specification.

    uv run python tests/lean/logs_scenarios.py     # rewrites tests/lean/logs_scenarios.jsonl

A scenario is a list of appends to one log, each with its rows and, when its write is cut,
how many of its bytes reach the file, and how a reader then finds the log: as it is, gone,
or a file it cannot read; `lean/Conformance/Files.lean` has the fields. `play` plays one on
a file, where a cut write fails as on a full disk, and returns the complete lines of the log
and the line with no end, and what `read_log` gives of the log as found
(`lake exe contraagent-lean logs`).
`tests/lean/logs_scenarios.jsonl` holds scenarios (`scenarios`) with what the specification
answers for each; `tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

from contraagent._internal.runs.files import append_lines, last_line, read_lines, read_log

FILE = Path(__file__).with_name("logs_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "logs"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261124, 200

#: The rows a scenario appends: journal rows, a line that is no row, and an empty line.
ROWS = ('{"key":"a","ok":true}', '{"key":"b"}', "x", "")


def cut(path: Path, rows: list[str], written: int) -> None:
    """`append_lines(path, rows)` whose write takes `written` bytes and then fails, as on a
    full disk; a write of no more bytes than that is whole."""
    real = os.write

    def write(fd: int, data: Any) -> int:
        if written >= len(data):
            return real(fd, data)
        if written:
            real(fd, bytes(data)[:written])
        raise OSError(errno.ENOSPC, "No space left on device")

    os.write = write
    try:
        append_lines(path, rows)
    except OSError:
        pass
    finally:
        os.write = real


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play the scenario's appends on a file: its complete lines, and the line with no end."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "log.jsonl"
        path.touch()
        for step in scenario["steps"]:
            if step["written"] is None:
                append_lines(path, step["rows"])
            else:
                cut(path, step["rows"], step["written"])
        lines, count = read_lines(path)
        assert count == len(lines) and last_line(path) == (lines[-1] if lines else None)
        raw = path.read_bytes()
        if scenario["found"] != "present":
            path.unlink()
        if scenario["found"] == "unreadable":
            path.mkdir()  # a folder in its place: opening it fails, on every OS
        try:
            log = read_log(path)
        except OSError:
            read = None
        else:
            rows = [json.dumps(row, separators=(",", ":")) for row in log.rows]
            read = {"rows": rows, "unread": log.unread, "cutShort": log.cut_short}
        return {"lines": lines, "tail": raw[raw.rfind(b"\n") + 1 :].decode(), "read": read}


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: a few appends of a few rows each, some of them cut after any of
    their bytes: inside a row, just before a newline, or before the first byte."""
    steps = []
    for _ in range(rng.randint(1, 7)):
        rows = [rng.choice(ROWS) for _ in range(rng.randint(0, 3))]
        size = sum(len(row) + 1 for row in rows) + 1
        steps.append({"rows": rows, "written": rng.randint(0, size) if rng.random() < 0.45 else None})
    return {"steps": steps, "found": rng.choices(["present", "absent", "unreadable"], [8, 1, 1])[0]}


def scenarios(seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [scenario(rng) for _ in range(count)]


def _exe() -> Any:
    spec = importlib.util.spec_from_file_location("lean_exe", Path(__file__).with_name("exe.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    _exe().rewrite(FILE, WHAT, scenarios(SEED, COUNT))
