"""pydantic models for the files a run leaves on disk.

Two shapes, both generic over the domain:

* `JournalRow` — one line of `runs/<run>/journal.jsonl`, written when a
  task finishes. `extra="allow"`: a domain adds its own columns (counts of
  what the task produced, say) and they round-trip untouched. The monitor
  reads only the fields named here.
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

from pydantic import BaseModel, ConfigDict, Field

# --- journal ---------------------------------------------------------------


class Hop(BaseModel):
    """One launch in a failover walk: where it ran and how it ended."""

    model_config = ConfigDict(extra="allow")

    route: str = ""
    model: str = ""
    #: The `[credentials.<name>]` this hop authenticated as (a hop may change it).
    credential: str = ""
    stop: str = ""
    wall_s: float = 0.0
    #: What the coding agent reported this hop cost, in USD; None when it reports none.
    cost_usd: float | None = None


class QuotaReading(BaseModel):
    """A subscription's utilization as the coding agent reported it during an attempt
    (Claude Code: when a session starts or resumes; omp: at each launch, what the
    account's latest request reported). Account-wide: it includes
    whatever else used the same account, parallel tasks too."""

    model_config = ConfigDict(extra="allow")

    observed_at: str | None = None
    #: The credential (account) the utilization belongs to; readings of different accounts do not compare.
    credential: str = ""
    five_hour_pct: float | None = None
    five_hour_resets_at: str | None = None
    seven_day_pct: float | None = None
    seven_day_resets_at: str | None = None
    status: str = ""


class TokenUsage(BaseModel):
    """Tokens one attempt used, summed over its API calls, rounds and hops."""

    model_config = ConfigDict(extra="allow")

    input: int = 0
    output: int = 0
    #: Input served from the prompt cache.
    cache_read: int = 0
    #: Input written to the prompt cache.
    cache_creation: int = 0
    #: API calls the coding agent made.
    calls: int = 0


class JournalRow(BaseModel):
    """One finished attempt. `key` is the stable `Task.key`; `kind`/`unit`
    group the monitor's rollup; `executor` says who ran it; `stop` is
    `Stop.value` (or a Python task's completed/error)."""

    model_config = ConfigDict(extra="allow")

    ts: str
    run_id: str = ""
    #: The label grouping runs (`Run(run_group=)`); the run id when none was given.
    run_group: str = ""
    key: str
    attempt: int = 0
    kind: str
    executor: Literal["agent", "python"] = "agent"
    unit: str = ""
    #: The coding agent that ran the launch; empty for a Python task.
    agent: str = ""
    model: str = ""
    #: The `[credentials.<name>]` the launch authenticated as (never a secret).
    credential: str = ""
    route: str = ""
    hops: list[Hop] = Field(default_factory=list)
    stop: str
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
    #: A digest of what defines the task's work (`Task.fingerprint`): what a resume compares.
    fingerprint: str = ""
    #: The flow call that created the task (`Origin.flow_call`); None for a task with no origin.
    flow_call: str | None = None


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
