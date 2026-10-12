"""Stopping what a run started, however the run ends.

`try/finally` covers a run returning or raising. It does not cover the two
ways a run actually gets stopped in practice: SIGTERM from whatever
supervises it, and Ctrl-C at a terminal. Neither runs a `finally` that is
already unwinding, so without this the agent processes of an interrupted
run are reparented to init and keep running.
"""

from __future__ import annotations

import logging
import os
import signal
from collections.abc import Callable
from types import FrameType
from typing import Any

from contraagent.backends import live_processes as live

_logger = logging.getLogger(__name__)

#: What `signal.signal` returns: a Python handler, SIG_DFL / SIG_IGN, or None
#: for a handler installed outside Python.
_Handler = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


def install_signal_handlers(teardown_fn: Callable[[], None]) -> None:
    """Make `teardown_fn` run on SIGTERM and SIGINT.

    SIGINT is handled rather than re-raised, so Ctrl-C produces the orderly
    stop and a second Ctrl-C forces the issue. The handler puts back the
    handler each signal had when this was installed, captured here rather
    than read inside the handler (where it would be the handler itself), so
    a signal arriving after the teardown is not swallowed by a stale handler
    and a host application's own handler gets its turn.
    """
    previous: dict[int, _Handler] = {}

    def _on_signal(signum, frame):
        prior = previous.get(signum)
        # None: a handler not installed from Python; the default is the closest.
        signal.signal(signum, signal.SIG_DFL if prior is None else prior)
        teardown_fn()
        if callable(prior) and prior is not signal.default_int_handler:
            prior(signum, frame)
            return
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        # Re-raise the default action so the exit status reports why.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            previous[sig] = signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            # Not the main thread, or no such signal here; the atexit
            # registration still covers an ordinary exit.
            pass


def run(*callbacks: Callable[[], None]) -> None:
    """Stop the live agents, then call each of `callbacks` (servers, VMs, leases).

    Reached three ways — the end of the run, the signal handler, and the
    interpreter exiting — so the caller makes it idempotent (`Run.teardown`
    does), and this never raises: a teardown that fails while handling a
    signal turns an orderly stop into a traceback and leaves the process
    alive. Agents go first: they are the children that would otherwise be
    reparented to init, and an in-flight task is blocked in `wait()` on a
    worker thread where no `finally` of ours is running.
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
