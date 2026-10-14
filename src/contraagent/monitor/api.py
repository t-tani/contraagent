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

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, ValidationError, WrapValidator

from contraagent.execution.schemas import JournalRow, QuotaReading, QuotaRest, SkippedHop, TokenUsage  # part of this contract

API_VERSION = "3.3.0"


class Closed(BaseModel):
    """A shape the monitor builds itself: every key is declared here."""

    model_config = ConfigDict(extra="forbid")


class Open(BaseModel):
    """A shape that carries keys another component or a domain chose: the declared
    fields are what the monitor and its UI rely on, the rest pass through."""

    model_config = ConfigDict(extra="allow")


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


class Info(Closed):
    """What the UI shows before a run is picked: the title, the panel tabs to offer,
    and the version of this contract."""

    title: str
    panels: list[PanelInfo]
    api_version: str = Field(description="Version of this API contract (semver)")
    hosts: bool = Field(False, description="the runs come from many hosts (a hub): `/api/hosts` lists them")


# --- /api/runs -------------------------------------------------------------


#: Who executes a task: a coding agent, or this process in Python (`Task.executor`).
Executor = Literal["agent", "python"]


class TaskCounts(Closed):
    """A run's tasks (not attempts) by how they ended. `not_started`: refused for
    an input, or waiting behind a task that failed; `running`: running now (in a
    live run); `waiting`: queued."""

    total: int
    done: int
    failed: int
    not_started: int
    running: int = 0
    waiting: int
    skipped: int


class AccountQuota(Closed):
    """One account's subscription utilization over a run. `last` was taken when the
    account's last session started, so it leaves out that session's own use."""

    credential: str
    account: str = Field("", description="the account the readings are of (`QuotaReading.account`); empty when not known")
    first: QuotaReading
    last: QuotaReading


class RunSummary(Closed):
    """One run directory, as the run picker lists it."""

    run: str
    run_group: str = Field(description="the label grouping runs (`Run(run_group=)`); the run id when none was given")
    attempts: int = Field(description="journal rows: finished task attempts")
    ok: int
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
    stub: bool = Field(False, description="a stub run: the stub agent played its tasks (`Pipeline(stub=)`, `contraagent run --stub`)")
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

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from", description="the first day, YYYY-MM-DD")
    to: str = Field(description="the last day, YYYY-MM-DD")
    tz: str
    days: list[str] = Field(description="every day of the period, in order")


class TrendTotals(Closed):
    """The period's runs and attempts, summed."""

    runs: int = Field(description="runs with an attempt in the period, or started in it")
    attempts: int
    ok: int
    cost_usd: float | None = Field(description="what the coding agents reported; null when no attempt reported a cost")
    wall_s: float
    tokens: TokenUsage


class TrendDay(Closed):
    """One day: its attempts (by when they ended), and its cost per group (`Monitor(groups=)`; a kind in none is its own)."""

    day: str
    cost_usd: dict[str, float] = Field(description="group -> cost, USD; a group with no cost reported is absent")
    attempts: int
    ok: int


class TrendKind(Closed):
    """One kind over the period. A task is one key of one run; its last attempt in the period says how it ended."""

    kind: str
    group: str
    executor: Executor
    tasks: int
    tasks_ok: int
    attempts: int
    ok: int
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
    """One account's utilization of one window over the period: each day's and each hour's highest reading."""

    credential: str
    window: Literal["five_hour", "seven_day"]
    daily_peak: list[float | None] = Field(description="per day of `period.days`; null when no reading arrived that day")
    hourly_peak: list[float | None] = Field(
        description="per hour from the period's first instant (the first day's midnight in `tz`); null when no reading arrived in it"
    )


class TrendRest(Open):
    """A start or end of a credential's rest (`rests.jsonl`), with its run."""

    run: str
    ts: str | None = None
    event: str | None = None
    credential: str | None = None


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
    ok: int
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

#: `failed`: ran and failed. `blocked`: did not start (refused for a missing or
#: off-contract input, or waiting behind a failed or blocked task).
TaskState = Literal["pending", "running", "done", "failed", "skipped", "blocked"]


#: A flow call's state: `running` until it `returned`, `raised` or was `closed`.
FlowCallState = Literal["running", "returned", "raised", "closed"]


class FlowLoop(Closed):
    """A loop of a generator around a call site, and the pass the call site was in."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    line: int = Field(description="the loop's first line, which names it")
    pass_: int | None = Field(
        alias="pass",
        description="one iteration of this loop, numbered from 1 since the loop was last entered in that frame; null when not counted",
    )


class FlowFrame(Closed):
    """One frame of a flow path (outermost first): a call site in flow code."""

    function: str = Field(description="`module.qualname`")
    file: str = Field(description="relative to the run's working directory when under it, else as recorded")
    line: int
    loops: list[FlowLoop] = Field(
        default_factory=list,
        description="the loops of a generator whose pass `line` was in, outermost first; empty outside a loop and for any other frame",
    )


class TimeBoxInfo(Closed):
    """A flow call's own deadline (`time_box`), as `flow_calls.jsonl` records it."""

    started_at: str = Field(description="when the flow call started, where its deadline counts from (UTC ISO 8601)")
    deadline_s: float = Field(description="seconds from `started_at` to the deadline")
    grace_s: float = Field(description="seconds past the deadline its `finishing_kinds` still launch")
    slack_s: float = Field(description="seconds before the deadline from which its tasks are ordered for it")
    finishing_kinds: list[str] = Field(default_factory=list, description="the kinds that still launch past the deadline")


class FlowCallNode(Closed):
    """One flow call (`flow_calls.jsonl`): a generator the run drove, or the flow itself."""

    id: str = Field(description="`0` for the top flow, `<parent>.<n>` for a child")
    parent: str | None = Field(description="the parent flow call's id; null for a top flow")
    function: str = Field(description="`module.qualname` of the generator function (or of a flow that does not yield)")
    flow: list[FlowFrame] = Field(
        default_factory=list, description="the flow path where the parent yielded it, with its loops' passes; empty for a top flow"
    )
    state: FlowCallState
    error: str | None = Field(None, description="`<type>: <message>` of what it raised (or what closing it raised); else null")
    time_box: TimeBoxInfo | None = Field(None, description="its own deadline, for a flow call yielded through `time_box`; else null")


class DeferralCause(Closed):
    """Why the queue deferred a task, as data (`Deferral.cause`). `cause`: `deadline`,
    `grace_window` (past the deadline's grace window), `cannot_finish` (`need_s`, `left_s`),
    `dependency_not_queued`, `rest` (the credential of every hop it could take rests:
    `rests`), or a runner's own name."""

    cause: str
    need_s: float | None = Field(None, description="`cannot_finish`: the work it needed, in seconds")
    left_s: float | None = Field(None, description="`cannot_finish`: the time left before the deadline, in seconds")
    flow_call: str | None = Field(
        None, description="`deadline`, `grace_window`, `cannot_finish`: the flow call whose time box it is; null for the run's deadline"
    )
    rests: list[SkippedHop] = Field(default_factory=list, description="`rest`: each hop passed over and why its credential rests")


class PlanNode(Open):
    """A queued task (a `plan.jsonl` row, passed through) with its state and
    layout. The journal fields (`wall_s` .. `attempts`) appear once it finished.
    The origin fields (`flow` .. `flow_call`) say where the flow created it."""

    key: str
    kind: str
    unit: str = ""
    claims: list[str] = Field(default_factory=list, description="the names it holds while it runs, its kind's `claims` filled in")
    after: list[str] = Field(default_factory=list, description="task keys it waits for")
    executor: Executor = "agent"
    flow: list[FlowFrame] = Field(default_factory=list, description="the flow path: frames of flow code that created it, outermost first")
    created_from: list[str] = Field(default_factory=list, description="keys whose results its flow call had received when it created it")
    flow_call: str | None = Field(None, description="the id of the flow call that created it; null for a task with no origin")
    ts: str = Field("", description="when it was queued (absent for a node rebuilt from the journal)")
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


class QuotaCap(Closed):
    """One credential's quota caps (`[credentials.<name>] max_five_hour_pct`, `max_seven_day_pct`)."""

    credential: str
    five_hour_pct: float | None = None
    seven_day_pct: float | None = None


class CredentialRest(QuotaRest):
    """A rest of one credential (`rests.jsonl`): why it began, when, and when it ended."""

    since: str = Field(description="when it began resting, ISO 8601")
    ended: str = Field("", description="when it was found not resting again, ISO 8601; empty while it rests (or the run ended first)")


class PlanGroup(Closed):
    """A group: a column of the pipeline view (a kind, or the kinds `Monitor(groups=)` puts
    together), its members counted by state."""

    id: str
    label: str
    total: int
    done: int
    failed: int
    running: int
    pending: int
    skipped: int
    blocked: int


class ModelUsage(Closed):
    """What a run's agent sessions spent on one model of one coding agent, from each
    journal row's hops (a failover's hops on two models count apart). Python tasks have
    no model and are not counted."""

    agent: str
    model: str
    sessions: int = Field(description="hops: agent sessions launched on it (pool members tried on one hop count once)")
    calls: int = Field(0, description="API calls")
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    cost_usd: float | None = Field(None, description="what the coding agent reported; null when no session on it reported a cost")
    wall_s: float = 0.0


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
    tools: list[str] | None = Field(
        None, description="agent task: `[]`, a light launch with no tools (`agent_task(tools=())`); null, the tools its role allows"
    )
    executor: Executor | None = None
    function: str | None = Field(None, description="Python task: `module.qualname` of its function")
    signature: str | None = Field(None, description="Python task: the function's signature")
    doc: str | None = Field(None, description="Python task: the function's docstring")
    file: str | None = Field(None, description="Python task: the source file, relative to the run's working directory when inside it")
    line: int | None = Field(None, description="Python task: the function's first line in `file`")


# --- cursor ----------------------------------------------------------------


class StageEntry(Closed):
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
# What `contraagent.backends.streams.normalize_stream_event` emits: one
# renderable event per transcript line, the same vocabulary for every backend
# (`backends/claude/stream.py`, `backends/omp/trace.py`). Fields are as wide as
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
    value: float | str
    tone: Tone | None = None
    tip: str | None = None
    sub: list[list[str]] = Field(default_factory=list)


class TilesBody(_Body):
    type: Literal["tiles"] = "tiles"
    tiles: list[PanelTile]


class TableColumn(Closed):
    """A column of a table body: `id` names the key of each row it shows. `bar`: a bar in
    the cell, as long as the value against the column's largest."""

    id: str
    label: str
    align: Literal["start", "end"] | None = None
    format: ValueFormat | None = None
    bar: bool = False
    tip: str | None = None


class TableBody(_Body):
    """Rows of values, one key per column; a row's `_tone` is its status."""

    type: Literal["table"] = "table"
    columns: list[TableColumn]
    rows: list[dict[str, Any]]


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


class BlocksBody(_Body):
    """Bodies one under another: a panel of several parts."""

    type: Literal["blocks"] = "blocks"
    blocks: list[PanelBody]


#: The `type` of each typed body.
PANEL_TYPES = ("tiles", "table", "columns", "lines", "heatmap", "hbars", "blocks")


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
    | Annotated[BlocksBody, Tag("blocks")]
    | Annotated[JsonObject, Tag("untyped")],
    Discriminator(_panel_kind),
]
BlocksBody.model_rebuild()


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
