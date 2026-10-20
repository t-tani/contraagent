"""The facts a run records, one type each, used by every layer that writes or reads them.

A task's result (`TaskResult`), the run's files (`journal.jsonl`, `plan.jsonl`,
`flow_calls.jsonl`, `deferred.jsonl`, `rests.jsonl`, `services.jsonl`) and the monitor's HTTP API all hold
these values; each is defined here once, as a pydantic model, so a file row and an API
response are the same type. Values are frozen. Nothing here imports anything outside the
standard library and pydantic.

* `Executor`: who executes a task.
* `Loop`, `Frame`: a flow path (`Origin.flow`, plan and flow call `flow`).
* `Changes`: the files one attempt changed.
* `TokenUsage`, `OtherModel`, `Hop`: one launch of an attempt on one route.
* `SafetyStop`: a safety classifier that stopped part of a launch, which went on.
* `Window`, `WINDOWS`, `QuotaWindow`, `QuotaReading`: a subscription's utilization, as a
  coding agent reports it, and the windows it is measured over.
* `Rest`, `SkippedHop`, `RestEvent`: a credential that rests on its quota, a hop an
  attempt passed over because of it, and a line of `rests.jsonl`.
* `DeferralCause`: why a task was deferred, as data.
* `TimeBoxRecord`: a flow call's time box as `flow_calls.jsonl` records it.
* `ServiceEvent`: a service's start or stop, a line of `services.jsonl`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, ClassVar, Literal, NamedTuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

#: Who executes a task: a coding agent, or this process in Python (`Task.executor`).
Executor = Literal["agent", "python"]


# --- flow path ---------------------------------------------------------------


class Loop(BaseModel):
    """A `for` or `while` loop of an async flow around a call site, and the pass the call
    site was in."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True)

    line: int = Field(description="the loop's first line, which names it")
    pass_: int | None = Field(
        validation_alias=AliasChoices("pass", "pass_"),
        serialization_alias="pass",
        description="one iteration of this loop, numbered from 1 since the loop was last entered in that frame; null when not counted",
    )


class Frame(BaseModel):
    """One frame of a flow path (outermost first): a call site in flow code where a task
    was created. A comprehension is not a loop."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True)

    function: str = Field(description="`module.qualname`")
    file: str = Field(description="relative to the run's working directory when under it, else as recorded")
    line: int
    loops: tuple[Loop, ...] = Field(
        default=(),
        description="the loops of an async flow whose pass `line` was in, outermost first; empty outside a loop and for any other frame",
    )


# --- changes -----------------------------------------------------------------


class Changes(BaseModel):
    """The files one attempt changed under its task's `changes` patterns, as paths relative
    to the working directory: those it `created`, `modified` and `deleted`. Of a failed
    attempt's created files, `removed` lists those the runner removed, and `kept` those it
    left in place because the kind keeps them (`keep_failed_changes`)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    created: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    #: The created files removed because the attempt failed.
    removed: tuple[str, ...] = ()
    #: The created files left in place though the attempt failed: its kind keeps them
    #: (`keep_failed_changes`).
    kept: tuple[str, ...] = ()


# --- hop ---------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Tokens summed over API calls: an attempt's (its rounds and hops, in `JournalRow.usage`)
    or one hop's (`Hop.usage`)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    input: int = 0
    output: int = 0
    #: Input served from the prompt cache.
    cache_read: int = 0
    #: Input written to the prompt cache.
    cache_creation: int = 0
    #: API calls the coding agent made.
    calls: int = 0
    #: The whole input of the attempt's first API call (cache included): what the coding agent
    #: loads before the task starts (system prompt, tools, the prompt). None when no call was read.
    resident: int | None = None
    #: The peak context: the whole input of the largest API call (cache read and cache write
    #: included), the largest over every hop and round summed here. None when no call was read.
    peak_context: int | None = None
    #: The context window of the model whose call is the peak context, as the coding agent
    #: reports it (`LaunchResult.context_window`); None when it reports none.
    context_window: int | None = None


class OtherModel(BaseModel):
    """What a hop spent on a model other than its own (`Hop.other_models`)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    #: Part of the hop's `cost_usd`; None when the coding agent reported none.
    cost_usd: float | None = None
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0

    def plus(self, other: OtherModel) -> OtherModel:
        """This spend and `other`'s, summed: the cost None only when neither reported one."""
        both = self.cost_usd is None and other.cost_usd is None
        return OtherModel(
            cost_usd=None if both else (self.cost_usd or 0.0) + (other.cost_usd or 0.0),
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=self.cache_read + other.cache_read,
            cache_creation=self.cache_creation + other.cache_creation,
        )


class Hop(BaseModel):
    """One launch of an attempt on one route of its failover chain: where it ran and how
    it ended."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    #: The route's label in its chain (`Route.label`).
    route: str = ""
    #: The coding agent that ran the launch.
    agent: str = ""
    model: str = ""
    #: The `[credentials.<name>]` this hop authenticated as (a hop may change it).
    credential: str = ""
    stop: str = ""
    wall_s: float = 0.0
    #: What the coding agent reported this hop cost, in USD; None when it reports none.
    cost_usd: float | None = None
    #: This hop's tokens (its rounds, and pool members tried on it, summed); None when it
    #: reported no API call. The attempt's `usage` is every hop's.
    usage: TokenUsage | None = None
    #: What the hop spent on models other than `model`, by model (Claude Code summarizes a
    #: fetched page on a smaller one); their cost is in `cost_usd`, their tokens not in `usage`.
    other_models: dict[str, OtherModel] = Field(default_factory=dict)


#: The part of a launch a safety stop stopped (`SafetyStop.part`): a response of the
#: launch's own model, a request of a model that a tool calls, or one the coding agent
#: counted in words its reader does not recognize.
SafetyStopPart = Literal["response", "tool", "unread"]


class SafetyStop(BaseModel):
    """A safety classifier that stopped part of a launch while the launch went on (Claude
    Code reports them). `response`: it stopped a response of the launch's own model, whose
    unfinished tool calls did not run; the coding agent tells the model and goes on.
    `tool`: it refused a request of a model that a tool calls (Claude Code's `WebFetch`
    summarizes a page on a smaller model), and the tool call ended in an error. `unread`:
    the coding agent counted one whose words its reader does not recognize. The launch
    ends as it would have (`completed`, often); a refusal that ends the launch is stop
    `refused` instead."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    part: SafetyStopPart
    #: When it was seen; empty when the coding agent's event carries no time.
    ts: str = ""
    #: The model whose safeguards stopped it, as the coding agent names it (`Sonnet 5.5`); empty when not said.
    model: str = ""
    #: The classifier's category (`cyber`); empty when not said.
    category: str = ""
    #: The tool whose call it stopped: the tool that ended in an error (`tool`), or the
    #: first tool call the stopped response left unfinished (`response`); empty when none.
    tool: str = ""
    #: The provider's ids of the stopped request and message, for its support; empty when not said.
    request_id: str = ""
    message_id: str = ""


# --- quota -------------------------------------------------------------------

#: A subscription's window that a quota cap names and every coding agent's reading gives:
#: the 5-hour and the weekly one. A reading may name others (`QuotaReading.windows`: a
#: model's own week, `seven_day_opus`), which no cap names.
Window = Literal["five_hour", "seven_day"]


class WindowSpec(NamedTuple):
    """What one `Window` is: its name in a sentence, and how long a reading of it stands
    when the reading names no reset."""

    words: str
    length: timedelta


#: Every `Window`, in order: the one table routing, the trends and `Rest` read.
WINDOWS: dict[Window, WindowSpec] = {
    "five_hour": WindowSpec("5-hour", timedelta(hours=5)),
    "seven_day": WindowSpec("weekly", timedelta(days=7)),
}


_SPECS: dict[str, WindowSpec] = {name: spec for name, spec in WINDOWS.items()}


def window_spec(name: str) -> WindowSpec | None:
    """The `WINDOWS` entry of a window named `name`; None for another window (`seven_day_opus`)."""
    return _SPECS.get(name)


def window_words(name: str) -> str:
    """A window's name in a sentence (`5-hour`, `weekly`); another window keeps its own name."""
    spec = window_spec(name)
    return spec.words if spec is not None else name


class QuotaWindow(BaseModel):
    """One window of a reading: its utilization (%) and when it resets (ISO 8601)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    pct: float | None = None
    resets_at: str | None = None


class QuotaReading(BaseModel):
    """A subscription's utilization during a launch, from one of these sources:

    * Claude Code: in its stream, when a session starts or resumes;
    * Codex: in its stream, with each API call of a ChatGPT login;
    * omp (`omp`, `omp-rpc`): at each launch, what the account's latest request reported
      (`omp usage --json`, read before the launch: `Backend.usage_reading`);
    * opencode and pi: for an OpenCode Go model only, OpenCode's usage endpoint, read by
      contraagent before each launch (`Backend.usage_reading`); the agents report none.

    Account-wide: it includes whatever else used the same account, parallel tasks too.
    `LaunchResult.quota` holds a launch's, the journal's `quota` an attempt's that give a
    5-hour or weekly utilization."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    #: When this process received the reading (UTC ISO 8601). The utilization is
    #: account-wide, as of the API call it came with.
    observed_at: str | None = None
    #: The `[credentials.<name>]` of the session that reported it: whose account the
    #: utilization is (filled in by the runner, which knows the credential). Readings of
    #: different credentials do not compare.
    credential: str = ""
    five_hour_pct: float | None = None
    five_hour_resets_at: str | None = None
    seven_day_pct: float | None = None
    seven_day_resets_at: str | None = None
    status: str = ""
    #: Which account reported it: a 12-hex-digit digest that tells accounts apart and reveals
    #: none; '' when not known. One credential can stand
    #: for two accounts (`ambient` on two coding agents, a replaced token): their readings do
    #: not compare.
    account: str = ""
    #: The window `status` and `threshold_pct` are about (`five_hour`, `seven_day`, ...):
    #: Claude Code's `rateLimitType`.
    status_window: str = ""
    #: The utilization (%) past which `status` warns (Claude Code's `surpassedThreshold`).
    threshold_pct: float | None = None
    #: Usage past the limit, billed as extra: its status (`allowed`, `rejected`, ...), why it
    #: is off, and whether this request used it (Claude Code's `overageStatus`,
    #: `overageDisabledReason`, `isUsingOverage`).
    overage_status: str = ""
    overage_disabled_reason: str = ""
    using_overage: bool | None = None
    #: Every window the reading names, by its name (`five_hour`, `seven_day`, a model's own
    #: such as `seven_day_opus`): its utilization (%) and its reset. `five_hour_pct` and
    #: `seven_day_pct` are two of them.
    windows: dict[str, QuotaWindow] = Field(default_factory=dict)
    #: What else the coding agent sent with the reading, by its own name: a newer field
    #: this reader does not name yet.
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_windows(cls, windows: Mapping[str, QuotaWindow], **fields: Any) -> QuotaReading:
        """A reading of `windows` (by name), its `five_hour_*` and `seven_day_*` fields
        taken from those two; `fields`: the rest."""
        five, week = windows.get("five_hour"), windows.get("seven_day")
        return cls(
            five_hour_pct=five.pct if five is not None else None,
            five_hour_resets_at=five.resets_at if five is not None else None,
            seven_day_pct=week.pct if week is not None else None,
            seven_day_resets_at=week.resets_at if week is not None else None,
            windows=dict(windows),
            **fields,
        )

    def named_windows(self) -> dict[str, QuotaWindow]:
        """Every window the reading gives a utilization or a reset for, by name: each
        window of its fields (`five_hour`, `seven_day`), then those of `windows` (which win
        for the same name)."""
        named = {w: QuotaWindow(pct=getattr(self, f"{w}_pct"), resets_at=getattr(self, f"{w}_resets_at")) for w in WINDOWS}
        named.update(self.windows)
        return {k: v for k, v in named.items() if v.pct is not None or v.resets_at}


# --- rest --------------------------------------------------------------------


class Rest(BaseModel):
    """Why credential `credential` rests: past the cap of one window (`window` `five_hour`
    or `seven_day`, its reading `pct`, the cap `cap`), or by the quota rule (`rule`, what it
    said, `reading`, the reading it judged; `window` empty), or because a launch as it was
    refused (`stop` `auth_failed`: a 401 or 403), on that launch's coding agent `agent` and
    model `model` only, for the rest of the run. `until`, ISO 8601: when the
    window resets, for a cap; for the rule, the end it gave, else when the reading it judged
    stops standing (its earliest reset); empty when unknown, and for a refused credential."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    credential: str
    window: Literal["", Window] = ""
    pct: float | None = None
    cap: float | None = None
    rule: str = ""
    until: str = ""
    #: The account whose reading it is (`QuotaReading.account`); '' when not known.
    account: str = ""
    #: The reading the quota rule judged: `{observed_at, windows: {<window>: {pct, resets_at}}}`;
    #: None for a cap's rest.
    reading: dict[str, Any] | None = None
    #: `auth_failed` for a credential a launch was refused as; '' for a quota rest.
    stop: Literal["", "auth_failed"] = ""
    #: The coding agent a refused credential rests on; '' for a quota rest, which holds on every one.
    agent: str = ""
    #: The model a refused credential rests on; '' for a quota rest, which holds on every one.
    #: A skipped hop's is the hop's model.
    model: str = ""

    def text(self) -> str:
        """The rest in one line, for logs and the CLI: `personal rests: 5-hour usage 93%, max 90%`,
        `personal rests on claude/m1: authentication failed (auth_failed)`."""
        if self.stop:
            return f"{self.credential} rests on {self.agent}/{self.model}: authentication failed ({self.stop})"
        if self.rule:
            return f"{self.credential} rests: {self.rule}"
        return f"{self.credential} rests: {window_words(self.window)} usage {self.pct or 0:.0f}%, max {self.cap or 0:g}%"

    def to_dict(self) -> dict[str, Any]:
        """The rest as `rests.jsonl` and a deferral's cause record it: a cap's rest names no
        reading, a quota rest no stop, coding agent or model."""
        empty = {k for k in ("stop", "agent", "model") if not getattr(self, k)}
        return self.model_dump(mode="json", exclude=empty | ({"reading"} if self.reading is None else set()))

    def skipped(self, route: str, model: str) -> SkippedHop:
        """The hop `route` (its label) on `model` passed over because of this rest."""
        return SkippedHop(**{**self.to_dict(), "route": route, "model": model})


class SkippedHop(Rest):
    """A hop of the failover chain an attempt passed over without a launch, because its
    credential rested: its route label and model (`model`), and the rest."""

    route: str = ""


class RestEvent(Rest):
    """One line of `rests.jsonl`: `event` `start` when the credential began resting (with
    its rest), `end` when it was found not resting again (with the rest that ended)."""

    ts: str
    event: Literal["start", "end"]


# --- deferral ----------------------------------------------------------------


class DeferralCause(BaseModel):
    """Why a task was deferred, as data (`Deferral.cause`). `cause`: `deadline`,
    `grace_window` (past the deadline's grace window), `cannot_finish` (`need_s`, `left_s`),
    `dependency_not_queued`, `dependency_deferred` (a task whose output it reads was
    deferred: `dependency`), `rest` (the credential of every hop it could take rests:
    `rests`), or a runner's own name. A field a cause does not have is left unset, and
    `deferred.jsonl` records only the fields set."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    cause: str
    need_s: float | None = Field(default=None, description="`cannot_finish`: the work it needed, in seconds")
    left_s: float | None = Field(default=None, description="`cannot_finish`: the time left before the deadline, in seconds")
    flow_call: str | None = Field(
        default=None,
        description="`deadline`, `grace_window`, `cannot_finish`: the flow call whose time box it is; null for the run's deadline",
    )
    rests: tuple[SkippedHop, ...] = Field(default=(), description="`rest`: each hop passed over and why its credential rests")
    dependency: str | None = Field(default=None, description="`dependency_deferred`: the key of the deferred task whose output it reads")

    def to_dict(self) -> dict[str, Any]:
        """The cause as `deferred.jsonl` records it: the fields set."""
        return self.model_dump(mode="json", exclude_unset=True)


# --- time box ----------------------------------------------------------------


class TimeBoxRecord(BaseModel):
    """A flow call's own deadline (`time_box`, `TimeBox`), as `flow_calls.jsonl` records it."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    started_at: str = Field(description="when the flow call started, where its deadline counts from (UTC ISO 8601)")
    deadline_s: float = Field(description="seconds from `started_at` to the deadline")
    grace_s: float = Field(description="seconds past the deadline its `finishing_kinds` still launch")
    slack_s: float = Field(description="seconds before the deadline from which its tasks are ordered for it")
    finishing_kinds: tuple[str, ...] = Field(default=(), description="the kinds that still launch past the deadline")


# --- service -----------------------------------------------------------------

#: Why a service stopped: the run ended (`run_end`), or the run was stopped by a signal
#: (`interrupted`).
ServiceStopCause = Literal["run_end", "interrupted"]


class ServiceEvent(BaseModel):
    """One line of `services.jsonl`: the service a claim name stands for started (`event`
    `start`) or stopped (`stop`). A start with an `error` did not start; a stop with an
    `error` raised while it stopped, and the service counts as stopped."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    ts: str = Field(description="when the start or the stop ended (UTC ISO 8601)")
    event: Literal["start", "stop"]
    name: str = Field(description="the claim name the service stands for")
    key: str | None = Field(default=None, description="`start`: the task whose claim started it")
    address: str | None = Field(default=None, description="`start`: what the service gave its tasks to reach it; null for none")
    cause: ServiceStopCause | None = Field(default=None, description="`stop`: why it stopped")
    error: str | None = Field(
        default=None, description="the exception of a start that failed or a stop that raised; null when it went well"
    )
    wall_s: float = Field(default=0.0, description="how long the start or the stop took, in seconds")
