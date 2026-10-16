"""Per-kind config: how one kind of task is routed and what it may spend.

A *kind* is whatever label a domain gives a class of task ("triage",
"verify", ...). It is a plain string here; a `str`-valued `enum.Enum`
works too, because its members hash and compare equal to their values.
Each kind carries its own budgets (turn cap, wall clock, cost)
because a run-wide cap would flatten the difference between reading a file
listing and walking a decompiler.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from contraagent._internal.backends.launch import Limits, Stop
from contraagent._internal.contracts.contract import DEFAULT_MAX_CORRECTIONS
from contraagent._internal.dispatch.task import kind_name


@dataclass(frozen=True)
class KindConfig:
    """One kind's resolved routing and budgets. Backend-neutral settings stay here.

    `agent`: the coding agent (a registered `Backend` name) the kind runs on.
    """

    agent: str = "claude"
    model: str = ""
    effort: str | None = None
    # Model-level failover is opt-in per kind: hand the agent the chain's
    # same-agent remainder so it can retry a different model inside one
    # launch. Off by default: a task silently re-running on another model
    # is a change of mind the operator did not ask for.
    model_failover: bool = False
    max_turns: int = 50
    timeout_s: float = 600
    max_budget_usd: float | None = None
    stall_s: float | None = None
    max_concurrent: int | None = None
    settings: str = ""
    context_budget: int | None = None
    #: Warn (`JournalRow.context_warned`, a queue `note`) when a launch's peak context passes
    #: this % of `context_budget`; it does not stop the launch. Needs a `context_budget`.
    context_warn_pct: int | None = None
    max_denials: int | None = None
    disallowed_tools: tuple[str, ...] = ()
    exclude_dynamic_sections: bool = False
    #: The `[credentials.<name>]` this kind launches with ("ambient": the agent's own default).
    credential: str = "ambient"
    #: Traits its credential must carry (`agent_task(requires=...)`), e.g. ("zdr",).
    requires: tuple[str, ...] = ()
    #: A light launch (`agent_task(tools=())`): every route's coding agent must run one (`Backend.light_launch`).
    light: bool = False
    # Retry policy for a dispatch that comes back without progress (see
    # `RetryingRunner`): the fresh attempts after the first, and the base of the
    # exponential backoff.
    retries: int = 2
    retry_backoff_base: float = 2.0
    #: The stops after which a launch's output, when it passes every check, is kept as a
    #: partial result (`agent_task(partial_on=)`): some of `PARTIAL_STOPS`.
    partial_on: tuple[str, ...] = ()
    #: Leave the files a failed attempt created under its task's `changes` patterns in place
    #: (`Changes.kept`) instead of removing them (`Changes.removed`).
    keep_failed_changes: bool = False
    #: The correction rounds after the first launch: how many times an output that fails its
    #: checks goes back to the same session with the errors (`run_until_valid(max_corrections=)`).
    max_corrections: int = DEFAULT_MAX_CORRECTIONS

    @property
    def partial_stops(self) -> frozenset[Stop]:
        """`partial_on` as stops (`run_checked(partial_on=)`)."""
        return frozenset(Stop(s) for s in self.partial_on)

    @classmethod
    def build(cls, defaults: dict[str, Any], overrides: dict[str, Any] | None) -> KindConfig:
        """Merge defaults with per-kind overrides. Unknown keys are dropped."""
        d = dict(defaults)
        d.update({k: v for k, v in (overrides or {}).items() if k in cls.__dataclass_fields__})
        d["disallowed_tools"] = tuple(d.get("disallowed_tools") or ())
        d["requires"] = tuple(d.get("requires") or ())
        d["partial_on"] = tuple(d.get("partial_on") or ())
        return cls(**d)

    def limits(self) -> Limits:
        return Limits(
            timeout_s=self.timeout_s,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            context_budget=self.context_budget,
            context_warn_pct=self.context_warn_pct,
            stall_s=self.stall_s,
            disallowed_tools=self.disallowed_tools,
            max_denials=self.max_denials,
        )

    def with_(self, **changes: Any) -> KindConfig:
        return replace(self, **changes)


#: The stops a kind may keep a partial result after (`partial_on`): those the runner itself
#: ends a launch on for time, with no word from the agent that it is done or why not.
PARTIAL_STOPS: tuple[str, ...] = (Stop.TIMEOUT.value, Stop.STALLED.value)


#: The numeric keys of a task table (`[tasks.<kind>]`), with the type each
#: must hold; the routing keys (agent, model, ...) are checked in `config.py`.
#: Listed explicitly so a typo is an error rather than a key `build` drops.
TASK_TABLE_KEYS: dict[str, type | tuple[type, ...]] = {
    "max_turns": int,
    "timeout_s": (int, float),
    "max_budget_usd": (int, float),
    "stall_s": (int, float),
    "context_budget": int,
    "context_warn_pct": int,
    "max_denials": int,
    "max_concurrent": int,
    "retries": int,
    "retry_backoff_base": (int, float),
    "max_corrections": int,
}

#: The most correction rounds a kind may allow (`max_corrections`): each is a full turn
#: of the same session, its context growing, and an output still wrong after this many is
#: not converging.
MAX_CORRECTIONS_LIMIT = 20

assert set(TASK_TABLE_KEYS) <= {f.name for f in fields(KindConfig)}


def configs_from_tables(kinds, tables: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Per-kind KindConfig from the config's `[tasks.<kind>]` tables.

    A kind with no table gets the bare field defaults; `require_budgets`
    is what refuses to run on those.
    """
    tables = tables or {}
    return {k: KindConfig.build({}, tables.get(kind_name(k))) for k in kinds}


def require_budgets(
    configs: dict[str, Any], tables: dict[str, dict[str, Any]], required: tuple[str, ...] = ("max_turns", "timeout_s")
) -> None:
    """Fail loudly on a kind whose budgets the config never set.

    The question is "did the config say so", not "does the value look like
    a default": `KindConfig` carries 50 turns and 600s as field defaults,
    so a value comparison cannot tell an unset key from one deliberately
    set to 50. Those defaults are plausible enough to launch a task and
    wrong enough to ruin one, and the truncation reads as a verdict rather
    than a budget.
    """
    errors = missing_budgets(configs, tables, required)
    if errors:
        raise ValueError("; ".join(errors))


def with_context_warn(configs: dict[str, Any], default_pct: int | None) -> dict[str, Any]:
    """Give `[defaults].context_warn_pct` to each kind that has a `context_budget` and no
    `context_warn_pct` of its own."""
    if default_pct is None:
        return configs
    return {k: c.with_(context_warn_pct=default_pct) if c.context_budget and c.context_warn_pct is None else c for k, c in configs.items()}


def context_warn_problems(configs: dict[str, Any]) -> list[str]:
    """One message per kind with a `context_warn_pct` but no `context_budget` to be a percent of."""
    return sorted(
        f"kind {kind_name(k)} has context_warn_pct = {c.context_warn_pct} but no context_budget: "
        f"set context_budget in agent_task({kind_name(k)!r}, context_budget=...) or in [tasks.{kind_name(k)}]"
        for k, c in configs.items()
        if c.context_warn_pct is not None and not c.context_budget
    )


def missing_budgets(
    configs: dict[str, Any], tables: dict[str, dict[str, Any]], required: tuple[str, ...] = ("max_turns", "timeout_s")
) -> list[str]:
    """What `require_budgets` refuses: one message per kind without its budgets."""
    out = []
    for k in configs:
        name = kind_name(k)
        lacking = [m for m in required if m not in tables.get(name, {})]
        if lacking:
            keys = ", ".join(f"{m}=..." for m in lacking)
            out.append(f"kind {name} has no budget ({', '.join(lacking)}): set it in agent_task({name!r}, {keys}) or in [tasks.{name}]")
    return sorted(out)
