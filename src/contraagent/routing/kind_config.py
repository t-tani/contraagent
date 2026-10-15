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

from contraagent.backends.launch import Limits
from contraagent.dispatch.task import kind_name


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
    context_warn: int | None = None
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

    @classmethod
    def build(cls, defaults: dict, overrides: dict | None) -> KindConfig:
        """Merge defaults with per-kind overrides. Unknown keys are dropped."""
        d = dict(defaults)
        d.update({k: v for k, v in (overrides or {}).items() if k in cls.__dataclass_fields__})
        d["disallowed_tools"] = tuple(d.get("disallowed_tools") or ())
        d["requires"] = tuple(d.get("requires") or ())
        return cls(**d)

    def limits(self) -> Limits:
        return Limits(
            timeout_s=self.timeout_s,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            context_budget=self.context_budget,
            stall_s=self.stall_s,
            disallowed_tools=self.disallowed_tools,
            max_denials=self.max_denials,
        )

    def with_(self, **changes) -> KindConfig:
        return replace(self, **changes)


#: The numeric keys of a task table (`[tasks.<kind>]`), with the type each
#: must hold; the routing keys (agent, model, ...) are checked in `config.py`.
#: Listed explicitly so a typo is an error rather than a key `build` drops.
TASK_TABLE_KEYS: dict[str, type | tuple[type, ...]] = {
    "max_turns": int,
    "timeout_s": (int, float),
    "max_budget_usd": (int, float),
    "stall_s": (int, float),
    "context_budget": int,
    "context_warn": int,
    "max_denials": int,
    "max_concurrent": int,
    "retries": int,
    "retry_backoff_base": (int, float),
}

assert set(TASK_TABLE_KEYS) <= {f.name for f in fields(KindConfig)}


def configs_from_tables(kinds, tables: dict[str, dict] | None = None) -> dict:
    """Per-kind KindConfig from the config's `[tasks.<kind>]` tables.

    A kind with no table gets the bare field defaults; `require_budgets`
    is what refuses to run on those.
    """
    tables = tables or {}
    return {k: KindConfig.build({}, tables.get(kind_name(k))) for k in kinds}


def require_budgets(configs: dict, tables: dict[str, dict], required: tuple[str, ...] = ("max_turns", "timeout_s")) -> None:
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


def missing_budgets(configs: dict, tables: dict[str, dict], required: tuple[str, ...] = ("max_turns", "timeout_s")) -> list[str]:
    """What `require_budgets` refuses: one message per kind without its budgets."""
    out = []
    for k in configs:
        name = kind_name(k)
        lacking = [m for m in required if m not in tables.get(name, {})]
        if lacking:
            keys = ", ".join(f"{m}=..." for m in lacking)
            out.append(f"kind {name} has no budget ({', '.join(lacking)}): set it in agent_task({name!r}, {keys}) or in [tasks.{name}]")
    return sorted(out)
