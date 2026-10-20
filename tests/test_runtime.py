"""Offline tests of the process runtime: the subprocess loop, the live-agent
registry, signal handling and the run's teardown. Real child processes, sub-second
limits."""

import contextlib
import dataclasses
import inspect
import logging
import os
import signal
import stat
import subprocess
import sys
import textwrap
import threading
import time

import psutil
import pytest

from contraagent import Task
from contraagent._internal.backends import live_processes
from contraagent._internal.backends.credentials import SecretField
from contraagent._internal.backends.launch import STDIN_THRESHOLD
from contraagent._internal.backends.process import LaunchError, run_process
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.execution import teardown
from contraagent._internal.execution.python_tasks import PythonTaskRunner
from contraagent._internal.execution.services import ServiceFailed, Services
from contraagent._internal.platform import processes
from contraagent._internal.platform.groups import groups
from contraagent.backends import Launch, Stop
from contraagent.config import Limits
from contraagent.engine import Run


def _launch(tmp_path, *, timeout=5.0, stall=None, prompt="", stream=True, **kw) -> Launch:
    return Launch(
        prompt=prompt,
        cwd=tmp_path,
        limits=Limits(timeout_s=timeout, stall_s=stall),
        stream_path=tmp_path / "s.jsonl" if stream else None,
        **kw,
    )


def _py(code: str) -> list[str]:
    """A Python child running `code`, whose print writes "\\n" on every OS (Windows' "\\r\\n"
    would be passed through as an agent's output is)."""
    return [sys.executable, "-c", "import sys; sys.stdout.reconfigure(newline='\\n')\n" + textwrap.dedent(code)]


_alive = processes.alive

#: A child that sleeps, in a group of its own as an agent is.
_SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]

posix = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")


# --- pydantic lower bound ------------------------------------------------


def test_secret_serializer_has_a_signature():
    """pydantic < 2.8 calls inspect.signature on a PlainSerializer's function and
    fails on a builtin (`str`) at import time."""
    serializer = next(m for m in SecretField.__metadata__ if type(m).__name__ == "PlainSerializer")
    inspect.signature(serializer.func)


# --- subprocess loop -----------------------------------------------------


def test_exit_and_stream_capture(tmp_path):
    lines = [f"line {i}" for i in range(2000)]
    out, err, code, killed = run_process(
        _py("import sys\nfor i in range(2000): print('line', i)\nprint('oops', file=sys.stderr)"), dict(os.environ), _launch(tmp_path)
    )
    assert killed is None and code == 0
    assert out.decode().splitlines() == lines
    assert err.strip() == "oops"
    stream = (tmp_path / "s.jsonl").read_bytes()
    assert stream.endswith(out) and stream.startswith(b'{"type": "launch"')
    assert live_processes.live_count() == 0


def test_timeout_kills_the_process_group(tmp_path):
    pidfile = tmp_path / "grandchild"
    code = f"""
        import subprocess, sys, time
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        open({str(pidfile)!r}, "w").write(str(p.pid))
        print("started", flush=True)
        time.sleep(30)
    """
    t0 = time.monotonic()
    # The timeout is longer than a Python start and a spawn under load; the kill still
    # comes well before the child's 30 s sleep ends.
    out, _, exit_code, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=2))
    assert killed is Stop.TIMEOUT
    assert time.monotonic() - t0 < 6
    assert out == b"started\n"
    if sys.platform != "win32":  # Windows has no signal to report: the job is ended
        assert exit_code == -signal.SIGTERM
    grandchild = int(pidfile.read_text())
    deadline = time.monotonic() + 10
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _alive(grandchild), "the child's own child outlived the group kill"


def test_stall_stops_a_silent_process(tmp_path):
    code = """
        import time
        print("hello", flush=True)
        time.sleep(30)
    """
    t0 = time.monotonic()
    # The stall limit counts from the launch: it is longer than a Python start under load.
    out, _, _, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=10, stall=1.5))
    assert killed is Stop.STALLED
    assert out == b"hello\n"
    assert time.monotonic() - t0 < 5


def test_sink_stop_ends_the_run(tmp_path):
    code = """
        import time
        print("a", flush=True)
        print("STOP", flush=True)
        time.sleep(30)
    """
    seen: list[bytes] = []

    def sink(line: bytes):
        seen.append(line)
        return Stop.RATE_LIMITED if line == b"STOP" else None

    t0 = time.monotonic()
    _, _, _, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=10), sink=sink)
    assert killed is Stop.RATE_LIMITED
    assert seen == [b"a", b"STOP"]
    assert time.monotonic() - t0 < 5


def test_sink_sees_lines_split_across_reads(tmp_path):
    big = "x" * 300_000  # longer than one 64KB read
    code = """
        import sys
        sys.stdout.write("x" * 300_000 + "\\nmid\\ntail")
    """
    seen: list[bytes] = []
    _, _, code_, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path), sink=lambda line: seen.append(line))
    assert killed is None and code_ == 0
    assert seen == [big.encode(), b"mid", b"tail"]


def test_eof_without_exit_is_still_bounded(tmp_path):
    """A child that closes its stdout and keeps running is held to the deadline."""
    code = """
        import os, sys, time
        print("bye", flush=True)
        os.close(1)
        time.sleep(30)
    """
    t0 = time.monotonic()
    out, _, _, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=2))
    assert out == b"bye\n" and killed is Stop.TIMEOUT
    assert time.monotonic() - t0 < 6


def test_long_prompt_goes_over_stdin(tmp_path):
    prompt = "p" * (STDIN_THRESHOLD * 4)
    code = """
        import sys
        data = sys.stdin.read()
        print(len(data), data[:1])
    """
    out, _, code_, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, prompt=prompt))
    assert killed is None and code_ == 0
    assert out.decode().split() == [str(len(prompt)), "p"]


# --- live-process registry -----------------------------------------------


def test_teardown_does_not_disable_later_runs():
    first = subprocess.Popen(_SLEEP, **groups.popen_options())
    live_processes.register(first)
    assert live_processes.stop_all(timeout=2) == 1
    assert first.poll() is not None

    second = subprocess.Popen(_SLEEP, **groups.popen_options())
    try:
        live_processes.register(second, since=live_processes.epoch())
        time.sleep(0.1)
        assert second.poll() is None, "an agent launched after a finished teardown was killed"
        assert live_processes.live_count() == 1
    finally:
        live_processes.stop_all(timeout=2)


def test_launch_racing_a_teardown_is_stopped():
    since = live_processes.epoch()  # the worker notes the epoch, then spawns
    live_processes.stop_all(timeout=1)  # ... while a teardown runs
    late = subprocess.Popen(_SLEEP, **groups.popen_options())
    live_processes.register(late, since=since)
    assert late.poll() is not None
    assert live_processes.live_count() == 0


def test_register_during_teardown_is_stopped(monkeypatch):
    """A registration landing while stop_all is still sweeping is refused."""
    from contraagent._internal.backends import live_processes as lp

    racer: list[subprocess.Popen] = []
    real_stop = lp._stop

    def stop_and_race(procs, timeout):
        p = subprocess.Popen(_SLEEP, **groups.popen_options())
        lp.register(p)
        racer.append(p)
        return real_stop(procs, timeout)

    monkeypatch.setattr(lp, "_stop", stop_and_race)
    lp.stop_all(timeout=1)
    assert racer[0].poll() is not None


# --- signal handling -----------------------------------------------------


@pytest.fixture
def restore_signals():
    saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    yield
    for s, h in saved.items():
        signal.signal(s, h)


def test_sigint_handler_restores_the_previous_one(restore_signals):
    signal.signal(signal.SIGINT, signal.default_int_handler)
    calls: list[str] = []
    restore = teardown.install_signal_handlers(lambda: calls.append("teardown"))
    handler = signal.getsignal(signal.SIGINT)
    assert handler is not signal.default_int_handler
    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGINT, None)
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    teardown.settle()  # the teardown runs on a thread of its own
    assert calls == ["teardown"]
    restore()


def test_host_handler_is_restored_and_called(restore_signals):
    host_calls: list[int] = []
    host = lambda signum, frame: host_calls.append(signum)
    signal.signal(signal.SIGTERM, host)
    calls: list[str] = []
    restore = teardown.install_signal_handlers(lambda: calls.append("teardown"))
    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    assert host_calls == [signal.SIGTERM]
    assert signal.getsignal(signal.SIGTERM) is host
    restore()  # waits for the teardown the signal started
    assert calls == ["teardown"]


def _refused_everywhere(tmp_path) -> None:
    """An agent's launch, a process registered late, a Python task and a service start are
    each refused."""
    with pytest.raises(LaunchError, match="stopping on a signal"):
        run_process(_py("print(1)"), dict(os.environ), _launch(tmp_path))
    late = subprocess.Popen(_SLEEP, **groups.popen_options())  # spawned before the refusal, registered after
    assert live_processes.register(late) is False
    assert late.poll() is not None and live_processes.live_count() == 0
    result = PythonTaskRunner().run(make_python_task("look", lambda: 1))
    assert not result.ok and result.stop == "launch_failed" and "stopping on a signal" in result.reason
    services = Services({"index": lambda name: contextlib.nullcontext("http://index")}, tmp_path)
    with pytest.raises(ServiceFailed, match="the run is ending"):
        with services.held(dataclasses.replace(make_python_task("look", lambda: 1), claims=["index"])):
            pass


@pytest.mark.parametrize("signum", ["SIGTERM", "SIGINT"])
def test_no_launch_starts_after_a_signal_teardown_has_ended(tmp_path, monkeypatch, restore_signals, signum):
    """From the signal's handler on, before the teardown and after it alike: for good when the
    signal ends the process (SIGTERM), until the run's handlers are put back otherwise."""
    if threading.current_thread() is not threading.main_thread():  # pragma: no cover
        pytest.skip("signal handlers live on the main thread")
    monkeypatch.setattr(live_processes, "_refused", False)  # put back after the test, as is `_ending`
    monkeypatch.setattr(teardown, "_ending", False)
    ended: list[int] = []
    kill = os.kill
    monkeypatch.setattr(os, "kill", lambda pid, sig: ended.append(sig) if pid == os.getpid() else kill(pid, sig))
    sig = getattr(signal, signum)
    signal.signal(sig, signal.SIG_DFL if sig == signal.SIGTERM else signal.default_int_handler)
    restore = teardown.install_signal_handlers(lambda: None)
    with contextlib.suppress(KeyboardInterrupt):
        signal.getsignal(sig)(sig, None)
    teardown.settle()  # the teardown has ended (and SIGTERM's default action was asked for)
    assert ended == ([sig] if sig == signal.SIGTERM else [])
    _refused_everywhere(tmp_path)
    restore()
    if sig == signal.SIGTERM:
        _refused_everywhere(tmp_path)  # the process is ending: no run of it launches again
    else:
        out, _, code, _ = run_process(_py("print(1)"), dict(os.environ), _launch(tmp_path))
        assert code == 0 and out.strip() == b"1"  # Ctrl-C caught: a later run launches


def test_restore_with_no_signal_ends_the_teardown_thread(restore_signals):
    before = {t for t in threading.enumerate() if t.name == "contraagent-teardown"}
    calls: list[str] = []
    restore = teardown.install_signal_handlers(lambda: calls.append("teardown"))
    (thread,) = {t for t in threading.enumerate() if t.name == "contraagent-teardown"} - before
    restore()
    thread.join(timeout=30)
    assert not thread.is_alive() and calls == []


#: SIGTERM delivered while the main thread holds the lock of `append_lines`, as it does while
#: it writes a journal row, with a teardown that writes a line too. A teardown run inside
#: the handler would wait there for the lock its own thread holds, for ever.
_HOLDING = """
import signal
import sys
import threading
from pathlib import Path

from contraagent._internal.backends.base import exit_dir
from contraagent._internal.runs import files
from contraagent.engine import Run

runs = Path(sys.argv[1])
run = Run("r", runs)
run.stop_on_signals()
run.on_teardown(lambda: files.append_lines(runs / "teardown.log", ["torn down"]))
print(exit_dir("secret-"), flush=True)
with files._append_lock:
    signal.raise_signal(signal.SIGTERM)  # its handler runs here, on this thread, before this returns
    print("handled", flush=True)
threading.Event().wait()  # the teardown ends the process
"""


@posix
def test_sigterm_while_the_main_thread_holds_the_append_lock_still_ends_the_process(tmp_path):
    script = tmp_path / "holding.py"
    script.write_text(_HOLDING)
    (tmp_path / "tmp").mkdir()
    proc = subprocess.Popen(
        [sys.executable, str(script), str(tmp_path / "runs")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "TMPDIR": str(tmp_path / "tmp")},
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        pytest.fail("the process never ended: its teardown waited for a lock its own thread held")
    secret, handled = out.splitlines()
    assert handled == "handled" and proc.returncode == -signal.SIGTERM, err
    assert (tmp_path / "runs" / "teardown.log").read_text() == "torn down\n"
    assert not os.path.exists(secret)


# --- run -----------------------------------------------------------------


#: A pipeline whose coding agent sleeps, launched by `run_process` as any agent is, with a
#: token on its command line to find it by.
_DRIVER = """
import os
import sys
from contraagent import Pipeline, agent_task
from contraagent.backends import Backend
from contraagent.backends import LaunchResult, Stop
from contraagent.backends import EventFold

token, runs = sys.argv[1], sys.argv[2]


class Done(EventFold):
    def result(self, launch, agent, *, exit_code, killed):
        return LaunchResult(label=launch.label, agent=agent, stop=Stop.COMPLETED, ok=True)


class Sleeper(Backend):
    name = "sleeper"
    binary = sys.executable

    def argv(self, launch):
        self.scratch(launch.label, "config")  # the backend's scratch root
        return [sys.executable, "-c", "import time; time.sleep(300)", token]

    def env(self, launch):
        return dict(os.environ)

    def fold(self, launch):
        return Done()


work = agent_task("work", instructions="x", max_turns=1, timeout_s=600, agent="sleeper")
# A server's arguments may hold a secret: they are written to an owner-only temporary directory.
servers = lambda task, params, own: {"index": {"command": "index", "args": ["--token", "secret"]}}
Pipeline(backends={"sleeper": Sleeper()}, runs_dir=runs, mcp_servers=servers).run(lambda: work("a"), run_id="sleep")
"""


def _with_token(*parts: str) -> list[int]:
    """The pids whose command line holds each of `parts`."""
    return [p.pid for p in processes.scan().values() if all(part in p.cmd for part in parts)]


@pytest.mark.parametrize("how", [pytest.param("SIGTERM", marks=posix), pytest.param("SIGINT", marks=posix), "kill"])
def test_an_agent_ends_with_the_pipeline_that_launched_it(tmp_path, how):
    """SIGTERM and Ctrl-C reach the run's teardown; a kill (SIGKILL; TerminateProcess on
    Windows), which runs nothing, leaves the watchdog (the job on Windows) to stop the
    agent. Either way no agent outlives its pipeline. SIGTERM and Ctrl-C also remove the
    temporary directories the run made: its MCP servers' and the backend's scratch root."""
    token = f"contraagent-test-{os.getpid()}-{how}-{time.monotonic_ns()}"
    script = tmp_path / "driver.py"
    script.write_text(_DRIVER)
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    made = lambda: sorted(p.name for root in tmp.iterdir() for p in root.iterdir())
    driver = subprocess.Popen(
        [sys.executable, str(script), token, str(tmp_path / "runs")], stderr=subprocess.PIPE, env={**os.environ, "TMPDIR": str(tmp)}
    )
    try:
        # The agent's processes: one, or on Windows a venv's python.exe and the interpreter it
        # starts, which carries the same command line (as the driver's own interpreter does).
        agents = lambda: [pid for pid in _with_token(token, "sleep(300)") if pid != driver.pid]
        deadline = time.monotonic() + 30
        while not agents() and time.monotonic() < deadline:
            time.sleep(0.1)
        found = agents()
        assert found, "the agent never started"
        assert [name.split("-")[0] for name in made()] == ["mcp", "sleeper"], made()
        if how == "kill":
            driver.kill()
        else:
            os.kill(driver.pid, getattr(signal, how))
        driver.wait(timeout=20)
        deadline = time.monotonic() + 15
        while any(map(_alive, found)) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not any(map(_alive, found)), f"the agent outlived its pipeline ({how})"
        if how != "kill":
            assert made() == [], f"temporary directories outlived the pipeline ({how})"
    finally:
        driver.kill()
        driver.wait()
        if driver.stderr is not None:
            driver.stderr.close()
        for pid in _with_token(token):
            with contextlib.suppress(psutil.Error):
                psutil.Process(pid).kill()


@posix
def test_run_lock_is_not_world_writable(tmp_path):
    run = Run("r", tmp_path)
    try:
        mode = stat.S_IMODE((tmp_path / "r.lock").stat().st_mode)
        assert not mode & stat.S_IWOTH and not mode & stat.S_IWGRP
    finally:
        run.close()


def test_run_logs_through_logging_by_default(tmp_path, caplog, capsys):
    run = Run("r", tmp_path, lock=False)
    with caplog.at_level(logging.INFO, logger="contraagent._internal.execution.run"):
        run._on_event("duplicate_key_refused", None, key="k")
        run._on_event("note", None, follow_up_failed="boom")
        run._on_event("retry", Task(kind="read", key="t"))
    levels = {r.getMessage().split()[0]: r.levelno for r in caplog.records}
    assert levels == {"[refused]": logging.WARNING, "[error]": logging.WARNING, "[retry]": logging.INFO}
    assert [r.getMessage() for r in caplog.records][2] == "[retry] t: no progress; again"
    assert capsys.readouterr().out == ""


def test_teardown_runs_once_under_concurrent_calls(tmp_path):
    run = Run("r", tmp_path, lock=False)
    calls: list[int] = []
    run.on_teardown(lambda: (calls.append(1), time.sleep(0.05)))
    threads = [threading.Thread(target=run.teardown) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    run.teardown()
    assert calls == [1]


@pytest.mark.parametrize("ended", [False, True])
def test_a_launch_with_no_group_left_to_signal_is_still_waited_for(monkeypatch, ended):
    """On macOS `killpg` refuses a group whose processes have all ended: the child is
    still waited for (killed first if it runs), never left for the garbage collector."""
    from contraagent._internal.backends import process

    monkeypatch.setattr(process.groups, "terminate", lambda proc: False)
    child = subprocess.Popen([sys.executable, "-c", "pass" if ended else "import time; time.sleep(30)"])
    if ended:
        while psutil.Process(child.pid).status() != psutil.STATUS_ZOMBIE and sys.platform != "win32":
            time.sleep(0.01)
    t0 = time.monotonic()
    process._terminate(child)
    assert child.returncode is not None and time.monotonic() - t0 < 5
