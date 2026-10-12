"""The agent processes this interpreter started, and how to stop them.

Every backend already launches its CLI in its own session
(`start_new_session=True`) and already has a `_terminate` that kills the
group — so a run that ends on its own terms leaves nothing behind. The gap
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
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

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

#: How long a group gets to exit on SIGTERM before it is killed. Long enough
#: for the CLI to write its own farewell and release its ports, short enough
#: that a teardown does not feel like a hang.
_TERM_GRACE_S = 5.0


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
    with _lock:
        late = _stopping > 0 or (since is not None and since != _epoch)
        if not late:
            _live.append(proc)
    if late:
        _kill_group(proc)
    return proc


def _kill_group(proc: subprocess.Popen) -> None:
    """SIGTERM a process group, then SIGKILL whatever is left of it."""
    for sig, grace in ((signal.SIGTERM, _TERM_GRACE_S), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(proc.pid, sig)
        except (OSError, ProcessLookupError):
            return
        try:
            proc.wait(timeout=grace)
            return
        except (subprocess.TimeoutExpired, OSError):
            continue


def unregister(proc: subprocess.Popen) -> None:
    """Forget a process that has exited on its own."""
    with _lock:
        try:
            _live.remove(proc)
        except ValueError:
            pass


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
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            stopped += 1
        except (OSError, ProcessLookupError):
            unregister(proc)
    for proc in procs:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except (subprocess.TimeoutExpired, OSError):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        finally:
            unregister(proc)
    return stopped
