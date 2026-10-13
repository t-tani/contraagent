"""Task queue (`WorkQueue`): when, and how many, tasks launch at once.

One finished task wakes the ready tasks at the head of the queue. A task is
ready when:

* every `Task.after` key is done;
* no task of a *different* kind holds one of its units (`Task.units`: its
  `unit` and its `extra_units`). Tasks of the same kind on one unit run
  concurrently on purpose; only a different kind on that unit has to wait its
  turn;
* the kind's own cap (`runner.config(task).max_concurrent`) and every tag's
  capacity (`tag_capacity`) have room.

The schedule is a greedy list schedule: whenever a slot is free, the first
task in the order that can start, starts; no slot idles while a task can start
(Graham's bound, within 2 - 1/m of the best makespan, holds for any such order).
The order:

* by bottom level, highest first: a task's estimate plus the longer of its
  known dependents' path and its `tail_s` (`_blevel`), so long remaining chains
  start first;
* a task that has waited longer than `overdue_s` since it became startable by
  its dependencies is **overdue**: overdue tasks come first, the longest
  waiting first (a task's wait is bounded however high the levels of later
  arrivals are);
* the **starvation guard**: when the first task in the order that cannot start
  is overdue, a later task may not take a resource it still needs: one of its
  tags, one of its units (a task of another kind), or a place under its kind's cap (a
  task of its kind). So a task that needs two tags, or a unit that a stream of
  tasks of one kind keeps busy, starts once what holds them ends.

With a deadline (`deadline_s`), from `deadline - slack_s` on the objective is
the work finished by the deadline, not the makespan: tasks of `finishing_kinds`
come first, then the smallest bottom level first, and a task whose own
estimate is known and whose bottom level is longer than the time left is
deferred at once (a flow may answer the deferral). Past the deadline only
`finishing_kinds` still launch, for a grace window (`grace_s`). On top sit one
retry for the stop values in `retry_on`, and throttling (two `throttle_on`
results in a row halve the slots for `throttle_s`).

Every `Task` carries two identities (`dispatch/task.py`): `.id`, fresh per
object and used only for this queue's bookkeeping, and `.key`, the stable
identity of the unit of work. `add()` refuses a task whose key is already in
flight (queued or running): that is the same work dispatched twice at once,
reported as `on_event("duplicate_key_refused", ...)`. A key that has *finished*
may be queued again (a re-dispatch after a no-progress attempt). `Task.after`
reads the cumulative done-by-key record, because a journal records keys and a
dependency means "this work is done", not "this particular launch finished".
`skip(task)` (resume) is asked once per queued task; a task it accepts finishes
as `skipped` without launching.

Every task the queue accepts finishes exactly once, through `follow_up`: with
its last attempt's result, as `skipped`, or as `deferred` (not launched by the
deadline or the grace window, or with no way to launch; `ok` False, not passed
to `on_result`). A follow-up task `add()` refuses finishes as `duplicate_key`,
so whoever waits for it is answered. Finished results settle from one deque,
never recursively, so a long chain of skipped follow-ups costs no stack. The
run continues while follow-ups queue work, deferred results included: a
`follow_up` may answer a deferral with a `finishing_kinds` task.

The queue records nothing itself. It reports through callbacks:

* `on_event(event, task, **fields)` for `queued`, `start`, `retry`, `throttle`,
  `deferred`, `end`, `duplicate_key_refused` and `note`;
* `on_result(result, attempt)` for every result, discarded retries included;
* `follow_up(result) -> list[Task]` for the follow-up work (main thread only; an
  exception there is reported as a `note` and isolated to that item). Its tasks
  are queued with `extend()`.

`runner` only needs to satisfy `TaskRunner` (`.config(task).max_concurrent`
and `.run(task)`); nothing here imports a concrete runner. A runner may also
say why a task cannot launch now (`.deferral(task)`, a reason or None): the
queue asks it just before it would start the task, and defers the task instead.
A runner that finds the same once the task has started returns a `deferred`
result, finished as a deferral too.
"""

from __future__ import annotations

import random
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Protocol

from contraagent.dispatch.task import STOP_DEFERRED, STOP_DUPLICATE_KEY, Task, TaskResult

#: Used when a task carries no estimate and the `estimate` callback has none: about one
#: coding-agent session, the usual task. Only an ordering default; a task with no known
#: estimate is never deferred for the deadline.
DEFAULT_ESTIMATE_S = 300.0

#: How long a startable task waits before it is overdue: about two agent sessions, so the
#: bottom level orders the ordinary waits and only a real starvation turns into first come.
OVERDUE_S = 600.0

#: The share of `deadline_s` before the deadline from which the queue orders for the
#: deadline, when `slack_s` is not given.
SLACK_SHARE = 0.25

#: How long `finishing_kinds` still launch past the deadline, when `grace_s` is not given.
GRACE_S = 900.0

OnEvent = Callable[..., None]  # on_event(event: str, task: Task | None, **fields)
FollowUp = Callable[[TaskResult], list[Task]]
OnResult = Callable[[TaskResult, int], None]  # on_result(result, attempt)


class _HasMaxConcurrent(Protocol):
    max_concurrent: int | None


class TaskRunner(Protocol):
    """The entire surface `WorkQueue` needs from a runner: a per-task
    concurrency cap, and a way to actually run one. `contraagent.execution.runner.AgentRunner` satisfies this with no changes and no
    inheritance -- structural, not nominal."""

    def config(self, task: Task) -> _HasMaxConcurrent: ...

    def run(self, task: Task) -> TaskResult: ...


class WorkQueue:
    """Runs Tasks against one `TaskRunner`, enforcing the per-unit
    ordering, concurrency-cap, retry, and throttle rules described in this
    module's docstring. Construct one per run; `add()` tasks, then `run()`
    to drain the queue to completion.
    """

    def __init__(
        self,
        runner: TaskRunner,
        *,
        follow_up: FollowUp | None = None,
        on_event: OnEvent | None = None,
        on_result: OnResult | None = None,
        max_concurrent: int = 8,
        deadline_s: float | None = None,
        retry_wait_s: float = 60.0,
        throttle_s: float = 300.0,
        skip: Callable[[Task], bool] | None = None,
        grace_s: float = GRACE_S,
        retry_on: frozenset[str] = frozenset(),
        throttle_on: frozenset[str] = frozenset(),
        finishing_kinds: tuple[str, ...] = (),
        tag_capacity: Mapping[str, int] | None = None,
        estimate: Callable[[Task], float | None] | None = None,
        overdue_s: float = OVERDUE_S,
        slack_s: float | None = None,
    ):
        self.runner = runner
        self.follow_up: FollowUp = follow_up or (lambda result: [])
        self.max_concurrent = max(1, int(max_concurrent))
        self.deadline_at = time.monotonic() + deadline_s if deadline_s else None
        # From `deadline - slack_s` on, the queue orders for the deadline (the module docstring).
        self.slack_s = slack_s if slack_s is not None else (SLACK_SHARE * deadline_s if deadline_s else 0.0)
        # Post-deadline grace: opener kinds stop launching, but the caller's
        # short finishing kinds (`finishing_kinds`, e.g. a report) still go;
        # otherwise the finishing work would be deferred with everything else.
        self.grace_s = grace_s
        self.hard_stop_at = (self.deadline_at + grace_s) if self.deadline_at is not None else None
        self.finishing_kinds = tuple(finishing_kinds)
        self.tag_capacity: dict[str, int] = dict(tag_capacity or {})
        # A domain's own estimate per task (e.g. from past runs); used when a
        # task carries none. Asked again on every pass, so it may learn as the run goes.
        self._estimate_fn = estimate
        self.overdue_s = overdue_s
        self._ready_since: dict[str, float] = {}  # by .id: when its dependencies were all done
        # Stop values worth one retry, and stop values that count toward a
        # throttle (two in a row halve the slots for `throttle_s`). The queue
        # attaches no meaning to either: the caller names them.
        self.retry_on = frozenset(retry_on)
        self.throttle_on = frozenset(throttle_on)
        self.retry_wait_s = retry_wait_s
        self.throttle_s = throttle_s
        self._skip = skip  # resume: whether a task's work is already done
        self.on_event: OnEvent = on_event or (lambda *a, **k: None)
        # Per-result callback, discarded retries included; `on_event("end")` fires
        # for the final attempt only.
        self._on_result = on_result

        self._queued: list[Task] = []
        self._known: set[str] = set()  # by .id: this exact dispatch
        # by .key: units of work currently queued or running. Not cumulative
        # (see `_finish`): a finished key may be dispatched again; what this
        # guards against is two *concurrent* dispatches of the same work.
        self._inflight_keys: set[str] = set()
        self._running: dict[Future, Task] = {}
        # Per unit: which kind currently occupies
        # it and how many of that kind's tasks are in flight. A different
        # kind wanting that same unit waits; more of the SAME kind does not.
        self._running_unit_kind: dict[str, str] = {}
        self._running_unit_count: dict[str, int] = {}
        self._done: dict[str, TaskResult] = {}  # by .id
        self._done_keys: set[str] = set()  # by .key: what `after` checks
        self._attempt: dict[str, int] = {}
        self._not_before: dict[str, float] = {}
        self._throttled_until = 0.0
        self._consec_throttled = 0
        self.results: list[TaskResult] = []
        self.deferred: list[Task] = []
        # Results waiting to finish (`_settle`), and whether a drain is under way.
        self._settling: deque[TaskResult] = deque()
        self._draining = False
        self._seq: dict[str, int] = {}  # by .id: arrival order
        self._successors: dict[str, list[Task]] = {}  # by .key: known dependents

    # --- queueing -----------------------------------------------------------

    def add(self, task: Task) -> bool:
        """Queue one task. Same `.id` queues once (defensive — callers mint a
        fresh one per `Task` object, so this should never actually collide).
        A second task whose `.key` is already *in flight* (queued or
        running — not merely ever-seen) is a structural duplicate — the
        same unit of work dispatched twice at once — and is refused,
        loudly, rather than silently re-run. A task `skip` accepts finishes
        as `skipped` without launching."""
        if task.id in self._known:
            return False
        self._known.add(task.id)
        self._seq[task.id] = len(self._seq)
        for dep in task.after:
            self._successors.setdefault(dep, []).append(task)
        if task.key in self._inflight_keys:
            self.on_event("duplicate_key_refused", task, key=task.key)
            return False
        self._inflight_keys.add(task.key)
        self.on_event("queued", task)
        if self._skip is not None and self._skip(task):
            self._settle(TaskResult.skipped(task))
            return True
        self._queued.append(task)
        return True

    def extend(self, tasks: Iterable[Task]) -> None:
        """Queue follow-up work: `add()` each task, and finish one it refuses as a
        duplicate key as `duplicate_key`, so whoever waits for it is answered."""
        for task in tasks:
            if task.id in self._known:
                continue
            if not self.add(task):
                self._settle(TaskResult.duplicate_key(task))

    # --- launch conditions --------------------------------------------------

    def past_deadline(self) -> bool:
        return self.deadline_at is not None and time.monotonic() >= self.deadline_at

    def past_hard_stop(self) -> bool:
        return self.hard_stop_at is not None and time.monotonic() >= self.hard_stop_at

    def in_endgame(self) -> bool:
        """From `deadline - slack_s` on: ordered for the deadline (the module docstring)."""
        return self.deadline_at is not None and time.monotonic() >= self.deadline_at - self.slack_s

    def _finishing(self, task: Task) -> bool:
        """A short finishing task: still launches inside the grace window."""
        return task.kind in self.finishing_kinds

    def slots(self) -> int:
        """Current concurrency cap. Halved right after back-to-back 429s."""
        if time.monotonic() < self._throttled_until:
            return max(1, self.max_concurrent // 2)
        return self.max_concurrent

    def _held_by_other_kind(self, task: Task) -> bool:
        """A task of another kind holds one of its units."""
        for unit in task.units:
            occupant = self._running_unit_kind.get(unit)
            if occupant is not None and occupant != task.kind:
                return True
        return False

    def _startable(self, task: Task, now: float) -> bool:
        """Its dependencies are done and it is not waiting for a retry."""
        return all(d in self._done_keys for d in task.after) and now >= self._not_before.get(task.id, 0.0)

    def _free(self, task: Task) -> bool:
        """What it needs is free: its units (no other kind holds one), a place under its
        kind's cap, and every tag."""
        if self._held_by_other_kind(task):
            return False
        cap = self.runner.config(task).max_concurrent
        if cap is not None and sum(1 for t in self._running.values() if t.kind == task.kind) >= cap:
            return False
        return not any(self._tag_full(t) for t in task.tags)

    def _possible(self, task: Task) -> bool:
        """It could start with nothing else running: no capacity of 0 stands in its way."""
        cap = self.runner.config(task).max_concurrent
        return (cap is None or cap > 0) and all(self.tag_capacity.get(t, 1) > 0 for t in task.tags)

    def _takes(self, task: Task, head: Task) -> bool:
        """Whether starting `task` takes a resource `head` still needs: a capped tag of
        its, one of its units (for another kind), or a place under its kind's cap."""
        if any(t in self.tag_capacity for t in set(task.tags) & set(head.tags)):
            return True
        if task.kind != head.kind and set(task.units) & set(head.units):
            return True
        return task.kind == head.kind and self.runner.config(head).max_concurrent is not None

    # --- progress -----------------------------------------------------------

    def run(self) -> dict:
        """Drain the queue or hit the driver timeout."""
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as pool:
            while self._queued or self._running:
                self._start_ready(pool)
                if not self._running:
                    if not self._queued:
                        break
                    # Each branch below either launches nothing new or defers
                    # what is queued; a deferral's follow-ups may queue more
                    # work, which the next pass handles.
                    if self.past_hard_stop():
                        self._defer_all("grace window exhausted")
                        continue
                    if self.past_deadline():
                        if self._drop_openers():  # finishing tasks stay; loop to launch them
                            continue
                        self._defer_all("deadline")
                        continue
                    if self._sleep_until_retry():
                        continue
                    self._defer_all("no launchable task (dependency never queued)")
                    continue
                done, _ = wait(list(self._running), timeout=1.0, return_when=FIRST_COMPLETED)
                for fut in done:
                    task = self._running.pop(fut)
                    self._release(task)
                    self._on_done(task, fut)
        return self._summary(time.monotonic() - t0)

    def _drop_openers(self) -> bool:
        """Past the deadline: defer openers, keep short finishing tasks. Returns
        True when tasks remain to launch (finishing tasks, or what the deferrals'
        follow-ups queued)."""
        openers = [t for t in self._queued if not self._finishing(t)]
        self._queued = [t for t in self._queued if self._finishing(t)]
        for t in openers:
            self._defer(t, "deadline")
        return bool(self._queued)

    def _known_est(self, task: Task) -> float | None:
        if task.estimate_s is not None:
            return task.estimate_s
        return self._estimate_fn(task) if self._estimate_fn is not None else None

    def _est(self, task: Task) -> float:
        est = self._known_est(task)
        return est if est is not None else DEFAULT_ESTIMATE_S

    def _blevel(self, task: Task, memo: dict[str, float]) -> float:
        """Bottom level: this task's estimate plus the longer of the longest
        path through its known dependents (Kwok & Ahmad 1999, the HLFET
        family) and its `tail_s`, the work after it not queued yet. Memoized,
        cycle-safe (a key revisited while open contributes nothing), and
        iterative, so a long chain costs no stack."""
        on_path: set[str] = set()
        stack: list[tuple[Task, bool]] = [(task, False)]
        while stack:
            t, expanded = stack.pop()
            successors = self._successors.get(t.key, ())
            if expanded:
                on_path.discard(t.key)
                tail = max((memo.get(d.key, 0.0) for d in successors), default=0.0)
                memo[t.key] = self._est(t) + max(tail, t.tail_s or 0.0)
            elif t.key not in memo and t.key not in on_path:
                on_path.add(t.key)
                stack.append((t, True))
                stack.extend((d, False) for d in successors if d.key not in memo and d.key not in on_path)
        return memo[task.key]

    def _overdue(self, task: Task, now: float) -> bool:
        since = self._ready_since.get(task.id)
        return since is not None and now - since >= self.overdue_s

    def _order(self, tasks: list[Task], memo: dict[str, float], now: float, endgame: bool) -> list[Task]:
        """The launch order (the module docstring). Before the endgame: overdue tasks
        first, the longest waiting first (tasks that became startable together: the
        highest bottom level first), then the highest bottom level, then arrival.
        In it: finishing tasks first, then the smallest bottom level, then arrival."""

        def key(t: Task) -> tuple:
            seq = self._seq.get(t.id, 0)
            if endgame:
                return (0 if self._finishing(t) else 1, self._blevel(t, memo), seq)
            if self._overdue(t, now):
                return (0, self._ready_since[t.id], -self._blevel(t, memo), seq)
            return (1, 0.0, -self._blevel(t, memo), seq)

        return sorted(tasks, key=key)

    def _tag_full(self, tag: str) -> bool:
        limit = self.tag_capacity.get(tag)
        return limit is not None and sum(1 for t in self._running.values() if tag in t.tags) >= limit

    def _start_ready(self, pool: ThreadPoolExecutor) -> None:
        if self.past_hard_stop():
            return
        if self.past_deadline():
            self._drop_openers()
        now = time.monotonic()
        for t in self._queued:  # each task's wait starts when it could start but for resources
            if t.id not in self._ready_since and self._startable(t, now):
                self._ready_since[t.id] = now
        memo: dict[str, float] = {}
        past_deadline = self.past_deadline()
        endgame = self.in_endgame()
        if endgame and not past_deadline:
            self._defer_late(memo, now)
            memo = {}  # the deferrals' follow-ups may have queued more
        head: Task | None = None  # the first task in the order that cannot start
        guarded = False
        for task in self._order(self._queued, memo, now, endgame):
            if len(self._running) >= self.slots():
                break
            if past_deadline and not self._finishing(task):
                continue  # queued by a deferral's follow-up; deferred on the next pass
            if not self._startable(task, now):
                continue
            if not self._free(task):
                if head is None:
                    head = task
                    guarded = self._overdue(task, now) and self._possible(task)
                continue
            if guarded and head is not None and self._takes(task, head):
                continue  # the starvation guard
            why = self._deferral(task)
            if why:  # the runner has no way to launch it now
                self._queued.remove(task)
                self._defer(task, why)
                continue
            self._queued.remove(task)
            self._ready_since.pop(task.id, None)
            attempt = self._attempt.get(task.id, 0) + 1
            self._attempt[task.id] = attempt
            self.on_event("start", task, attempt=attempt, running=len(self._running) + 1, slots=self.slots())
            self._occupy(task)
            self._running[pool.submit(self.runner.run, task)] = task

    def _defer_late(self, memo: dict[str, float], now: float) -> None:
        """In the endgame: defer each task that could start but whose work cannot finish
        before the deadline, its own estimate known and its bottom level longer than the
        time left. Finishing tasks are kept: they have the grace window."""
        assert self.deadline_at is not None
        left = self.deadline_at - now
        late: list[tuple[Task, float]] = []
        for t in self._queued:
            if self._finishing(t) or not self._startable(t, now) or self._known_est(t) is None:
                continue
            need = self._blevel(t, memo)
            if need > left:
                late.append((t, need))
        if not late:
            return
        ids = {t.id for t, _ in late}
        self._queued = [t for t in self._queued if t.id not in ids]
        for t, need in late:
            self._defer(t, f"cannot finish before the deadline: needs {need:.0f}s, {left:.0f}s left")

    def _occupy(self, task: Task) -> None:
        for unit in task.units:
            self._running_unit_kind[unit] = task.kind
            self._running_unit_count[unit] = self._running_unit_count.get(unit, 0) + 1

    def _release(self, task: Task) -> None:
        for unit in task.units:
            self._running_unit_count[unit] -= 1
            if self._running_unit_count[unit] <= 0:
                del self._running_unit_count[unit]
                del self._running_unit_kind[unit]

    def _deferral(self, task: Task) -> str | None:
        """The runner's reason not to launch `task` now (`deferral`), if it gives one."""
        ask = getattr(self.runner, "deferral", None)
        if ask is None:
            return None
        try:
            return ask(task)
        except Exception as exc:  # a broken check must not stop the queue: launch, and say so
            self.on_event("note", task, deferral_failed=repr(exc)[:200])
            return None

    def _on_done(self, task: Task, fut: Future) -> None:
        try:
            res: TaskResult = fut.result()
        except Exception as exc:  # one task must not stop the driver
            res = TaskResult.launch_failed(task, f"exception: {exc!r}")
        if res.stop == STOP_DEFERRED:  # started, then found no way to launch: never launched
            self.on_event("deferred", task, reason=res.reason)
            self._ready_since.pop(task.id, None)
            self.deferred.append(task)
            self._settle(res)
            return
        if self._on_result is not None:
            try:
                self._on_result(res, self._attempt.get(task.id, 0))
            except Exception as exc:  # recording never stops progress
                self.on_event("note", task, record_failed=repr(exc)[:200])
        if res.stop in self.throttle_on:
            self._consec_throttled += 1
            if self._consec_throttled >= 2 and time.monotonic() >= self._throttled_until:
                self._throttled_until = time.monotonic() + self.throttle_s
                self.on_event("throttle", task, slots=self.slots(), throttle_s=self.throttle_s)
        else:
            self._consec_throttled = 0

        if res.stop in self.retry_on and self._attempt.get(task.id, 1) < 2 and not self.past_deadline():
            # Full jitter (AWS's "Exponential Backoff and Jitter"): with a
            # fixed wait, every task that failed in the same outage would
            # retry at the same instant.
            wait_s = random.uniform(0, self.retry_wait_s)
            self.on_event("retry", task, stop=res.stop, wait_s=wait_s, reason=res.reason)
            self._not_before[task.id] = time.monotonic() + wait_s
            self._ready_since.pop(task.id, None)  # its wait starts again after the retry wait
            self._queued.insert(0, task)
            return
        self._settle(res)

    def _settle(self, res: TaskResult) -> None:
        """Finish `res`, and every result its follow-ups settle in turn, from
        one deque: a call made while a drain is under way only appends."""
        self._settling.append(res)
        if self._draining:
            return
        self._draining = True
        try:
            while self._settling:
                self._finish(self._settling.popleft())
        finally:
            self._draining = False

    def _finish(self, res: TaskResult) -> None:
        """Close one task; queue whatever `follow_up` returns.

        A `duplicate_key` result leaves the key's bookkeeping alone (the key
        belongs to the task in flight). A `deferred` result marks its key done,
        so a finishing task after it can launch, but is no `end` and no entry
        in `results`: it never launched.

        `follow_up()` is caller-supplied logic (deciding what runs next) — a
        bug or an unexpected state shape in one callback must not take down
        every other item's progress. A raise here just means this one
        result's follow-up work never gets queued; everything already running
        or queued continues.
        """
        task = res.task
        if res.stop != STOP_DUPLICATE_KEY:
            self._done_keys.add(task.key)
            self._inflight_keys.discard(task.key)
        if res.stop not in (STOP_DEFERRED, STOP_DUPLICATE_KEY):
            self.results.append(res)
            self._done[task.id] = res
            self.on_event("end", task, attempt=self._attempt.get(task.id, 0), **res.summary())
        try:
            follow_ups = self.follow_up(res)
        except Exception as exc:  # one callback must not stop the queue
            self.on_event("note", task, follow_up_failed=repr(exc)[:300])
            return
        self.extend(follow_ups)

    def _sleep_until_retry(self) -> bool:
        """Wait for the next retry time when retries are pending."""
        now = time.monotonic()
        waits = [self._not_before[t.id] - now for t in self._queued if self._not_before.get(t.id, 0.0) > now]
        if not waits:
            return False
        time.sleep(min(max(0.05, min(waits)), 5.0))
        return True

    def _defer_all(self, reason: str) -> None:
        tasks, self._queued = self._queued, []
        for t in tasks:
            self._defer(t, reason)

    def _defer(self, task: Task, reason: str) -> None:
        """Not launched: reported as `deferred`, then finished as such."""
        self.on_event("deferred", task, reason=reason)
        self._ready_since.pop(task.id, None)
        self.deferred.append(task)
        self._settle(TaskResult.deferred(task, reason))

    def _summary(self, wall_s: float) -> dict:
        by_stop: dict[str, int] = {}
        for r in self.results:
            by_stop[r.stop] = by_stop.get(r.stop, 0) + 1
        # Per-kind count and wall time. A domain's own per-kind figures (calls,
        # context use) come from its own summary, not from this one.
        by_kind: dict[str, dict] = {}
        for k in {r.task.kind for r in self.results}:
            rs = [r for r in self.results if r.task.kind == k]
            by_kind[k] = {"n": len(rs), "ok": sum(1 for r in rs if r.ok), "wall_s": round(sum(r.wall_s for r in rs), 1)}
        return {
            "wall_s": round(wall_s, 1),
            "finished": len(self.results),
            "ok": sum(1 for r in self.results if r.ok),
            "by_stop": by_stop,
            "by_kind": by_kind,
            "deferred": [t.key for t in self.deferred],
        }
