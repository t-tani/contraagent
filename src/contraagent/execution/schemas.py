"""pydantic models for the files a run leaves on disk.

Each is generic over the domain; the values a row holds (a hop, a rest, a flow path,
a deferral's cause) are the record types of `dispatch/records.py`.

* `JournalRow` — one line of `runs/<run>/journal.jsonl`, written when a
  task finishes. `extra="allow"`: a domain adds its own columns (counts of
  what the task produced, say) and they round-trip untouched. The monitor
  reads only the fields named here.
* `PlanRow`, `FlowCallRow`, `DeferredRow` — one line of `plan.jsonl`,
  `flow_calls.jsonl`, `deferred.jsonl`. `RestEvent` (`dispatch/records.py`) is one
  line of `rests.jsonl`.
* `Cursor` — the resume cursor (`CursorStore`): where a run is, so a resume
  never guesses. `extra="forbid"` throughout, because a renamed field or a
  typo'd stage name should fail loudly at write time instead of silently
  drifting the way an untyped dict does.

Nothing here knows what a stage or a unit *means*; `CursorStore` can be
given the legal vocabulary and checks it at the one call site that invents
a new value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contraagent.backends.launch import Stop
from contraagent.dispatch.flow import FlowState
from contraagent.dispatch.records import (
    Changes,
    DeferralCause,
    Executor,
    Frame,
    Hop,
    QuotaReading,
    SkippedHop,
    TimeBoxRecord,
    TokenUsage,
)
from contraagent.dispatch.task import STOP_PARTIAL, STOP_SKIPPED

# --- journal ---------------------------------------------------------------

#: The `stop` values contraagent writes: every `Stop`, `skipped`, and a Python task's `partial`.
#: The schema lists them as an enum; a row a domain's own code wrote with another value still validates.
JOURNAL_STOPS: tuple[str, ...] = (*(s.value for s in Stop), STOP_SKIPPED, STOP_PARTIAL)


class JournalRow(BaseModel):
    """One finished attempt. `key` is the stable `Task.key`, one task; `kind`
    and `unit` are its kind and unit; `executor` says who ran it; `stop` is
    `Stop.value` (or a Python task's completed/error)."""

    model_config = ConfigDict(extra="allow")

    ts: str
    run_id: str = ""
    #: The label grouping runs (`Run(run_group=)`); the run id when none was given.
    run_group: str = ""
    key: str
    attempt: int = 0
    kind: str
    executor: Executor = "agent"
    unit: str = ""
    #: The coding agent that ran the launch; empty for a Python task.
    agent: str = ""
    model: str = ""
    #: The `[credentials.<name>]` the launch authenticated as (never a secret).
    credential: str = ""
    route: str = ""
    hops: list[Hop] = Field(default_factory=list)
    #: The hops passed over without a launch because their credential rested (quota), in
    #: order; not in `hops`, which are launches.
    skipped_hops: list[SkippedHop] = Field(default_factory=list)
    stop: str = Field(json_schema_extra={"enum": list(JOURNAL_STOPS)})
    ok: bool
    wall_s: float = 0.0
    exit_code: int | None = None
    signal: int | None = None
    reason: str = ""
    #: Rounds the output contract took (1: on-contract the first time); None without one.
    rounds: int | None = None
    #: The errors of each round that failed its output checks, in order, cut at 5 each:
    #: each was sent back as the next round; after `invalid_output`, the last is what still stood.
    round_errors: list[list[str]] = Field(default_factory=list)
    #: What the plugin's stop hook sent back within a launch, before the agent ended its turn
    #: (Claude Code), one list per objection, cut at 5 each: a fix-up that took no round.
    hook_errors: list[list[str]] = Field(default_factory=list)
    #: Tokens of every API call of the attempt (its rounds and hops); None for a Python task or a launch that reported none.
    usage: TokenUsage | None = None
    #: What the coding agent reported the attempt cost, in USD (rounds and hops summed); None when it reports none.
    cost_usd: float | None = None
    #: Utilization readings received during the attempt, oldest first; empty when the agent reports none.
    quota: list[QuotaReading] = Field(default_factory=list)
    #: The queries of the web searches the attempt made, in call order (rounds and hops included).
    web_queries: list[str] = Field(default_factory=list)
    #: Event types the coding agent sent that this contraagent does not read, with their
    #: counts (rounds and hops summed): a newer coding agent than its reader.
    unread_events: dict[str, int] = Field(default_factory=dict)
    #: The files the attempt changed under its task's `changes` patterns; None when it declares none.
    changes: Changes | None = None
    #: The kind's `context_budget` the attempt's launches ran under (tokens of one API call's
    #: input); None without one. With `usage.peak_context`: how close the attempt came to it.
    context_budget: int | None = None
    #: The attempt's peak context passed the kind's `context_warn_pct`% of `context_budget`
    #: (the launch was not stopped for it).
    context_warned: bool = False
    #: A digest of what defines the task's work (`Task.fingerprint`): what a resume compares.
    fingerprint: str = ""
    #: The flow call that created the task (`Origin.flow_call`); None for a task with no origin.
    flow_call: str | None = None
    #: The attempt was played from a recording (a replay), not launched or called: it spent nothing.
    replayed: bool = False


# --- plan, flow calls, deferrals ------------------------------------------


class PlanRow(BaseModel):
    """One line of `runs/<run>/plan.jsonl`: a task a queue accepted, with its dependencies
    and its origin. A task with no origin (built by hand) has an empty `flow` and
    `created_from`, and `flow_call` null; `base_kind` is set only for an implementation kind."""

    model_config = ConfigDict(extra="allow", serialize_by_alias=True)

    ts: str = Field("", description="when it was queued (absent for a node rebuilt from the journal)")
    key: str
    kind: str
    unit: str = ""
    claims: list[str] = Field(default_factory=list, description="the names it holds while it runs, its kind's `claims` filled in")
    after: list[str] = Field(default_factory=list, description="task keys it waits for")
    priority: float = Field(0.0, description="its task call's `priority`: a tie-breaker in the queue, higher first")
    executor: Executor = "agent"
    flow: list[Frame] = Field(default_factory=list, description="the flow path: frames of flow code that created it, outermost first")
    created_from: list[str] = Field(default_factory=list, description="keys whose results its flow call had received when it created it")
    flow_call: str | None = Field(None, description="the id of the flow call that created it; null for a task with no origin")
    base_kind: str = Field(
        "",
        description="an implementation kind's base kind (`agent_task(implementations=)`), its group unless `groups` lists it; else empty",
    )

    def to_dict(self) -> dict:
        """The row as `plan.jsonl` records it: `base_kind` only when it is set."""
        return self.model_dump(mode="json", exclude=None if self.base_kind else {"base_kind"})


class FlowCallRow(BaseModel):
    """One line of `runs/<run>/flow_calls.jsonl`. `event` `start`: `parent`, `function`,
    `flow` (the flow path where the parent yielded it; empty for a top flow call) and, for a
    flow call yielded through `time_box`, `time_box`; `end`: `state` (`returned`, `raised`,
    `closed`) and `error` (`"<type>: <message>"` or null). A row holds only its event's fields."""

    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)

    ts: str
    id: str
    event: Literal["start", "end"]
    parent: str | None = None
    function: str = ""
    flow: list[Frame] = Field(default_factory=list)
    time_box: TimeBoxRecord | None = None
    state: FlowState | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """The row as `flow_calls.jsonl` records it: the fields set."""
        return self.model_dump(mode="json", exclude_unset=True)


class DeferredRow(BaseModel):
    """One line of `runs/<run>/deferred.jsonl`: a task the queue deferred, never launched;
    why in one line (`reason`) and as data (`cause`)."""

    model_config = ConfigDict(extra="forbid")

    ts: str
    key: str
    kind: str = ""
    unit: str = ""
    reason: str = ""
    cause: DeferralCause | None = None

    @field_validator("cause", mode="before")
    @classmethod
    def _no_cause(cls, v: object) -> object:
        return None if v == {} else v

    def to_dict(self) -> dict:
        """The row as `deferred.jsonl` records it: the cause's fields that are set, `{}` for none."""
        return {**self.model_dump(mode="json", exclude={"cause"}), "cause": self.cause.to_dict() if self.cause is not None else {}}


# --- resume cursor ---------------------------------------------------------


class HistoryEntry(BaseModel):
    """One transition, run- and unit-level alike: `{name, at}`."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str
    at: datetime


class Inflight(BaseModel):
    """Work items dispatched but not yet recorded, and who dispatched them.

    `pid`/`start_ticks` identify the dispatching process, not just a
    timestamp: `CursorStore.set_inflight` uses them to tell "the prior
    dispatcher is still alive" from "that process is gone" as a verifiable
    fact rather than a guess about how long a launch should take.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    item_ids: list[str] = Field(default_factory=list)
    since: datetime
    pid: int | None = None
    start_ticks: int | None = None


class UnitCursor(BaseModel):
    """One unit's position in the per-unit step sequence.

    `stage` is the run stage that was active the last time this unit's step
    advanced: the run's stage can move on while a unit mid-fan-out has not
    been touched, and comparing the two is how a reader tells a unit is
    lagging rather than done. `completed` lists the steps already applied.
    `loop_pass` is the pass number of a loop inside the step (0 until a loop records one).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    stage: str | None = None
    step: str | None = None
    completed: list[str] = Field(default_factory=list)
    loop_pass: int = 0
    inflight: Inflight | None = None
    history: list[HistoryEntry] = Field(default_factory=list)


class Cursor(BaseModel):
    """The run's one resume cursor.

    `markers` is a free-form store of event lists keyed by name (a stall, a
    skipped step, a reroute): no closed vocabulary, so values stay
    `list[dict]` rather than per-key models.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str
    run: str
    stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    units: dict[str, UnitCursor] = Field(default_factory=dict)
    markers: dict[str, list[dict]] = Field(default_factory=dict)
    updated_at: datetime
