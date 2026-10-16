"""A fake coding agent: a Python script on PATH, under the agent's name.

It is started as the real CLI is, by its name, so it is a script with a `#!` line and
its executable bit: POSIX starts it, Windows does not (a program there is a `.exe`, or a
batch file that npm made), so a test that needs one is skipped there."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest


def write_fake_cli(bindir: Path, name: str, body: str) -> Path:
    """`bindir/name`, a Python script that runs `body`; the test is skipped on Windows."""
    if sys.platform == "win32":
        pytest.skip("a fake coding agent is a #! script, which Windows does not start")
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / name
    script.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8", newline="\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script
