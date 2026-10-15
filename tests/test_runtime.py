"""Offline tests of the process runtime: the subprocess loop, the live-agent
registry, signal handling and the run's teardown. Real child processes, sub-second
limits."""

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
from pathlib import Path

import pytest

from contraagent import Task
from contraagent._internal.backends import live_processes
from contraagent._internal.backends.credentials import SecretField
from contraagent._internal.backends.launch import STDIN_THRESHOLD
from contraagent._internal.backends.process import run_process
from contraagent._internal.execution import teardown
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
    return [sys.executable, "-c", textwrap.dedent(code)]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); it has exited all the same.
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0] != "Z"
    except OSError:
        return False


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
        import subprocess, time
        p = subprocess.Popen(["sleep", "30"])
        open({str(pidfile)!r}, "w").write(str(p.pid))
        print("started", flush=True)
        time.sleep(30)
    """
    t0 = time.monotonic()
    out, _, exit_code, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=0.8))
    assert killed is Stop.TIMEOUT
    assert time.monotonic() - t0 < 5
    assert out == b"started\n"
    assert exit_code == -signal.SIGTERM
    grandchild = int(pidfile.read_text())
    deadline = time.monotonic() + 2
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
    out, _, _, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=10, stall=0.3))
    assert killed is Stop.STALLED
    assert out == b"hello\n"
    assert time.monotonic() - t0 < 3


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
    out, _, _, killed = run_process(_py(code), dict(os.environ), _launch(tmp_path, timeout=0.8))
    assert out == b"bye\n" and killed is Stop.TIMEOUT
    assert time.monotonic() - t0 < 5


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
    first = subprocess.Popen(["sleep", "30"], start_new_session=True)
    live_processes.register(first)
    assert live_processes.stop_all(timeout=2) == 1
    assert first.poll() is not None

    second = subprocess.Popen(["sleep", "30"], start_new_session=True)
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
    late = subprocess.Popen(["sleep", "30"], start_new_session=True)
    live_processes.register(late, since=since)
    assert late.poll() is not None
    assert live_processes.live_count() == 0


def test_register_during_teardown_is_stopped(monkeypatch):
    """A registration landing while stop_all is still sweeping is refused."""
    from contraagent._internal.backends import live_processes as lp

    racer: list[subprocess.Popen] = []
    real_stop = lp._stop

    def stop_and_race(procs, timeout):
        p = subprocess.Popen(["sleep", "30"], start_new_session=True)
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
    teardown.install_signal_handlers(lambda: calls.append("teardown"))
    handler = signal.getsignal(signal.SIGINT)
    assert handler is not signal.default_int_handler
    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGINT, None)
    assert calls == ["teardown"]
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_host_handler_is_restored_and_called(restore_signals):
    host_calls: list[int] = []
    host = lambda signum, frame: host_calls.append(signum)
    signal.signal(signal.SIGTERM, host)
    calls: list[str] = []
    teardown.install_signal_handlers(lambda: calls.append("teardown"))
    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    assert calls == ["teardown"] and host_calls == [signal.SIGTERM]
    assert signal.getsignal(signal.SIGTERM) is host


# --- run -----------------------------------------------------------------


#: A pipeline whose coding agent sleeps, launched by `run_process` as any agent is, with a
#: token on its command line to find it by.
_DRIVER = """
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
        return [sys.executable, "-c", "import time; time.sleep(300)", token]

    def env(self, launch):
        return {"PATH": "/usr/bin:/bin"}

    def fold(self, launch):
        return Done()


work = agent_task("work", instructions="x", max_turns=1, timeout_s=600, agent="sleeper")
Pipeline(backends={"sleeper": Sleeper()}, runs_dir=runs).run(lambda: work("a"), run_id="sleep")
"""


def _with_token(token: str) -> list[int]:
    """The pids whose command line holds `token`."""
    out = []
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if token.encode() in (d / "cmdline").read_bytes():
                    out.append(int(d.name))
            except OSError:
                pass
    return out


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT, signal.SIGKILL])
def test_an_agent_ends_with_the_pipeline_that_launched_it(tmp_path, sig):
    """SIGTERM and Ctrl-C reach the run's teardown; SIGKILL, which runs nothing, leaves
    the watchdog to stop the agent. Either way no agent outlives its pipeline."""
    token = f"contraagent-test-{os.getpid()}-{sig.name}-{time.monotonic_ns()}"
    script = tmp_path / "driver.py"
    script.write_text(_DRIVER)
    driver = subprocess.Popen([sys.executable, str(script), token, str(tmp_path / "runs")], stderr=subprocess.PIPE)
    try:
        agents = lambda: [pid for pid in _with_token(token) if pid != driver.pid]
        deadline = time.monotonic() + 30
        while not agents() and time.monotonic() < deadline:
            time.sleep(0.1)
        [agent] = agents()
        os.kill(driver.pid, sig)
        driver.wait(timeout=20)
        deadline = time.monotonic() + 15
        while _alive(agent) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _alive(agent), f"the agent outlived its pipeline ({sig.name})"
    finally:
        driver.kill()
        driver.wait()
        if driver.stderr is not None:
            driver.stderr.close()
        for pid in _with_token(token):
            os.kill(pid, signal.SIGKILL)


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
