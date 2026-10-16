"""pydantic models for the files a run leaves on disk.

Each is generic over the domain; the values a row holds (a hop, a rest, a flow path,
a deferral's cause) are the record types of `dispatch/records.py`.

* `JournalRow` — one line of `runs/<run>/journal.jsonl`, written when a
  task finishes. `extra="allow"`: a domain adds its own columns (counts of
  what the task produced, say) and they round-trip untouched. The monitor
  reads only the fields named here.
* `LaunchRow` — one line of `runs/<run>/launches.jsonl`: one launch, as
  `LaunchResult.as_dict` writes it.
* `PlanRow`, `FlowCallRow`, `DeferredRow` — one line of `plan.jsonl`,
  `flow_calls.jsonl`, `deferred.jsonl`. `RestEvent` and `ServiceEvent`
  (`dispatch/records.py`) are one line of `rests.jsonl` and of `services.jsonl`.
* `RunInfo` — `runs/<run>/run.json`: who drives the run, which run it is, its run format.
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
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contraagent._internal.backends.launch import Stop
from contraagent._internal.dispatch.flow import FlowState
from contraagent._internal.dispatch.records import (
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
from contraagent._internal.dispatch.task import STOP_PARTIAL, STOP_SKIPPED
from contraagent._internal.routing.preflight import PreflightRecord

# --- journal ---------------------------------------------------------------

#: The `stop` values contraagent writes: every `Stop`, `skipped`, and a Python task's `partial`.
#: The schema lists them as an enum; a row a domain's own code wrote with another value still validates.
JOURNAL_STOPS: tuple[str, ...] = (*(s.value for s in Stop), STOP_SKIPPED, STOP_PARTIAL)


class JournalRow(BaseModel):
    """One finished attempt. `key` is the stable `Task.key`, one task; `kind`
    and `unit` are its kind and unit; `executor` says who ran it; `stop` is
    `Stop.value` (or a Python task's completed/error)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

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
    #: The correction rounds its kind allowed after the first (`max_corrections`); None
    #: without an output contract, or in a run format before it was recorded.
    max_corrections: int | None = None
    #: What the plugin's stop hook sent back within a launch, before the agent ended its turn
    #: (Claude Code), one list per objection, cut at 5 each: none of them took a correction round.
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
    #: The SHA-256 of the outside state its fingerprint covered when the attempt started
    #: (`agent_task(outside_state=)`); empty for a task that declares none.
    outside: str = ""
    #: Why a resume ran the task again although an earlier attempt of the run had finished it
    #: (its outside state changed, ...); empty when no earlier attempt had.
    rerun: str = ""
    #: The flow call that created the task (`Origin.flow_call`); None for a task with no origin.
    flow_call: str | None = None
    #: The attempt was played from a recording (a replay), not launched or called: it spent nothing.
    replayed: bool = False


# --- launches --------------------------------------------------------------


class LaunchUsage(BaseModel):
    """A launch's tokens as `launches.jsonl` records them (`Usage.as_dict`)."""

    model_config = ConfigDict(extra="forbid")

    n_calls: int = Field(description="API calls the coding agent made")
    resident: int = Field(description="the whole input of the first API call; 0 with no call")
    peak_context: int = Field(description="the whole input of the largest API call; 0 with no call")
    context_total: int = Field(description="every API call's whole input, summed")
    input: int
    cache_read: int
    cache_creation: int
    output_total: int = Field(description="the output tokens of the launch's result")


class LaunchQuota(QuotaReading):
    """The latest quota reading of a launch and its quota refusal, as `launches.jsonl` records
    them in one (`rate_limit`): `status` `quota` for a refusal with no reading."""

    retry_after_s: float | None = Field(None, description="the cool-off the provider stated with a quota refusal, in seconds")


class DeniedCall(BaseModel):
    """A tool call the coding agent refused (`denied`): the tool and the head of its input."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    input: str = Field(description="the call's input as JSON, cut at 160 characters")


class LaunchRow(BaseModel):
    """One line of `runs/<run>/launches.jsonl`: one launch of a coding agent
    (`LaunchResult.as_dict`)."""

    model_config = ConfigDict(extra="forbid")

    ts: str = Field(description="when the launch started")
    label: str
    wall_s: float
    stop: Stop
    ok: bool
    exit: int | None = Field(description="the coding agent's exit code; null when it did not exit")
    agent: str
    cli_version: str
    argv: list[str] = Field(description="the command line, a prompt after `-p` cut at 200 characters")
    model: str
    session_id: str
    num_turns: int | None
    duration_api_ms: int | None
    cost_usd: float | None
    usage: LaunchUsage
    context_window: int | None
    context_pct: float | None
    rate_limit: LaunchQuota | None
    permission_denials: int = Field(description="tool calls refused")
    denied: list[DeniedCall] = Field(description="the first 10 refused tool calls")
    tool_uses: dict[str, int]
    hollow: bool
    tool_args: dict[str, list] = Field(description="by tool, the first 5 inputs of its calls")
    web_queries: list[str]
    unread_events: dict[str, int]
    init_model: str
    init_tools: int
    init_errors: list[dict]
    api_retries: int
    retry_errors: dict[str, int]
    result_head: str = Field(description="the final message, cut at 200 characters")
    stderr_tail: str = Field(description="the end of standard error, 300 characters")
    rounds: int | None
    round_errors: list[list[str]]
    round_costs: list[float | None]
    max_corrections: int | None = Field(None, description="the correction rounds its kind allowed after the first")
    unwrapped: bool
    hook_errors: list[list[str]]
    context_budget: int | None
    context_warned: bool


# --- plan, flow calls, deferrals ------------------------------------------


class PlanRow(BaseModel):
    """One line of `runs/<run>/plan.jsonl`: a task a queue accepted, with its dependencies
    and its origin. A task with no origin (built by hand) has an empty `flow` and
    `created_from`, and `flow_call` null; `base_kind` is set only for an implementation kind,
    `credential` only for a task whose call names one."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", serialize_by_alias=True)

    ts: str = Field("", description="when it was queued (absent for a node rebuilt from the journal)")
    key: str
    kind: str
    unit: str = ""
    claims: list[str] = Field(default_factory=list, description="the names it holds while it runs, its kind's `claims` filled in")
    after: list[str] = Field(default_factory=list, description="task keys it waits for")
    priority: float = Field(0.0, description="its task call's `priority`: a tie-breaker in the queue, higher first")
    credential: str = Field(
        "",
        description="the credential its task call names (`credential=`), which every route of its kind ran it as; "
        "empty when it names none, or a run-wide override outranks it",
    )
    executor: Executor = "agent"
    flow: list[Frame] = Field(default_factory=list, description="the flow path: frames of flow code that created it, outermost first")
    created_from: list[str] = Field(default_factory=list, description="keys whose results its flow call had received when it created it")
    flow_call: str | None = Field(None, description="the id of the flow call that created it; null for a task with no origin")
    base_kind: str = Field(
        "",
        description="an implementation kind's base kind (`agent_task(implementations=)`), its group unless `groups` lists it; else empty",
    )

    def to_dict(self) -> dict[str, Any]:
        """The row as `plan.jsonl` records it: `base_kind` and `credential` only when set."""
        unset = {name for name in ("base_kind", "credential") if not getattr(self, name)}
        return self.model_dump(mode="json", exclude=unset or None)


class FlowCallRow(BaseModel):
    """One line of `runs/<run>/flow_calls.jsonl`. `event` `start`: `parent`, `function`,
    `flow` (the flow path where the parent yielded it; empty for a top flow call) and, for a
    flow call yielded through `time_box`, `time_box`; `end`: `state` (`returned`, `raised`,
    `closed`) and `error` (`"<type>: <message>"` or null). A row holds only its event's fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", serialize_by_alias=True)

    ts: str
    id: str
    event: Literal["start", "end"]
    parent: str | None = None
    function: str = ""
    flow: list[Frame] = Field(default_factory=list)
    time_box: TimeBoxRecord | None = None
    state: FlowState | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The row as `flow_calls.jsonl` records it: the fields set."""
        return self.model_dump(mode="json", exclude_unset=True)


class DeferredRow(BaseModel):
    """One line of `runs/<run>/deferred.jsonl`: a task the queue deferred, never launched;
    why in one line (`reason`) and as data (`cause`)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

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

    def to_dict(self) -> dict[str, Any]:
        """The row as `deferred.jsonl` records it: the cause's fields that are set, `{}` for none."""
        return {**self.model_dump(mode="json", exclude={"cause"}), "cause": self.cause.to_dict() if self.cause is not None else {}}


# --- run.json --------------------------------------------------------------


class RunInfo(BaseModel):
    """`runs/<run>/run.json`: who drives the run (`pid`, `start_ticks`, `host_id`), which run
    it is (`run_id`, `run_uid`), its run format, and what the run recorded about itself since.
    `Run.update_info` may add fields of a caller's own."""

    model_config = ConfigDict(extra="allow")

    format: int = Field(1, ge=1, description="the run format of the run directory; a run.json without it is of run format 1")
    run_id: str
    run_uid: str = Field(description="the id no other run has, on any host; kept when the run is resumed")
    host_id: str = Field(description="the host that drives the run (`CONTRAAGENT_HOST_ID`, else the host name)")
    run_group: str
    pid: int
    start_ticks: int | None = Field(
        description="the start of `pid` as the host's OS records it: on Linux clock ticks after boot "
        "(`/proc/<pid>/stat`), on macOS and Windows microseconds after the epoch; compared only "
        "for equality on this host, so a recycled pid is not taken for the run's process"
    )
    argv: list[str]
    cwd: str = Field(description="the run's working directory, absolute")
    started_at: str = Field(description="when the latest run start began")
    finished_at: str | None = Field(None, description="when the run finished; absent while it runs or after it was killed")
    stub: bool | None = Field(None, description="true for a stub run")
    replay: str | None = Field(None, description="the recordings directory a replay plays")
    max_workers: int | None = Field(None, description="how many tasks run at once")
    quota_caps: dict[str, dict[Literal["five_hour_pct", "seven_day_pct"], float]] | None = Field(
        None, description="by credential, the quota caps of each that has one"
    )
    quota_rule: str | None = Field(None, description="the quota rule's `module.qualname`; empty without one")
    preflight: PreflightRecord | None = Field(None, description="what the run's preflight did")


# --- resume cursor ---------------------------------------------------------


class HistoryEntry(BaseModel):
    """One transition, run- and unit-level alike: `{name, at}`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", validate_assignment=True)

    name: str
    at: datetime


class Inflight(BaseModel):
    """Work items dispatched but not yet recorded, and who dispatched them.

    `pid`/`start_ticks` identify the dispatching process, not just a
    timestamp: `CursorStore.set_inflight` uses them to tell "the prior
    dispatcher is still alive" from "that process is gone" as a verifiable
    fact rather than a guess about how long a launch should take.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", validate_assignment=True)

    item_ids: list[str] = Field(default_factory=list)
    since: datetime
    pid: int | None = None
    #: The start of `pid` as the OS records it (`RunInfo.start_ticks`).
    start_ticks: int | None = None


class UnitCursor(BaseModel):
    """One unit's position in the per-unit step sequence.

    `stage` is the run stage that was active the last time this unit's step
    advanced: the run's stage can move on while a unit mid-fan-out has not
    been touched, and comparing the two is how a reader tells a unit is
    lagging rather than done. `completed` lists the steps already applied.
    `loop_pass` is the pass number of a loop inside the step (0 until a loop records one).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", validate_assignment=True)

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

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str
    run: str
    stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    units: dict[str, UnitCursor] = Field(default_factory=dict)
    markers: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    updated_at: datetime
