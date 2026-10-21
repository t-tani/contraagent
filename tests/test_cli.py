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


@pytest.mark.parametrize(("args", "says"), [(["--interval", "0"], "--interval"), (["--interval", "5", "--ttl", "5"], "--ttl")])
def test_a_usage_error_exits_2_with_the_command_s_usage(capsys, monkeypatch, args, says):
    monkeypatch.delenv("CONTRAAGENT_HUB_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["relay", "--hub", "http://hub:8790", *args])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "usage: contraagent relay" in err and f"{says} must be more than" in err


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
    committed = snapshot.SNAPSHOT.read_text(encoding="utf-8")
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


# --- loading `path/to/file.py:attr` -----------------------------------------------------------


def test_a_file_named_as_a_module_already_imported_is_refused(tmp_path):
    import queue  # noqa: F401 (a standard library module, imported)

    from contraagent._internal.commandline import load_attr

    (tmp_path / "queue.py").write_text("flow = 1\n", encoding="utf-8")
    with pytest.raises(ImportError, match="the module name 'queue' is already .*queue.py; rename queue.py"):
        load_attr(f"{tmp_path / 'queue.py'}:flow")
    assert sys.modules["queue"].__name__ == "queue" and hasattr(sys.modules["queue"], "Queue")


def test_files_of_one_name_load_in_turn_and_import_their_neighbours_when_they_run(tmp_path):
    from contraagent._internal.commandline import load_attr

    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "loadattr_steps.py").write_text(
            f"def flow():\n    import loadattr_helper_{name}\n    return loadattr_helper_{name}.WHO\n", encoding="utf-8"
        )
        (tmp_path / name / f"loadattr_helper_{name}.py").write_text(f"WHO = {name!r}\n", encoding="utf-8")
    try:
        assert load_attr(f"{tmp_path / 'a' / 'loadattr_steps.py'}:flow")() == "a"
        assert load_attr(f"{tmp_path / 'b' / 'loadattr_steps.py'}:flow")() == "b"  # anew, under the same name
    finally:
        for name in ("loadattr_steps", "loadattr_helper_a", "loadattr_helper_b"):
            sys.modules.pop(name, None)
        for name in ("a", "b"):
            if str(tmp_path / name) in sys.path:
                sys.path.remove(str(tmp_path / name))


EARLY_FLOWS = """\
import asyncio

from contraagent import agent_task

triage = agent_task("triage", instructions="t", output=str, max_turns=5, timeout_s=60)


async def keywords():
    await triage("u", text="hi")  # LINE


async def sleeping():
    await asyncio.sleep(1)  # LINE


def generator():
    yield triage("u")
"""


@pytest.fixture
def early_flows(tmp_path):
    """`early_flows.py`, whose flows raise before their first task."""
    path = tmp_path / "early_flows.py"
    path.write_text(EARLY_FLOWS, encoding="utf-8")
    yield path
    sys.modules.pop("early_flows", None)
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


@pytest.mark.parametrize(
    ("name", "line", "said"),
    [
        ("keywords", 9, "TypeError: triage(...): text=: this task declares no params model, so it takes no params"),
        ("sleeping", 13, "TypeError: a timer of 1s (asyncio.sleep, a timeout of asyncio.wait, call_later) needs a clock"),
        ("generator", None, "early_flows.generator is a generator flow; a flow that waits for outputs is"),
    ],
)
def test_run_reports_a_flow_that_raised_before_its_first_task_as_check_does(name, line, said, early_flows, capsys):
    """One line with the flow's place, when there is one, and the guidance; exit 1, no traceback."""
    if line is not None:
        assert EARLY_FLOWS.splitlines()[line - 1].endswith("# LINE")
    at = f"{early_flows}:{line}: " if line is not None else ""
    for command in (["check"], ["run", "--stub", "--runs-dir", str(early_flows.parent / "runs")]):
        assert main([command[0], f"{early_flows}:{name}", *command[1:]]) == 1
        out = capsys.readouterr().out
        [error] = [text for text in out.splitlines() if text.startswith("  error: ")]
        assert at in error and said in error and "Traceback" not in out, out
        assert out.rstrip().endswith("read: (contraagent docs tasks)")


def test_run_keeps_the_traceback_of_an_exception_that_did_not_pass_through_the_flow(early_flows, monkeypatch):
    """A bug of contraagent's own (here, a name it calls that is not callable) is raised."""
    monkeypatch.setattr("contraagent._internal.pipeline.pipeline.Run", None)
    with pytest.raises(TypeError, match="'NoneType' object is not callable"):
        main(["run", f"{early_flows}:keywords", "--stub", "--runs-dir", str(early_flows.parent / "runs")])


PENDING_FLOWS = """\
from pydantic import BaseModel

from contraagent import agent_task


class Found(BaseModel):
    text: str


class Review(BaseModel):
    found: Found
    more: list[Found] = []


find = agent_task("find", instructions="f", output=Found, max_turns=5, timeout_s=60)
review = agent_task("review", instructions="r", params=Review, output=str, max_turns=5, timeout_s=60)


async def flow():
    found = find("a")
    await review("a", Review(found=found, more=[found]))
"""


def test_a_pending_a_params_model_refused_is_explained_by_run_and_check(tmp_path, capsys):
    """pydantic refuses the `Pending` before contraagent sees it: run and check add, for each
    field, what a task call says of a `Pending` in its params. The exception stays pydantic's."""
    from pydantic import ValidationError

    from contraagent import Pipeline
    from contraagent._internal.commandline import load_attr
    from contraagent.testing import StubAgent

    path = tmp_path / "pending_flows.py"
    path.write_text(PENDING_FLOWS, encoding="utf-8")
    said = [
        f"Review{where} is the Pending of find-a, the future output of a task call; a task is given values. In an "
        f"async def flow, await the task call and pass its output ({field}=await ...); for an order with no output "
        "passed on, give the task call in .options(after=[...]) (contraagent docs tasks)"
        for where, field in ((".found", "found"), (".more[0]", "more"))
    ]
    try:
        for command in (["check"], ["run", "--stub", "--runs-dir", str(tmp_path / "runs")]):
            assert main([command[0], f"{path}:flow", *command[1:]]) == 1
            out = capsys.readouterr().out
            assert "ValidationError: 2 validation errors for Review" in out and all(text in out for text in said), out
        agent = StubAgent({"find": lambda launch: {"text": "t"}})
        pipeline = Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)
        [call] = pipeline.run(load_attr(f"{path}:flow"), run_id="python").flow_errors
        assert isinstance(call.error, ValidationError) and "Pending of" not in str(call.error)
    finally:
        sys.modules.pop("pending_flows", None)
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
