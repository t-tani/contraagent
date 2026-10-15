"""The generic task-dispatch envelope: identity, dependency shape, and
result shape. Nothing here imports anything outside the standard library:
no LLM types, no domain package. A domain's own record of a run travels in
`TaskResult.launch_result` and `payload`, opaque to this module.

`WorkQueue` (`dispatch/queue.py`), `FlowDriver` (`dispatch/flow.py`),
and `AgentRunner`'s dispatch loop
(`execution/runner.py`) only ever need what is defined here. A domain
package builds its own `Kind` vocabulary and payload types on top via `Task.payload`/
`TaskResult.payload`, two slots this module treats as fully opaque, and
supplies `contraagent.dispatch.interceptors.TaskScope`/`ResultEnricher`
implementations for whatever domain-specific lifecycle or progress logic a
dispatch needs.

The design follows the same shape used by CloudEvents (context attributes
vs. an opaque `data` field), event-sourcing's envelope/payload split,
Temporal's `Payload` (the worker core never interprets payload bytes --
that is entirely the domain-supplied `DataConverter`'s job), and Airflow's
Operator/XCom distinction: one named, opaque payload slot on a generic
envelope, not flattened domain fields and not a compile-time-generic
`Task[KindT, PayloadT]`. `Task` itself is, in GoF terms, a Command object --
a request encapsulated as data -- so it stays a plain value type with no
behavior to override; the actual extension points (what varies per domain)
live in `contraagent.dispatch.interceptors`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

#: The key prefix of a Python task (`Task.fn`): `python:<kind>` or `python:<kind>-<unit>`.
PYTHON_KEY_PREFIX = "python:"


def kind_name(kind) -> str:
    """The string form of a kind: an enum member's value, or the string itself.

    A kind is whatever label a domain gives a class of task. A `str`-valued
    `enum.Enum` works as well as a plain string, because its members hash and
    compare equal to their values.
    """
    return str(getattr(kind, "value", kind))


@dataclass(frozen=True)
class Loop:
    """A `for` or `while` loop of a generator around a call site. `line`: its first
    line, which names it. `pass_`: the pass the call site was in, one iteration
    numbered from 1 since the loop was last entered in that frame activation (on
    disk `pass`); None when it was not counted."""

    line: int
    pass_: int | None = 1


@dataclass(frozen=True)
class Frame:
    """One frame of flow code where a task was created: `function` is
    `module.qualname`, `file` and `line` the call site. `loops` are the loops
    whose pass the call site was in, outermost first, for a generator frame;
    empty for any other frame, outside a loop, or when they cannot be found. A
    comprehension is not a loop."""

    function: str
    file: str
    line: int
    loops: tuple[Loop, ...] = ()


@dataclass(frozen=True)
class Origin:
    """Where a task was created.

    `flow`: the flow path, the frames of flow code that created it, outermost
    first, across flow calls (a child flow call's frames follow the frames of
    the parent's yield that started it). Their loops' passes say in which
    iteration of each loop around it the task was created.
    `created_from`: the keys whose results its flow call had received when it
    was created (the flow call's frontier).
    `flow_call`: the id of the flow call that created it.
    """

    flow: tuple[Frame, ...] = ()
    created_from: tuple[str, ...] = ()
    flow_call: str = "0"


@dataclass(frozen=True)
class TimeBox:
    """A deadline over the tasks of one flow call and of the flow calls it starts: from
    `deadline_at` (`time.monotonic()`), only `finishing_kinds` still launch, for `grace_s`;
    from `deadline_at - slack_s` the queue orders them for the deadline. `flow_call`: the
    flow call it bounds, None for the queue's own deadline over the whole run.
    `deadline_s`: its length, counted from its flow call's start."""

    deadline_at: float
    deadline_s: float
    grace_s: float
    slack_s: float = 0.0
    finishing_kinds: frozenset[str] = frozenset()
    flow_call: str | None = None

    def cause(self, name: str, **fields: Any) -> dict:
        """A deferral's cause (`Deferral.cause`) under this box: `flow_call` names it."""
        return {"cause": name, **fields, **({"flow_call": self.flow_call} if self.flow_call is not None else {})}


@dataclass
class Task:
    """One schedulable unit of work.

    `kind`: the class of work, a hashable discriminator a domain uses for
    per-kind config and concurrency-class lookup (the generic scheduler only
    ever hashes or compares it, never interprets its value). For a Python
    task, its own name.
    `unit`: what the kind is applied to (a domain decides what a unit is -- a
    file, a document, a topic). It names the task and its output; it locks
    nothing. Empty: the task's own key.
    `after`: task keys this one depends on, named in terms of `key` below,
    never `id`.
    `fn`: a Python task's function, run in-process on the pool instead of
    a coding-agent launch. None for an agent task.
    `claims`: the names this task holds while it runs; no more tasks hold one
    name at once than its capacity (WorkQueue's `claim_capacity`; 1 by default).
    `time_boxes`: the time boxes of the flow calls that created it, outermost
    first (`TimeBox`); the queue holds it to each of them, beside its own deadline.
    `rerun_on_resume`: a resume runs it again even when an earlier attempt of the run
    finished it (a final step that reports or publishes the state of the work).
    `estimate_s`: expected wall time, used to order the ready set.
    `tail_s`: expected wall time of the work that follows this task but is
    not queued yet (a flow creates it from this task's result); the queue's
    bottom level counts it like a successor (see `WorkQueue._blevel`).
    `priority`: a tie-breaker in the queue's order, higher first: it orders tasks
    the bottom level, overdue waiting and the deadlines leave equal, never
    against them. Scheduling, not work: no part of the fingerprint.
    `params`: what the task is given (scalars reach an agent as
    `CONTRAAGENT_PARAMS`).
    `attempt`: retry ordinal; 0 is the first try.
    `id`: a fresh, meaningless-by-design value per `Task` object, used only
    as the scheduler's own internal bookkeeping key.
    `key`: the stable, semantic identity a domain assigns (what `after`
    references, what a resumed run recognizes as "the same dispatch").
    `payload`: opaque domain data. Nothing in this module reads it.
    `origin`: where a flow created it (`Origin`); None for a task built by hand.
    `fingerprint`: a digest of what defines its work, set by whoever builds it;
    a resumed run skips a key only when its last journal row is ok with the
    same fingerprint.
    `base_kind`: for a kind that is one of several implementations of one step, the
    step's kind (`agent_task(implementations=)`); empty for any other. Recorded in
    `plan.jsonl`; nothing here reads it.
    """

    kind: str
    unit: str = ""
    after: tuple[str, ...] = ()
    fn: Callable[[], None] | None = None
    claims: tuple[str, ...] = ()
    time_boxes: tuple[TimeBox, ...] = ()
    rerun_on_resume: bool = False
    estimate_s: float | None = None
    tail_s: float | None = None
    priority: float = 0.0
    params: dict = field(default_factory=dict)
    attempt: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    key: str = ""
    payload: Any = None
    origin: Origin | None = None
    fingerprint: str = ""
    base_kind: str = ""

    def __post_init__(self) -> None:
        # Generic, collision-safe fallbacks -- a domain that always assigns
        # both explicitly (a domain's own task factory does) never hits these;
        # they exist so a bare `Task("kind")` from a hypothetical second
        # domain, or a test, is still self-consistent on its own.
        if not self.key:
            self.key = self.id
        if not self.unit:
            self.unit = self.key

    @property
    def declared_unit(self) -> str:
        """The unit the task was given: empty for one given none (whose `unit` is its key)."""
        return "" if self.unit == self.key else self.unit

    @property
    def executor(self) -> Literal["agent", "python"]:
        """Who executes it: "python" for a Python task (`fn`), "agent" otherwise."""
        return "python" if self.fn is not None else "agent"


# The generic stop vocabulary. A domain adds its own stop values as strings.
STOP_COMPLETED = "completed"
STOP_ERROR = "error"
STOP_SKIPPED = "skipped"
STOP_LAUNCH_FAILED = "launch_failed"
STOP_INVALID_INPUT = "invalid_input"
STOP_INVALID_OUTPUT = "invalid_output"
# Not launched: past the queue's deadline, its work too long to finish before it, or with
# no way to launch (never journaled).
STOP_DEFERRED = "deferred"
# Not queued: a task with the same key was in flight (never journaled).
STOP_DUPLICATE_KEY = "duplicate_key"


@dataclass(frozen=True)
class Deferral:
    """Why a task is not launched: `reason` in one line (logs, the CLI), and `cause`, the
    same as data for a reader that words it itself (the monitor): `{"cause": <name>, ...}`.
    The queue's own causes: `deadline`, `grace_window` (past the deadline's grace window),
    `cannot_finish` (`need_s`, `left_s`) and `dependency_not_queued`; the first three name
    the time box's `flow_call` when the deadline is one's (`TimeBox`), not the run's. A
    runner adds its own (`rest`: `routing.quota`)."""

    reason: str
    cause: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Changes:
    """The files one attempt changed under its task's `changes` patterns, as paths
    relative to the working directory: those it `created`, `modified` and `deleted`.
    `removed`: the files it created that were removed because the attempt failed."""

    created: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


@dataclass
class TaskResult:
    """A task's final result. `payload` is opaque domain data (e.g. a state
    delta) a `ResultEnricher` attaches -- never read by this module."""

    task: Task
    ok: bool
    stop: str
    # The domain's own record of the run (for an agent task, its
    # `LaunchResult`), carried opaquely; nothing in this module reads it.
    launch_result: Any = None
    wall_s: float = 0.0
    # Why it ended the way it did, in one line (empty when nothing needs saying).
    reason: str = ""
    # What the runner reports beside the verdict, as data: the queue sends it as one
    # `on_event("note", task, **notes)` when the task finishes (`context_warned`: a launch's
    # peak context passed its kind's `context_warn_pct`). Empty: no note.
    notes: dict[str, Any] = field(default_factory=dict)
    # (agent, model) the launch actually ran on. Differs from the Kind's
    # configured model whenever the router failed over, so a postmortem can
    # tell "the model did this" from "the model we asked for did this".
    route: str = ""
    # Every launch in the walk that produced this result, in order: one
    # {"route", "model", "stop", "wall_s"} per hop, so a failover is visible
    # after the fact and not only in `route`, which names the last hop.
    hops: tuple[dict, ...] = ()
    # An output check's verdict when the work was checked outside a backend
    # (a Python task): how many rounds it took, and the errors of each round
    # that failed its checks (the last: what stayed wrong).
    rounds: int | None = None
    round_errors: tuple[tuple[str, ...], ...] = ()
    # The files the attempt changed under its task's `changes` patterns; None when it declares none.
    changes: Changes | None = None
    # The hops the walk passed over without a launch, in order, each a plain dict a runner
    # fills (`{"route", "model", ...}` and why its credential rests). Not in `hops`: no launch.
    skipped_hops: tuple[dict, ...] = ()
    # A `deferred` result's cause as data (`Deferral.cause`); None for any other result.
    cause: dict | None = None
    # False when another attempt cannot end otherwise (a replay with no recording for the
    # task): a retrying runner stops at this one.
    retryable: bool = True
    payload: Any = None

    @classmethod
    def skipped(cls, task: Task) -> TaskResult:
        return cls(task=task, ok=True, stop=STOP_SKIPPED)

    @classmethod
    def deferred(cls, task: Task, deferral: Deferral) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_DEFERRED, reason=deferral.reason, cause=dict(deferral.cause))

    @classmethod
    def duplicate_key(cls, task: Task) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_DUPLICATE_KEY, reason=f"key {task.key!r} already in flight")

    @classmethod
    def launch_failed(cls, task: Task, reason: str) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_LAUNCH_FAILED, reason=reason)

    def summary(self) -> dict:
        """Queue `end`-line summary. Generic only -- a domain's own delta
        lives in `payload`, passed through opaquely rather than flattened
        into named keys here."""
        return {
            "stop": self.stop,
            "ok": self.ok,
            "wall_s": round(self.wall_s, 1),
            "reason": self.reason,
            "route": self.route,
            "payload": self.payload,
        }
