"""`FlowDriver`: runs async flows over a `WorkQueue`, one flow call per asyncio Task of flow code.

A flow that waits for outputs is an `async def` function (an async flow). It waits
with `await` on the running event loop; at this level it waits for a `Task` through
`driver.wait`:

    async def flow():
        res = await driver.wait(Task("survey", unit="a"))      # one task: its answer
        found = await asyncio.gather(*[driver.wait(Task("scan", unit=u)) for u in units])
        merged = await asyncio.gather(*[per_unit(u) for u in units])  # flow calls, concurrently
        rest = await helper(res)                                  # the same flow call
        part = await time_box(per_unit(u), deadline_s=600)       # a flow call with its own deadline

A **flow call** is one asyncio Task whose coroutine is flow code (`code.flow_code`): the
top flow passed to `start()` (ids `"0"`, `"1"`, ... in start order), or a Task that flow
code creates (`asyncio.gather` of coroutines, `asyncio.create_task`,
`asyncio.TaskGroup.create_task`, `time_box`), whose id is `"<parent>.<n>"`, numbered
from 1 in creation order within the parent. A Task asyncio makes around an awaitable
that is not flow code (`gather` wrapping what `wait` returns) is no flow call and takes
no number. So the same flow code gives the same ids in every run, whatever order its
tasks finish in. `await helper()` runs in the same flow call. The flow call whose code
runs is a context variable (`current`). Each flow call is reported through
`on_flow_call("start" | "end", call)`; its `state` is `running` until it `returned`,
`raised` or was `closed` (cancelled).

The driver numbers flow calls through a task factory on the event loop
(`loop.set_task_factory`), set by `driving()` for as long as it drives flows and put
back after. One driver drives the flows of one event loop at a time: a second raises
RuntimeError.

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
  result (one future per key, created when it is first awaited).
* A deferred task (`TaskResult.stop == "deferred"`) is answered like any other result
  before `past_grace()`; after it, the waiting flow call is cancelled (closed), and so
  is a parent that awaits it. The tasks a cancelled flow call created are not
  cancelled: they run, as a task nothing awaits does.
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
* `finish()` cancels every flow call still running once the queue has run (recorded
  `closed`).

Flow code runs on the event loop's thread; a step longer than `slow_step_s` (between
two waits of one flow call) is logged. Nothing here knows what a task does or what its
output is: that is `answer`'s business.
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
import sys
import time
import warnings
import weakref
from collections.abc import Awaitable, Callable, Coroutine, Generator, Iterable, Iterator
from dataclasses import dataclass, field, replace
from types import CodeType, FrameType, GeneratorType
from typing import Any, Literal, NoReturn, Protocol, cast

from contraagent._internal.dispatch.code import flow_code, loop_runner
from contraagent._internal.dispatch.entry import run_sync
from contraagent._internal.dispatch.queue import GRACE_S, SLACK_SHARE, WorkQueue
from contraagent._internal.dispatch.task import STOP_DEFERRED, STOP_DUPLICATE_KEY, Task, TaskResult, TimeBox

_logger = logging.getLogger(__name__)

FlowState = Literal["running", "returned", "raised", "closed"]

#: How many event loop iterations in a row with no flow activity end `settle`.
QUIET_ITERATIONS = 3

#: The longest `settle` lets the flow calls run before it returns.
SETTLE_S = 5.0

#: The longest `finish` waits for the flow calls it cancelled to end.
FINISH_S = 5.0

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
    """`on_flow_call(event, call)`: a flow call started (`event` `"start"`) or ended
    (`"end"`, its `state` and `value` or `error` set)."""

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
    raised). `time_box`: its own deadline, when it was started through
    `time_box`; `started_at` (`time.time()`): when it started. `task`: its
    asyncio Task."""

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
    task: asyncio.Task[Any] | None = field(default=None, repr=False)
    #: Its coroutine (the flow code the Task runs).
    coro: Any = field(default=None, repr=False)
    _children: itertools.count = field(default_factory=lambda: itertools.count(1), init=False, repr=False)
    # Its own code ran since it last received a result: the next result starts a new frontier.
    _ran: bool = field(default=False, init=False, repr=False)
    # The results its frontier holds: (order, n, key), the order that of the wait or the
    # child flow call that gave it, so its frontier follows their order, not their timing.
    _received: list[tuple[int, int, str]] = field(default_factory=list, init=False, repr=False)
    # Its place among the waits and flow calls of its parent (creation order).
    _order: int = field(default=0, init=False, repr=False)
    # It is being cancelled by the driver: it ends `closed`, whatever it ends with.
    _closing: bool = field(default=False, init=False, repr=False)


#: The flow call whose code runs.
_call: contextvars.ContextVar[FlowCall | None] = contextvars.ContextVar("contraagent_flow_call", default=None)

#: The driver that drives the flows of each event loop.
_drivers: dict[asyncio.AbstractEventLoop, FlowDriver] = {}


def _driver_here() -> FlowDriver | None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return _drivers.get(loop)


class FlowDriver:
    """Drives flow calls on the running event loop over one `WorkQueue` (see the module
    docstring).

    `run(queue, *flows)` (or `await run_async(queue, *flows)`) is the whole cycle. Wired
    by hand, on the event loop: `with driver.driving():`, `driver.start(flow)` for each
    top flow (a coroutine), `driver.attach(queue)` with `follow_up=driver.follow_up` on
    the queue, `await queue.run_async()`, then `await driver.finish()`.
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
        # Flow events so far (a flow call started or ended, a task added, a wait begun or
        # answered): `settle` runs the event loop until it stops changing.
        self._activity = 0
        self._tops = itertools.count()
        self._running = 0
        self._futures: dict[str, asyncio.Future[TaskResult]] = {}  # by task key
        self._queued_keys: set[str] = set()
        self._outbox: list[Task] = []
        self._queue: WorkQueue | None = None
        self._next: _Next | None = None
        self._made: FlowCall | None = None
        self._previous: Any = None
        self._orders = itertools.count()
        # The place of each Task that is no flow call, created by a flow call's code.
        self._task_order: weakref.WeakKeyDictionary[asyncio.Task[Any], int] = weakref.WeakKeyDictionary()

    # --- the cycle -----------------------------------------------------------

    def run(self, queue: WorkQueue, *flows: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Run `run_async` on a new event loop; the queue's summary. From a thread whose
        event loop is running it raises RuntimeError: await `run_async` there instead."""
        return run_sync(lambda: self.run_async(queue, *flows), called="FlowDriver.run()", instead="await driver.run_async(...)")

    async def run_async(self, queue: WorkQueue, *flows: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Start every flow on the running event loop, run `queue` until no task is queued or
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
        """Drive the flows of the running event loop until the block ends: its task factory
        numbers the flow calls. RuntimeError when another driver drives this event loop's
        flows (one run per event loop at a time)."""
        loop = asyncio.get_running_loop()
        if loop in _drivers:
            raise RuntimeError(SECOND_RUN)
        _drivers[loop] = self
        self._previous = loop.get_task_factory()
        loop.set_task_factory(self._factory)  # pyright: ignore[reportArgumentType]
        try:
            yield self
        finally:
            loop.set_task_factory(self._previous)
            del _drivers[loop]

    def start(self, flow: Coroutine[Any, Any, Any]) -> FlowCall:
        """Start a top flow call: a coroutine of flow code, run as an asyncio Task. Inside
        `driving()`."""
        if isinstance(flow, GeneratorType):
            raise generator_flow_error(flow.__qualname__)
        if not inspect.iscoroutine(flow):
            raise TypeError(f"a flow call is a coroutine (a call of an async def function), not {type(flow).__name__}")
        if _driver_here() is not self:
            flow.close()
            raise RuntimeError("FlowDriver.start() runs inside driving(), on its event loop")
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

    def follow_up(self, result: TaskResult) -> list[Task]:
        """`WorkQueue`'s `follow_up`: record the result and answer what waits for it (the
        flow code runs when the queue next waits). Queues nothing itself: an empty list."""
        key = result.task.key
        if result.stop != STOP_DUPLICATE_KEY:  # the key's own result is still to come
            self.done[key] = result
        fut = self._futures.pop(key, None)
        if fut is not None and not fut.done():
            fut.set_result(result)
        return []

    async def settle(self) -> bool:
        """Let the flow calls run until each waits for a task (or for something else): until
        `QUIET_ITERATIONS` iterations of the event loop in a row see no flow activity, at most
        `SETTLE_S`. Whether a flow call still runs."""
        if not self._running:
            return False
        quiet, end = 0, time.monotonic() + SETTLE_S
        while quiet < QUIET_ITERATIONS and time.monotonic() < end:
            before = self._activity
            await asyncio.sleep(0)
            quiet = quiet + 1 if self._activity == before else 0
        return self._running > 0

    def alive(self) -> bool:
        """Whether a flow call still runs."""
        return self._running > 0

    async def finish(self) -> None:
        """Cancel every flow call still running and let it end (recorded `closed`). The
        tasks they created are not cancelled."""
        rest = [c for c in self.calls.values() if c.state == "running"]
        tasks = [c.task for c in rest if c.task is not None and not c.task.done()]
        for call in rest:
            call._closing = True
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=FINISH_S)
        for call in rest:
            if call.state == "running":  # it would not end
                self._end(call, "closed")

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

    # --- tasks -----------------------------------------------------------------

    def add(self, task: Task) -> None:
        """Queue a task the flow code created, held to the time boxes of the flow call that
        created it (before `attach`, it waits for the queue)."""
        call = _call.get()
        self._activity += 1
        if call is not None:
            call._ran = True
        self._enqueue(task, call)

    async def wait(self, item: Any) -> Any:
        """Wait for the task `waits_for(item)` gives (queued when it is not yet) to finish;
        `answer(item, result)`. Past `past_grace()` a deferred task cancels the flow call
        that waits (CancelledError)."""
        task = self._waits_for(item)
        call = _call.get()
        here = asyncio.current_task()
        own = call is not None and here is call.task
        order = self._task_order.get(here, -1) if not own and here is not None else -1
        order = order if order >= 0 else next(self._orders)
        self._activity += 1
        if own and call is not None:
            call._ran = True
        key = task.key
        result = self.done.get(key)
        if result is None:
            fut = self._futures.get(key)
            if fut is None:
                fut = self._futures[key] = asyncio.get_running_loop().create_future()
            self._enqueue(task, call)  # a key the queue refuses answers `fut` at once
            result = await asyncio.shield(fut)
            self._activity += 1
        if result.stop == STOP_DEFERRED and self.past_grace is not None and self.past_grace() and call is not None:
            self._cancel(call, own)
        if call is not None:
            self._receive(call, (key,), order)
        return self._answer(item, result)

    def _enqueue(self, task: Task, call: FlowCall | None) -> None:
        if task.key in self._queued_keys or task.key in self.done:
            return
        boxes = self.time_boxes(call)
        if boxes and not task.time_boxes:
            task = replace(task, time_boxes=boxes)
        self._queued_keys.add(task.key)
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
        call._received += [(order, i, key) for i, key in enumerate(keys)]
        call.frontier = tuple(dict.fromkeys(key for _, _, key in sorted(call._received)))

    def _stepped(self, call: FlowCall, elapsed: float) -> None:
        """One step of `call`'s code ran for `elapsed` seconds: logged past `slow_step_s`."""
        if elapsed > self.slow_step_s:
            _logger.warning(
                "flow call %s (%s) ran %.1fs between two waits on the event loop's thread; heavy work belongs in a Python task",
                call.id,
                call.function,
                elapsed,
            )

    # --- flow calls ------------------------------------------------------------

    def _create(self, nxt: _Next) -> asyncio.Task[Any]:
        """Create the Task of `nxt.coro` through the event loop, so its task factory makes
        it the flow call `nxt` says."""
        self._next = nxt
        try:
            return asyncio.get_running_loop().create_task(nxt.coro)
        finally:
            self._next = None

    def _factory(self, loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any) -> asyncio.Future[Any]:
        """The event loop's task factory while the driver drives it: a Task of flow code
        created in a flow call is a new flow call; any other Task is made as before."""
        nxt = self._next if self._next is not None and self._next.coro is coro else None
        self._next = None
        parent = _call.get()
        if parent is not None:
            parent._ran = True
            self._activity += 1
        code = _code(coro)
        is_flow = nxt is not None or (parent is not None and code is not None and flow_code(code.co_filename))
        if not is_flow:
            made = self._previous(loop, coro, **kwargs) if self._previous is not None else asyncio.Task(coro, loop=loop, **kwargs)
            if parent is not None and isinstance(made, asyncio.Task):  # a wait it runs has this place
                self._task_order[made] = next(self._orders)
            return made
        if nxt is not None and nxt.top:
            parent = None
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
        given = kwargs.pop("context", None)
        kwargs.pop("eager_start", None)  # its code runs once it is numbered, on the loop's next turn
        context = given.copy() if given is not None else contextvars.copy_context()
        context.run(_call.set, call)
        self.calls[call.id] = call
        self._running += 1
        self._activity += 1
        self._made = call
        try:
            self._on_flow_call("start", call)
        except Exception as error:  # the child does not run; the parent receives the error
            coro.close()
            coro = _raise(error)
        call.coro = coro
        task = asyncio.Task(_Timed(coro, lambda elapsed: self._stepped(call, elapsed)), loop=loop, context=context, **kwargs)
        call.task = task
        task.add_done_callback(lambda t, call=call: self._task_done(call, t))
        return task

    def _task_done(self, call: FlowCall, task: asyncio.Task[Any]) -> None:
        if call.state != "running":
            return
        if task.cancelled():
            self._end(call, "closed")
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
        self._activity += 1
        try:
            self._on_flow_call("end", call)
        except Exception:
            _logger.exception("on_flow_call('end') of flow call %s raised", call.id)
        if call.parent is not None and state != "closed":
            self._receive(call.parent, call.frontier, call._order)
        if self._queue is not None:
            self._queue.wake()


async def _raise(error: BaseException) -> NoReturn:
    raise error


class _Timed(collections.abc.Coroutine[Any, Any, Any]):
    """`coro`, run by a Task step by step, giving `stepped` how long each step ran: from a
    resumption to the next suspension, or to its end."""

    def __init__(self, coro: Coroutine[Any, Any, Any], stepped: Callable[[float], None]) -> None:
        self._coro, self._stepped = coro, stepped

    def send(self, value: Any) -> Any:
        start = time.monotonic()
        try:
            return self._coro.send(value)
        finally:
            self._stepped(time.monotonic() - start)

    def throw(self, typ: Any, val: Any = None, tb: Any = None) -> Any:
        start = time.monotonic()
        try:
            if val is None and tb is None:
                return self._coro.throw(typ)
            return self._coro.throw(typ, val, tb)  # pyright: ignore[reportCallIssue, reportArgumentType]
        finally:
            self._stepped(time.monotonic() - start)

    def close(self) -> None:
        self._coro.close()

    def __await__(self) -> Generator[Any, None, Any]:
        return self._coro.__await__()


def _code(coro: Any) -> CodeType | None:
    return getattr(coro, "cr_code", None) or getattr(coro, "gi_code", None)


def _function(coro: Any, code: CodeType | None) -> str:
    frame = getattr(coro, "cr_frame", None) or getattr(coro, "gi_frame", None)
    module = frame.f_globals.get("__name__", "") if frame is not None else ""
    name = code.co_qualname if code is not None else getattr(coro, "__qualname__", type(coro).__name__)
    return f"{module}.{name}" if module else name


def _site(parent: FlowCall) -> tuple[str, int] | None:
    """Where `parent` creates a Task: the innermost frame of flow code on the stack when its
    own code runs, else where its coroutine waits (its `cr_await` chain)."""
    frame: FrameType | None
    if parent.task is not None and asyncio.current_task() is parent.task:
        frame = sys._getframe(2)
        while frame is not None and not loop_runner(frame):
            if flow_code(frame.f_code.co_filename):
                return (frame.f_code.co_filename, frame.f_lineno or frame.f_code.co_firstlineno)
            frame = frame.f_back
        return None
    found = None
    for frame in suspended_frames(parent.coro):
        if flow_code(frame.f_code.co_filename):
            found = (frame.f_code.co_filename, frame.f_lineno or frame.f_code.co_firstlineno)
    return found


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
    not shown; any other warning is, as before."""
    found: list[str] = []
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
    entry = warnings.filters[0]
    warnings.showwarning = show
    try:
        yield found
    finally:
        if warnings.showwarning is show:
            warnings.showwarning = previous
        with contextlib.suppress(ValueError):
            cast(list[Any], warnings.filters).remove(entry)
            mutated = getattr(warnings, "_filters_mutated", None)
            if mutated is not None:
                mutated()


def driven_here() -> bool:
    """Whether a driver drives the flows of the running event loop (a run runs on it)."""
    return _driver_here() is not None


#: Why a second run cannot start on an event loop that runs one.
SECOND_RUN = (
    "another run drives the flows of this event loop; one event loop runs one run at a time: "
    "await the first run's end, or start this one on an event loop of its own (in another thread)"
)
