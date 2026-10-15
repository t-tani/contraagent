"""The monitor's HTTP contract: one pydantic model per response and per live-feed event.

`Monitor` (core.py) computes its views as plain dicts so a Python caller can
use them without a web stack; the server validates each one against the
model here before it reaches the wire, and FastAPI publishes these models as
the OpenAPI document (`/api/openapi.json`, committed as `openapi.json` next to
this file). A front end built against that document is built against this
module.

Two rules keep the wire stable:

* Responses are serialized with `exclude_unset`: a key the core did not emit
  is not invented on the wire, so an optional field here (a contract
  spec's `status`, `fresh` ...) is absent rather than `null`
  when it does not apply. Readers must treat every non-required field as
  possibly missing.
* Shapes the monitor builds itself forbid unknown keys (`extra="forbid"`),
  so a key added in core.py without being declared here fails the tests
  instead of drifting silently. Shapes that pass a file another component
  wrote straight through (journal rows, plan rows, contract records, task
  definitions) and shapes a domain extends (a panel body, the `task_detail`
  callback's keys, a custom backend's transcript events) allow extra keys, and
  say so.

Bump `API_VERSION` when a field is removed, renamed or changes meaning
(major), or added (minor).
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    TypeAdapter,
    ValidationError,
    WrapValidator,
    field_validator,
    model_validator,
)

# The record types a run writes are part of this contract: a response holds them as they are.
from contraagent._internal.dispatch.flow import FlowState
from contraagent._internal.dispatch.records import DeferralCause, Executor, Frame, Rest, RestEvent, TimeBoxRecord, TokenUsage
from contraagent._internal.execution.schemas import JournalRow, PlanRow, QuotaReading
from contraagent._internal.routing.preflight import PreflightRecord
from contraagent._internal.routing.quota import QuotaCap

API_VERSION = "3.4.0"


class Closed(BaseModel):
    """A shape the monitor builds itself: every key is declared here."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class Open(BaseModel):
    """A shape that carries keys another component or a domain chose: the declared
    fields are what the monitor and its UI rely on, the rest pass through."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")


#: A JSON object whose keys a domain chooses (a panel's body, a contract file's content).
JsonObject = dict[str, Any]


# --- /api/info -------------------------------------------------------------


class PanelInfo(Closed):
    """A panel a domain registered: its tab label, tooltip and glyph, and what it is
    computed over (`run`: one run, a tab of the run; `trends`: the runs of a period)."""

    name: str
    title: str
    description: str
    icon: str
    scope: Literal["run", "trends"] = "run"
    tab: str = Field("", description="a trends panel's tab of the Trends page, with the panels of the same `tab`; '': on the first tab")


class ExportInfo(Closed):
    """What an export holds (`contraagent monitor export`): the monitor's views of some
    runs, written as files and read without a server."""

    exported_at: str = Field(description="when it was written, ISO 8601")
    runs: list[str] = Field(description="the runs it holds, newest activity first")
    left_out: list[str] = Field(description="the views it does not hold: `transcripts`, `processes`")
    redacted: list[str] = Field(
        description="what was taken out of the views: `paths` (made relative, else `<path>`), `host`, and each key named with --exclude"
    )


class Info(Closed):
    """What the UI shows before a run is picked: the title, the panel tabs to offer,
    and the version of this contract."""

    title: str
    panels: list[PanelInfo]
    api_version: str = Field(description="Version of this API contract (semver)")
    hosts: bool = Field(False, description="the runs come from many hosts (a hub): `/api/hosts` lists them")
    export: ExportInfo | None = Field(None, description="set only in an export: what it holds; a server never sends it")


# --- /api/runs -------------------------------------------------------------


class TaskCounts(Closed):
    """A run's tasks (not attempts) by how they ended. `not_started`: refused for
    an input, or waiting behind a task that failed; `running`: running now (in a
    live run); `waiting`: queued in a live run; `not_run`: deferred, or queued in a
    run that is no longer live (it will not run)."""

    total: int
    done: int
    partial: int = Field(0, description="tasks whose last result was `partial`: ok, the output a placeholder; not in `done`")
    failed: int
    not_started: int
    running: int = 0
    waiting: int
    not_run: int = 0
    skipped: int


class AccountQuota(Closed):
    """One account's subscription utilization over a run. `last` was taken when the
    account's last session started, so it leaves out that session's own use."""

    credential: str
    account: str = Field("", description="the account the readings are of (`QuotaReading.account`); empty when not known")
    first: QuotaReading
    last: QuotaReading
    rests: list[CredentialRest] = Field(
        default_factory=list,
        description="its rests now (`/api/hosts`): those a live run began and that have not ended, nor passed their `until`",
    )


class RunSummary(Closed):
    """One run directory, as the run picker lists it."""

    run: str
    run_group: str = Field(description="the label grouping runs (`Run(run_group=)`); the run id when none was given")
    attempts: int = Field(description="journal rows: finished task attempts")
    ok: int = Field(description="journal rows that passed, not counting `partial` ones")
    partial: int = Field(0, description="journal rows with stop `partial`")
    not_run: int = Field(0, description="journal rows of tasks that never ran: refused for an input (`invalid_input`) or skipped")
    tasks: TaskCounts
    cost_usd: float | None = Field(None, description="what the coding agents reported the run cost, in USD; null when none reported")
    tokens: TokenUsage = Field(description="tokens of every attempt, summed")
    quota: list[AccountQuota] = Field(
        default_factory=list, description="per credential (account): the run's first and last utilization reading; highest weekly use first"
    )
    wall_s: int = Field(description="sum of the rows' wall time, rounded to seconds")
    last_ts: str = Field(description="ISO time of the last journal row, else the directory's mtime")
    kinds: dict[str, int] = Field(description="journal rows per task kind")
    running: bool = Field(description="the process that runs it is alive")
    unresponsive: bool = Field(False, description="its host last reported it alive and has stopped reporting (a hub only)")
    host_id: str = Field("", description="the host that drives it; empty when its run.json does not say")
    run_uid: str = Field("", description="the id no other run has, on any host; empty when its run.json does not say")
    started_at: str
    stub: bool = Field(
        False,
        description="a stub run: the stub agent, or a replay's recordings, played its tasks (`Pipeline(stub=)`, `contraagent run --stub`)",
    )
    replay: str = Field(
        "",
        description="a replay: the directory of the recordings it played (`Pipeline(replay=)`), and with `record_missing` "
        "recorded into (then `stub` is false, and each played attempt's journal row says `replayed`); empty otherwise",
    )
    row_extras: list[str] = Field(
        default_factory=list,
        description="the journal columns that are the pipeline's own (`Run(row_extras=)`), in the order they first appear",
    )


class HostSummary(Closed):
    """One host that drives runs."""

    host_id: str
    up: bool = Field(description="its reports keep arriving (a hub: a heartbeat within the TTL; one host: always)")
    last_seen: str = Field(description="when it last reported, ISO 8601; empty when it does not report (one host)")
    interval_s: float | None = Field(description="seconds between its reports; null when it does not report")
    runs: int = Field(description="its runs")
    running: int = Field(description="its runs whose process is alive")
    unresponsive: int = Field(description="its runs last reported alive since it stopped reporting")


class Hosts(Closed):
    """The hosts, and each account's utilization over every run of every host."""

    hosts: list[HostSummary]
    quota: list[AccountQuota] = Field(
        default_factory=list,
        description="per credential (account): its first and last utilization reading over every run; highest weekly use first",
    )


# --- /api/trends -------------------------------------------------------------


class TrendPeriod(Closed):
    """The period: days `from`..`to`, both included, in the time zone `tz` (an IANA name)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from", description="the first day, YYYY-MM-DD")
    to: str = Field(description="the last day, YYYY-MM-DD")
    tz: str
    days: list[str] = Field(description="every day of the period, in order")


class TrendTotals(Closed):
    """The period's runs and attempts, summed."""

    runs: int = Field(description="runs with an attempt in the period, or started in it")
    attempts: int
    ok: int = Field(description="attempts that passed, not counting `partial` ones")
    partial: int = Field(0, description="attempts with stop `partial`: ok, counted apart from `ok`")
    cost_usd: float | None = Field(description="what the coding agents reported; null when no attempt reported a cost")
    wall_s: float
    tokens: TokenUsage


class TrendDay(Closed):
    """One day: its attempts (by when they ended), and its cost per group (`Monitor(groups=)`; a kind in none is its own)."""

    day: str
    cost_usd: dict[str, float] = Field(description="group -> cost, USD; a group with no cost reported is absent")
    attempts: int
    ok: int = Field(description="attempts that passed, not counting `partial` ones")
    partial: int = Field(0, description="attempts with stop `partial`: ok, counted apart from `ok`")


class TrendKind(Closed):
    """One kind over the period. A task is one key of one run; its last attempt in the period says how it ended."""

    kind: str
    group: str
    executor: Executor
    tasks: int
    tasks_ok: int = Field(description="tasks whose last attempt passed, not counting `partial` ones")
    tasks_partial: int = Field(0, description="tasks whose last attempt was `partial`")
    attempts: int
    ok: int = Field(description="attempts that passed, not counting `partial` ones")
    partial: int = Field(0, description="attempts with stop `partial`: ok, counted apart from `ok`")
    wall_s: float = Field(description="every attempt's wall time, summed")
    wall_s_median: float = Field(description="the median attempt's wall time")
    cost_usd: float | None
    tokens: TokenUsage


class TrendStop(Closed):
    """Attempts that ended on one `stop`, and by which kinds."""

    stop: str
    attempts: int
    kinds: dict[str, int]


class TrendDenial(Closed):
    """Tool calls the coding agent's permissions refused, of one tool (`launches.jsonl` `denied`)."""

    tool: str
    count: int
    kinds: dict[str, int]


class TrendQuota(Closed):
    """One account's utilization of one window over the period: each day's and each hour's highest reading.
    A credential whose token was replaced has one entry per account."""

    credential: str
    account: str = Field("", description="the account the readings are of (`QuotaReading.account`); empty when not known")
    window: str = Field(description="`five_hour`, `seven_day`, or another window a reading names (`seven_day_opus`)")
    daily_peak: list[float | None] = Field(description="per day of `period.days`; null when no reading arrived that day")
    hourly_peak: list[float | None] = Field(
        description="per hour from the period's first instant (the first day's midnight in `tz`); null when no reading arrived in it"
    )


class TrendRest(RestEvent):
    """A start or end of a credential's rest (a `rests.jsonl` row), with its run."""

    run: str


class TrendDeferral(Closed):
    """A deferred task (`deferred.jsonl`), with its run; `cause` is `DeferralCause.cause`."""

    run: str
    ts: str
    key: str
    kind: str
    cause: str
    reason: str


class TrendRun(Closed):
    """One run of the period: its attempts in the period."""

    run: str
    run_group: str
    host_id: str
    started_at: str
    finished_at: str
    last_ts: str = Field(description="when its last attempt in the period ended; empty when it has none")
    attempts: int
    ok: int = Field(description="attempts that passed, not counting `partial` ones")
    partial: int = Field(0, description="attempts with stop `partial`: ok, counted apart from `ok`")
    cost_usd: float | None
    wall_s: float
    stub: bool


class TrendStarts(Closed):
    """Run starts by weekday (`weekdays`, Monday first) and hour (`hours`) in the period's time zone: `counts[weekday][hour]`."""

    weekdays: list[str]
    hours: list[int]
    counts: list[list[int]]


class Trends(Closed):
    """What the runs of a period add up to (`Monitor.trends`). `bodies`: the same numbers as
    panel bodies (`{"type": "blocks", ...}`), in English, for a page with no words of its own;
    `panels`: the trend panels a domain registered (`Panel(scope="trends")`)."""

    period: TrendPeriod
    totals: TrendTotals
    daily: list[TrendDay]
    kinds: list[TrendKind]
    models: list[ModelUsage]
    stops: list[TrendStop]
    denials: list[TrendDenial]
    quota: list[TrendQuota]
    rests: list[TrendRest]
    deferred: list[TrendDeferral]
    deferred_causes: dict[str, int]
    runs: list[TrendRun]
    starts: TrendStarts
    bodies: dict[str, JsonObject]
    panels: list[PanelInfo]


# --- journal ---------------------------------------------------------------


class JournalPage(Closed):
    """Journal rows after a line offset; pass `total` back as `since` to get only newer rows."""

    entries: list[JournalRow]
    total: int


# --- plan ------------------------------------------------------------------

#: `failed`: ran and failed. `partial`: its last result was `partial` (ok, its output a
#: placeholder a resume makes again). `blocked`: did not start (refused for a missing or
#: off-contract input, or waiting behind a failed or blocked task).
TaskState = Literal["pending", "running", "done", "partial", "failed", "skipped", "blocked"]


class FlowCallNode(Closed):
    """One flow call (`flow_calls.jsonl`): a generator the run drove, or the flow itself."""

    id: str = Field(description="`0` for the top flow, `<parent>.<n>` for a child")
    parent: str | None = Field(description="the parent flow call's id; null for a top flow")
    function: str = Field(description="`module.qualname` of the generator function (or of a flow that does not yield)")
    flow: list[Frame] = Field(
        default_factory=list, description="the flow path where the parent yielded it, with its loops' passes; empty for a top flow"
    )
    state: FlowState
    error: str | None = Field(None, description="`<type>: <message>` of what it raised (or what closing it raised); else null")
    time_box: TimeBoxRecord | None = Field(None, description="its own deadline, for a flow call yielded through `time_box`; else null")


class PlanNode(PlanRow):
    """A queued task (a `plan.jsonl` row, passed through) with its state and
    layout. The journal fields (`wall_s` .. `attempts`) appear once it finished.
    The origin fields (`flow` .. `flow_call`) say where the flow created it."""

    state: TaskState
    level: int = Field(description="depth in the dependency graph, 0 for a task that waits for nothing")
    group: str
    wall_s: float = 0.0
    stop: str = ""
    route: str = ""
    attempts: int = 1
    deferred: str = Field(
        "",
        description="why the queue deferred it, never launched (`deferred.jsonl`): a deadline, a resting credential; empty when it was not",
    )
    deferred_cause: DeferralCause | None = Field(
        None, description="the same as data; null when it was not deferred, or the run recorded no cause"
    )


class CredentialRest(Rest):
    """A rest of one credential (`rests.jsonl`): why it began, when, and when it ended."""

    since: str = Field(description="when it began resting, ISO 8601")
    ended: str = Field("", description="when it was found not resting again, ISO 8601; empty while it rests (or the run ended first)")


class PlanGroup(Closed):
    """A group: a column of the pipeline view (a kind, the kinds `Monitor(groups=)` puts
    together, or the implementation kinds of a base kind), its members counted by state."""

    id: str
    label: str
    total: int
    done: int
    partial: int = 0
    failed: int
    running: int
    pending: int
    skipped: int
    blocked: int


class ModelUsage(Closed):
    """What a run's agent sessions spent on one model of one coding agent, from each
    journal row's hops (a failover's hops on two models count apart), a hop's spend on
    other models (`Hop.other_models`) on each of them. Python tasks have no model and are
    not counted."""

    agent: str
    model: str
    sessions: int = Field(
        description="hops: agent sessions launched on it (pool members tried on one hop count once); 0 for an other model only"
    )
    calls: int = Field(0, description="API calls")
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    cost_usd: float | None = Field(None, description="what the coding agent reported; null when no session on it reported a cost")
    wall_s: float = 0.0
    peak_context: int | None = Field(
        None, description="peak context: the largest input of one API call of a session on it (tokens); null when none reported one"
    )
    context_window: int | None = Field(
        None, description="its context window (tokens of one API call's input) as the coding agent reported it; null when none did"
    )


class Plan(Closed):
    """The queued tasks, their groups, and the flow calls that created them. A run with
    no `flow_calls.jsonl` (its tasks queued by hand, not by a flow) has no flow call."""

    nodes: list[PlanNode]
    groups: list[PlanGroup]
    flow_calls: list[FlowCallNode] = Field(default_factory=list, description="in start order")
    quota_caps: list[QuotaCap] = Field(default_factory=list, description="the run's credentials that have quota caps (`run.json`)")
    quota_rule: str = Field("", description="`module.qualname` of the run's quota rule (`Pipeline(quota_rule=)`); empty for none")
    rests: list[CredentialRest] = Field(
        default_factory=list, description="each rest of a credential in the run (`rests.jsonl`), in start order"
    )
    models: list[ModelUsage] = Field(default_factory=list, description="each model the run's agent sessions ran on, in order of first use")
    preflight: PreflightRecord | None = Field(
        None, description="what the run's preflight did (`run.json`); null when its run.json records none"
    )


# --- outputs (contracts) -----------------------------------------------------


class FileView(Closed):
    """A contract's file as it is now. `content` is the parsed JSON, else the
    text (cut at 20 000 characters, `truncated`), else null when unreadable."""

    exists: bool
    size: int = 0
    mtime: str = ""
    truncated: bool = False
    content: Any = None


class ContractField(Closed):
    """One top-level field of the model a contract file must satisfy."""

    name: str
    type: str = Field(description="JSON-schema type, `list[...]`, a `$ref` name, or `a|b` for a union")
    required: bool


ContractStatus = Literal["valid", "invalid", "refused", "pending", "failed", "running"]


class ContractSpec(Open):
    """One declared `OutputContract` / `InputContract` (its record, passed through,
    minus the raw JSON schema, which `fields` summarizes). `status`, `rounds`
    and `errors` are on outputs only."""

    io: Literal["output", "input"]
    path: str
    schema_name: str
    schema_ref: str = ""
    fresh: bool | None = None
    required: bool | None = None
    validators: list[str] = Field(default_factory=list)
    preserve: list[str] = Field(
        default_factory=list, description="output: JSON pointers to the parts of the file the task keeps as they were (`*`: every member)"
    )
    file: FileView
    fields: list[ContractField]
    status: ContractStatus | None = None
    rounds: int | None = Field(None, description="rounds it took to pass, when the journal recorded it")
    errors: list[str] = Field(default_factory=list)


class ContractRecord(Open):
    """What one task declared it reads and leaves behind (`contracts/<key>.json`)."""

    key: str
    kind: str = ""
    unit: str = ""
    executor: Executor = "agent"
    params: dict[str, str | int | float | bool] = Field(default_factory=dict, description="the task's scalar params")
    outputs: list[ContractSpec] = Field(default_factory=list)
    inputs: list[ContractSpec] = Field(default_factory=list)


class OutputTally(Closed):
    valid: int
    invalid: int
    refused: int
    pending: int
    failed: int
    running: int


class Outputs(Closed):
    contracts: list[ContractRecord]
    tally: OutputTally = Field(description="output contracts per status")


# --- definitions -----------------------------------------------------------


class DefinitionFile(Open):
    """One file that defines a task: its instructions (a task without a plugin), the role's agent file, a skill, the schema ..."""

    path: str
    part: str
    text: str


class TaskDefinition(Open):
    """What defined one kind of task in this run (`definitions/<kind>.json`).
    Beyond `kind`, the keys are the task adapter's choice; these are the ones
    the bundled adapters write."""

    kind: str
    role: str | None = None
    plugin_dirs: list[str] = Field(default_factory=list)
    files: list[DefinitionFile] = Field(default_factory=list)
    plugin: bool | None = None
    name: str | None = None
    root: str | None = None
    params: str | None = None
    requires: list[str] = Field(default_factory=list)
    output: str | None = None
    output_from: Literal["file", "message"] | None = Field(
        None, description="agent task: `file`, the agent writes its output; `message`, its final message is the output"
    )
    validators: list[str] = Field(default_factory=list)
    preserve: list[str] = Field(
        default_factory=list, description="agent task: JSON pointers to the parts of its output file it keeps (`agent_task(preserve=)`)"
    )
    output_of: str | None = Field(None, description="agent task: the kind whose output file it writes (`agent_task(output_of=)`)")
    base_kind: str | None = Field(None, description="agent task: an implementation kind's base kind (`agent_task(implementations=)`)")
    tools: list[str] | None = Field(
        None, description="agent task: `[]`, a light launch with no tools (`agent_task(tools=())`); null, the tools its role allows"
    )
    executor: Executor | None = None
    function: str | None = Field(None, description="Python task: `module.qualname` of its function")
    signature: str | None = Field(None, description="Python task: the function's signature")
    doc: str | None = Field(None, description="Python task: the function's docstring")
    file: str | None = Field(None, description="Python task: the source file, relative to the run's working directory when inside it")
    line: int | None = Field(None, description="Python task: the function's first line in `file`")
    retries: int | None = Field(
        None,
        description="Python task: the fresh attempts after the first, each after an exception of `retry_on` (`@python_task(retries=)`)",
    )
    retry_on: list[str] | None = Field(None, description="Python task: the exception classes that give an attempt a fresh one")


# --- cursor ----------------------------------------------------------------


class StageEntry(Closed):
    """One transition of the cursor (`HistoryEntry`), its time as `datetime.isoformat` gives it."""

    name: str
    at: str


class UnitPosition(Closed):
    """One unit's place in the per-unit step sequence; `inflight` are the work
    items dispatched but not yet recorded."""

    stage: str | None
    step: str | None
    completed: list[str]
    loop_pass: int
    inflight: list[str]


class CursorView(Closed):
    """The run's resume cursor. The REST endpoint answers `{}` (every field
    absent) for a run that keeps none; the live feed sends `null`."""

    stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    history: list[StageEntry] = Field(default_factory=list)
    updated_at: str = ""
    units: dict[str, UnitPosition] = Field(default_factory=dict)
    markers: dict[str, list[JsonObject]] = Field(default_factory=dict, description="free-form event lists by name")


# --- procs -----------------------------------------------------------------


class _Process(Closed):
    """What every process in the tree carries. `ProcNode` and `AgentProcess`
    differ only in whether the launch fields are required; as siblings they
    say so without a subclass narrowing its parent's optional fields, which
    type checkers reject."""

    pid: int
    age_s: int
    cmd: str = Field(description="the first three words of the command line")
    full_cmd: str
    children: list[ProcNode] = Field(default_factory=list)


class ProcNode(_Process):
    """A process in the run's tree (three levels deep at most). The launch fields
    are set on the topmost process of an agent launch."""

    key: str | None = None
    kind: str | None = None
    unit: str | None = None
    role: str | None = Field(None, description="the role it runs as, from the prompt's TELEMETRY line")
    model: str | None = None
    plugin: str | None = None


class AgentProcess(_Process):
    """One live agent launch: the topmost process of a coding-agent CLI, found by its
    `CONTRAAGENT_*` environment; or, for an agent behind a library-call backend (no
    child process), the run's own process, from its in-flight marker, with empty
    `cmd`, `full_cmd`, `role`, `model` and `plugin`."""

    key: str
    kind: str
    unit: str
    role: str = Field(description="the role it runs as, from the prompt's TELEMETRY line; empty when none")
    model: str
    plugin: str


class InflightPythonTask(Closed):
    """A Python task running inside the run's own process."""

    key: str
    kind: str
    unit: str
    pid: int
    age_s: int


class Procs(Closed):
    """The run's live processes. Everything but the run's own fields is empty when it is not alive."""

    run: str
    alive: bool
    pid: int | None
    argv: list[str]
    started_at: str
    max_workers: int | None
    run_group: str
    launches: list[AgentProcess]
    tree: list[ProcNode]
    python_tasks: list[InflightPythonTask]


# --- one task --------------------------------------------------------------


class TaskLaunch(Closed):
    """A live launch of the task (a child process, or an in-process marker with empty plugin/model/role/cmd)."""

    key: str | None
    kind: str | None
    unit: str | None
    pid: int | None
    age_s: int | None
    plugin: str | None
    model: str | None
    role: str | None
    cmd: str = Field(description="the full command line, cut at 600 characters")


class UpstreamTask(Closed):
    key: str
    kind: str
    unit: str
    executor: Executor
    outputs: list[ContractSpec]


class DownstreamTask(Closed):
    key: str
    kind: str
    unit: str
    executor: Executor


class TaskIO(Closed):
    """The task's params, what it reads and leaves behind, and its neighbours in the plan."""

    params: dict[str, Any]
    inputs: list[ContractSpec]
    outputs: list[ContractSpec]
    executor: Executor
    upstream: list[UpstreamTask]
    downstream: list[DownstreamTask]


class TaskDetail(Open):
    """One task, by its key. Open: the `task_detail` callback merges its own keys
    in (a failing one leaves `task_detail_error` instead)."""

    key: str = Field(description="the task key asked for")
    rows: list[JournalRow]
    launches: list[TaskLaunch] = Field(description="its launches running now; empty once it has finished (finished attempts are `rows`)")
    definition: TaskDefinition | None
    io: TaskIO
    stream: str | None = Field(description="the transcript's task key for /stream and /events/stream, null when it has none")
    row_extras: list[str] = Field(
        default_factory=list,
        description="the columns of `rows` that are the pipeline's own (`Run(row_extras=)`), in the order they first appear",
    )
    task_detail_error: str | None = None


# --- transcript ------------------------------------------------------------
#
# What `contraagent.backends.normalize_stream_line` emits: the
# renderable events of each transcript line, the same vocabulary for every backend
# (`backends/<agent>/wire.py`). Fields are as wide as
# the normalizers make them (a tool name the agent did not send is null).


class TranscriptEvent(Open):
    """Normalizers may add keys; the declared ones are what the UI renders."""


class LaunchEvent(TranscriptEvent):
    """Head of one invocation: the exact argv, cwd and the submitted prompt."""

    type: Literal["launch"]
    ts: float | None = Field(None, description="Unix time the launch started")
    argv: list[str]
    cwd: str
    prompt: str = Field(description="cut at 200 000 characters")
    prompt_truncated: int = Field(0, description="characters of the prompt not shown")


class MessageUpdateEvent(TranscriptEvent):
    """A piece of assistant prose: `ev` is `text_delta` or `thinking_delta` (omp may send its other delta kinds)."""

    type: Literal["message_update"]
    ev: str
    delta: str


class ToolStartEvent(TranscriptEvent):
    """A tool call starting (or omp's progress update for it). `call` pairs it with its end event."""

    type: Literal["tool_execution_start", "tool_execution_update"]
    tool: str | None
    cmd: str = Field(description="a one-line preview: the command, pattern, path, URL or query")
    intent: str
    call: str
    web_query: str | None = Field(None, description="the query, when the call is a web search")
    web_fetch: str | None = Field(None, description="the URL, when the call reads a web page")


class ToolEndEvent(TranscriptEvent):
    """A tool call's result. `tool` is empty for claude, which names only the call id."""

    type: Literal["tool_execution_end"]
    tool: str | None
    out: str
    err: bool
    call: str


class ToolCallEchoEvent(TranscriptEvent):
    """omp: a tool call carried on a message or turn (`acall`)."""

    type: Literal["acall"]
    tool: str | None
    cmd: str
    call: str
    intent: str
    web_query: str | None = Field(None, description="the query, when the call is a web search")
    web_fetch: str | None = Field(None, description="the URL, when the call reads a web page")


class ToolResultEchoEvent(TranscriptEvent):
    """omp: a tool result carried as a `toolResult` message (`aresult`)."""

    type: Literal["aresult"]
    tool: str | None
    call: str
    out: str
    err: bool


class MessageEvent(TranscriptEvent):
    """omp: a whole message or a turn's closing thinking. Either `role` + `text`, or `thinking`."""

    type: Literal["message_start", "message_end", "turn_end"]
    role: str | None = None
    text: str | None = None
    thinking: str | None = None


class NoticeEvent(TranscriptEvent):
    """A line of session bookkeeping: init, a retry, a rate-limit status, a custom message."""

    type: Literal["notice"]
    text: str


class RetryEvent(TranscriptEvent):
    """omp: the agent retrying after a provider error."""

    type: Literal["auto_retry_start"]
    attempt: int | None = None
    err: str = ""


class OtherEvent(TranscriptEvent):
    """Any other event: omp's bare lifecycle markers (`agent_start`, `agent_end`,
    `turn_start`, `auto_retry_end`) and whatever a custom backend's registered
    normalizer emits, including a known `type` whose fields do not match above."""

    type: str


_EVENT_MODELS: dict[str, type[TranscriptEvent]] = {}
for _m in (
    LaunchEvent,
    MessageUpdateEvent,
    ToolStartEvent,
    ToolEndEvent,
    ToolCallEchoEvent,
    ToolResultEchoEvent,
    MessageEvent,
    NoticeEvent,
    RetryEvent,
):
    for _t in get_args(_m.model_fields["type"].annotation):  # the Literal's values
        _EVENT_MODELS[_t] = _m


def _event_tag(v: Any) -> str:
    if isinstance(v, BaseModel):
        return "other" if isinstance(v, OtherEvent) else type(v).__name__
    t = v.get("type") if isinstance(v, dict) else None
    m = _EVENT_MODELS.get(t) if isinstance(t, str) else None
    return m.__name__ if m else "other"


def _lenient(v: Any, handler):
    """A transcript is an agent's raw output through a normalizer this process may
    not own: an event that does not fit its declared model is passed on as
    `OtherEvent` rather than failing the whole page."""
    try:
        return handler(v)
    except ValidationError:
        return OtherEvent.model_validate(v)


AnyTranscriptEvent = Annotated[
    Annotated[LaunchEvent, Tag("LaunchEvent")]
    | Annotated[MessageUpdateEvent, Tag("MessageUpdateEvent")]
    | Annotated[ToolStartEvent, Tag("ToolStartEvent")]
    | Annotated[ToolEndEvent, Tag("ToolEndEvent")]
    | Annotated[ToolCallEchoEvent, Tag("ToolCallEchoEvent")]
    | Annotated[ToolResultEchoEvent, Tag("ToolResultEchoEvent")]
    | Annotated[MessageEvent, Tag("MessageEvent")]
    | Annotated[NoticeEvent, Tag("NoticeEvent")]
    | Annotated[RetryEvent, Tag("RetryEvent")]
    | Annotated[OtherEvent, Tag("other")],
    Discriminator(_event_tag),
    WrapValidator(_lenient),
]


def _any_of_items(schema: dict) -> None:
    """`OtherEvent` matches any event, so the item schema is `anyOf` (match the
    first model whose `type` fits), not the `oneOf` the tagged union implies."""
    items = schema.get("items", {})
    if "oneOf" in items:
        items["anyOf"] = items.pop("oneOf")
        items["description"] = (
            "Dispatch on `type`; an event whose `type` is none of the literals above, or whose fields do not fit, is an OtherEvent."
        )


class StreamPage(Closed):
    """A page of one transcript. `total` is the file's line count: pass it back as
    `since` for the next page. The first page (`since=0`) is the tail; `behind`
    lines precede it, fetched by asking again with a smaller `since`."""

    events: list[AnyTranscriptEvent] = Field(json_schema_extra=_any_of_items)
    total: int
    behind: int


# --- panel bodies ------------------------------------------------------------
#
# What a panel returns: a typed body, drawn with the monitor's tiles, table and
# charts, or any other JSON object, shown as a JSON tree. A body is typed by its
# `type`; one of these types that does not validate is an error, never a JSON tree.

#: A status a value or a row is in: the monitor's status colours (`Tone` in the UI).
Tone = Literal["failed", "attention", "done", "running", "muted", "neutral"]
#: Every `Tone`, in order.
TONES: tuple[str, ...] = get_args(Tone)

#: How a number is written. `usd`: dollars; `pct`: a fraction (0.97 is 97%); `duration`:
#: seconds; `tokens`: a count of tokens (1.2k); `datetime`: an ISO 8601 time; `number`: as is.
ValueFormat = Literal["usd", "pct", "duration", "tokens", "datetime", "number"]


class _Body(Closed):
    title: str | None = Field(default=None, description="a heading over the body")
    collapsed: bool = Field(default=False, description="shown folded, under its title")


class PanelTile(Closed):
    """A figure as a tile (`cae-stat-tiles`). `sub`: lines under the value, each a row of facts."""

    id: str
    label: str
    value: int | float | str = Field(description="a number as given (an integer stays one), or text already formatted")
    tone: Tone | None = None
    tip: str | None = None
    sub: list[list[str]] = Field(default_factory=list)


class TilesBody(_Body):
    type: Literal["tiles"] = "tiles"
    tiles: list[PanelTile]


class TableColumn(Closed):
    """A column of a table body: `id` names the key of each row it shows. `bar`: a bar in
    the cell, as long as the value against the column's largest. `link`: the key of each
    row that holds the URL the cell leads to (http or https; any other is no link)."""

    id: str
    label: str
    align: Literal["start", "end"] | None = None
    format: ValueFormat | None = None
    bar: bool = False
    link: str | None = Field(default=None, min_length=1, description="the key of the row that holds the cell's URL")
    tip: str | None = None


class TableBody(_Body):
    """Rows of values, one key per column; a row's `_tone` is its status (a `Tone`)."""

    type: Literal["table"] = "table"
    columns: list[TableColumn]
    rows: list[dict[str, Any]]

    @field_validator("rows")
    @classmethod
    def _tones_known(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, row in enumerate(rows):
            tone = row.get("_tone")
            if tone is not None and tone not in TONES:
                raise ValueError(f"rows[{i}]._tone is {tone!r}; a tone is one of {', '.join(TONES)}")
        return rows


class ChartSeries(Closed):
    """One series: a value per label of the chart's `x`; null where it has none."""

    name: str
    values: list[float | None]


class ColumnsBody(_Body):
    """Vertical bars, one group per label of `x`; `stacked` puts the series of a label on one bar."""

    type: Literal["columns"] = "columns"
    x: list[str]
    series: list[ChartSeries]
    unit: ValueFormat | None = None
    stacked: bool = False


class LinesBody(_Body):
    type: Literal["lines"] = "lines"
    x: list[str]
    series: list[ChartSeries]
    unit: ValueFormat | None = None


class HeatmapBody(_Body):
    """A value per row (`y`) and column (`x`): `values[row][column]`, null where there is none."""

    type: Literal["heatmap"] = "heatmap"
    x: list[str]
    y: list[str]
    values: list[list[float | None]]
    unit: ValueFormat | None = None


class HBar(Closed):
    label: str
    value: float
    tone: Tone | None = None


class HBarsBody(_Body):
    """Horizontal bars, one per label, in the order given."""

    type: Literal["hbars"] = "hbars"
    bars: list[HBar]
    unit: ValueFormat | None = None


class NoteBody(_Body):
    """Text beside the figures: what a part shows, how to read a number. `text` is
    markdown (paragraphs, lists, emphasis, code, http(s) links; any markup in it is shown
    as text). `tone` marks a note that warns (`attention`) or reports a failure (`failed`)."""

    type: Literal["note"] = "note"
    text: str
    tone: Tone | None = None


class GridCell(Closed):
    """One cell of a status grid: the state it is in, in words, and that state's tone.
    `tip` adds a fact about this cell to its tooltip (a run's id, a count)."""

    label: str = Field(min_length=1)
    tone: Tone
    tip: str | None = None


class StatusGridBody(_Body):
    """A state per row (`y`) and column (`x`): `cells[row][column]`, null where there is
    none. Each cell is coloured by its tone and named by its label (in the legend, the
    tooltip and the table): the states of hourly cycles by day, say."""

    type: Literal["status_grid"] = "status_grid"
    x: list[str]
    y: list[str]
    cells: list[list[GridCell | None]]

    @model_validator(mode="after")
    def _shaped(self) -> StatusGridBody:
        if len(self.cells) != len(self.y):
            raise ValueError(f"cells has {len(self.cells)} rows; y has {len(self.y)}")
        for i, row in enumerate(self.cells):
            if len(row) != len(self.x):
                raise ValueError(f"cells[{i}] has {len(row)} cells; x has {len(self.x)}")
        return self


class BlocksBody(_Body):
    """Bodies one under another: a panel of several parts."""

    type: Literal["blocks"] = "blocks"
    blocks: list[PanelBody]


#: The `type` of each typed body.
PANEL_TYPES = ("tiles", "table", "columns", "lines", "heatmap", "hbars", "status_grid", "note", "blocks")


def _panel_kind(v: Any) -> str:
    t = v.get("type") if isinstance(v, dict) else getattr(v, "type", None)
    return t if t in PANEL_TYPES else "untyped"


#: What a panel returns: a typed body, or any JSON object (shown as a JSON tree).
PanelBody = Annotated[
    Annotated[TilesBody, Tag("tiles")]
    | Annotated[TableBody, Tag("table")]
    | Annotated[ColumnsBody, Tag("columns")]
    | Annotated[LinesBody, Tag("lines")]
    | Annotated[HeatmapBody, Tag("heatmap")]
    | Annotated[HBarsBody, Tag("hbars")]
    | Annotated[StatusGridBody, Tag("status_grid")]
    | Annotated[NoteBody, Tag("note")]
    | Annotated[BlocksBody, Tag("blocks")]
    | Annotated[JsonObject, Tag("untyped")],
    Discriminator(_panel_kind),
]
BlocksBody.model_rebuild()

_PANEL_BODY = TypeAdapter(PanelBody)


def panel_data(value: Any) -> Any:
    """A panel's body as the monitor serves it, a run panel's and a trends panel's alike:
    checked against `PanelBody` (a typed body that does not validate raises, it is never
    shown as a JSON tree), then as JSON data."""
    return _PANEL_BODY.dump_python(_PANEL_BODY.validate_python(value), mode="json", exclude_unset=True)


# --- live feeds (Server-Sent Events) -------------------------------------
#
# `/events?run=` and `/events/stream?run=&key=` send `text/event-stream`
# messages: `event: <name>` plus one `data:` line of JSON. Each model below is
# one message, `event` being the SSE event name and `data` the parsed JSON.


class JournalMessage(Closed):
    """One journal row, sent once per row: the whole journal on connect, then each new row."""

    event: Literal["journal"]
    data: JournalRow


class ProcsMessage(Closed):
    """The live processes, sent when a launch starts or ends (not on every age tick)."""

    event: Literal["procs"]
    data: Procs


class PlanMessage(Closed):
    event: Literal["plan"]
    data: Plan


class OutputsMessage(Closed):
    event: Literal["outputs"]
    data: Outputs


class CursorMessage(Closed):
    """The resume cursor, or null for a run that keeps none."""

    event: Literal["cursor"]
    data: CursorView | None


class PanelMessage(Closed):
    """A domain panel's body (`PanelBody`), sent when it changed. `{"error": ...}`
    when the panel raised."""

    event: str = Field(pattern=r"^panel:.+$", description="`panel:<name>`, one per run panel in /api/info `panels`")
    data: PanelBody


class FeedReady(Closed):
    journal: int = Field(description="journal rows sent before this message")


class ReadyMessage(Closed):
    """Sent once per connection, after the first round of messages: the journal
    replayed so far and the current value of every other view. A row that
    arrives after it is new, not part of the replay."""

    event: Literal["ready"]
    data: FeedReady


class StreamMessage(Closed):
    """`/events/stream`: the first message is the transcript's tail page, then each
    message carries only the events after the previous one."""

    event: Literal["stream"]
    data: StreamPage


#: One message of `/events?run=`.
RunEvent = JournalMessage | ProcsMessage | PlanMessage | OutputsMessage | CursorMessage | PanelMessage | ReadyMessage

# Models that name a later one are built now, in this module's names.
for _model in (AccountQuota, RunSummary, Hosts, Trends, _Process):
    _model.model_rebuild()
