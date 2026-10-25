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
Each group is told with the start of its first process, and the watchdog signals
a group only while that start is unchanged, so a group number reused after the
agents are gone is left alone (`watchdog`).
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Collection

from contraagent._internal.backends import watchdog
from contraagent._internal.platform import processes
from contraagent._internal.platform.groups import KILL_AFTER_S, REAP_S, groups

_lock = threading.Lock()
_live: list[subprocess.Popen] = []
#: The task key each live agent was launched for (`register(task=)`), by pid.
_task_of: dict[int, str] = {}
#: Bumped each time a teardown starts. A launch notes it before spawning
#: (`epoch()`) and hands it back to `register`: a different value means a
#: teardown began while the child was being started, so the sweep may already
#: have passed it by and the child is stopped on the way in.
_epoch = 0
#: How many teardowns are in flight. While any is, every registration is a
#: latecomer, whether or not its launch noted an epoch.
_stopping = 0
#: Set by a signal handler (`refuse_launches`): from then on every launch is refused, before
#: and after the teardown alike, until `allow_launches` (never, when the signal ends the
#: process). One assignment, so the handler takes no lock; `register` reads it under
#: `_lock`, which `stop_all` holds while it takes its list, so a process either is in that
#: list or is refused, whichever comes first.
_refused = False

#: Why a launch is refused while the process stops.
REFUSED = "refused: the run is stopping on a signal"

#: The watchdog's process (`watchdog`) and this interpreter's end of its socket.
_watchdog: subprocess.Popen | None = None
_watch: socket.socket | None = None
#: The pid that started the watchdog: a forked child of this interpreter starts its own.
_watch_pid = 0


def _tell_watchdog(line: str) -> None:
    """Tell the watchdog an agent group started (`+pgid start`) or ended (`-pgid`), starting it
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
                    [sys.executable, "-I", watchdog.__file__, processes.__file__, str(KILL_AFTER_S)],
                    stdin=theirs.fileno(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,  # POSIX only: Windows needs no watchdog
                )
                theirs.close()
                if _watch_pid == 0:
                    atexit.register(_release_watchdog)
                _watch, _watch_pid = ours, os.getpid()
            # MSG_NOSIGNAL: a watchdog that is gone is an error here, never a SIGPIPE
            # (a short command of the command line restores SIGPIPE's default, which ends the process).
            _watch.sendall(f"{line}\n".encode(), getattr(socket, "MSG_NOSIGNAL", 0))
        except OSError:
            pass


def _release_watchdog() -> None:
    """At the interpreter's exit with no agent listed, end the watchdog: closing the socket
    is its end of file, and with no group to stop it exits at once. With agents still
    listed it stays, to stop them once this interpreter is gone."""
    global _watchdog, _watch
    with _lock:
        if _watch is None or _watch_pid != os.getpid() or _live:
            return
        watch, proc, _watch, _watchdog = _watch, _watchdog, None, None
    watch.close()
    if proc is not None:
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass


def epoch() -> int:
    """The current teardown epoch; pass it to `register` as `since`. Every spawn site calls
    it before it starts an agent, so it first seals this process (`processes.seal_self`):
    an agent cannot read the environment or the memory of the process that holds every
    hop's credential."""
    processes.seal_self()
    with _lock:
        return _epoch


def refuse_launches() -> None:
    """Refuse every launch from now on (`launches_refused`, `register`). Called from a signal
    handler, before it wakes the teardown: it takes no lock."""
    global _refused
    _refused = True


def allow_launches() -> None:
    """Allow launches again, once the run a signal stopped has ended and the process goes on."""
    global _refused
    with _lock:
        _refused = False


def launches_refused() -> bool:
    """Whether a signal is stopping the run: a launch is refused before it starts."""
    return _refused


def register(proc: subprocess.Popen, since: int | None = None, task: str = "") -> bool:
    """Publish a spawned agent so the teardown can reach it; False when it was refused (and
    stopped) instead. `task`: the key of the task it was launched for, which `task_pids`
    answers by.

    A process registered while a teardown is running, or whose launch began
    (`since`, from `epoch()`) before a teardown that has since started, is
    killed on the spot. Without this, a worker thread that starts a task while
    the teardown is in flight orphans it: the sweep is over, the child is
    live, and the run it belonged to is gone. It is a race between a thread
    pool and a signal, and the only way to win it is to refuse the latecomer.

    A signal refuses every registration from the moment its handler runs
    (`refuse_launches`), before the teardown starts and after it ends, so no
    agent starts between the teardown and the end of the process. Without a
    signal the refusal is scoped to a teardown, not to the interpreter: a
    launch that begins after it has finished registers normally, so a second
    run in the same process (a notebook, a service, a test session) can still
    start agents.
    """
    groups.adopt(proc)
    with _lock:
        late = _refused or _stopping > 0 or (since is not None and since != _epoch)
        if not late:
            _live.append(proc)
            if task:
                _task_of[proc.pid] = task
    if late:
        _kill_group(proc)
        groups.release(proc)
    else:
        start = processes.start_ticks(proc.pid)
        if start is not None:  # a pid without its start is not trusted (`watchdog`)
            _tell_watchdog(f"+{proc.pid} {start}")
    return not late


def _kill_group(proc: subprocess.Popen) -> None:
    """Ask a process group to stop, then kill whatever is left of it."""
    if not groups.terminate(proc):
        return
    try:
        proc.wait(timeout=KILL_AFTER_S)
        return
    except (subprocess.TimeoutExpired, OSError):
        pass
    groups.kill(proc)
    try:
        proc.wait(timeout=REAP_S)
    except (subprocess.TimeoutExpired, OSError):
        pass


def unregister(proc: subprocess.Popen) -> None:
    """Forget a process that has exited on its own, or was stopped."""
    with _lock:
        try:
            _live.remove(proc)
        except ValueError:
            return
        _task_of.pop(proc.pid, None)
    groups.release(proc)
    _tell_watchdog(f"-{proc.pid}")


def task_pids(keys: Collection[str]) -> dict[str, list[int]]:
    """The live processes of the agents launched for each task of `keys`, by key: each
    agent's group as the OS lists it (`groups.members`), else the agent and its
    descendants (`processes.tree`). A task with no live agent is left out."""
    wanted = set(keys)
    with _lock:
        procs = [(p, _task_of[p.pid]) for p in _live if _task_of.get(p.pid) in wanted]
    out: dict[str, list[int]] = {}
    for proc, key in procs:
        pids = groups.members(proc)
        out.setdefault(key, []).extend(pids if pids is not None else processes.tree(proc.pid))
    return out


def live_count() -> int:
    with _lock:
        return len([p for p in _live if p.poll() is None])


def stop_all(timeout: float = KILL_AFTER_S) -> int:
    """Stop every live agent group. Returns how many were signalled.

    Idempotent, and nothing here raises, because a teardown that failed while
    handling a termination would leave the process running, which is the
    situation this exists to prevent. It waits for the agents to end: call it
    from the teardown's own thread, never from a signal handler.
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
