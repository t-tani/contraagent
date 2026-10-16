"""The agent processes this interpreter started, and how to stop them.

Every backend already launches its CLI in a group of its own (`groups`: a
session on POSIX, a process group and a Job Object on Windows) and already has a
`_terminate` that stops the group — so a run that ends on its own terms leaves
nothing behind. The gap
is the run that does not: an in-flight agent is sitting in `proc.wait()` on
a worker thread when the driver is terminated, no `finally` runs, and the
child is reparented to init and keeps running. Two orphaned agents per
interrupted run is how a machine accumulates them.

So the spawn sites publish the handle here, and the teardown stops whatever
is still live. The registry is deliberately process-local and unowned by any
one backend: an agent is a `claude` or an `omp` depending on routing, and
the teardown should not have to know which was in flight to clean up.

The kill is by process group, not by pid. The CLI spawns its own children —
hooks, the model client — and killing the leader alone leaves those running
with the port they inherited.

A teardown needs this interpreter to run it. One killed outright (SIGKILL, the
OOM killer) runs nothing. On Windows the OS ends the agents then, as it closes the
interpreter's handle of each agent's job (`groups`). On POSIX a **watchdog** outlives it: one small process per
interpreter, in a session of its own, started with the first agent. It holds
one end of a socket pair and is told each agent group as it starts and ends;
when this interpreter is gone, however it went, the kernel closes the other
end, and the watchdog stops the groups still listed and exits. One per
interpreter rather than one per launch, and no `PR_SET_PDEATHSIG`: that fires
when the *thread* that forked exits (launches fork from worker threads), and it
would need a `preexec_fn`, which is unsafe in a process with threads. The
agent itself is started as before, so its pid and exit status are its own.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time

from contraagent._internal.platform.groups import groups

#: Reentrant because `stop_all` runs from a signal handler, which can land on
#: the main thread while that same thread is inside `register`/`unregister`.
_lock = threading.RLock()
_live: list[subprocess.Popen] = []
#: Bumped each time a teardown starts. A launch notes it before spawning
#: (`epoch()`) and hands it back to `register`: a different value means a
#: teardown began while the child was being started, so the sweep may already
#: have passed it by and the child is stopped on the way in.
_epoch = 0
#: How many teardowns are in flight. While any is, every registration is a
#: latecomer, whether or not its launch noted an epoch.
_stopping = 0

#: How long a group gets to exit once asked (SIGTERM, CTRL_BREAK) before it is killed. Long enough
#: for the CLI to write its own farewell and release its ports, short enough
#: that a teardown does not feel like a hang.
_TERM_GRACE_S = 5.0


#: The watchdog: lines `+<pgid>` and `-<pgid>` on its stdin, a socket; at its end of
#: file (this interpreter is gone) it stops the groups still listed, as `_kill_group` does.
_WATCHDOG = r"""
import os, signal, time
groups, buf = set(), b""
while True:
    try:
        data = os.read(0, 4096)
    except InterruptedError:
        continue
    except OSError:
        data = b""
    if not data:
        break
    buf += data
    *lines, buf = buf.split(b"\n")
    for line in lines:
        if line[:1] == b"+":
            groups.add(int(line[1:]))
        elif line[:1] == b"-":
            groups.discard(int(line[1:]))
def alive(g):
    try:
        os.killpg(g, 0)
        return True
    except OSError:
        return False
for g in list(groups):
    try:
        os.killpg(g, signal.SIGTERM)
    except OSError:
        groups.discard(g)
end = time.monotonic() + 5.0
while groups and time.monotonic() < end:
    time.sleep(0.1)
    groups = {g for g in groups if alive(g)}
for g in groups:
    try:
        os.killpg(g, signal.SIGKILL)
    except OSError:
        pass
"""

_watchdog: subprocess.Popen | None = None
_watch: socket.socket | None = None
#: The pid that started the watchdog: a forked child of this interpreter starts its own.
_watch_pid = 0


def _tell_watchdog(line: str) -> None:
    """Tell the watchdog an agent group started (`+pgid`) or ended (`-pgid`), starting it
    first when there is none; none where the OS ends the groups itself. Never raises: an
    agent runs whether or not it is watched."""
    global _watchdog, _watch, _watch_pid
    if groups.dies_with_interpreter:
        return
    with _lock:
        try:
            if _watch is None or _watch_pid != os.getpid() or (_watchdog is not None and _watchdog.poll() is not None):
                if line.startswith("-"):
                    return  # nothing to forget in a watchdog that does not know it
                ours, theirs = socket.socketpair()
                if sys.platform == "darwin":  # no MSG_NOSIGNAL there: the socket's own option
                    ours.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_NOSIGPIPE", 0x1022), 1)
                _watchdog = subprocess.Popen(
                    [sys.executable, "-I", "-c", _WATCHDOG],
                    stdin=theirs.fileno(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,  # POSIX only: Windows needs no watchdog
                )
                theirs.close()
                _watch, _watch_pid = ours, os.getpid()
            # MSG_NOSIGNAL: a watchdog that is gone is an error here, never a SIGPIPE
            # (the command line restores SIGPIPE's default, which would end the run).
            _watch.sendall(f"{line}\n".encode(), getattr(socket, "MSG_NOSIGNAL", 0))
        except OSError:
            pass


def epoch() -> int:
    """The current teardown epoch; pass it to `register` as `since`."""
    with _lock:
        return _epoch


def register(proc: subprocess.Popen, since: int | None = None) -> subprocess.Popen:
    """Publish a spawned agent so the teardown can reach it.

    A process registered while a teardown is running, or whose launch began
    (`since`, from `epoch()`) before a teardown that has since started, is
    killed on the spot. Without this, a worker thread that starts a task while
    the teardown is in flight orphans it: the sweep is over, the child is
    live, and the run it belonged to is gone. It is a race between a thread
    pool and a signal, and the only way to win it is to refuse the latecomer.

    The refusal is scoped to that teardown, not to the interpreter: a launch
    that begins after it has finished registers normally, so a second run in
    the same process (a notebook, a service, a test session) can still start
    agents.
    """
    groups.adopt(proc)
    with _lock:
        late = _stopping > 0 or (since is not None and since != _epoch)
        if not late:
            _live.append(proc)
    if late:
        _kill_group(proc)
        groups.release(proc)
    else:
        _tell_watchdog(f"+{proc.pid}")
    return proc


def _kill_group(proc: subprocess.Popen) -> None:
    """Ask a process group to stop, then kill whatever is left of it."""
    if not groups.terminate(proc):
        return
    try:
        proc.wait(timeout=_TERM_GRACE_S)
        return
    except (subprocess.TimeoutExpired, OSError):
        pass
    groups.kill(proc)
    try:
        proc.wait(timeout=5.0)
    except (subprocess.TimeoutExpired, OSError):
        pass


def unregister(proc: subprocess.Popen) -> None:
    """Forget a process that has exited on its own, or was stopped."""
    with _lock:
        try:
            _live.remove(proc)
        except ValueError:
            return
    groups.release(proc)
    _tell_watchdog(f"-{proc.pid}")


def live_count() -> int:
    with _lock:
        return len([p for p in _live if p.poll() is None])


def stop_all(timeout: float = _TERM_GRACE_S) -> int:
    """Stop every live agent group. Returns how many were signalled.

    Idempotent and safe to call from a signal handler: nothing here raises,
    because a teardown that failed while handling a termination would leave
    the process running, which is the situation this exists to prevent.
    """
    global _epoch, _stopping
    with _lock:
        _epoch += 1
        _stopping += 1
        procs = list(_live)
    try:
        return _stop(procs, timeout)
    finally:
        with _lock:
            _stopping -= 1


def _stop(procs: list[subprocess.Popen], timeout: float) -> int:
    stopped = 0
    deadline = time.monotonic() + timeout
    for proc in procs:
        if proc.poll() is not None:
            unregister(proc)
            continue
        if groups.terminate(proc):
            stopped += 1
        else:
            unregister(proc)
    for proc in procs:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except (subprocess.TimeoutExpired, OSError):
            groups.kill(proc)
        finally:
            unregister(proc)
    return stopped
