"""The watchdog that stops the agents of an interpreter killed outright: it signals a
process group only while the group's leader is the process that was registered."""

import os
import signal
import socket
import subprocess
import sys
import threading

import pytest

from contraagent._internal.backends import live_processes, watchdog
from contraagent._internal.platform import processes
from contraagent._internal.platform.groups import KILL_AFTER_S, groups

posix = pytest.mark.skipif(sys.platform == "win32", reason="the watchdog runs on POSIX only")

TERM, KILL = 15, 9


class Clock:
    """A clock that moves only when the watchdog pauses."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def pause(self, seconds: float) -> None:
        self.now += seconds


def _stop(groups: dict[int, int], starts: dict[int, int | None], *, live=(), pids=()):
    """Run `watchdog.stop` against fakes; the signals sent, as (pgid, signal)."""
    sent: list[tuple[int, int]] = []
    live = set(live)

    def send(pgid: int, signum: int) -> None:
        if signum == 0 and pgid not in live:
            raise ProcessLookupError(pgid)
        sent.append((pgid, signum))

    clock = Clock()
    watchdog.stop(
        groups,
        starts.get,
        send,
        TERM,
        KILL,
        kill_after_s=KILL_AFTER_S,
        exists=lambda pid: pid in pids or starts.get(pid) is not None,
        clock=clock,
        pause=clock.pause,
    )
    return [s for s in sent if s[1] != 0]


def test_a_group_whose_leader_has_another_start_is_not_signalled():
    assert _stop({100: 5}, {100: 7}) == []


def test_a_group_whose_leader_has_the_recorded_start_is_signalled():
    assert _stop({100: 5, 200: 6}, {100: 5, 200: 9}) == [(100, TERM)]


def test_a_group_whose_leader_is_gone_is_signalled():
    """The processes the agent started may outlive it; their group keeps its number."""
    assert _stop({100: 5}, {}) == [(100, TERM)]


def test_a_leader_whose_start_cannot_be_read_is_not_trusted():
    assert _stop({100: 5}, {}, pids={100}) == []


def test_a_group_left_after_the_grace_is_killed_only_while_it_is_still_the_agents():
    assert _stop({100: 5}, {100: 5}, live={100}) == [(100, TERM), (100, KILL)]
    starts: dict[int, int | None] = {100: 5}

    def send(pgid: int, signum: int) -> None:
        if signum == TERM:
            starts[100] = 8  # the agent ended and its pid went to another process
        sent.append((pgid, signum))

    sent: list[tuple[int, int]] = []
    clock = Clock()
    watchdog.stop(
        {100: 5}, starts.get, send, TERM, KILL, kill_after_s=KILL_AFTER_S, exists=lambda pid: True, clock=clock, pause=clock.pause
    )
    assert sent == [(100, TERM)]


def test_lines_name_each_group_with_its_start():
    read, write = os.pipe()
    os.write(write, b"+100 5\n+200 6\n-100\n+bad\n+300 7")
    os.close(write)
    try:
        assert watchdog.read_groups(read) == {200: 6}
    finally:
        os.close(read)


@posix
def test_register_tells_the_watchdog_the_start_of_the_group(monkeypatch):
    told: list[str] = []
    monkeypatch.setattr(live_processes, "_tell_watchdog", told.append)
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], **groups.popen_options())
    try:
        assert live_processes.register(proc)
        assert told == [f"+{proc.pid} {processes.start_ticks(proc.pid)}"]
    finally:
        live_processes.unregister(proc)
        proc.kill()
        proc.wait()


def _run_watchdog(line: str) -> None:
    """Start the watchdog, tell it `line`, and end this side of its socket, as an
    interpreter killed outright does; return once the watchdog has exited."""
    ours, theirs = socket.socketpair()
    proc = subprocess.Popen(
        [sys.executable, "-I", watchdog.__file__, processes.__file__, str(KILL_AFTER_S)], stdin=theirs.fileno(), start_new_session=True
    )
    theirs.close()
    ours.sendall(f"{line}\n".encode())
    ours.close()
    assert proc.wait(timeout=30) == 0


@posix
def test_the_watchdog_process_signals_only_the_group_it_was_told():
    agent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        start = processes.start_ticks(agent.pid)
        assert start is not None
        _run_watchdog(f"+{agent.pid} {start + 1}")
        assert agent.poll() is None, "a group with another start was signalled"
        # Reaped as it ends, as init reaps an agent whose interpreter is gone: a zombie
        # would keep the group signallable until the grace ends.
        reaper = threading.Thread(target=agent.wait)
        reaper.start()
        _run_watchdog(f"+{agent.pid} {start}")
        reaper.join(timeout=30)
        assert agent.returncode == -signal.SIGTERM
    finally:
        agent.kill()
        agent.wait()
