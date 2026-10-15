"""`FlowDriver`: runs generator flows over a `WorkQueue`, one flow call per generator.

A flow written as a generator yields what it waits for and receives the
answer at the `yield`:

    def flow():
        res = yield Task("survey", unit="a")             # one item: its answer
        results = yield [Task("scan", unit=u) for u in units]  # a batch: answers in order
        merged = yield [per_unit(u) for u in units]      # generators: flow calls, concurrently
        rest = yield from helper(res)                    # the same flow call
        part = yield time_box(per_unit(u), deadline_s=600)  # a flow call with its own deadline

A **flow call** is one generator the driver runs: the top flow passed to
`start()` (ids `"0"`, `"1"`, ... in start order), or a generator yielded by
another flow call (`"<parent>.<n>"`, numbered from 1 in yield order), so the
same flow code gives the same ids in every run. Each is reported through
`on_flow_call("start" | "end", call)`; its `state` is `running` until it
`returned`, `raised` or was `closed`.

What a yield means is set by four callbacks, so a typed layer plugs in
without changing the driver:

* `waits_for(item) -> Task`: the task a yielded item waits for. Default:
  the item itself, which must be a `Task`.
* `answer(item, result) -> value`: what the flow receives for a finished
  task; an exception it raises is thrown into the flow at the `yield`.
  Default: the `TaskResult` itself. `result_or_raise` raises `TaskFailed` /
  `TaskDeferred` instead of answering a result that is not ok.
* `created() -> list[Task]`: tasks created while a flow call's code ran
  (queued whether or not it yields them), read after every step. `current`
  is that flow call while its code runs. Default: none.
* `on_flow_call(event, call)`: a flow call started or ended. An exception
  it raises at a child's start fails the child before its code runs: the
  child ends `raised` with it, and the parent receives it at its `yield`.

Rules:

* A yielded item is a list or tuple (a batch), a generator (a child flow
  call), or anything `waits_for` accepts. A batch item may itself be a
  generator. A batch waits for every item, then sends the answers in order;
  if any item's answer is an exception (a failed task under
  `result_or_raise`, or a child flow call that raised), the first by position
  is thrown instead.
* `done[key]` holds every result the driver has seen: a task whose key is
  done is answered at once, without queueing it again; tasks with the same
  key wait for one result.
* A deferred task (`TaskResult.stop == "deferred"`) is answered like any
  other result before `past_grace()`; after it, the waiting flow call is
  closed (`GeneratorExit` at its `yield`), and so is a parent waiting on it.
* A **time box** (`time_box(generator, deadline_s=, ...)`, yielded like the
  generator it wraps) is a flow call with a deadline of its own, counted from
  that flow call's start: every task created in it, or in a flow call it
  starts, carries its `TimeBox` (`Task.time_boxes`, outermost first), and the
  queue holds the task to it as to the run's own deadline (`WorkQueue`). A
  task it defers is answered at its `yield` like any other deferral
  (`TaskDeferred`), so the flow call, or its parent, goes on past it.
* A flow call's `frontier` is the keys whose results it received when it
  was last resumed: a batch gives the union of its items (a child flow call
  contributes its own last frontier); a child starts with its parent's.
* Steps run from one work list, never recursively: a thousand child flow
  calls cost no stack.
* `finish()` closes every flow call still suspended once the queue has run
  (recorded `closed`).

Flow code runs on the scheduler's thread inside `follow_up`; a step longer
than `slow_step_s` is logged. Nothing here knows what a task does or what
its output is: that is `answer`'s business.
"""

from __future__ import annotations

import inspect
import itertools
import logging
import time
from collections import deque
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass, field, replace
from types import GeneratorType
from typing import Any, Literal

from contraagent._internal.dispatch.queue import GRACE_S, SLACK_SHARE, WorkQueue
from contraagent._internal.dispatch.task import STOP_DEFERRED, STOP_DUPLICATE_KEY, Task, TaskResult, TimeBox

_logger = logging.getLogger(__name__)

FlowState = Literal["running", "returned", "raised", "closed"]
WaitsFor = Callable[[Any], Task]
Answer = Callable[[Any, TaskResult], Any]
Created = Callable[[], Iterable[Task]]
OnFlowCall = Callable[[str, "FlowCall"], None]


class TaskFailed(Exception):
    """A task a flow waited for did not succeed: it failed, or was refused as a
    duplicate key. `item` is what the flow yielded, `result` the task's
    `TaskResult`; `stop` and `key` are the result's."""

    def __init__(self, result: TaskResult, item: Any = None) -> None:
        self.result = result
        self.item = item
        self.stop = result.stop
        self.key = result.task.key
        detail = f": {result.reason}" if result.reason else ""
        super().__init__(f"task {self.key} {self.stop}{detail}")


class TaskDeferred(TaskFailed):
    """A task a flow waited for was not launched: past the queue's deadline, its
    remaining work too long to finish before it, or with no way to launch. A flow may catch it and yield a task of a
    `finishing_kinds` kind instead."""


def result_or_raise(item: Any, result: TaskResult) -> TaskResult:
    """An `answer`: the result when it is ok; `TaskDeferred` for a deferred task,
    `TaskFailed` for any other."""
    if result.ok:
        return result
    if result.stop == STOP_DEFERRED:
        raise TaskDeferred(result, item)
    raise TaskFailed(result, item)


@dataclass(frozen=True, eq=False)
class TimeBoxed:
    """A generator to run as a flow call with a deadline of its own. Build one with `time_box`."""

    gen: GeneratorType = field(repr=False)
    deadline_s: float
    grace_s: float
    slack_s: float
    finishing_kinds: tuple[str, ...]


def time_box(
    flow: Generator[Any, Any, Any],
    *,
    deadline_s: float,
    grace_s: float = GRACE_S,
    finishing_kinds: Iterable[str] = (),
    slack_s: float | None = None,
) -> TimeBoxed:
    """`flow`, a generator, to yield as a flow call with a deadline of its own: `deadline_s`
    from the moment it starts, over the tasks it and the flow calls it starts create. Past
    it only `finishing_kinds` still launch, for `grace_s`; the rest are deferred and its
    flow receives `TaskDeferred`. From `deadline_s - slack_s` (default a quarter of
    `deadline_s`) its tasks are ordered for the deadline. Its tasks are held to the run's
    deadline and to every enclosing time box too, so the earliest deadline stops them."""
    if not isinstance(flow, GeneratorType):
        raise TypeError(f"time_box() takes a generator (a flow call), not {type(flow).__name__}")
    if not deadline_s or deadline_s <= 0:
        raise ValueError(f"time_box(): deadline_s must be a positive number of seconds, not {deadline_s!r}")
    if grace_s < 0 or (slack_s is not None and slack_s < 0):
        raise ValueError("time_box(): grace_s and slack_s are seconds, not negative")
    if isinstance(finishing_kinds, str):
        raise TypeError(f"time_box(): finishing_kinds is a list of kinds, not the string {finishing_kinds!r}")
    slack = slack_s if slack_s is not None else SLACK_SHARE * deadline_s
    return TimeBoxed(flow, float(deadline_s), float(grace_s), float(slack), tuple(finishing_kinds))


@dataclass(eq=False)
class FlowCall:
    """One generator the driver runs.

    `id`: `"0"` for the first top flow, `"<parent>.<n>"` for a child.
    `function`: `module.qualname` of the generator function. `site`: the
    parent's `(file, line)` where it was yielded; None for a top flow.
    `frontier`: the keys whose results it received when it was last resumed.
    `value`: what it returned; `error`: what it raised (or what closing it
    raised). `time_box`: its own deadline, when it was yielded through
    `time_box`; `started_at` (`time.time()`): when it started."""

    id: str
    gen: GeneratorType = field(repr=False)
    parent: FlowCall | None = field(default=None, repr=False)
    function: str = ""
    site: tuple[str, int] | None = None
    state: FlowState = "running"
    frontier: tuple[str, ...] = ()
    value: Any = field(default=None, repr=False)
    error: BaseException | None = None
    time_box: TimeBox | None = None
    started_at: float = field(default_factory=time.time)
    _children: itertools.count = field(default_factory=lambda: itertools.count(1), repr=False)


# A slot's outcome: an answer to send, an exception to throw, or closed.
_CLOSED = object()


@dataclass(eq=False)
class _Wait:
    """What one suspended flow call waits for: one slot per yielded item."""

    call: FlowCall
    items: list[Any]
    batch: bool
    outcomes: list[Any]
    errors: list[BaseException | None]
    keys: list[tuple[str, ...]]
    remaining: int


class FlowDriver:
    """Drives flow calls from one `WorkQueue`'s results (see the module docstring).

    `run(queue, *flows)` is the whole cycle. Wired by hand: pass
    `follow_up=driver.follow_up` to the queue, `queue.extend(driver.start(flow))`
    for each top flow, `queue.run()`, then `driver.finish()`.
    """

    def __init__(
        self,
        *,
        waits_for: WaitsFor | None = None,
        answer: Answer | None = None,
        created: Created | None = None,
        on_flow_call: OnFlowCall | None = None,
        past_grace: Callable[[], bool] | None = None,
        slow_step_s: float = 1.0,
    ) -> None:
        self._waits_for = waits_for or _task_itself
        self._answer = answer or (lambda item, result: result)
        self._created = created or (lambda: ())
        self._on_flow_call = on_flow_call or (lambda event, call: None)
        #: Whether the queue is past its grace window; `run()` sets the queue's
        #: `past_hard_stop` when none is given.
        self.past_grace: Callable[[], bool] | None = past_grace
        self.slow_step_s = slow_step_s
        #: Every flow call, by id, in start order.
        self.calls: dict[str, FlowCall] = {}
        #: Every result seen, by task key.
        self.done: dict[str, TaskResult] = {}
        #: The flow call whose code is running, None between steps.
        self.current: FlowCall | None = None
        self._tops = itertools.count()
        self._waits: dict[str, _Wait] = {}  # by flow call id: a suspended call's wait
        self._waiters: dict[str, list[tuple[_Wait, int]]] = {}  # by task key
        self._child_slot: dict[str, tuple[_Wait, int]] = {}  # by child call id
        self._queued_keys: set[str] = set()
        self._work: deque[tuple[FlowCall, Any, BaseException | None]] = deque()
        self._outbox: list[Task] = []
        self._draining = False

    # --- the cycle -----------------------------------------------------------

    def run(self, queue: WorkQueue, *flows: Generator) -> dict:
        """Start every flow on `queue`, run it, close what is left; the queue's
        summary. Sets the queue's `follow_up`, and `past_grace` to its
        `past_hard_stop` unless one was given."""
        queue.follow_up = self.follow_up
        if self.past_grace is None:
            self.past_grace = queue.past_hard_stop
        for flow in flows:
            queue.extend(self.start(flow))
        try:
            return queue.run()
        finally:
            self.finish()

    def start(self, flow: Generator) -> list[Task]:
        """Run a top flow to its first wait; the tasks to queue."""
        if not isinstance(flow, GeneratorType):
            raise TypeError(f"a flow call is a generator, not {type(flow).__name__}")
        call = self._new_call(str(next(self._tops)), flow, parent=None, frontier=())
        self._work.append((call, None, None))
        return self._drain()

    def follow_up(self, result: TaskResult) -> list[Task]:
        """`WorkQueue`'s `follow_up`: record the result, resume what waited for it;
        the tasks to queue."""
        key = result.task.key
        if result.stop != STOP_DUPLICATE_KEY:  # the key's own result is still to come
            self.done[key] = result
        for wait, slot in self._waiters.pop(key, ()):
            self._settle_task(wait, slot, result)
        return self._drain()

    def finish(self) -> None:
        """Close every flow call still suspended, children before parents."""
        for call in reversed(list(self.calls.values())):
            if call.state == "running":
                self._close(call)
        self._work.clear()
        self._waits.clear()
        self._waiters.clear()
        self._child_slot.clear()

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
    def waiting(self) -> list[FlowCall]:
        """The flow calls suspended at a `yield`."""
        return [w.call for w in self._waits.values()]

    # --- steps -----------------------------------------------------------------

    def _drain(self) -> list[Task]:
        if self._draining:
            return []  # the drain under way returns these tasks too
        self._draining = True
        try:
            while self._work:
                call, value, exc = self._work.popleft()
                self._step(call, value, exc)
        finally:
            self._draining = False
        out, self._outbox = self._outbox, []
        return out

    def _step(self, call: FlowCall, value: Any, exc: BaseException | None) -> None:
        self.current = call
        t0 = time.monotonic()
        try:
            item = call.gen.throw(exc) if exc is not None else call.gen.send(value)
        except StopIteration as stop:
            self._end(call, "returned", value=stop.value)
            return
        except Exception as error:
            self._end(call, "raised", error=error)
            return
        finally:
            self.current = None
            elapsed = time.monotonic() - t0
            if elapsed > self.slow_step_s:
                _logger.warning(
                    "flow call %s (%s) ran %.1fs between yields on the scheduler's thread; heavy work belongs in a Python task",
                    call.id,
                    call.function,
                    elapsed,
                )
            self._queue(self._created(), call)
        self._wait(call, item)

    def _wait(self, call: FlowCall, item: Any) -> None:
        batch = isinstance(item, (list, tuple))
        items = list(item) if batch else [item]
        n = len(items)
        wait = _Wait(call, items, batch, [None] * n, [None] * n, [()] * n, n)
        self._waits[call.id] = wait
        if n == 0:
            self._resume(wait)
            return
        for slot, it in enumerate(items):
            boxed = it if isinstance(it, TimeBoxed) else None
            if boxed is not None:
                it = boxed.gen
            if isinstance(it, GeneratorType):
                if inspect.getgeneratorstate(it) != inspect.GEN_CREATED:
                    self._fill(wait, slot, error=RuntimeError(f"generator {it.__qualname__} was already started"))
                    continue
                child = self._new_call(f"{call.id}.{next(call._children)}", it, parent=call, frontier=call.frontier, announce=False)
                if boxed is not None:  # its clock starts now, with the flow call
                    child.time_box = TimeBox(
                        deadline_at=time.monotonic() + boxed.deadline_s,
                        deadline_s=boxed.deadline_s,
                        grace_s=boxed.grace_s,
                        slack_s=boxed.slack_s,
                        finishing_kinds=frozenset(boxed.finishing_kinds),
                        flow_call=child.id,
                    )
                self._child_slot[child.id] = (wait, slot)
                try:
                    self._on_flow_call("start", child)
                except Exception as error:  # the child does not run; the parent receives the error
                    it.close()
                    self._end(child, "raised", error=error)
                    continue
                self._work.append((child, None, None))
                continue
            try:
                task = self._waits_for(it)
            except Exception as error:  # thrown at the yield
                self._fill(wait, slot, error=error)
                continue
            if task.key in self.done:
                self._settle_task(wait, slot, self.done[task.key])
                continue
            self._waiters.setdefault(task.key, []).append((wait, slot))
            self._queue([task], call)

    def _queue(self, tasks: Iterable[Task], call: FlowCall) -> None:
        """Queue the tasks `call` created or yielded, each held to `call`'s time boxes."""
        boxes = self.time_boxes(call)
        for task in tasks:
            if task.key not in self._queued_keys and task.key not in self.done:
                if boxes and not task.time_boxes:
                    task = replace(task, time_boxes=boxes)
                self._queued_keys.add(task.key)
                self._outbox.append(task)

    def _settle_task(self, wait: _Wait, slot: int, result: TaskResult) -> None:
        if result.stop == STOP_DEFERRED and self.past_grace is not None and self.past_grace():
            self._fill(wait, slot, outcome=_CLOSED, keys=(result.task.key,))
            return
        try:
            value = self._answer(wait.items[slot], result)
        except Exception as error:
            self._fill(wait, slot, error=error, keys=(result.task.key,))
            return
        self._fill(wait, slot, outcome=value, keys=(result.task.key,))

    def _fill(self, wait: _Wait, slot: int, *, outcome: Any = None, error: BaseException | None = None, keys: tuple[str, ...] = ()) -> None:
        wait.outcomes[slot] = outcome
        wait.errors[slot] = error
        wait.keys[slot] = keys
        wait.remaining -= 1
        if wait.remaining == 0:
            self._resume(wait)

    def _resume(self, wait: _Wait) -> None:
        call = wait.call
        del self._waits[call.id]
        if call.state != "running":
            return
        if any(o is _CLOSED for o in wait.outcomes):
            self._close(call)
            return
        call.frontier = tuple(dict.fromkeys(k for keys in wait.keys for k in keys))
        error = next((e for e in wait.errors if e is not None), None)
        if error is not None:
            self._work.append((call, None, error))
        else:
            self._work.append((call, wait.outcomes if wait.batch else wait.outcomes[0], None))

    # --- flow calls ------------------------------------------------------------

    def _new_call(
        self, call_id: str, gen: GeneratorType, parent: FlowCall | None, frontier: tuple[str, ...], announce: bool = True
    ) -> FlowCall:
        module = gen.gi_frame.f_globals.get("__name__", "") if gen.gi_frame is not None else ""
        function = f"{module}.{gen.__qualname__}" if module else gen.__qualname__
        site = _site(parent.gen) if parent is not None else None
        call = FlowCall(id=call_id, gen=gen, parent=parent, function=function, site=site, frontier=frontier)
        self.calls[call_id] = call
        if announce:
            self._on_flow_call("start", call)
        return call

    def _end(self, call: FlowCall, state: FlowState, *, value: Any = None, error: BaseException | None = None) -> None:
        call.state = state
        call.value = value
        call.error = error
        self._on_flow_call("end", call)
        parent = self._child_slot.pop(call.id, None)
        if parent is None:
            return
        wait, slot = parent
        if state == "returned":
            self._fill(wait, slot, outcome=value, keys=call.frontier)
        elif state == "raised":
            self._fill(wait, slot, error=error, keys=call.frontier)
        else:
            self._fill(wait, slot, outcome=_CLOSED)

    def _close(self, call: FlowCall) -> None:
        self._waits.pop(call.id, None)
        error: BaseException | None = None
        try:
            call.gen.close()
        except Exception as exc:  # closing ran code that raised (or yielded again)
            error = exc
        self._end(call, "closed", error=error)


def _task_itself(item: Any) -> Task:
    if isinstance(item, Task):
        return item
    raise TypeError(f"a flow yields a Task, a generator (or a time_box of one), or a list or tuple of them, not {type(item).__name__}")


def _site(gen: GeneratorType) -> tuple[str, int] | None:
    """Where `gen` is suspended: the innermost generator of its `yield from` chain."""
    inner = gen.gi_yieldfrom
    while isinstance(inner, GeneratorType):
        gen, inner = inner, inner.gi_yieldfrom
    frame = gen.gi_frame
    return (frame.f_code.co_filename, frame.f_lineno) if frame is not None else None
