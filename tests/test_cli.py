"""The command line as one tree: every command answers `--help`, and a command's module is
imported only when the command line names it."""

import argparse
import importlib.util
import signal
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


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGPIPE")
def test_a_command_puts_back_the_sigpipe_handler_it_found(capsys):
    """A short command ends quietly on a closed pipe while it runs; the program that called
    `main` keeps its own handler after (a test process killed later by a closed pipe)."""
    before = signal.getsignal(signal.SIGPIPE)
    assert main(["docs"]) == 0
    assert signal.getsignal(signal.SIGPIPE) == before


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGPIPE")
def test_a_run_keeps_python_s_sigpipe_handling_for_its_agents_pipes(tmp_path, capsys, monkeypatch):
    """A write to an agent that has exited raises BrokenPipeError, which the launch handles:
    with SIGPIPE's default it would end the run, with no teardown."""
    (tmp_path / "steps.py").write_text(
        "import signal\nfrom contraagent import python_task\n"
        "@python_task\ndef handler() -> bool:\n    return signal.getsignal(signal.SIGPIPE) == signal.SIG_IGN\n"
        "async def flow():\n    assert await handler()\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    try:
        assert main(["run", "steps.py:flow"]) == 0, capsys.readouterr().out
    finally:
        sys.modules.pop("steps", None)


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


def test_a_taken_port_ends_the_monitor_before_it_announces_an_address(tmp_path, capsys, caplog):
    import socket

    from contraagent._internal.commandline import address, bind

    caplog.set_level("INFO")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert main(["monitor", "--runs-dir", str(tmp_path), "--port", str(port)]) == 2
    err = capsys.readouterr().err
    assert err == f"contraagent monitor: port {port} on 127.0.0.1 is already in use (--port)\n"
    assert " on http://" not in caplog.text
    with bind("127.0.0.1", 0) as sock:  # the address announced is the one bound
        assert address(sock) == f"http://127.0.0.1:{sock.getsockname()[1]}"


def test_the_stream_format_help_lists_every_registered_format():
    from contraagent._internal.backends import known_agents

    [commands] = [a for a in parser("monitor")._actions if isinstance(a, argparse._SubParsersAction)]
    [option] = [a for a in commands.choices["monitor"]._actions if a.dest == "stream_format"]
    assert f"built-in format ({', '.join(known_agents())})" in (option.help or "")
