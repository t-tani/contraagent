"""The command line as one tree: every command answers `--help`, and a command's module is
imported only when the command line names it."""

import argparse
import subprocess
import sys

import pytest

from contraagent.cli import main, parser


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
        "import sys; from contraagent.cli import parser; parser('docs'); "
        "print(sorted(m for m in sys.modules if m.startswith(('contraagent.monitor', 'contraagent.hub', 'fastapi'))))"
    )
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "[]"


def test_the_monitor_package_imports_without_its_server():
    code = "import sys, contraagent.monitor; print([m for m in ('fastapi', 'contraagent.monitor.server') if m in sys.modules])"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip() == "[]"


def test_python_m_contraagent_monitor_is_the_monitor_command():
    done = subprocess.run([sys.executable, "-m", "contraagent.monitor", "--help"], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.startswith("usage: contraagent monitor")


def test_a_usage_error_exits_2_with_the_command_s_usage(capsys, monkeypatch):
    monkeypatch.delenv("CONTRAAGENT_HUB_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["relay", "--hub", "http://hub:8790", "--interval", "0"])
    assert exc.value.code == 2
    assert "usage: contraagent relay" in capsys.readouterr().err
