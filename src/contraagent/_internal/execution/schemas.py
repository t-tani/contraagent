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
  never guesses. `validate_assignment` throughout, because a value of the wrong
  type should fail loudly at write time instead of silently drifting the way an
  untyped dict does.

Each is a `RecordModel`: a reader ignores a field it does not know.

Nothing here knows what a stage or a unit *means*; `CursorStore` can be
given the legal vocabulary and checks it at the one call site that invents
a new value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator

from contraagent._internal.backends.launch import Stop
from contraagent._internal.dispatch.flow import FlowState
from contraagent._internal.dispatch.records import (
    Changes,
    DeferralCause,
    Executor,
    Frame,
    Hop,
    QuotaReading,
    RecordModel,
    SafetyStop,
    SkippedHop,
    TimeBoxRecord,
    TokenUsage,
)
from contraagent._internal.dispatch.task import STOP_CANCELLED, STOP_PARTIAL, STOP_SKIPPED
from contraagent._internal.routing.preflight import PreflightRecord

# --- journal ---------------------------------------------------------------

#: The `stop` values contraagent writes: every `Stop`, `skipped`, a Python task's `partial`, and
#: `cancelled` (a task called with `.options(cancellable=True)` that no flow call waited for).
#: The schema lists them as an enum; a row a domain's own code wrote with another value still validates.
JOURNAL_STOPS: tuple[str, ...] = (*(s.value for s in Stop), STOP_SKIPPED, STOP_PARTIAL, STOP_CANCELLED)


class JournalRow(RecordModel):
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
    #: Each safety stop of the attempt, in order (rounds and hops included): a safety
    #: classifier stopped part of a launch, and the launch went on (`SafetyStop`).
    safety_stops: list[SafetyStop] = Field(default_factory=list)
    #: Event types the coding agent sent that this contraagent does not read, with their
    #: counts (rounds and hops summed): a newer coding agent than its reader.
    unread_events: dict[str, int] = Field(default_factory=dict)
    #: What of the attempt's tokens could not be read (`LaunchResult.usage_unknown`; over its
    #: rounds and hops, `tokens` when any launch's are unknown, else `calls` when any launch's
    #: are): `calls`, `usage` holds the totals the coding agent printed, and its per-call
    #: figures (`resident`, `peak_context`) stand for one call of those totals; `tokens`, the
    #: tokens of a launch that ran are missing from `usage`. '' when every token was read.
    usage_unknown: Literal["", "calls", "tokens"] = ""
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
    #: The digest of each part of what the fingerprint covers, by the part's name
    #: (`Task.fingerprint_parts`): `definition`, `params`, `outside`, `output_of` (the file it
    #: fills in, as it was when the attempt started), `input_files` (the path and hash of each
    #: input file among its params, which `params` holds too); a run of 0.6 also has `output:<key>` (an
    #: output it read) and `after:<key>` (a task it only waited for). What a resume names when
    #: it runs the task again; empty in a run of an earlier release.
    fingerprint_parts: dict[str, str] = Field(default_factory=dict)
    #: The SHA-256 of the outside state its fingerprint covered when the attempt started
    #: (`agent_task(outside_state=)`); empty for a task that declares none.
    outside: str = ""
    #: Why a resume ran the task again although an earlier attempt of the run had finished it
    #: (its outside state changed, ...); empty when no earlier attempt had.
    rerun: str = ""
    #: For a task that fills in another task's file (`output_of`): the digest of the file as
    #: the attempt left it, which a resume compares the file with; empty for any other task.
    output_of_after: str = ""
    #: The flow call that created the task (`Origin.flow_call`); None for a task with no origin.
    flow_call: str | None = None
    #: The attempt was played from a recording (a replay), not launched or called: it spent nothing.
    replayed: bool = False


# --- launches --------------------------------------------------------------


class LaunchUsage(RecordModel):
    """A launch's tokens as `launches.jsonl` records them (`Usage.as_dict`)."""

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


class DeniedCall(RecordModel):
    """A tool call the coding agent refused (`denied`): the tool and the head of its input."""

    tool: str
    input: str = Field(description="the call's input as JSON, cut at 160 characters")


class LaunchRow(RecordModel):
    """One line of `runs/<run>/launches.jsonl`: one launch of a coding agent
    (`LaunchResult.as_dict`)."""

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
    safety_stops: list[SafetyStop] = Field(default_factory=list)
    unread_events: dict[str, int]
    usage_unknown: Literal["", "calls", "tokens"] = Field("", description="what of the launch's tokens could not be read")
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
    unwrapped: bool
    hook_errors: list[list[str]]
    context_budget: int | None
    context_warned: bool


# --- plan, flow calls, deferrals ------------------------------------------


class PlanRow(RecordModel):
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
        description="the credential its call options name (`.options(credential=)`), which every route of its kind ran it as; "
        "empty when it names none, or a run-wide override outranks it",
    )
    executor: Executor = "agent"
    flow: list[Frame] = Field(default_factory=list, description="the flow path: frames of flow code that created it, outermost first")
    created_from: list[str] = Field(
        default_factory=list,
        description="keys of the results that reached its flow call between that flow call's previous resume "
        "and the one in which it created the task",
    )
    flow_call: str | None = Field(None, description="the id of the flow call that created it; null for a task with no origin")
    given_from: list[str] = Field(
        default_factory=list,
        description="keys of the tasks whose outputs it was given in its params: an output, or one item of an output that "
        "is a list, whose JSON is a value of its params; shown only, never part of its fingerprint",
    )
    input_files: list[dict[str, str]] = Field(
        default_factory=list,
        description="the input files among its params, as its task call hashed them: `param` (its place in the params, "
        "`notes/0`), `path` and `sha256`; absent when it has none",
    )
    base_kind: str = Field(
        "",
        description="an implementation kind's base kind (`agent_task(implementations=)`), its group unless `groups` lists it; else empty",
    )

    def to_dict(self) -> dict[str, Any]:
        """The row as `plan.jsonl` records it: `base_kind`, `credential` and `input_files` only when set."""
        unset = {name for name in ("base_kind", "credential", "input_files") if not getattr(self, name)}
        return self.model_dump(mode="json", exclude=unset or None)


class FlowCallRow(RecordModel):
    """One line of `runs/<run>/flow_calls.jsonl`. `event` `start`: `parent`, `function`,
    `flow` (the flow path where the parent created it; empty for a top flow call) and, for a
    flow call started through `time_box`, `time_box`; `end`: `state` (`returned`, `raised`,
    `closed`) and `error` (`"<type>: <message>"` or null), for one that `raised`,
    `raised_at` and `raised_by` when known, and for a top flow call `unawaited` when it
    created a task nothing used. A row holds only its event's fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(serialize_by_alias=True)

    ts: str
    id: str
    event: Literal["start", "end"]
    parent: str | None = None
    function: str = ""
    flow: list[Frame] = Field(default_factory=list)
    time_box: TimeBoxRecord | None = None
    state: FlowState | None = None
    error: str | None = None
    raised_at: Frame | None = Field(
        None,
        description="where the exception left the flow call's own code (mostly the `await` that failed); "
        "absent when no frame of flow code is in it",
    )
    raised_by: str | None = Field(
        None,
        description="the key of the failed task the exception is (`TaskFailed.key`, the first one in an exception group), "
        "the same in every flow call it passes through; absent for an exception of flow code's own",
    )
    unawaited: list[str] | None = Field(
        None,
        description="for a top flow call: the keys of the tasks created in it or in the flow calls it started that no flow "
        "call awaited, no task waits for with `after=` and no flow call returned, in creation order; they ran all the same. "
        "Absent when there is none",
    )

    def to_dict(self) -> dict[str, Any]:
        """The row as `flow_calls.jsonl` records it: the fields set."""
        return self.model_dump(mode="json", exclude_unset=True)


class DeferredRow(RecordModel):
    """One line of `runs/<run>/deferred.jsonl`: a task the queue deferred, never launched;
    why in one line (`reason`) and as data (`cause`)."""

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


class RunInfo(RecordModel):
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
    flow: str | None = Field(
        None,
        description="`module.qualname` of the run's top flow (`Pipeline.run(flow)`): the runs of one flow, which the monitor's "
        "forecast compares; absent in a run of an earlier release",
    )
    preflight: PreflightRecord | None = Field(None, description="what the run's preflight did")


# --- resume cursor ---------------------------------------------------------


class HistoryEntry(RecordModel):
    """One transition, run- and unit-level alike: `{name, at}`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    name: str
    at: datetime


class Inflight(RecordModel):
    """Work items dispatched but not yet recorded, and who dispatched them.

    `pid`/`start_ticks` identify the dispatching process, not just a
    timestamp: `CursorStore.set_inflight` uses them to tell "the prior
    dispatcher is still alive" from "that process is gone" as a verifiable
    fact rather than a guess about how long a launch should take.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    item_ids: list[str] = Field(default_factory=list)
    since: datetime
    pid: int | None = None
    #: The start of `pid` as the OS records it (`RunInfo.start_ticks`).
    start_ticks: int | None = None


class UnitCursor(RecordModel):
    """One unit's position in the per-unit step sequence.

    `stage` is the run stage that was active the last time this unit's step
    advanced: the run's stage can move on while a unit mid-fan-out has not
    been touched, and comparing the two is how a reader tells a unit is
    lagging rather than done. `completed` lists the steps already applied.
    `loop_pass` is the pass number of a loop inside the step (0 until a loop records one).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    stage: str | None = None
    step: str | None = None
    completed: list[str] = Field(default_factory=list)
    loop_pass: int = 0
    inflight: Inflight | None = None
    history: list[HistoryEntry] = Field(default_factory=list)


class Cursor(RecordModel):
    """The run's one resume cursor.

    `markers` is a free-form store of event lists keyed by name (a stall, a
    skipped step, a reroute): no closed vocabulary, so values stay
    `list[dict]` rather than per-key models.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    schema_version: str
    run: str
    stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    units: dict[str, UnitCursor] = Field(default_factory=dict)
    markers: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    updated_at: datetime
