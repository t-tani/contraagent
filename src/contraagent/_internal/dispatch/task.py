"""The generic task-dispatch envelope: identity, dependency shape, and
result shape. Nothing here imports anything outside the standard library and
pydantic (the record types of `dispatch/records.py`): no LLM types, no domain package. A domain's own record of a run travels in
`TaskResult.launch_result` and `payload`, opaque to this module.

`WorkQueue` (`dispatch/queue.py`), `FlowDriver` (`dispatch/flow.py`),
and `AgentRunner`'s dispatch loop
(`execution/runner.py`) only ever need what is defined here. A domain
package builds its own `Kind` vocabulary and payload types on top via `Task.payload`/
`TaskResult.payload`, two slots this module treats as fully opaque, and
supplies `contraagent.TaskScope`/`ResultEnricher`
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
live in `contraagent._internal.dispatch.interceptors`.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contraagent._internal.dispatch.records import Changes, DeferralCause, Executor, Frame, Hop, Played, SkippedHop

#: The key prefix of a Python task (`Task.fn`): `python:<kind>` or `python:<kind>-<unit>`.
PYTHON_KEY_PREFIX = "python:"


def kind_name(kind) -> str:
    """The string form of a kind: an enum member's value, or the string itself.

    A kind is whatever label a domain gives a class of task. A `str`-valued
    `enum.Enum` works as well as a plain string, because its members hash and
    compare equal to their values.
    """
    return str(getattr(kind, "value", kind))


def fingerprint_of(kind: str, unit: str, key: str, parts: Mapping[str, str]) -> str:
    """A task's fingerprint from its kind, unit and key and the digest of each part of its
    work (`Task.fingerprint_parts`): the SHA-256 of their canonical JSON."""
    body = {"kind": kind_name(kind), "unit": unit, "key": key, "parts": dict(parts)}
    text = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


#: The characters of an `fnmatch` pattern, which a kind name does not hold.
GLOB_CHARACTERS = frozenset("*?[")


def kind_matches(kind, patterns: frozenset[str]) -> bool:
    """Whether `kind` is matched by one of `patterns` (kind names or `fnmatch` patterns of
    them, `*` for every kind): what a stub run or a replay executes (`--execute`)."""
    name = kind_name(kind)
    return name in patterns or any(fnmatch.fnmatchcase(name, p) for p in patterns)


@dataclass(frozen=True)
class Origin:
    """Where a task was created.

    `flow`: the flow path, the frames of flow code that created it, outermost
    first, across flow calls (a child flow call's frames follow the frames of
    the parent where it created that flow call). Their loops' passes say in which
    iteration of each loop around it the task was created.
    `created_from`: the keys of the results that reached its flow call between
    that flow call's previous resume and the resume in which it created the task
    (the flow call's frontier: see `FlowDriver`).
    `flow_call`: the id of the flow call that created it.
    `given_from`: the keys of the tasks whose outputs it was given in its params: of the
    outputs the flow had received when it created the task, each one that is among its
    params whole, or one whole item of which is (an output that is a list, a Rows), by its
    JSON. Shown only, never part of its fingerprint.
    """

    flow: tuple[Frame, ...] = ()
    created_from: tuple[str, ...] = ()
    flow_call: str = "0"
    given_from: tuple[str, ...] = ()


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

    def cause(self, name: str, **fields: Any) -> DeferralCause:
        """A deferral's cause (`Deferral.cause`) under this box: `flow_call` names it."""
        box = {"flow_call": self.flow_call} if self.flow_call is not None else {}
        return DeferralCause.model_validate({"cause": name, **fields, **box})


@dataclass(frozen=True)
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
    `params`: what the task is given (an agent reads them in its call file,
    `CONTRAAGENT_CALL`).
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
    `fingerprint_at_start`: its fingerprint is complete only when it is about to start (it
    covers outside state, or the file an `output_of` task fills in): the queue asks the
    runner for the task as it starts (`starting`) and a resume asks whether to skip it
    then, not when it is queued.
    `outside`: the SHA-256 of its outside state, once it is about to start; empty for a
    task that declares none, or before.
    `fingerprint_parts`: a digest of each part of what its fingerprint covers, by the
    part's name (`fingerprint_of`), so a resume can say which part changed; empty for a
    task whose builder gives none.
    `base_kind`: for a kind that is one of several implementations of one step, the
    step's kind (`agent_task(implementations=)`); empty for any other. Recorded in
    `plan.jsonl`; nothing here reads it.
    `credential`: the credential its call options name (a `[credentials.<name>]`), which
    every route of its kind runs it as; empty: its kind's own. Routing, not work: no part
    of the fingerprint.
    `cancellable`: its task call's options gave `cancellable=True`: once the flow call that
    created it and every flow call that waited for it were closed, and no flow call waits for
    it, the flow driver cancels it (`WorkQueue.cancel`). False: it runs to its end whatever
    happens to its flow calls.
    `cwd`: an agent task's working directory, absolute, when its call options name one
    (`.options(cwd=)`): the coding agent runs in it, and its call file, its validators and
    its `changes` patterns are relative to it. None: the runner's (`Pipeline(cwd=)`). A
    Python task has none: its function runs in this process, whose current directory its
    other threads share; a `Task` with both `fn` and `cwd` raises `ValueError`. Where it
    works, not what: no part of the fingerprint.
    """

    kind: str
    unit: str = ""
    after: tuple[str, ...] = ()
    fn: Callable[[], object] | None = None
    claims: tuple[str, ...] = ()
    time_boxes: tuple[TimeBox, ...] = ()
    rerun_on_resume: bool = False
    estimate_s: float | None = None
    tail_s: float | None = None
    priority: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    key: str = ""
    payload: Any = None
    origin: Origin | None = None
    fingerprint: str = ""
    base_kind: str = ""
    # Fields new since 0.1.0 come last, so a positional argument keeps its place.
    fingerprint_at_start: bool = False
    outside: str = ""
    credential: str = ""
    fingerprint_parts: dict[str, str] = field(default_factory=dict)
    cancellable: bool = False
    cwd: Path | None = None

    def __post_init__(self) -> None:
        if self.fn is not None and self.cwd is not None:
            raise ValueError(
                f"Task {self.kind!r}: a Python task (fn) has no cwd: its function runs in this process, "
                "whose current directory every task shares; give it the directory as a param"
            )
        # Generic, collision-safe fallbacks -- a domain that always assigns
        # both explicitly (a domain's own task factory does) never hits these;
        # they exist so a bare `Task("kind")` from a hypothetical second
        # domain, or a test, is still self-consistent on its own.
        if not self.key:
            object.__setattr__(self, "key", self.id)
        if not self.unit:
            object.__setattr__(self, "unit", self.key)

    @property
    def declared_unit(self) -> str:
        """The unit the task was given: empty for one given none (whose `unit` is its key)."""
        return "" if self.unit == self.key else self.unit

    @property
    def executor(self) -> Executor:
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
# A Python task that returned a `Partial`: ok, its output a placeholder; a resume runs it again.
STOP_PARTIAL = "partial"
# A task called with `cancellable=True` that no flow call waits for any longer (`WorkQueue.cancel`):
# not launched, or its launch stopped; not ok, not retried, run again by a resume.
STOP_CANCELLED = "cancelled"


#: Why a task ends `cancelled`, in one line.
CANCELLED_REASON = "cancelled: no flow call waits for it any longer"


@dataclass(frozen=True)
class Partial[Out]:
    """What a Python task returns when it could do only part of its work (a server it
    needs was unavailable): `value`, its output as usual (checked against its output
    schema, written to its output file, and what the flow receives), and `reason`, why,
    in one line. The task finishes ok with stop `partial`, so the flow and later tasks go
    on; a resume runs it again (`Pipeline.run(resume=True)`)."""

    value: Out
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise TypeError(f"Partial: reason must say why the output is partial, in one line, not {self.reason!r}")


@dataclass(frozen=True)
class Deferral:
    """Why a task is not launched: `reason` in one line (logs, the CLI), and `cause`, the
    same as data for a reader that words it itself (the monitor): a `DeferralCause`.
    The queue's own causes: `deadline`, `grace_window` (past the deadline's grace window),
    `cannot_finish` (`need_s`, `left_s`) and `dependency_not_queued`; the first three name
    the time box's `flow_call` when the deadline is one's (`TimeBox`), not the run's. A
    runner adds its own (`rest`: its credential rests, `CredentialRests`)."""

    reason: str
    cause: DeferralCause


@dataclass(frozen=True)
class TaskResult:
    """A task's final result: how its last attempt ended.

    `task`: the `Task` it is the result of (its `attempt` is the last attempt's).
    `ok`: True when the task did its work (stop `completed`, `partial` or `skipped`).
    `stop`: why it ended, one stop value (`completed`, `invalid_output`, `deferred`, ...).
    `launch_result`: an agent task's `LaunchResult` (its last hop's); None for a Python task.
    `wall_s`: the last attempt's time in seconds.
    `reason`: why it ended that way, in one line; empty when nothing needs saying.
    `notes`: what the runner reports beside the verdict, as data (`context_warned`); empty: none.
    `route`: the route the last hop ran on; differs from the kind's first route after a failover.
    `hops`: each launch of the attempt, in order, one `Hop` per route it launched on.
    `rounds`: the rounds its output checks took (1: passed at once); 0 or None when none ran (refused, or no output contract).
    `round_errors`: the errors of each round that failed its checks, in order; the last is what stayed wrong.
    `max_corrections`: the corrections its kind allowed, the stop hook's and the resumes in all; None when no output contract ran.
    `changes`: the files the attempt changed under its `changes` patterns; None when it declares none.
    `skipped_hops`: the hops passed over without a launch, in order, each with why its credential rests.
    `cause`: a `deferred` result's cause as data (`Deferral.cause`); None for any other result.
    `retryable`: False when another attempt cannot end otherwise (a replay with no recording, the stub agent's
    example that failed its checks, a command the operating system refused to start). Neither the retrying
    runner nor the queue's `retry_on` tries it again.
    `replayed`: True when the attempt was played from a recording, not launched or called.
    `played`: the recording a replayed attempt played (`Played`); None for any other attempt.
    `payload`: domain data a `ResultEnricher` attached; never read by this module.
    """

    task: Task
    ok: bool
    stop: str
    launch_result: Any = None
    wall_s: float = 0.0
    reason: str = ""
    # The queue sends it as one `on_event("note", task, **notes)` when the task finishes.
    notes: dict[str, Any] = field(default_factory=dict)
    route: str = ""
    hops: tuple[Hop, ...] = ()
    rounds: int | None = None
    round_errors: tuple[tuple[str, ...], ...] = ()
    changes: Changes | None = None
    # Not in `hops`: no launch.
    skipped_hops: tuple[SkippedHop, ...] = ()
    cause: DeferralCause | None = None
    # A retrying runner stops at a result that is not retryable.
    retryable: bool = True
    replayed: bool = False
    payload: Any = None
    # Fields new since 0.1.0 come last, so a positional argument keeps its place.
    max_corrections: int | None = None
    played: Played | None = None

    @classmethod
    def skipped(cls, task: Task) -> TaskResult:
        return cls(task=task, ok=True, stop=STOP_SKIPPED)

    @classmethod
    def deferred(cls, task: Task, deferral: Deferral) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_DEFERRED, reason=deferral.reason, cause=deferral.cause)

    @classmethod
    def cancelled(cls, task: Task, reason: str = "") -> TaskResult:
        """The result of a task cancelled before it launched (`WorkQueue.cancel`)."""
        return cls(task=task, ok=False, stop=STOP_CANCELLED, reason=reason or CANCELLED_REASON)

    @classmethod
    def duplicate_key(cls, task: Task) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_DUPLICATE_KEY, reason=f"key {task.key!r} already in flight")

    @classmethod
    def launch_failed(cls, task: Task, reason: str) -> TaskResult:
        return cls(task=task, ok=False, stop=STOP_LAUNCH_FAILED, reason=reason)

    def summary(self) -> dict[str, Any]:
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
