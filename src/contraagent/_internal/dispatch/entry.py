"""`run_sync`: the synchronous entry over a coroutine (`WorkQueue.run`, `Pipeline.run`).

It runs the coroutine on a new event loop in this thread, as `asyncio.run` does, but
leaves the SIGINT handler alone. `asyncio.run` puts in its own when the default one is
installed, and that one only cancels the coroutine at its next `await`: Ctrl-C in the
flow's code or in the preflight, before the queue's first wait, would go on to the
next launch. Here a `KeyboardInterrupt` that a signal handler raises stops the code it
interrupts, as in a run without an event loop; one raised while the loop waits ends
the coroutine (it is cancelled, so its `finally` blocks run: the run's teardown, its
services, its lock) and is raised again.

The tasks left on the loop are cancelled and given `CANCEL_S` seconds to end. A task
that ignores its cancellation (an `except BaseException` that goes on) is then left:
its name is logged and `run_sync` returns or raises, so a Ctrl-C is not followed by a
wait with no end. A second Ctrl-C ends that wait too.

From a thread whose event loop is running, the coroutine cannot run here: the caller
awaits the coroutine itself (`instead`), and `run_sync` raises RuntimeError saying so.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

#: The seconds the tasks left on the loop have, once cancelled, to end.
CANCEL_S = 30.0

_logger = logging.getLogger(__name__)


def run_sync[T](start: Callable[[], Coroutine[Any, Any, T]], *, called: str, instead: str) -> T:
    """Run the coroutine `start()` returns to its end on a new event loop; its value.
    RuntimeError, before `start` is called, when this thread's event loop is running:
    `called` names the synchronous entry and `instead` what to await in its place."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(f"{called} was called from a running event loop; use `{instead}` there instead")
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(start())
    finally:
        try:
            _cancel_rest(loop)  # a coroutine a KeyboardInterrupt left waiting: its `finally` blocks run
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            loop.close()


def _cancel_rest(loop: asyncio.AbstractEventLoop, limit_s: float | None = None) -> None:
    """Cancel every task left on `loop` and let each one end, within `limit_s` seconds
    (`CANCEL_S`); the names of those that did not end are logged."""
    rest = asyncio.all_tasks(loop)
    if not rest:
        return
    for task in rest:
        task.cancel()
    limit = CANCEL_S if limit_s is None else limit_s
    _, left = loop.run_until_complete(asyncio.wait(rest, timeout=limit))
    for task in rest - left:
        if not task.cancelled():
            task.exception()  # retrieved: an error a task raised as it ended is not reported twice
    if left:
        names = ", ".join(sorted(task.get_name() for task in left))
        _logger.warning("%d task(s) did not end within %gs of being cancelled and are left behind: %s", len(left), limit, names)
