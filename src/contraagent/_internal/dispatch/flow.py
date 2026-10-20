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
`running` until it `returned`, `raised` or was `closed` (cancelled). Its frontier
reaches the flow call that awaits it when it ends, on record or not.

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
turn. That is the flows' quiescence, exact by construction. `follow_up` only keeps a
result. The drain gives the kept results to the flow code one at a time, in the order
they came, and after each one lets the flow calls run until every one waits again. So
the steps of the flow calls run in the order the results are given, whatever thread or
callback of the event loop ran meanwhile, and every step follows from one result. On
a resume (`replay`), the results of skipped tasks are given before the results of tasks
that ran, and of those that have come, the one the journal of the run's earlier attempts
recorded first is given first. So a flow whose code depends on the order its tasks
finish in (`as_completed`, a list it appends to as each await returns) takes on a
resume the path it took. A
clock, a thread or I/O that flow code asks the flow loop for raises TypeError at its
`await`; a future of another event loop raises asyncio's RuntimeError there.

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
* `holds(value) -> keys`: the keys of the tasks whose results `value`, what a flow call
  returned, holds (a typed layer's references to tasks). Default: none.

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
* A flow call's `frontier`, the created from of each task it creates, is the keys of the
  results that reached the flow call since its previous resume, up to its last one. A
  result reaches a flow call when a callback of the flow loop runs for it in that flow
  call: the step that resumes it after a task it awaits, a done callback of a `gather`
  or `TaskGroup` it awaits, or the step that resumes it when a flow call it awaits
  ends, which brings that flow call's frontier. An await of a result given before
  resumes it at once, by that key. So a `gather` gives the union of its items, an
  awaited child flow call its frontier when it ended, a child starts with its parent's,
  and the results of a task or a flow call that nothing awaits reach no one. Awaiting a
  flow call that has already ended does not suspend; it resumes the flow call at once,
  by that flow call's frontier, as an await of a result given before does: its Task, a
  `FlowTask`, tells the driver when flow code gets its value (`await`, and `result()`,
  which `gather` calls on an item that has ended). The keys are
  listed by the flow call that queued each (by id), then in the order it queued them:
  so a flow whose code does not depend on the order its tasks finish in gives the same
  frontiers in every order. How the driver finds them: each callback of the flow loop
  carries the keys that led to it (`FlowLoop`'s cause); a step of a flow call is a
  callback in the context its Task runs every step in (`Task.get_context()`), and every
  other callback in a flow call runs in a copy of that context.
* The queue does not end while a flow call runs (`settle`, its `between_passes`): it
  waits for the tasks the flow calls create, within the run's deadline.
* A failure stops only the code that needed it (keep going). A task that did not
  succeed raises at the `await` of each flow call that waits for it; the exception
  ends that flow call unless its code catches it, and is raised again where a parent
  awaits the flow call (`asyncio.gather` without `return_exceptions`, `await task`),
  and so on up. Nothing else is cancelled: `gather` leaves its other items running,
  and the tasks already queued or running finish. A parent that ends, returned or
  raised, does not close its children: they go on, and the run waits for every flow
  call. Only an `asyncio.TaskGroup` cancels its other flow calls at a failure (they
  end `closed`); the tasks they created still run to their end. A flow call that
  `raised` records where (`FlowCall.raised_at`) and because of which failed task
  (`FlowCall.raised_by`). An exception of flow code's own (not a task's outcome) is a
  flow error wherever a parent catches it (`flow_errors()`).
* A flow call that still waits once the flows are quiescent, while no task the driver
  queued is still to give its result, waits for what nothing will answer (an
  `asyncio.Event` nobody sets, a `Queue` nobody fills): `settle` closes it, its `error`
  a RuntimeError that names where it waits.
* `finish()` cancels every flow call still running once the queue has run (recorded
  `closed`), and every other Task on the flow loop.
* An unawaited task is one the flow code created and never used: no flow call awaited
  it (`wait`), no task waits for it (`Task.after`), and no flow call returned it
  (`holds`). It runs all the same: this is information, never an error. A top flow
  call lists the unawaited tasks created in it or in the flow calls it started
  (`FlowCall.unawaited`), once every one of them has ended: so its `"end"` comes
  through `on_flow_call` when the last flow call it started ended, if that is after
  it (its `ended_at` says when it ended itself). For a flow that does not wait,
  `unawaited(value)` lists them.

Flow code runs on the thread of the event loop that drives it; a callback of the flow
loop longer than `slow_step_s` (a step of one flow call between two waits) is logged,
and so is a drain that runs that long in all; contraagent's own work in the step (a task
call, a flow call's creation) is not counted (`FlowLoop`, `not_flow_code`). Nothing here knows what a task does or
what its output is: that is `answer`'s business.
"""

from __future__ import annotations

import asyncio
import collections
import collections.abc
import contextlib
import contextvars
import heapq
import inspect
import itertools
import logging
import re
import sys
import time
import warnings
from collections.abc import Awaitable, Callable, Coroutine, Generator, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from types import CodeType, FrameType, GeneratorType, TracebackType
from typing import Any, Literal, NoReturn, Protocol

from contraagent._internal.dispatch.code import contraagent_file, flow_code
from contraagent._internal.dispatch.entry import run_sync
from contraagent._internal.dispatch.flowloop import DRAIN_CODE, Cause, FlowLoop, FlowTask
from contraagent._internal.dispatch.queue import GRACE_S, SLACK_SHARE, WorkQueue
from contraagent._internal.dispatch.records import Frame
from contraagent._internal.dispatch.task import STOP_DEFERRED, STOP_DUPLICATE_KEY, STOP_SKIPPED, Task, TaskResult, TimeBox

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


class Holds(Protocol):
    """`holds(value)`: the keys of the tasks whose results `value`, what a flow call
    returned, holds; by default none."""

    def __call__(self, value: Any, /) -> Iterable[str]: ...


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
    `frontier`: the keys of the results that resumed it last (see the module docstring).
    `value`: what it returned; `error`: what it raised (or what cancelling it
    raised, or, for one closed because it waited for what nothing would answer,
    the RuntimeError that says where it waited). For one that `raised`, `raised_at` is
    where the exception left its own code (the innermost frame of flow code of its own
    coroutine and the functions it awaited in it: mostly the line of the `await` that
    failed), and `raised_by` the key of the failed task the exception is (`TaskFailed.key`,
    the first one in an exception group), the same key in every flow call it passes
    through; None for an exception of flow code's own. `time_box`: its own deadline,
    when it was started through `time_box`; `started_at` (`time.time()`): when it
    started. `recorded`: whether it is on record (`on_flow_call("start")` came:
    see the module docstring). `task`: its asyncio Task. `ended_at` (`time.time()`): when
    it ended, None while it runs. `unawaited`: for a top flow call whose flow calls have
    all ended, the keys of the unawaited tasks created in it or in the flow calls it
    started, in the order they were created (see the module docstring)."""

    id: str
    parent: FlowCall | None = field(default=None, repr=False)
    function: str = ""
    site: tuple[str, int] | None = None
    state: FlowState = "running"
    frontier: tuple[str, ...] = ()
    value: Any = field(default=None, repr=False)
    error: BaseException | None = None
    raised_at: Frame | None = None
    raised_by: str | None = None
    time_box: TimeBox | None = None
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    unawaited: tuple[str, ...] = ()
    recorded: bool = False
    task: asyncio.Task[Any] | None = field(default=None, repr=False)
    #: Its coroutine (the flow code the Task runs).
    coro: Any = field(default=None, repr=False)
    _children: itertools.count = field(default_factory=lambda: itertools.count(1), init=False, repr=False)
    # Its children that ended `raised`, in the order they ended: where an exception it ends
    # with came from (`FlowDriver._raised_at`).
    _raised_children: list[FlowCall] = field(default_factory=list, init=False, repr=False)
    # The length of the traceback of the exception it ended `raised` with, then.
    _traceback_len: int = field(default=0, init=False, repr=False)
    # It ended `raised` with an exception of flow code's own, the first flow call to end with
    # it: a flow error (`FlowDriver.flow_errors`).
    _own_error: bool = field(default=False, init=False, repr=False)
    # How many tasks it queued.
    _queued: itertools.count = field(default_factory=itertools.count, init=False, repr=False)
    # The context its Task runs every step in.
    _context: contextvars.Context | None = field(default=None, init=False, repr=False)
    # The keys of the results that reached it since it last resumed, in the order they came.
    _reached: dict[str, None] = field(default_factory=dict[str, None], init=False, repr=False)
    # The keys of every result that reached it, its parent's when it was created, and what the
    # flow calls whose end it awaited had received (`FlowDriver.received`).
    _received: set[str] = field(default_factory=set[str], init=False, repr=False)
    # It is being cancelled by the driver: it ends `closed`, whatever it ends with.
    _closing: bool = field(default=False, init=False, repr=False)
    # Why the driver closes it, when it waits for what nothing answers: its `error` then.
    _stopped: BaseException | None = field(default=None, init=False, repr=False)
    # The keys of the cancellable tasks it created or waited for (`Task.cancellable`).
    _cancellable: set[str] = field(default_factory=set, init=False, repr=False)
    # The top flow call it was started in (itself for a top flow call).
    _top: FlowCall | None = field(default=None, init=False, repr=False)
    # For a top flow call: how many of the flow calls started in it (itself included) run.
    _tree: int = field(default=0, init=False, repr=False)


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

    `replay`, on a resume: each task key's place in the journal of the run's earlier
    attempts (the index of its last journal row); the results of skipped tasks are given
    to the flow code in that order (see the module docstring).
    """

    def __init__(
        self,
        *,
        waits_for: WaitsFor | None = None,
        answer: Answer | None = None,
        on_flow_call: OnFlowCall | None = None,
        holds: Holds | None = None,
        past_grace: Callable[[], bool] | None = None,
        slow_step_s: float = 1.0,
        replay: Mapping[str, int] | None = None,
    ) -> None:
        self._waits_for = waits_for or _task_itself
        self._answer = answer or (lambda item, result: result)
        self._on_flow_call = on_flow_call or (lambda event, call: None)
        self._holds: Holds = holds or (lambda value: ())
        #: Whether the queue is past its grace window; `attach()` sets the queue's
        #: `past_hard_stop` when none is given.
        self.past_grace: Callable[[], bool] | None = past_grace
        self.slow_step_s = slow_step_s
        # Each key's place in the journal of the run's earlier attempts: the order in which the
        # results of skipped tasks are given (see the module docstring).
        self._replay: Mapping[str, int] = replay or {}
        #: Every flow call, by id, in start order.
        self.calls: dict[str, FlowCall] = {}
        #: Every result seen, by task key.
        self.done: dict[str, TaskResult] = {}
        # The event loop flow code runs on.
        self._loop = FlowLoop(make_task=self._make_task, on_run=self._on_run, on_slow=self._slow, slow_s=slow_step_s)
        self._tops = itertools.count()
        self._running = 0
        self._waiters: dict[str, list[asyncio.Future[TaskResult]]] = {}  # by task key, one per await
        # Each key the driver queued: its place, the id of the flow call that queued it (as
        # numbers) and how many that flow call had queued before, the same in every run.
        self._queued_keys: dict[str, tuple[tuple[int, ...], int]] = {}
        self._open: set[str] = set()  # keys queued whose result has not come
        # The cancellable tasks whose result has not come, by key: the flow call that created each.
        self._creators: dict[str, FlowCall] = {}
        # The keys to cancel as the queue is attached: closed before it was.
        self._to_cancel: list[str] = []
        # What `answer` raised at an await, by id (kept alive): a task's outcome, not a flow call's own.
        self._outcomes: dict[int, BaseException] = {}
        # The flow calls that ended `raised` with an exception of flow code's own, the first
        # to end with it, in the order they ended.
        self._own_errors: list[FlowCall] = []
        self._outbox: list[Task] = []
        # The results not yet given to the flow code, in the order they came.
        self._results: collections.deque[TaskResult] = collections.deque()
        # The results of skipped tasks not yet given, by their key's place in `replay`.
        self._replayed: list[tuple[int, int, TaskResult]] = []
        self._arrived = itertools.count()
        self._queue: WorkQueue | None = None
        self._main: asyncio.AbstractEventLoop | None = None
        self._driving = False
        self._wake_due = False
        self._next: _Next | None = None
        self._made: FlowCall | None = None
        # The flow call whose step the flow loop runs now (a callback in its own context).
        self._step: FlowCall | None = None
        # The keys of the tasks created under each top flow call (by id; "" for a flow that
        # does not wait), in creation order, and the keys of those used (see `unawaited`).
        self._created: dict[str, dict[str, None]] = {}
        self._used: set[str] = set()

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
        """`WorkQueue`'s `follow_up`: keep the result for the flow code, which receives it at
        the next drain, when the queue next settles (one result at a time, in the order they
        came; a skipped task's on a resume, in the order of `replay`). Queues nothing itself:
        an empty list."""
        place = self._replay.get(result.task.key) if result.stop == STOP_SKIPPED else None
        if place is not None:
            heapq.heappush(self._replayed, (place, next(self._arrived), result))
        else:
            self._results.append(result)
        if self._waiters.get(result.task.key) and self._queue is not None and self._main is not None and not self._wake_due:
            # A wait of the queue that has begun ends, so that the next pass settles.
            self._wake_due = True
            self._main.call_soon(self._wake_queue)
        return []

    def _give(self, result: TaskResult) -> None:
        """Give one result to the flow code: record it and complete the futures that wait for
        it, their callbacks caused by its key."""
        key = result.task.key
        if result.stop != STOP_DUPLICATE_KEY:  # the key's own result is still to come
            self.done[key] = result
            self._open.discard(key)
            self._creators.pop(key, None)
        with self._loop.caused_by(_Led((key,), frozenset((key,)))):
            for fut in self._waiters.pop(key, ()):
                if not fut.done():  # one whose flow call was cancelled is done
                    fut.set_result(result)

    def _run_flows(self) -> None:
        """Let the flow code run until it waits, then give it the results that came, one at a
        time, letting it run until it waits again after each."""
        self._loop.drain()
        while self._replayed or self._results:
            self._give(heapq.heappop(self._replayed)[2] if self._replayed else self._results.popleft())
            self._loop.drain()

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
        self._run_flows()
        if self._close_stuck():
            self._run_flows()
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
        self._run_flows()
        self._close_rest()

    def unawaited(self, value: Any = None) -> tuple[str, ...]:
        """For a flow that does not wait (it ran in no flow call) and returned `value`: the
        keys of the tasks it created that no task waits for (`Task.after`) and `value` does
        not hold (`holds`), in the order it created them."""
        self._used.update(self._holds(value))
        return self._unused("")

    def _unused(self, top: str) -> tuple[str, ...]:
        return tuple(key for key in self._created.get(top, {}) if key not in self._used)

    def received(self, call: FlowCall | None) -> frozenset[str]:
        """The keys of the results that reached `call` (its causal past): every result that
        resumed it or reached it in a callback (as for its frontier, but from its start, not
        only its last resume), what its parent had received when it created `call`, and what
        each flow call whose end `call` observed (awaited directly, through `gather` or a
        `TaskGroup`, or in a done callback in its context) had received, whether it was
        still running or had already ended when `call` got its value (`FlowTask`). A flow
        call it started and never awaited gives it nothing. With no flow call (a flow that does not
        wait), every result given so far."""
        if call is None:
            return frozenset(self.done)
        return frozenset(call._received)

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
        """Run the flows (`_run_flows`) from a plain callback of the running event loop (from
        Python 3.14 a drain inside a Task step raises), and wait for it to end."""
        if not self._loop.ready() and not self._results and not self._replayed:
            return
        main = asyncio.get_running_loop()
        ended: asyncio.Future[None] = main.create_future()

        def drain() -> None:
            try:
                self._run_flows()
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
        if not self._running or self._loop.ready() or self._results or self._replayed or self._open:
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
            self._record(call)
            if task.cancellable and task.key not in self.done and task.key not in self._creators:
                self._creators[task.key] = call
                call._cancellable.add(task.key)
        top = call._top.id if call is not None and call._top is not None else ""
        self._created.setdefault(top, {})[task.key] = None
        self._used.update(task.after)
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
        key = task.key
        self._used.add(key)
        result = self.done.get(key)
        if call is not None and key in self._creators:
            call._cancellable.add(key)
        if result is not None and call is not None:  # given before: a resume by its key, at once
            call.frontier, call._reached = (key,), {}
            call._received.add(key)
            self._loop.set_cause(_Led(call.frontier, frozenset(call._received)))
        if result is None:
            fut: asyncio.Future[TaskResult] = self._loop.create_future()
            self._waiters.setdefault(key, []).append(fut)
            self._enqueue(task, call)  # a key the queue refuses answers `fut` at once
            result = yield from fut.__await__()
        if result.stop == STOP_DEFERRED and self.past_grace is not None and self.past_grace() and call is not None:
            self._cancel(call, own)
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
        self._queued_keys[task.key] = (
            (tuple(int(n) for n in call.id.split(".")), next(call._queued)) if call is not None else ((), len(self._queued_keys))
        )
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

    def _on_run(self, context: contextvars.Context, cause: Cause) -> Cause:
        """`FlowLoop`'s `on_run`: what led to the callback (a `_Led`) reaches the flow call the
        callback runs in: its keys reach its frontier, its past what the flow call received. A
        callback in the flow call's own context is a step of it: it resumes, its frontier
        becomes what reached it, and what the step schedules is led by its frontier and all it
        received."""
        call = context.get(_call)
        self._step = call if call is not None and context is call._context else None
        if call is None:
            return cause
        led = cause if isinstance(cause, _Led) else _Led()
        call._reached.update(dict.fromkeys(led.keys))
        call._received |= led.past
        if context is call._context:  # its Task runs every step in this context, and nothing else does
            last = ((sys.maxsize,), 0)  # a key queued elsewhere: after, in the order it came
            call.frontier = tuple(sorted(call._reached, key=lambda key: self._queued_keys.get(key, last)))
            call._reached = {}
            return _Led(call.frontier, frozenset(call._received))
        return cause

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
        if parent is not None:  # what its parent had received is what it can be given
            call._received = set(parent._received)
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
        call._top = parent._top if parent is not None else call
        if call._top is not None:
            call._top._tree += 1
        self._made = call
        try:
            self._on_flow_call("create", call)
        except Exception as error:  # the child does not run; the parent receives the error
            coro.close()
            coro = _raise(error)
        if parent is None:  # a top flow call is always on record
            self._record(call)
        call.coro = coro
        call._context = context
        task = FlowTask(
            coro, loop=self._loop, name=name, context=context, observed=lambda t, at_once, call=call: self._observe(call, at_once)
        )
        call.task = task
        # In an empty context: the driver's own callback reaches no flow call.
        task.add_done_callback(lambda t, call=call: self._task_done(call, t), context=contextvars.Context())
        return task

    def _shows(self, call: FlowCall, state: FlowState, error: BaseException | None) -> bool:
        """Whether the end of `call` is something to see: an error of its own, or the error
        the driver closed it with. A task's outcome that `answer` raised at an await and that
        passed through unchanged is not: the task's own record says it."""
        return error is not None and self._outcomes.get(id(error)) is not error

    def _raised_at(self, call: FlowCall, error: BaseException) -> Frame | None:
        """Where `error` left the code of `call`, which ends with it: the innermost frame
        of flow code in its traceback, above contraagent's own code (a task call's `await`,
        the driver) and before the frames of the child flow call it came from.

        An exception that passes from a child flow call to its parent keeps the child's
        traceback after the parent's own frames (a Task's exception is raised again at its
        `await` with the traceback it ended with). So each flow call that ends `raised`
        keeps the length of that traceback on its own record (`_traceback_len`), and its
        parent, which ends with the same exception object, leaves out that many frames from
        the end. The child is found among the parent's own children that ended `raised`
        (`_raised_children`), not through a map from exceptions: the records hold what they
        are about, and nothing is keyed by an object's identity. An exception that came from
        a flow call that is not a child (a Task its sibling created) is read whole."""
        entries: list[TracebackType] = []
        tb = error.__traceback__
        while tb is not None:
            entries.append(tb)
            tb = tb.tb_next
        call._traceback_len = len(entries)
        own = entries
        child = next((c for c in reversed(call._raised_children) if c.error is error), None)
        if child is not None and child._traceback_len < len(entries):
            own = entries[: len(entries) - child._traceback_len]
        found = None
        for tb in own:
            code = tb.tb_frame.f_code
            if contraagent_file(code.co_filename):  # a task call's await, the driver: below flow code
                break
            if flow_code(code.co_filename):
                module = tb.tb_frame.f_globals.get("__name__", "")
                function = f"{module}.{code.co_qualname}" if module else code.co_qualname
                found = Frame(function=function, file=code.co_filename, line=tb.tb_lineno or code.co_firstlineno)
        return found

    def _own(self, error: BaseException) -> bool:
        """Whether `error` is an exception of flow code's own: not what `answer` raised at an
        await of a task (a `TaskFailed`, a `TaskDeferred`); an exception group is when any
        exception in it is."""
        if isinstance(error, BaseExceptionGroup):
            return any(self._own(inner) for inner in error.exceptions)
        return self._outcomes.get(id(error)) is not error

    def flow_errors(self) -> list[FlowCall]:
        """The flow errors, one per exception, in creation order: each flow call that raised
        an exception of flow code's own (not a task's `TaskFailed` or `TaskDeferred` passing
        through), the first to end with it, whether or not a parent caught it
        (`asyncio.gather(..., return_exceptions=True)`); and each top flow call that raised
        any other exception, or was closed with an error (it waited for what nothing would
        answer). An exception of flow code's own is a bug or a broken rule
        (`TooManyPasses`), never an outcome to tolerate. One that reached a top flow call is
        listed once, for the flow call it started in, whose `raised_at` is where."""
        return [
            c
            for c in self.calls.values()
            if c._own_error
            or (
                c.parent is None
                and c.error is not None
                and c.state != "returned"
                and not any(own.error is c.error for own in self._own_errors)
            )
        ]

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
        call.ended_at = time.time()
        if state == "returned":
            try:
                self._used.update(self._holds(value))
            except Exception:
                _logger.exception("holds() of what flow call %s returned raised", call.id)
        if state == "raised" and error is not None:
            call.raised_at = self._raised_at(call, error)
            call.raised_by = failed_key(error)
            if call.parent is not None:
                call.parent._raised_children.append(call)
            if self._own(error) and not any(c.error is error for c in self._own_errors):
                call._own_error = True
                self._own_errors.append(call)
        self._running -= 1
        if self._shows(call, state, error):
            self._record(call)
        top = call._top
        if top is not None:
            top._tree -= 1
        if call is not top:
            self._ended(call)
        if top is not None and top._tree == 0 and top.state != "running":
            top.unawaited = self._unused(top.id)
            self._ended(top)
        if state == "closed":
            for key in sorted(call._cancellable):
                self._cancel_unwaited(key)

    def _observe(self, child: FlowCall, at_once: bool) -> None:
        """Flow code got the value of `child`, a flow call that ended (`FlowTask`): what
        `child` had received reaches the flow call whose code runs, and so does its frontier
        when nothing else brings it. An `await` of a child that had ended before it does not
        resume the flow call: as an await of a result given before, it resumes it at once,
        by the child's frontier. `gather` collecting the child's value in a done callback
        brings its frontier to the next resume; `gather` of items that had all ended collects
        them in the step that calls it, and their frontiers join the flow call's at once. In
        a step that a callback of the child resumed, the cause already brought both."""
        call = _call.get()
        if call is None or call is child:
            return
        call._received |= child._received
        if self._step is not call:  # a callback in its context: the next resume brings it
            call._reached.update(dict.fromkeys(child.frontier))
            return
        if at_once:  # an await that did not suspend: a resume by the child's end, at once
            call.frontier, call._reached = child.frontier, {}
        else:  # got in a step without a resume (`gather` of items that had all ended), or one that brought it
            last = ((sys.maxsize,), 0)
            call.frontier = tuple(sorted({*call.frontier, *child.frontier}, key=lambda key: self._queued_keys.get(key, last)))
        self._loop.set_cause(_Led(call.frontier, frozenset(call._received)))

    def _ended(self, call: FlowCall) -> None:
        try:
            self._on_flow_call("end", call)
        except Exception:
            _logger.exception("on_flow_call('end') of flow call %s raised", call.id)

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


@dataclass(frozen=True)
class _Led:
    """What led to a callback of the flow loop (its `Cause`): `keys`, the results that reached
    it, which make the frontier of the flow call it resumes; `past`, every result that had
    reached the flow call whose step scheduled it (`FlowDriver.received`)."""

    keys: tuple[str, ...] = ()
    past: frozenset[str] = frozenset()


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


def failed_key(error: BaseException) -> str | None:
    """The key of the failed task `error` is: a `TaskFailed`'s (a `TaskDeferred`'s too), or
    the first one's in an exception group (an `asyncio.TaskGroup`'s), depth first; None for
    any other exception."""
    if isinstance(error, TaskFailed):
        return error.key
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            key = failed_key(inner)
            if key is not None:
                return key
    return None


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
