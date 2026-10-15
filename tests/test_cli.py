"""The command line as one tree: every command answers `--help`, and a command's module is
imported only when the command line names it."""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from contraagent._internal.cli import main, parser


def _commands(ap: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    found = [path]
    for action in ap._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found += _commands(sub, (*path, name))
    return found


COMMANDS = _commands(parser())


def test_the_tree_holds_every_command():
    assert {c for c in COMMANDS if len(c) <= 2} >= {
        (),
        ("monitor",),
        ("monitor", "export"),
        ("relay",),
        ("hub",),
        ("hub", "prune"),
        ("plugin", "new"),
        ("plugin", "lint"),
        ("plugin", "render"),
        ("call", "validate"),
        ("check",),
        ("run",),
        ("docs",),
    }


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: " ".join(c) or "contraagent")
def test_every_command_answers_help(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*command, "--help"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith(f"usage: {' '.join(('contraagent', *command))}")


def test_a_command_s_module_is_imported_only_when_it_is_named():
    code = (
        "import sys; from contraagent._internal.cli import parser; parser('docs'); "
        "print(sorted(m for m in sys.modules if m.startswith(('contraagent._internal.monitor', 'contraagent._internal.hub', 'fastapi'))))"
    )
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "[]"


def test_a_usage_error_exits_2_with_the_command_s_usage(capsys, monkeypatch):
    monkeypatch.delenv("CONTRAAGENT_HUB_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["relay", "--hub", "http://hub:8790", "--interval", "0"])
    assert exc.value.code == 2
    assert "usage: contraagent relay" in capsys.readouterr().err


def _help_snapshot():
    spec = importlib.util.spec_from_file_location("cli_help", Path(__file__).parent / "cli" / "help.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_command_s_help_matches_the_snapshot():
    snapshot = _help_snapshot()
    committed = snapshot.SNAPSHOT.read_text()
    written_with = committed.splitlines()[0]
    if written_with != snapshot.header().rstrip("\n"):
        pytest.skip(f"argparse's output depends on the Python version; the snapshot is {written_with}")
    assert snapshot.render() == committed, "stale: run `uv run python tests/cli/help.py`"
