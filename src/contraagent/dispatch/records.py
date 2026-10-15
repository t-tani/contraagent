"""The facts a run records, one type each, used by every layer that writes or reads them.

A task's result (`TaskResult`), the run's files (`journal.jsonl`, `plan.jsonl`,
`flow_calls.jsonl`, `deferred.jsonl`, `rests.jsonl`) and the monitor's HTTP API all hold
these values; each is defined here once, as a pydantic model, so a file row and an API
response are the same type. Values are frozen. Nothing here imports anything outside the
standard library and pydantic.

* `Executor`: who executes a task.
* `Loop`, `Frame`: a flow path (`Origin.flow`, plan and flow call `flow`).
* `Changes`: the files one attempt changed.
* `TokenUsage`, `OtherModel`, `Hop`: one launch of an attempt on one route.
* `Rest`, `SkippedHop`, `RestEvent`: a credential that rests on its quota, a hop an
  attempt passed over because of it, and a line of `rests.jsonl`.
* `DeferralCause`: why a task was deferred, as data.
* `TimeBoxRecord`: a flow call's time box as `flow_calls.jsonl` records it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

#: Who executes a task: a coding agent, or this process in Python (`Task.executor`).
Executor = Literal["agent", "python"]


# --- flow path ---------------------------------------------------------------


class Loop(BaseModel):
    """A `for` or `while` loop of a generator around a call site, and the pass the call
    site was in."""

    model_config = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True)

    line: int = Field(description="the loop's first line, which names it")
    pass_: int | None = Field(
        validation_alias=AliasChoices("pass", "pass_"),
        serialization_alias="pass",
        description="one iteration of this loop, numbered from 1 since the loop was last entered in that frame; null when not counted",
    )


class Frame(BaseModel):
    """One frame of a flow path (outermost first): a call site in flow code where a task
    was created. A comprehension is not a loop."""

    model_config = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True)

    function: str = Field(description="`module.qualname`")
    file: str = Field(description="relative to the run's working directory when under it, else as recorded")
    line: int
    loops: tuple[Loop, ...] = Field(
        default=(),
        description="the loops of a generator whose pass `line` was in, outermost first; empty outside a loop and for any other frame",
    )


# --- changes -----------------------------------------------------------------


class Changes(BaseModel):
    """The files one attempt changed under its task's `changes` patterns, as paths relative
    to the working directory: those it `created`, `modified` and `deleted`."""

    model_config = ConfigDict(extra="allow", frozen=True)

    created: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    #: The created files removed because the attempt failed.
    removed: tuple[str, ...] = ()


# --- hop ---------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Tokens summed over API calls: an attempt's (its rounds and hops, in `JournalRow.usage`)
    or one hop's (`Hop.usage`)."""

    model_config = ConfigDict(extra="allow")

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

    model_config = ConfigDict(extra="allow", frozen=True)

    #: Part of the hop's `cost_usd`; None when the coding agent reported none.
    cost_usd: float | None = None
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0


class Hop(BaseModel):
    """One launch of an attempt on one route of its failover chain: where it ran and how
    it ended."""

    model_config = ConfigDict(extra="allow", frozen=True)

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


# --- rest --------------------------------------------------------------------

#: A subscription window's name in a sentence.
_WINDOW_WORDS = {"five_hour": "5-hour", "seven_day": "weekly"}


class Rest(BaseModel):
    """Why credential `credential` rests: past the cap of one window (`window` `five_hour`
    or `seven_day`, its reading `pct`, the cap `cap`), or by the quota rule (`rule`, what it
    said, `reading`, the reading it judged; `window` empty). `until`, ISO 8601: when the
    window resets, for a cap; for the rule, the end it gave, else when the reading it judged
    stops standing (its earliest reset); empty when unknown."""

    model_config = ConfigDict(extra="allow", frozen=True)

    credential: str
    window: Literal["", "five_hour", "seven_day"] = ""
    pct: float | None = None
    cap: float | None = None
    rule: str = ""
    until: str = ""
    #: The account whose reading it is (`QuotaReading.account`); '' when not known.
    account: str = ""
    #: The reading the quota rule judged: `{observed_at, windows: {<window>: {pct, resets_at}}}`;
    #: None for a cap's rest.
    reading: dict | None = None

    def text(self) -> str:
        """The rest in one line, for logs and the CLI: `personal rests: 5-hour usage 93%, max 90%`."""
        if self.rule:
            return f"{self.credential} rests: {self.rule}"
        words = _WINDOW_WORDS.get(self.window, self.window)
        return f"{self.credential} rests: {words} usage {self.pct or 0:.0f}%, max {self.cap or 0:g}%"

    def to_dict(self) -> dict:
        """The rest as `rests.jsonl` and a deferral's cause record it: a cap's rest names no reading."""
        return self.model_dump(mode="json", exclude={"reading"} if self.reading is None else None)

    def skipped(self, route: str, model: str) -> SkippedHop:
        """The hop `route` (its label) on `model` passed over because of this rest."""
        return SkippedHop(route=route, model=model, **self.to_dict())


class SkippedHop(Rest):
    """A hop of the failover chain an attempt passed over without a launch, because its
    credential rested: its route label and model, and the rest."""

    route: str = ""
    model: str = ""


class RestEvent(Rest):
    """One line of `rests.jsonl`: `event` `start` when the credential began resting (with
    its rest), `end` when it was found not resting again (with the rest that ended)."""

    ts: str
    event: Literal["start", "end"]


# --- deferral ----------------------------------------------------------------


class DeferralCause(BaseModel):
    """Why a task was deferred, as data (`Deferral.cause`). `cause`: `deadline`,
    `grace_window` (past the deadline's grace window), `cannot_finish` (`need_s`, `left_s`),
    `dependency_not_queued`, `rest` (the credential of every hop it could take rests:
    `rests`), or a runner's own name. A field a cause does not have is left unset, and
    `deferred.jsonl` records only the fields set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cause: str
    need_s: float | None = Field(default=None, description="`cannot_finish`: the work it needed, in seconds")
    left_s: float | None = Field(default=None, description="`cannot_finish`: the time left before the deadline, in seconds")
    flow_call: str | None = Field(
        default=None,
        description="`deadline`, `grace_window`, `cannot_finish`: the flow call whose time box it is; null for the run's deadline",
    )
    rests: tuple[SkippedHop, ...] = Field(default=(), description="`rest`: each hop passed over and why its credential rests")

    def to_dict(self) -> dict:
        """The cause as `deferred.jsonl` records it: the fields set."""
        return self.model_dump(mode="json", exclude_unset=True)


# --- time box ----------------------------------------------------------------


class TimeBoxRecord(BaseModel):
    """A flow call's own deadline (`time_box`, `TimeBox`), as `flow_calls.jsonl` records it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    started_at: str = Field(description="when the flow call started, where its deadline counts from (UTC ISO 8601)")
    deadline_s: float = Field(description="seconds from `started_at` to the deadline")
    grace_s: float = Field(description="seconds past the deadline its `finishing_kinds` still launch")
    slack_s: float = Field(description="seconds before the deadline from which its tasks are ordered for it")
    finishing_kinds: tuple[str, ...] = Field(default=(), description="the kinds that still launch past the deadline")
