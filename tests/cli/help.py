"""Writes `help.txt` beside this file: every command's `--help`, at a fixed width.

    uv run python tests/cli/help.py

`tests/test_cli.py` fails while the file is stale. argparse's output differs between Python
versions, so the file names the version it was written with and the test compares on that
version only.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path

from contraagent._internal.cli import main, parser

SNAPSHOT = Path(__file__).parent / "help.txt"
COLUMNS = "100"


def commands(ap: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    found = [path]
    for action in ap._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found += commands(sub, (*path, name))
    return found


def header() -> str:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    return f"# Every command's --help (Python {version}, COLUMNS={COLUMNS}); `uv run python tests/cli/help.py` writes it.\n"


def render() -> str:
    saved = {key: os.environ.get(key) for key in ("COLUMNS", "LINES", "PYTHON_COLORS", "NO_COLOR")}
    os.environ.update(COLUMNS=COLUMNS, LINES="50", PYTHON_COLORS="0", NO_COLOR="1")
    try:
        out = [header()]
        for command in commands(parser()):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.suppress(SystemExit):
                main([*command, "--help"])
            out.append(f"\n$ {' '.join(('contraagent', *command, '--help'))}\n{buffer.getvalue()}")
        return "".join(out)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    SNAPSHOT.write_text(render())
