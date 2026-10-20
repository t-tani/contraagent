"""`FlowLoop`: the event loop flow code runs on, a ready queue and nothing else.

`FlowLoop` implements `asyncio.AbstractEventLoop`, the interface asyncio documents for
another implementation of an event loop. It holds the callbacks that are ready to run,
in a FIFO queue, and runs them in `drain()` until none is left. It has no clock, no
threads and no I/O: a method that needs one of them raises TypeError where flow code
calls it, with what to write instead. So `asyncio.sleep(1)`, `asyncio.wait_for(...,
timeout=1)`, `asyncio.timeout(1)` and `call_later` (a clock), `asyncio.to_thread`,
`run_in_executor` and `call_soon_threadsafe` (a thread), sockets, pipes, subprocesses
and signals (I/O) fail at the `await` that needs them. A future of another event loop
fails at its `await` too, with asyncio's own RuntimeError. `asyncio.sleep(0)` and
`asyncio.timeout(None)` need no clock and work.

Every callback a Future or a Task schedules goes through `call_soon` (asyncio's
documentation: a done callback "is scheduled with loop.call_soon()"). Nothing else
can schedule one, so when `drain()` returns, every Task on the loop waits for a future
that nothing on the loop will complete: only the code that drives the loop (the
`FlowDriver`, answering a task) can. That is the loop's quiescence, exact by
construction: no count of iterations, no wall clock.

The loop runs only inside `drain()`, on the caller's thread. `drain()` must not run
inside a step of another event loop's Task: from Python 3.14 a thread runs one Task
step at a time, and a step inside another raises RuntimeError. The driver calls it
from a plain callback of its own event loop (`call_soon`), or on a thread where no
event loop runs.

`create_task(coro)` hands the coroutine to `make_task`, the driver's, which decides
what the Task is (a flow call, numbered there); without one it makes a plain Task.
`eager_start` is dropped: a Task's first step runs in `drain()`, like every other.

While `drain()` runs, the running event loop of the thread is this one, so
`asyncio.get_running_loop()`, `asyncio.create_task`, `asyncio.TaskGroup` and
`asyncio.current_task()` in flow code see it; after `drain()`, even one that raised,
the previous running loop is back. That uses `asyncio._set_running_loop` and
`asyncio._get_running_loop`, which asyncio exports in `asyncio.__all__` and describes as
"a low-level function intended to be used by event loops": the API of an event loop's
implementer, used by Temporal's Python SDK and by uvloop, with types in typeshed. `call_soon` builds
an `asyncio.Handle(callback, args, loop, context)`, the constructor every event loop
uses (its arguments are the same since Python 3.7; Temporal calls it the same way),
and `drain()` runs it through the documented `Handle.get_context()`, not the private
`Handle._run`. These are the only names outside asyncio's documentation it uses; it
reads no private state of asyncio (no `_ready`, no `_fut_waiter`).

An asynchronous generator that flow code starts during `drain()` is finalized on this
loop: `drain()` puts in the loop's own `sys.set_asyncgen_hooks` while it runs, and
`close_asyncgens()` closes the ones still open, as `shutdown_asyncgens` does.

Each ready callback also carries a cause: the keys of the task results that led to it.
`call_soon` gives a callback the cause of the callback running now, or, outside
`drain()`, the cause of `caused_by(keys)` around the code that completes a future (the
driver, giving a result). Before a callback runs, `on_run(context, cause)` returns the
cause of the callbacks it schedules; without `on_run`, its own. Since every callback of
a Future or a Task goes through `call_soon`, the cause follows each future, done
callback and Task step, inside `asyncio.gather` and `asyncio.TaskGroup` too, without
reading them.

A callback that runs longer than `slow_s` is reported to `on_slow(context, seconds)`;
a drain that has run longer than `slow_s` in all, with no such callback before, is
reported once, with no context. Both count the time of flow code only: contraagent's own
work that flow code calls (a task call, the creation of a flow call, the analysis of a
loop), marked by `not_flow_code()`, is left out. It is the same on every machine and
takes longer on a busy one; moving work to a Python task would not shorten it. An exception a callback raises goes to the loop's
exception handler (by default, a logged error); SystemExit and KeyboardInterrupt stop
`drain()` and are raised again.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import contextvars
import inspect
import logging
import sys
import time
import weakref
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator, Iterator
from typing import Any, NoReturn, Protocol, TypeVarTuple, cast

_logger = logging.getLogger(__name__)

_Ts = TypeVarTuple("_Ts")

#: Where the rules for flow code are written.
_TOPIC = "(contraagent docs tasks)"


class MakeTask(Protocol):
    """`make_task(coro, name=, context=)`: the Task `FlowLoop.create_task` returns for `coro`."""

    def __call__(self, coro: Any, /, *, name: str | None = None, context: contextvars.Context | None = None) -> asyncio.Task[Any]: ...


#: The keys of the task results that led to a callback (see the module docstring).
Cause = tuple[str, ...]


class OnRun(Protocol):
    """`on_run(context, cause)`: a callback with `cause` is about to run in `context`; the
    cause of the callbacks it schedules."""

    def __call__(self, context: contextvars.Context, cause: Cause, /) -> Cause: ...


class OnSlow(Protocol):
    """`on_slow(context, seconds)`: a callback that ran in `context` took `seconds` (past
    `slow_s`); `context` None: the whole drain has run that long."""

    def __call__(self, context: contextvars.Context | None, seconds: float, /) -> None: ...


def no_clock(what: str) -> TypeError:
    return TypeError(
        f"{what} needs a clock, and flow code has none: an async flow waits only for task calls and flow calls. "
        f"Give a flow call a deadline with time_box(); put waiting, polling and I/O in a Python task {_TOPIC}"
    )


def no_threads(what: str) -> TypeError:
    return TypeError(
        f"{what} needs a thread, and flow code runs on none but its own: put the work in a Python task, "
        f"which runs on a thread of the run's pool {_TOPIC}"
    )


def no_io(what: str) -> TypeError:
    return TypeError(f"{what} needs I/O, and flow code does none: put the I/O in a Python task and await the task call {_TOPIC}")


def not_run_here(what: str) -> TypeError:
    return TypeError(f"{what}: contraagent runs the event loop of flow code; flow code does not start, stop or close it")


def not_flow_code() -> contextlib.AbstractContextManager[None]:
    """`FlowLoop.not_flow_code()` of the flow loop that runs on this thread; nothing outside one."""
    loop = asyncio._get_running_loop()  # pyright: ignore[reportPrivateUsage]
    return loop.not_flow_code() if isinstance(loop, FlowLoop) else contextlib.nullcontext()


class FlowLoop(asyncio.AbstractEventLoop):
    """The event loop flow code runs on: a FIFO ready queue, run by `drain()` (see the
    module docstring)."""

    def __init__(
        self,
        *,
        make_task: MakeTask | None = None,
        on_run: OnRun | None = None,
        on_slow: OnSlow | None = None,
        slow_s: float = 1.0,
    ) -> None:
        self._ready: collections.deque[tuple[asyncio.Handle, Callable[..., object], tuple[object, ...], Cause]] = collections.deque()
        self._make_task = make_task
        self._on_run = on_run
        self._on_slow = on_slow
        # The cause of the callback running now, or of `caused_by` outside a drain.
        self._cause: Cause = ()
        self.slow_s = slow_s
        self._closed = False
        self._draining = False
        # The time of contraagent's own work in flow code so far (`not_flow_code`), and how
        # deep such work is nested now (only the outermost counts).
        self._own_s = 0.0
        self._own_depth = 0
        self._handler: Callable[[asyncio.AbstractEventLoop, dict[str, Any]], object] | None = None
        self._asyncgens: weakref.WeakSet[AsyncGenerator[Any, Any]] = weakref.WeakSet()

    # --- what Futures and Tasks use -------------------------------------------

    def call_soon(self, callback: Callable[[*_Ts], object], *args: *_Ts, context: contextvars.Context | None = None) -> asyncio.Handle:
        handle = asyncio.Handle(callback, args, self, context)
        self._ready.append((handle, callback, args, self._cause))
        return handle

    def create_future(self) -> asyncio.Future[Any]:
        return asyncio.Future(loop=self)

    def create_task[T](
        self,
        coro: Coroutine[Any, Any, T] | Generator[Any, None, T],
        *,
        name: str | None = None,
        context: contextvars.Context | None = None,
        **kwargs: Any,
    ) -> asyncio.Task[T]:
        kwargs.pop("eager_start", None)  # its first step runs in drain(), never in its creator's
        if kwargs:
            raise TypeError(f"FlowLoop.create_task() takes no {', '.join(kwargs)}")
        if self._make_task is not None:
            with self.not_flow_code():
                return self._make_task(coro, name=name, context=context)
        return asyncio.Task(cast(Coroutine[Any, Any, T], coro), loop=self, name=name, context=context)

    @contextlib.contextmanager
    def not_flow_code(self) -> Iterator[None]:
        """Contraagent's own work that flow code calls: its time is not flow code's, so a
        slow step (`slow_s`) leaves it out."""
        self._own_depth += 1
        began = time.monotonic()
        try:
            yield
        finally:
            self._own_depth -= 1
            if not self._own_depth:
                self._own_s += time.monotonic() - began

    def time(self) -> float:
        """`time.monotonic()`: what `asyncio.timeout(None)` reads; nothing here schedules by it."""
        return time.monotonic()

    def get_debug(self) -> bool:
        return False

    def set_debug(self, enabled: bool) -> None:
        if enabled:
            raise not_run_here("set_debug(True)")

    def is_running(self) -> bool:
        return self._draining

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._draining:
            raise not_run_here("close()")
        self._closed = True
        self._ready.clear()

    def get_exception_handler(self) -> Callable[[asyncio.AbstractEventLoop, dict[str, Any]], object] | None:
        return self._handler

    def set_exception_handler(self, handler: Callable[[asyncio.AbstractEventLoop, dict[str, Any]], object] | None) -> None:
        self._handler = handler

    def default_exception_handler(self, context: dict[str, Any]) -> None:
        _logger.error("flow code: %s", context.get("message", "an exception in a callback"), exc_info=context.get("exception"))

    def call_exception_handler(self, context: dict[str, Any]) -> None:
        if self._handler is None:
            self.default_exception_handler(context)
            return
        try:
            self._handler(self, context)
        except Exception:
            _logger.exception("the flow loop's exception handler raised")

    def get_task_factory(self) -> None:
        return None

    def set_task_factory(self, factory: object) -> NoReturn:
        raise not_run_here("set_task_factory()")

    # --- the driver's side ----------------------------------------------------

    @contextlib.contextmanager
    def caused_by(self, cause: Cause) -> Iterator[None]:
        """Within the block, outside `drain()`, a callback scheduled has `cause`."""
        if self._draining:
            raise RuntimeError("FlowLoop.caused_by() is for the code that drives the loop, outside drain()")
        self._cause = cause
        try:
            yield
        finally:
            self._cause = ()

    def set_cause(self, cause: Cause) -> None:
        """Within the callback running now, a callback scheduled from here on has `cause`."""
        self._cause = cause

    def ready(self) -> bool:
        """Whether a callback is ready to run: false once `drain()` returned and nothing was
        scheduled since."""
        return bool(self._ready)

    def drain(self) -> int:
        """Run callbacks until none is ready; how many ran. Call it outside any Task step of
        another event loop (see the module docstring)."""
        previous = asyncio._get_running_loop()  # pyright: ignore[reportPrivateUsage]
        hooks = sys.get_asyncgen_hooks()
        asyncio._set_running_loop(self)  # pyright: ignore[reportPrivateUsage]
        sys.set_asyncgen_hooks(firstiter=self._asyncgen_firstiter, finalizer=self._asyncgen_finalizer)
        self._draining = True
        ran = 0
        start, own_start = time.monotonic(), self._own_s
        told = False
        try:
            while self._ready:
                handle, callback, args, cause = self._ready.popleft()
                if handle.cancelled():
                    continue
                ran += 1
                context = handle.get_context()
                self._cause = self._on_run(context, cause) if self._on_run is not None else cause
                began, own_began = time.monotonic(), self._own_s
                try:
                    context.run(callback, *args)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except BaseException as exc:
                    self.call_exception_handler({"message": "exception in a callback", "exception": exc, "handle": handle})
                if self._on_slow is not None:
                    now = time.monotonic()
                    step = now - began - (self._own_s - own_began)
                    drained = now - start - (self._own_s - own_start)
                    if step > self.slow_s:
                        told = True
                        self._on_slow(context, step)
                    elif not told and drained > self.slow_s:
                        told = True
                        self._on_slow(None, drained)
        finally:
            self._draining = False
            self._cause = ()
            sys.set_asyncgen_hooks(*hooks)
            asyncio._set_running_loop(previous)  # pyright: ignore[reportPrivateUsage]
        return ran

    def close_asyncgens(self) -> None:
        """Schedule the closing of every asynchronous generator flow code left open; the next
        `drain()` runs it."""
        for agen in list(self._asyncgens):
            self._asyncgens.discard(agen)
            self.call_soon(self._aclose, agen)

    def _asyncgen_firstiter(self, agen: AsyncGenerator[Any, Any]) -> None:
        self._asyncgens.add(agen)

    def _asyncgen_finalizer(self, agen: AsyncGenerator[Any, Any]) -> None:
        self._asyncgens.discard(agen)
        if not self._closed:
            self.call_soon(self._aclose, agen)

    def _aclose(self, agen: AsyncGenerator[Any, Any]) -> None:
        asyncio.Task(agen.aclose(), loop=self)  # pyright: ignore[reportArgumentType]

    async def shutdown_asyncgens(self) -> None:
        self.close_asyncgens()

    # --- a clock --------------------------------------------------------------

    def call_later(
        self,
        delay: float,
        callback: Callable[[*_Ts], object],
        *args: *_Ts,
        context: contextvars.Context | None = None,
    ) -> asyncio.TimerHandle:
        raise no_clock(f"a timer of {delay:g}s (asyncio.sleep, a timeout of asyncio.wait, call_later)")

    def call_at(
        self,
        when: float,
        callback: Callable[[*_Ts], object],
        *args: *_Ts,
        context: contextvars.Context | None = None,
    ) -> asyncio.TimerHandle:
        raise no_clock("a timeout (asyncio.timeout, asyncio.wait_for, call_at)")

    # --- threads --------------------------------------------------------------

    def call_soon_threadsafe(
        self, callback: Callable[[*_Ts], object], *args: *_Ts, context: contextvars.Context | None = None
    ) -> asyncio.Handle:
        raise no_threads("call_soon_threadsafe()")

    def run_in_executor(self, executor: Any, func: Callable[[*_Ts], Any], *args: *_Ts) -> NoReturn:
        raise no_threads("asyncio.to_thread() or run_in_executor()")

    def set_default_executor(self, executor: Any) -> NoReturn:
        raise no_threads("set_default_executor()")

    async def shutdown_default_executor(self, timeout: float | None = None) -> None:
        return None

    # --- running the loop -----------------------------------------------------

    def run_forever(self) -> NoReturn:
        raise not_run_here("run_forever()")

    def run_until_complete(self, future: Any) -> NoReturn:
        if inspect.iscoroutine(future):
            future.close()
        raise not_run_here("run_until_complete()")

    def stop(self) -> NoReturn:
        raise not_run_here("stop()")

    # --- I/O ------------------------------------------------------------------

    async def getaddrinfo(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("getaddrinfo()")

    async def getnameinfo(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("getnameinfo()")

    async def create_connection(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a connection (asyncio.open_connection, create_connection)")

    async def create_server(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a server (asyncio.start_server, create_server)")

    async def sendfile(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("sendfile()")

    async def start_tls(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("start_tls()")

    async def create_unix_connection(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a Unix socket connection")

    async def create_unix_server(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a Unix socket server")

    async def connect_accepted_socket(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("connect_accepted_socket()")

    async def create_datagram_endpoint(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a datagram endpoint")

    async def connect_read_pipe(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a pipe")

    async def connect_write_pipe(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a pipe")

    async def subprocess_shell(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a subprocess (asyncio.create_subprocess_shell)")

    async def subprocess_exec(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a subprocess (asyncio.create_subprocess_exec)")

    def add_reader(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("add_reader()")

    def remove_reader(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("remove_reader()")

    def add_writer(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("add_writer()")

    def remove_writer(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("remove_writer()")

    async def sock_recv(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_recv_into(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_recvfrom(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_recvfrom_into(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_sendall(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_sendto(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_connect(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_accept(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    async def sock_sendfile(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a socket")

    def add_signal_handler(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a signal handler")

    def remove_signal_handler(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise no_io("a signal handler")


#: The code of `FlowLoop.drain`: the bottom of the stack of every step of flow code.
DRAIN_CODE = FlowLoop.drain.__code__
