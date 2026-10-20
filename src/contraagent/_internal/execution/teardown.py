"""Stopping what a run started, however the run ends.

`try/finally` covers a run returning or raising. It does not cover the two
ways a run actually gets stopped in practice: SIGTERM from whatever
supervises it, and Ctrl-C at a terminal. Neither runs a `finally` that is
already unwinding, so without this the agent processes of an interrupted
run are reparented to init and keep running.

The teardown never runs inside the signal handler. Python runs a handler on the
main thread, between two bytecodes of whatever that thread was doing, and the main
thread is the event loop's: it may hold a lock the teardown needs (the lock of
`append_lines`, a service's), and a teardown that waited for it there would wait
for itself. The handler only records the signal and wakes a thread of its own
(`_Watch`), which runs the teardown while the main thread goes on, unwinds, and
lets go of its locks.
"""

from __future__ import annotations

import logging
import os
import queue
import signal
import threading
from collections.abc import Callable
from types import FrameType
from typing import Any

from contraagent._internal.backends import live_processes as live
from contraagent._internal.backends.base import remove_exit_dirs

_logger = logging.getLogger(__name__)

#: What `signal.signal` returns: a Python handler, SIG_DFL / SIG_IGN, or None
#: for a handler installed outside Python.
_Handler = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


class _Watch:
    """A thread that waits for a signal one of our handlers received and runs the teardown.

    The handler hands it the signal through a `queue.SimpleQueue`, whose `put` may be
    called from a signal handler (it takes no lock the interrupted code can hold). When
    the handler leaves ending the process to us (`ends`), the thread ends it after the
    teardown, by the signal's default action, so the exit status still names the signal.
    """

    def __init__(self, teardown_fn: Callable[[], None]) -> None:
        self._teardown_fn = teardown_fn
        self._wake: queue.SimpleQueue[tuple[int, bool] | None] = queue.SimpleQueue()
        #: Set by the handler before it returns or raises: a teardown is under way or about to be.
        self.fired = False
        self.done = threading.Event()
        self._thread = threading.Thread(target=self._wait, name="contraagent-teardown", daemon=True)
        self._thread.start()

    def fire(self, signum: int, ends: bool) -> None:
        """From the signal handler: no lock, no I/O."""
        global _ending
        self.fired = True
        _ending = _ending or ends
        self._wake.put((signum, ends))

    def stop(self) -> None:
        """End the thread, after the teardown a signal started, if one did."""
        self._wake.put(None)
        if self.fired:
            self.done.wait()

    def _wait(self) -> None:
        woken = self._wake.get()
        if woken is None:
            return
        signum, ends = woken
        try:
            try:
                self._teardown_fn()
            except Exception as exc:  # the process must still end
                _logger.warning("[teardown] %s", exc)
            if ends:
                # No `atexit` runs past the default action: its temporary directories go now.
                remove_exit_dirs()
                os.kill(os.getpid(), signum)
        finally:
            self.done.set()


_watches: list[_Watch] = []
_watches_lock = threading.Lock()
#: Whether a signal is ending the process: launches stay refused for good.
_ending = False


def settle() -> None:
    """Wait for the teardown a signal started to end, if one did. The main thread calls it
    as a run unwinds, before stopping what the teardown also stops, so the teardown's
    record of it (a service stopped as `interrupted`) is the one written. Never call it
    from a signal handler."""
    with _watches_lock:
        fired = [w for w in _watches if w.fired]
    for w in fired:
        w.done.wait()


def install_signal_handlers(teardown_fn: Callable[[], None]) -> Callable[[], None]:
    """Make `teardown_fn` run on SIGTERM and SIGINT, on a thread of its own. Returns a function
    that puts back the handlers each signal had, where ours is still the one installed, after
    the teardown a signal started has ended (a no-op off the main thread, where nothing was
    installed).

    The handler refuses every launch from then on (`live_processes.refuse_launches`: an
    agent, a Python task, a service), puts back the handler each signal had when this was
    installed, captured here rather than read inside the handler (where it would be the
    handler itself), so a second signal is not swallowed by a stale handler, and wakes the
    teardown. Launches stay refused until `restore` for a signal that leaves the process
    running, and for good for one that ends it. Then:

    * a handler of the host application's own is called, at once, on the main thread;
    * SIGINT otherwise raises KeyboardInterrupt, at once, where the main thread is, so
      Ctrl-C stops the flow's code without waiting for its next `await`; a second Ctrl-C
      forces the issue;
    * SIGTERM otherwise ends the process by its default action once the teardown is done,
      so the exit status reports why.
    """
    previous: dict[int, _Handler] = {}
    watch = _Watch(teardown_fn)

    def _on_signal(signum, frame):
        live.refuse_launches()  # first: no launch starts from here on, before the teardown or after it
        prior = previous.get(signum)
        if callable(prior) and prior is not signal.default_int_handler:
            signal.signal(signum, prior)
            watch.fire(signum, ends=False)
            prior(signum, frame)
            return
        ends = signum != signal.SIGINT
        # None: a handler not installed from Python; the default is the closest.
        signal.signal(signum, signal.SIG_DFL if prior is None or ends else prior)
        watch.fire(signum, ends)
        if not ends:
            raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            previous[sig] = signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            # Not the main thread, or no such signal here; the atexit
            # registration still covers an ordinary exit.
            pass
    with _watches_lock:
        _watches.append(watch)

    def restore() -> None:
        for sig, prior in previous.items():
            try:
                if signal.getsignal(sig) is _on_signal:
                    signal.signal(sig, signal.SIG_DFL if prior is None else prior)
            except (ValueError, OSError):
                pass
        watch.stop()
        with _watches_lock:
            if watch in _watches:
                _watches.remove(watch)
        if watch.fired and not _ending:
            # The run the signal stopped has ended, its tasks with it; the process goes on
            # (Ctrl-C caught, a host's handler): a later run may launch again.
            live.allow_launches()

    return restore


def run(*callbacks: Callable[[], None]) -> None:
    """Stop the live agents, then call each of `callbacks` (servers, VMs, leases).

    Reached three ways — the end of the run, the teardown thread a signal wakes, and the
    interpreter exiting — so the caller makes it idempotent (`Run.teardown` does), and
    this never raises: a teardown that fails while handling a signal turns an orderly
    stop into a traceback and leaves the process alive. Agents go first: they are the
    children that would otherwise be reparented to init, and an in-flight task is
    blocked in `wait()` on a worker thread where no `finally` of ours is running.
    """
    try:
        stopped = live.stop_all()
        if stopped:
            _logger.info("[teardown] stopped %d agent process group(s)", stopped)
    except Exception as exc:  # teardown never raises
        _logger.warning("[teardown] agents: %s", exc)
    for cb in callbacks:
        try:
            cb()
        except Exception as exc:
            _logger.warning("[teardown] %s: %s", getattr(cb, "__name__", cb), exc)
