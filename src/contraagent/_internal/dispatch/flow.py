"""`FlowDriver`: runs async flows over a `WorkQueue`, one flow call per asyncio Task of flow code.

A flow that waits for outputs is an `async def` function (an async flow). It waits
with `await`; at this level it waits for a `Task` through `driver.wait`:

    async def flow():
        res = await driver.wait(Task("survey", unit="a"))      # one task: its answer
        found = await asyncio.gather(*[driver.wait(Task("scan", unit=u)) for u in units])
        merged = await asyncio.gather(*[per_unit(u) for u in units])  # flow calls, concurrently
        rest = await helper(res)                                  # the same flow call
        part = await time_box(per_unit(u), deadline_s=600)       # a flow call with its own deadline

Flow code runs on an event loop of the driver's own, its `FlowLoop` (`flowloop.py`):
a queue of ready callbacks with no clock, no threads and no I/O. A flow call is one
asyncio Task on it: the top flow passed to `start()` (ids `"0"`, `"1"`, ... in start
order), or a Task created while a flow call's code runs (`asyncio.gather`,
`asyncio.create_task`, `asyncio.TaskGroup.create_task`, `time_box`), whose id is
`"<parent>.<n>"`, numbered from 1 in creation order within the parent. Every Task
takes a number, the one asyncio makes around a task call that `gather` is given too
(`ensure_future` wraps an awaitable that is no coroutine in one); since the flow loop
runs its callbacks in the order they come, the same flow code gives the same ids in
every run, whatever order its tasks finish in. `await helper()` runs in the same flow
call. The flow call whose code runs is a context variable (`current`).

A flow call is on record only once it does something a run shows: it creates a task
(`add`, a task call) or a flow call, or it ends with an error of its own (one that is
not what `answer` raised at an await of a task, passing through unchanged: that task's
own record says it) or the error the driver closed it with; a top flow call is on
record from its start. So a Task that only awaits a task already created
(asyncio's around `gather(task_call)`, or a helper that awaits its parent's task call)
and ends otherwise leaves no record, and the ids on record may skip numbers. Each flow
call is reported through `on_flow_call(event, call)`: `"create"` when its Task is
created, `"start"` when it is put on record (its `started_at` is still its creation),
`"end"` when it ends (`call.recorded` says whether it is on record). Its `state` is
`running` until it `returned`, `raised` or was `closed` (cancelled). What it receives
reaches its parent when it ends, on record or not.

Why every Task counts: `asyncio.ensure_future`, which `gather` calls on each item,
wraps an awaitable that is neither a future nor a coroutine (a task call) in a Task of
a coroutine of asyncio's own. Telling that Task from a flow call's would take asyncio's
internal names or a look at frames, and making a task call pass for a coroutine or a
future would make it claim a protocol it does not keep. So the driver tells no Task
apart: the numbers stay deterministic, and the record shows what a flow call did.
`wait()` returns a coroutine that keeps the protocol (`send`, `throw`, `close`), used
once, so `gather` hands it to the loop as any coroutine.

Flow code runs only when the driver drains the flow loop (`settle`, `finish`): from a
plain callback of the event loop that `driving()` runs on, never inside one of its Task
steps, or on a thread where no event loop runs (`settle_here`, `finish_here`, for
`contraagent check`). When the drain ends, no callback is ready: every flow call waits
for a task's result, which only the driver gives, or for a flow call that waits in
turn. That is the flows' quiescence, exact by construction. `follow_up` only completes
the futures that wait for a result; the flow code they wake runs at the next drain, so
the steps of the flow calls run in the order the results are given, whatever thread
or callback of the event loop ran meanwhile. A clock, a thread or I/O that flow code
asks the flow loop for raises TypeError at its `await`; a future of another event loop
raises asyncio's RuntimeError there.

The event loop of `driving()` keeps nothing of the driver: no task factory. One driver
drives the flows of one event loop at a time: a second raises RuntimeError.

What a wait means is set by callbacks, so a typed layer plugs in without changing
the driver:

* `waits_for(item) -> Task`: the task `wait(item)` waits for. Default: the item
  itself, which must be a `Task`.
* `answer(item, result) -> value`: what `await wait(item)` gives for a finished task;
  an exception it raises is raised at the `await`. Default: the `TaskResult` itself.
  `result_or_raise` raises `TaskFailed` / `TaskDeferred` instead of answering a result
  that is not ok.
* `on_flow_call(event, call)`: a flow call started or ended. An exception it raises
  at a child's start fails the child before its code runs: the child ends `raised`
  with it, and the parent receives it where it awaits the child.

Rules:

* A task reaches the queue when it is created (`add`) or first waited for (`wait`),
  whether or not anything awaits it.
* `done[key]` holds every result the driver has seen: a task whose key is done is
  answered at once, without queueing it again; tasks with the same key wait for one
  result. Each `await` waits on a future of its own, so cancelling one flow call that
  waits for a key leaves the others waiting for it.
* A deferred task (`TaskResult.stop == "deferred"`) is answered like any other result
  before `past_grace()`; after it, the waiting flow call is cancelled (closed), and so
  is a parent that awaits it.
* The tasks a closed flow call created run to their end, as a task nothing awaits does,
  but a `Task.cancellable` one: once the flow call that created it and every flow call
  that waited for it are closed, and no flow call waits for it (each `await` waits on a
  future of its own, which closing its flow call cancels), the driver cancels it
  (`WorkQueue.cancel`; before `attach`, as it attaches). A flow call that returns or
  raises does not cancel what it created.
* A **time box** (`time_box(coroutine, deadline_s=, ...)`) runs the coroutine as a
  flow call with a deadline of its own, counted from its creation: every task created
  in it, or in a flow call it starts, carries its `TimeBox` (`Task.time_boxes`,
  outermost first), and the queue holds the task to it as to the run's own deadline
  (`WorkQueue`). A task it defers is answered at its `await` like any other deferral
  (`TaskDeferred`), so the flow call, or its parent, goes on past it.
* A flow call's `frontier` is the keys whose results it received when it was last
  resumed: the keys it received since its own code last ran (a `gather` gives the union
  of its items; a child flow call that ends gives its own last frontier); a child starts
  with its parent's.
* The queue does not end while a flow call runs (`settle`, its `between_passes`): it
  waits for the tasks the flow calls create, within the run's deadline.
* A flow call that still waits once the flows are quiescent, while no task the driver
  queued is still to give its result, waits for what nothing will answer (an
  `asyncio.Event` nobody sets, a `Queue` nobody fills): `settle` closes it, its `error`
  a RuntimeError that names where it waits.
* `finish()` cancels every flow call still running once the queue has run (recorded
  `closed`), and every other Task on the flow loop.

Flow code runs on the thread of the event loop that drives it; a callback of the flow
loop longer than `slow_step_s` (a step of one flow call between two waits) is logged,
and so is a drain that runs that long in all. Nothing here knows what a task does or
what its output is: that is `answer`'s business.
"""

from __future__ import annotations

import asyncio
import collections.abc
import contextlib
import contextvars
import inspect
import itertools
import logging
import re
import time
import warnings
from collections.abc import Awaitable, Callable, Coroutine, Generator, Iterable, Iterator
from dataclasses import dataclass, field, replace
from types import CodeType, FrameType, GeneratorType
from typing import Any, Literal, NoReturn, Protocol

from contraagent._internal.dispatch.code import flow_code
from contraagent._internal.dispatch.entry import run_sync
from contraagent._internal.dispatch.flowloop import DRAIN_CODE, FlowLoop
from contraagent._internal.dispatch.queue import GRACE_S, SLACK_SHARE, WorkQueue
from contraagent._internal.dispatch.task import STOP_DEFERRED, STOP_DUPLICATE_KEY, Task, TaskResult, TimeBox

_logger = logging.getLogger(__name__)

FlowState = Literal["running", "returned", "raised", "closed"]

_TOPIC = "(contraagent docs tasks)"


class WaitsFor(Protocol):
    """`waits_for(item)`: the task a flow waits for when it awaits `wait(item)`; by default
    the item is the task."""

    def __call__(self, item: Any, /) -> Task: ...


class Answer(Protocol):
    """`answer(item, result)`: what the flow receives at `await wait(item)` once its task
    finished with `result`; by default the result itself."""

    def __call__(self, item: Any, result: TaskResult, /) -> Any: ...


class OnFlowCall(Protocol):
    """`on_flow_call(event, call)`: a flow call was created (`event` `"create"`, before its
    code runs), was put on record (`"start"`, at the first thing it does that a run shows),
    or ended (`"end"`, its `state` and `value` or `error` set; `call.recorded` says whether
    a `"start"` came)."""

    def __call__(self, event: str, call: FlowCall, /) -> None: ...


class TaskFailed(Exception):
    """A task a flow waited for did not succeed: it failed, or was refused as a
    duplicate key. `item` is what the flow awaited, `result` the task's
    `TaskResult`; `stop` and `key` are the result's."""

    def __init__(self, result: TaskResult, item: Any = None) -> None:
        self.result = result
        self.item = item
        self.stop: str = result.stop
        self.key: str = result.task.key
        detail = f": {result.reason}" if result.reason else ""
        super().__init__(f"task {self.key} {self.stop}{detail}")


class TaskDeferred(TaskFailed):
    """A task a flow waited for was not launched: past the queue's deadline, its
    remaining work too long to finish before it, or with no way to launch. A flow may catch
    it and await a task of a `finishing_kinds` kind instead."""


def result_or_raise(item: Any, result: TaskResult) -> TaskResult:
    """An `answer`: the result when it is ok; `TaskDeferred` for a deferred task,
    `TaskFailed` for any other."""
    if result.ok:
        return result
    if result.stop == STOP_DEFERRED:
        raise TaskDeferred(result, item)
    raise TaskFailed(result, item)


def generator_flow_error(name: str) -> TypeError:
    """The TypeError for a generator flow: what to write instead."""
    return TypeError(
        f"{name} is a generator flow; a flow that waits for outputs is an `async def` function that waits with `await`. "
        "Rewrite it: `def` -> `async def`; `yield x` -> `await x`; `yield [a, b]` -> `await asyncio.gather(a, b)`; "
        f"`yield from sub()` -> `await sub()`; `yield time_box(g, ...)` -> `await time_box(c, ...)` {_TOPIC}"
    )


@dataclass(frozen=True)
class _Box:
    deadline_s: float
    grace_s: float
    slack_s: float
    finishing_kinds: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class _Next:
    """The coroutine the next Task created is for, and what it is: a top flow call, or a
    flow call with a time box."""

    coro: Any
    box: _Box | None = None
    top: bool = False


def time_box[T](
    flow: Coroutine[Any, Any, T],
    *,
    deadline_s: float,
    grace_s: float = GRACE_S,
    finishing_kinds: Iterable[str] = (),
    slack_s: float | None = None,
) -> Awaitable[T]:
    """Run `flow`, a coroutine (a call of an async flow), as a flow call with a deadline of
    its own: `deadline_s` from now, over the tasks it and the flow calls it starts create.
    Past it only `finishing_kinds` still launch, for `grace_s`; the rest are deferred and
    its flow receives `TaskDeferred`. From `deadline_s - slack_s` (default a quarter of
    `deadline_s`) its tasks are ordered for the deadline. Its tasks are held to the run's
    deadline and to every enclosing time box too, so the earliest deadline stops them.

    It returns the flow call, created now as an asyncio Task: await it (`await time_box(sub(u), deadline_s=600)`)
    or pass it to `asyncio.gather`. Call it in an async flow's code."""
    try:
        if isinstance(flow, GeneratorType):
            raise generator_flow_error(f"time_box({flow.__qualname__}(...))")
        if not inspect.iscoroutine(flow):
            raise TypeError(f"time_box() takes a coroutine (a call of an async def flow), not {type(flow).__name__}")
        if not deadline_s or deadline_s <= 0:
            raise ValueError(f"time_box(): deadline_s must be a positive number of seconds, not {deadline_s!r}")
        if grace_s < 0 or (slack_s is not None and slack_s < 0):
            raise ValueError("time_box(): grace_s and slack_s are seconds, not negative")
        if isinstance(finishing_kinds, str):
            raise TypeError(f"time_box(): finishing_kinds is a list of kinds, not the string {finishing_kinds!r}")
        driver = _driver_here()
        if driver is None or _call.get() is None:
            raise RuntimeError("time_box() starts a flow call: call it in the code of an async flow that a run drives")
    except BaseException:
        if inspect.iscoroutine(flow):
            flow.close()
        raise
    slack = slack_s if slack_s is not None else SLACK_SHARE * deadline_s
    box = _Box(float(deadline_s), float(grace_s), float(slack), tuple(finishing_kinds))
    return driver._create(_Next(flow, box=box))


@dataclass(eq=False)
class FlowCall:
    """One flow call: an asyncio Task the driver runs.

    `id`: `"0"` for the first top flow, `"<parent>.<n>"` for a child.
    `function`: `module.qualname` of its async def function. `site`: the
    parent's `(file, line)` where it created the Task; None for a top flow.
    `frontier`: the keys whose results it received when it was last resumed.
    `value`: what it returned; `error`: what it raised (or what cancelling it
    raised, or, for one closed because it waited for what nothing would answer,
    the RuntimeError that says where it waited). `time_box`: its own deadline,
    when it was started through `time_box`; `started_at` (`time.time()`): when it
    started. `recorded`: whether it is on record (`on_flow_call("start")` came:
    see the module docstring). `task`: its asyncio Task."""

    id: str
    parent: FlowCall | None = field(default=None, repr=False)
    function: str = ""
    site: tuple[str, int] | None = None
    state: FlowState = "running"
    frontier: tuple[str, ...] = ()
    value: Any = field(default=None, repr=False)
    error: BaseException | None = None
    time_box: TimeBox | None = None
    started_at: float = field(default_factory=time.time)
    recorded: bool = False
    task: asyncio.Task[Any] | None = field(default=None, repr=False)
    #: Its coroutine (the flow code the Task runs).
    coro: Any = field(default=None, repr=False)
    _children: itertools.count = field(default_factory=lambda: itertools.count(1), init=False, repr=False)
    # Its own code ran since it last received a result: the next result starts a new frontier.
    _ran: bool = field(default=False, init=False, repr=False)
    # The results its frontier holds: (order, n, key), the order that of the wait or the
    # child flow call that gave it, so its frontier follows their order, not their timing.
    _received: list[tuple[int, int, str]] = field(default_factory=list, init=False, repr=False)
    # The keys of its frontier, received since its code last ran.
    _in_frontier: set[str] = field(default_factory=set, init=False, repr=False)
    # Its place among the waits and flow calls of its parent (creation order).
    _order: int = field(default=0, init=False, repr=False)
    # It is being cancelled by the driver: it ends `closed`, whatever it ends with.
    _closing: bool = field(default=False, init=False, repr=False)
    # Why the driver closes it, when it waits for what nothing answers: its `error` then.
    _stopped: BaseException | None = field(default=None, init=False, repr=False)
    # The keys of the cancellable tasks it created or waited for (`Task.cancellable`).
    _cancellable: set[str] = field(default_factory=set, init=False, repr=False)


#: The flow call whose code runs.
_call: contextvars.ContextVar[FlowCall | None] = contextvars.ContextVar("contraagent_flow_call", default=None)

#: The driver of each event loop it drives: the event loop of `driving()`, and its flow loop.
_drivers: dict[asyncio.AbstractEventLoop, FlowDriver] = {}


def _driver_here() -> FlowDriver | None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return _drivers.get(loop)


class FlowDriver:
    """Drives flow calls on its flow loop over one `WorkQueue` (see the module docstring).

    `run(queue, *flows)` (or `await run_async(queue, *flows)`) is the whole cycle. Wired
    by hand, on the event loop: `with driver.driving():`, `driver.start(flow)` for each
    top flow (a coroutine), `driver.attach(queue)` with `follow_up=driver.follow_up` on
    the queue, `await queue.run_async()`, then `await driver.finish()`. Where no event
    loop runs, `settle_here()` and `finish_here()` drive the flows on the calling thread.
    """

    def __init__(
        self,
        *,
        waits_for: WaitsFor | None = None,
        answer: Answer | None = None,
        on_flow_call: OnFlowCall | None = None,
        past_grace: Callable[[], bool] | None = None,
        slow_step_s: float = 1.0,
    ) -> None:
        self._waits_for = waits_for or _task_itself
        self._answer = answer or (lambda item, result: result)
        self._on_flow_call = on_flow_call or (lambda event, call: None)
        #: Whether the queue is past its grace window; `attach()` sets the queue's
        #: `past_hard_stop` when none is given.
        self.past_grace: Callable[[], bool] | None = past_grace
        self.slow_step_s = slow_step_s
        #: Every flow call, by id, in start order.
        self.calls: dict[str, FlowCall] = {}
        #: Every result seen, by task key.
        self.done: dict[str, TaskResult] = {}
        # The event loop flow code runs on.
        self._loop = FlowLoop(make_task=self._make_task, on_slow=self._slow, slow_s=slow_step_s)
        self._tops = itertools.count()
        self._running = 0
        self._waiters: dict[str, list[asyncio.Future[TaskResult]]] = {}  # by task key, one per await
        self._queued_keys: set[str] = set()
        self._open: set[str] = set()  # keys queued whose result has not come
        # The cancellable tasks whose result has not come, by key: the flow call that created each.
        self._creators: dict[str, FlowCall] = {}
        # The keys to cancel as the queue is attached: closed before it was.
        self._to_cancel: list[str] = []
        # What `answer` raised at an await, by id (kept alive): a task's outcome, not a flow call's own.
        self._outcomes: dict[int, BaseException] = {}
        self._outbox: list[Task] = []
        self._queue: WorkQueue | None = None
        self._main: asyncio.AbstractEventLoop | None = None
        self._driving = False
        self._wake_due = False
        self._next: _Next | None = None
        self._made: FlowCall | None = None
        self._orders = itertools.count()

    # --- the cycle -----------------------------------------------------------

    def run(self, queue: WorkQueue, *flows: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Run `run_async` on a new event loop; the queue's summary. From a thread whose
        event loop is running it raises RuntimeError: await `run_async` there instead."""
        return run_sync(lambda: self.run_async(queue, *flows), called="FlowDriver.run()", instead="await driver.run_async(...)")

    async def run_async(self, queue: WorkQueue, *flows: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Start every flow, run `queue` on the running event loop until no task is queued or
        running and no flow call runs, cancel what is left; the queue's summary. Sets the
        queue's `follow_up`, and `past_grace` to its `past_hard_stop` unless one was given."""
        with self.driving():
            queue.follow_up = self.follow_up
            try:
                for flow in flows:
                    self.start(flow)
                self.attach(queue)
                return await queue.run_async()
            finally:
                await self.finish()

    @contextlib.contextmanager
    def driving(self) -> Iterator[FlowDriver]:
        """Drive flows until the block ends: from the running event loop (`settle`,
        `finish`), or, where none runs, from this thread (`settle_here`, `finish_here`).
        RuntimeError when another driver drives the running event loop's flows (one run
        per event loop at a time), or when flow code calls it."""
        try:
            main: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            main = None
        if (main is not None and main in _drivers) or self._driving:
            raise RuntimeError(SECOND_RUN)
        self._main, self._driving = main, True
        self._loop.slow_s = self.slow_step_s
        _drivers[self._loop] = self
        if main is not None:
            _drivers[main] = self
        try:
            yield self
        finally:
            if main is not None:
                del _drivers[main]
            del _drivers[self._loop]
            self._main, self._driving = None, False

    def start(self, flow: Coroutine[Any, Any, Any]) -> FlowCall:
        """Start a top flow call: a coroutine of flow code, run as an asyncio Task of the flow
        loop (its code runs at the next drain). Inside `driving()`."""
        if isinstance(flow, GeneratorType):
            raise generator_flow_error(flow.__qualname__)
        if not inspect.iscoroutine(flow):
            raise TypeError(f"a flow call is a coroutine (a call of an async def function), not {type(flow).__name__}")
        if not self._driving:
            flow.close()
            raise RuntimeError("FlowDriver.start() runs inside driving()")
        self._create(_Next(flow, top=True))
        assert self._made is not None
        return self._made

    def attach(self, queue: WorkQueue) -> None:
        """Queue on `queue` from now on: the tasks created so far go to it, and it does not
        end while a flow call runs (its `between_passes` is `settle`). Sets `past_grace` to
        its `past_hard_stop` unless one was given."""
        self._queue = queue
        queue.between_passes = self.settle
        if self.past_grace is None:
            self.past_grace = queue.past_hard_stop
        out, self._outbox = self._outbox, []
        queue.extend(out)
        doomed, self._to_cancel = self._to_cancel, []
        for key in doomed:
            queue.cancel(key)

    def follow_up(self, result: TaskResult) -> list[Task]:
        """`WorkQueue`'s `follow_up`: record the result and complete the futures that wait for
        it (the flow code they wake runs at the next drain, when the queue next settles).
        Queues nothing itself: an empty list."""
        key = result.task.key
        if result.stop != STOP_DUPLICATE_KEY:  # the key's own result is still to come
            self.done[key] = result
            self._open.discard(key)
            self._creators.pop(key, None)
        answered = False
        for fut in self._waiters.pop(key, ()):
            if not fut.done():  # one whose flow call was cancelled is done
                fut.set_result(result)
                answered = True
        if answered and self._queue is not None and self._main is not None and not self._wake_due:
            # A wait of the queue that has begun ends, so that the next pass settles.
            self._wake_due = True
            self._main.call_soon(self._wake_queue)
        return []

    async def settle(self) -> bool:
        """Let the flow calls run until each waits (until the flow loop has no callback
        ready), from a callback of the running event loop; close a flow call that waits for
        what nothing will answer (see the module docstring). Whether a flow call still runs."""
        await self._drained()
        if self._close_stuck():
            await self._drained()
        return self._running > 0

    def settle_here(self) -> bool:
        """`settle` on this thread, where no event loop runs (`contraagent check`)."""
        self._no_loop_here("settle_here")
        self._loop.drain()
        if self._close_stuck():
            self._loop.drain()
        return self._running > 0

    def alive(self) -> bool:
        """Whether a flow call still runs."""
        return self._running > 0

    async def finish(self) -> None:
        """Cancel every flow call still running and let it end (recorded `closed`), and every
        other Task of the flow loop. The tasks they created are not cancelled."""
        self._cancel_rest()
        await self._drained()
        self._close_rest()

    def finish_here(self) -> None:
        """`finish` on this thread, where no event loop runs (`contraagent check`)."""
        self._no_loop_here("finish_here")
        self._cancel_rest()
        self._loop.drain()
        self._close_rest()

    def time_boxes(self, call: FlowCall | None) -> tuple[TimeBox, ...]:
        """The time boxes over the tasks `call` creates: its own and its ancestors',
        outermost first."""
        boxes: list[TimeBox] = []
        while call is not None:
            if call.time_box is not None:
                boxes.append(call.time_box)
            call = call.parent
        return tuple(reversed(boxes))

    @property
    def current(self) -> FlowCall | None:
        """The flow call whose code runs (a context variable); None outside one."""
        return _call.get()

    async def _drained(self) -> None:
        """Drain the flow loop from a plain callback of the running event loop (from Python
        3.14 a drain inside a Task step raises), and wait for it to end."""
        if not self._loop.ready():
            return
        main = asyncio.get_running_loop()
        ended: asyncio.Future[None] = main.create_future()

        def drain() -> None:
            try:
                self._loop.drain()
            finally:
                if not ended.done():
                    ended.set_result(None)

        main.call_soon(drain)
        await ended

    def _no_loop_here(self, name: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise RuntimeError(f"FlowDriver.{name}() runs where no event loop runs; await {name.removesuffix('_here')}() there")

    def _wake_queue(self) -> None:
        self._wake_due = False
        if self._queue is not None:
            self._queue.wake()

    def _close_stuck(self) -> bool:
        """When the flows are quiescent and no task queued here is still to give its result,
        close every flow call still running: nothing will answer any of them. Whether it did."""
        if not self._running or self._loop.ready() or self._open:
            return False
        for call in self.calls.values():
            if call.state == "running" and call.task is not None and not call.task.done():
                call._closing = True
                call._stopped = RuntimeError(_waits_forever(call))
                call.task.cancel()
        return True

    def _cancel_rest(self) -> None:
        for call in self.calls.values():
            if call.state == "running":
                call._closing = True
        for task in asyncio.all_tasks(self._loop):
            task.cancel()
        self._loop.close_asyncgens()

    def _close_rest(self) -> None:
        for call in self.calls.values():
            if call.state == "running":  # it would not end
                self._end(call, "closed")

    # --- tasks -----------------------------------------------------------------

    def add(self, task: Task) -> None:
        """Queue a task the flow code created, held to the time boxes of the flow call that
        created it (before `attach`, it waits for the queue)."""
        call = _call.get()
        if call is not None:
            call._ran = True
            self._record(call)
            if task.cancellable and task.key not in self.done and task.key not in self._creators:
                self._creators[task.key] = call
                call._cancellable.add(task.key)
        self._enqueue(task, call)

    def wait(self, item: Any) -> Coroutine[Any, Any, Any]:
        """A coroutine that waits for the task `waits_for(item)` gives (queued when it is not
        yet) and returns `answer(item, result)` once it finished; awaited once, as any
        coroutine. Past `past_grace()` a deferred task cancels the flow call that waits
        (CancelledError)."""
        return _Wait(self._waiting(item))

    def _waiting(self, item: Any) -> Generator[Any, None, Any]:
        task = self._waits_for(item)
        call = _call.get()
        here = asyncio.current_task()
        own = call is not None and here is call.task
        order = next(self._orders)
        if own and call is not None:
            call._ran = True
        key = task.key
        result = self.done.get(key)
        if call is not None and key in self._creators:
            call._cancellable.add(key)
        if result is None:
            fut: asyncio.Future[TaskResult] = self._loop.create_future()
            self._waiters.setdefault(key, []).append(fut)
            self._enqueue(task, call)  # a key the queue refuses answers `fut` at once
            result = yield from fut.__await__()
        if result.stop == STOP_DEFERRED and self.past_grace is not None and self.past_grace() and call is not None:
            self._cancel(call, own)
        if call is not None:
            self._receive(call, (key,), order)
        try:
            return self._answer(item, result)
        except BaseException as exc:
            self._outcomes[id(exc)] = exc
            raise

    def _enqueue(self, task: Task, call: FlowCall | None) -> None:
        if task.key in self._queued_keys or task.key in self.done:
            return
        boxes = self.time_boxes(call)
        if boxes and not task.time_boxes:
            task = replace(task, time_boxes=boxes)
        self._queued_keys.add(task.key)
        self._open.add(task.key)
        if self._queue is not None:
            self._queue.extend([task])
        else:
            self._outbox.append(task)

    def _cancel(self, call: FlowCall, own: bool) -> NoReturn:
        call._closing = True
        if not own and call.task is not None:
            call.task.cancel()
        raise asyncio.CancelledError

    def _receive(self, call: FlowCall, keys: tuple[str, ...], order: int) -> None:
        """`call` received the results of `keys`, from a wait or a child flow call of place
        `order`: they join its frontier, which starts anew when its code ran since the last
        result. The frontier is in the order of those places (a `gather`'s, by position)."""
        if call._ran:
            call._received, call._ran = [], False
        if not call._received:  # its first result since its code ran: the frontier starts anew
            call.frontier, call._in_frontier = (), set()
        new = [(order, i, key) for i, key in enumerate(keys)]
        if not new:
            return
        if not call._received or new[0] > call._received[-1]:  # after all the others: in order as it is
            call._received += new
            fresh = tuple(dict.fromkeys(key for key in keys if key not in call._in_frontier))
        else:
            call._received = sorted(call._received + new)
            call.frontier, call._in_frontier = (), set()
            fresh = tuple(dict.fromkeys(key for _, _, key in call._received))
        call.frontier += fresh
        call._in_frontier.update(fresh)

    def _slow(self, context: contextvars.Context | None, elapsed: float) -> None:
        """A callback of the flow loop ran for `elapsed` seconds (past `slow_step_s`): a step
        of the flow call of its context; with no context, a whole drain."""
        call = context.get(_call) if context is not None else None
        if call is not None:
            _logger.warning(
                "flow call %s (%s) ran %.1fs between two waits on the event loop's thread; heavy work belongs in a Python task",
                call.id,
                call.function,
                elapsed,
            )
        else:
            _logger.warning(
                "flow code has run %.1fs on the event loop's thread without waiting for a task; heavy work belongs in a Python task",
                elapsed,
            )

    # --- flow calls ------------------------------------------------------------

    def _create(self, nxt: _Next) -> asyncio.Task[Any]:
        """Create the Task of `nxt.coro` on the flow loop, as the flow call `nxt` says."""
        self._next = nxt
        try:
            return self._loop.create_task(nxt.coro)
        finally:
            self._next = None

    def _make_task(self, coro: Any, *, name: str | None = None, context: contextvars.Context | None = None) -> asyncio.Task[Any]:
        """`FlowLoop.create_task`: every Task is a new flow call, numbered in its parent (the
        flow call whose code creates it), which creating it puts on record (`_record`)."""
        nxt = self._next if self._next is not None and self._next.coro is coro else None
        self._next = None
        parent = _call.get()
        if nxt is not None and nxt.top:
            parent = None
        if parent is not None:
            parent._ran = True
            self._record(parent)
        code = _code(coro)
        call_id = f"{parent.id}.{next(parent._children)}" if parent is not None else str(next(self._tops))
        call = FlowCall(
            id=call_id,
            parent=parent,
            function=_function(coro, code),
            site=_site(parent) if parent is not None else None,
            frontier=parent.frontier if parent is not None else (),
        )
        call._order = next(self._orders)
        if nxt is not None and nxt.box is not None:  # its clock starts now, with the flow call
            box = nxt.box
            call.time_box = TimeBox(
                deadline_at=time.monotonic() + box.deadline_s,
                deadline_s=box.deadline_s,
                grace_s=box.grace_s,
                slack_s=box.slack_s,
                finishing_kinds=frozenset(box.finishing_kinds),
                flow_call=call.id,
            )
        context = context.copy() if context is not None else contextvars.copy_context()
        context.run(_call.set, call)
        self.calls[call.id] = call
        self._running += 1
        self._made = call
        try:
            self._on_flow_call("create", call)
        except Exception as error:  # the child does not run; the parent receives the error
            coro.close()
            coro = _raise(error)
        if parent is None:  # a top flow call is always on record
            self._record(call)
        call.coro = coro
        task = asyncio.Task(coro, loop=self._loop, name=name, context=context)
        call.task = task
        task.add_done_callback(lambda t, call=call: self._task_done(call, t))
        return task

    def _shows(self, call: FlowCall, state: FlowState, error: BaseException | None) -> bool:
        """Whether the end of `call` is something to see: an error of its own, or the error
        the driver closed it with. A task's outcome that `answer` raised at an await and that
        passed through unchanged is not: the task's own record says it."""
        return error is not None and self._outcomes.get(id(error)) is not error

    def _record(self, call: FlowCall) -> None:
        """Put `call` on record (`on_flow_call("start", call)`), once: at the first thing it
        does that a run shows. Its parent is on record already: creating it put it there."""
        if call.recorded:
            return
        call.recorded = True
        try:
            self._on_flow_call("start", call)
        except Exception:
            _logger.exception("on_flow_call('start') of flow call %s raised", call.id)

    def _task_done(self, call: FlowCall, task: asyncio.Task[Any]) -> None:
        if call.state != "running":
            return
        if task.cancelled():
            self._end(call, "closed", error=call._stopped)
            return
        error = task.exception()
        if error is not None:
            self._end(call, "closed" if call._closing else "raised", error=error)
        else:
            self._end(call, "closed" if call._closing else "returned", value=task.result())

    def _end(self, call: FlowCall, state: FlowState, *, value: Any = None, error: BaseException | None = None) -> None:
        call.state = state
        call.value = value
        call.error = error
        self._running -= 1
        if self._shows(call, state, error):
            self._record(call)
        try:
            self._on_flow_call("end", call)
        except Exception:
            _logger.exception("on_flow_call('end') of flow call %s raised", call.id)
        if call.parent is not None and state != "closed":
            self._receive(call.parent, call.frontier, call._order)
        if state == "closed":
            for key in sorted(call._cancellable):
                self._cancel_unwaited(key)

    def _cancel_unwaited(self, key: str) -> None:
        """Cancel the cancellable task of `key` when the flow call that created it is closed
        and no flow call waits for it: every flow call that waited for it was closed too."""
        creator = self._creators.get(key)
        if creator is None or creator.state != "closed" or key in self.done:
            return
        if any(not fut.done() for fut in self._waiters.get(key, ())):
            return  # a flow call still waits for it
        del self._creators[key]
        if self._queue is not None:
            self._queue.cancel(key)
        else:
            self._to_cancel.append(key)


class _Wait(collections.abc.Coroutine[Any, Any, Any]):
    """What `FlowDriver.wait` returns: a coroutine over the generator of
    `FlowDriver._waiting`, run once, by `await` or by a Task's `send` and `throw`."""

    __slots__ = ("_steps", "_used")

    def __init__(self, steps: Generator[Any, Any, Any]) -> None:
        self._steps = steps
        self._used = False

    def __await__(self) -> Generator[Any, Any, Any]:
        if self._used:
            raise RuntimeError("cannot reuse an awaited FlowDriver.wait(): call wait() again")
        self._used = True
        return self._steps

    def send(self, value: Any) -> Any:
        self._used = True
        return self._steps.send(value)

    def throw(self, typ: Any, val: Any = None, tb: Any = None) -> Any:
        self._used = True
        if val is None and tb is None:
            return self._steps.throw(typ)
        return self._steps.throw(typ, val, tb)  # pyright: ignore[reportCallIssue, reportArgumentType]

    def close(self) -> None:
        self._steps.close()


async def _raise(error: BaseException) -> NoReturn:
    raise error


def _code(coro: Any) -> CodeType | None:
    return getattr(coro, "cr_code", None) or getattr(coro, "gi_code", None)


def _function(coro: Any, code: CodeType | None) -> str:
    frame = getattr(coro, "cr_frame", None) or getattr(coro, "gi_frame", None)
    module = frame.f_globals.get("__name__", "") if frame is not None else ""
    name = code.co_qualname if code is not None else getattr(coro, "__qualname__", type(coro).__name__)
    return f"{module}.{name}" if module else name


def _site(parent: FlowCall) -> tuple[str, int] | None:
    """Where `parent` creates a Task: the innermost frame of flow code on the stack when its
    own code runs (down to the flow loop's drain), else where its coroutine waits (its
    `cr_await` chain)."""
    frame: FrameType | None
    if parent.task is not None and asyncio.current_task() is parent.task:
        frame = inspect.currentframe()
        while frame is not None and frame.f_code is not DRAIN_CODE:
            if flow_code(frame.f_code.co_filename):
                return (frame.f_code.co_filename, frame.f_lineno or frame.f_code.co_firstlineno)
            frame = frame.f_back
        return None
    found = None
    for frame in suspended_frames(parent.coro):
        if flow_code(frame.f_code.co_filename):
            found = (frame.f_code.co_filename, frame.f_lineno or frame.f_code.co_firstlineno)
    return found


def _waits_forever(call: FlowCall) -> str:
    """Why a flow call is closed when nothing will answer what it waits for: where it waits."""
    where = ""
    for frame in suspended_frames(call.coro):
        if flow_code(frame.f_code.co_filename):
            line = frame.f_lineno or frame.f_code.co_firstlineno
            where = f" at {frame.f_code.co_filename}:{line} ({frame.f_code.co_qualname})"
    return (
        f"flow call {call.id} ({call.function}) waits{where} for what nothing will answer: no task is queued or "
        "running and every flow call waits. A flow waits for task calls and flow calls (await, asyncio.gather, "
        f"asyncio.TaskGroup); an asyncio.Event, Queue or future that no flow code completes never ends {_TOPIC}"
    )


def suspended_frames(coro: Any) -> list[FrameType]:
    """The frames of a suspended coroutine and of each coroutine it awaits (its `cr_await`
    chain), outermost first."""
    out: list[FrameType] = []
    seen = 0
    while coro is not None and seen < 1000:
        seen += 1
        frame = getattr(coro, "cr_frame", None) or getattr(coro, "gi_frame", None)
        if frame is None:
            break
        out.append(frame)
        coro = getattr(coro, "cr_await", None) if hasattr(coro, "cr_await") else getattr(coro, "gi_yieldfrom", None)
    return out


def _task_itself(item: Any) -> Task:
    if isinstance(item, Task):
        return item
    raise TypeError(f"FlowDriver.wait() waits for a Task, not {type(item).__name__}")


#: The text of the RuntimeWarning Python gives for a coroutine that was never awaited.
_NEVER_AWAITED = re.compile(r"coroutine '(.+)' was never awaited")


@contextlib.contextmanager
def never_awaited() -> Iterator[list[str]]:
    """Collect, while the block runs, each coroutine that was never awaited (Python's
    RuntimeWarning "coroutine ... was never awaited", given when the coroutine is
    dropped): one line each, naming it and where it was dropped. Those warnings are
    not shown; any other warning is, as before: `warnings.catch_warnings` puts the
    filters and `warnings.showwarning` back after the block."""
    found: list[str] = []
    with warnings.catch_warnings():
        previous = warnings.showwarning

        def show(
            message: Warning | str, category: type[Warning], filename: str, lineno: int, file: Any = None, line: str | None = None
        ) -> None:
            m = _NEVER_AWAITED.search(str(message)) if issubclass(category, RuntimeWarning) else None
            if m is None:
                previous(message, category, filename, lineno, file, line)
                return
            found.append(
                f"coroutine {m.group(1)} was never awaited (dropped at {filename}:{lineno}): "
                f"a call of an async def function runs only when it is awaited; write `await {m.group(1).rpartition('.')[2]}(...)`"
            )

        warnings.filterwarnings("always", message=_NEVER_AWAITED.pattern, category=RuntimeWarning)
        warnings.showwarning = show
        yield found


def driven_here() -> bool:
    """Whether a driver drives the flows of the running event loop (a run runs on it), or
    the running event loop is a driver's flow loop (flow code runs)."""
    return _driver_here() is not None


#: Why a second run cannot start on an event loop that runs one.
SECOND_RUN = (
    "another run drives the flows of this event loop; one event loop runs one run at a time: "
    "await the first run's end, or start this one on an event loop of its own (in another thread)"
)
