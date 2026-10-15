"""Routing plan: config + overrides -> per-kind routing and budgets, and a failover chain.

`RoutingPlan.build` is the entry point. It folds the config file and the
caller's explicit overrides into one `KindConfig` per kind
(`resolve_routing`), refuses kinds whose budgets the config never set,
and makes one failover breaker per kind (`build_routers`). `preflight()` then
drops the routes that cannot answer before the first task.

    plan = RoutingPlan.build(PipelineConfig.load("pipeline.toml"), kinds, backends)
    plan.preflight()
    runner = AgentRunner(backends, plan.configs, routers=plan.routers, run_dir=run.dir)

The functions below are the steps `build` runs, usable on their own. Each
takes its inputs as parameters and reaches into no global state.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from contraagent.backends import Backend, backend_class, known_agents
from contraagent.backends.credentials import CredentialError, Pool
from contraagent.dispatch.task import kind_name
from contraagent.errors import ContraagentError, did_you_mean
from contraagent.routing.config import PipelineConfig
from contraagent.routing.kind_config import KindConfig, configs_from_tables, missing_budgets
from contraagent.routing.router import Route, Router, parse_chain

_logger = logging.getLogger(__name__)

#: The built-in last resort when neither an override nor the config names one.
DEFAULT_AGENT = "claude"
DEFAULT_EFFORT = "medium"


class RoutingError(ContraagentError, ValueError):
    """The routing plan is invalid (unknown kind, unsupported effort, bad chain).
    `errors` holds every problem found, one message each."""

    def __init__(self, *errors: str) -> None:
        super().__init__("\n".join(errors))
        self.errors = list(errors)


def _report(errors: list[str] | None, message: str) -> None:
    """Raise `message`, or append it to `errors` when the caller collects them."""
    if errors is None:
        raise RoutingError(message)
    errors.append(message)


@dataclass(frozen=True)
class Overrides:
    """Explicit choices that outrank the config file (e.g. command-line flags).

    Empty means "not passed" — distinguishable from "passed the same value
    the file has", which is what lets a config default exist at all. An
    `agent` or `model` also turns off every kind's failover hops; a
    `credential` is every hop's too, so a 429 never moves a task onto
    another identity.
    """

    agent: str = ""
    model: str = ""
    effort: str = ""
    credential: str = ""

    def run_defaults(self, defaults: Mapping) -> tuple[str, str, str]:
        """(agent, model, effort) for the run: this override, else `[defaults]`, else built-in."""
        return (
            self.agent or str(defaults.get("agent") or "") or DEFAULT_AGENT,
            self.model or str(defaults.get("model") or ""),
            self.effort or str(defaults.get("effort") or "") or DEFAULT_EFFORT,
        )


def check_effort(kind: str, agent: str, effort: str) -> None:
    """Reject an effort the resolved agent's CLI does not accept (`Backend.effort_levels`)."""
    message = effort_problem([kind], agent, effort)
    if message:
        raise RoutingError(message)


def effort_problem(kinds: list[str], agent: str, effort: str) -> str | None:
    """Why `agent` refuses `effort` for `kinds`, or None when it accepts it."""
    cls = backend_class(agent)
    levels = cls.effort_levels if cls is not None else None
    if levels is None or effort in levels:
        return None
    which = f"kind {kinds[0]}" if len(kinds) == 1 else f"kinds {', '.join(sorted(kinds))}"
    return (
        f"effort {effort!r} for {which} on agent {agent} is not accepted{did_you_mean(effort, levels)}; {agent} takes: {', '.join(levels)}"
    )


def check_task_tables(tables: Mapping[str, dict], kinds: Iterable) -> list[str]:
    """`[tasks.<name>]` tables naming no kind of this run, said out loud.

    Not an error: one config file often serves several flows. But a table nothing
    reads is also what a typo looks like, so each one is logged as a warning.
    """
    known = {kind_name(k) for k in kinds}
    unknown = sorted(set(tables) - known)
    for name in unknown:
        guess = did_you_mean(name, known) or " — a typo?"
        _logger.warning(f"[config] [tasks.{name}] is not a kind of this run (kinds: {', '.join(sorted(known))}); ignored{guess}")
    return unknown


def resolve_routing(
    configs: Mapping,
    tables: Mapping[str, dict],
    defaults: Mapping,
    backends: Mapping[str, Backend],
    overrides: Overrides = Overrides(),
    requirements: Mapping[str, Iterable[str]] | None = None,
    errors: list[str] | None = None,
    *,
    light: Iterable[str] = (),
) -> dict:
    """Fold the routing defaults and each kind's task table into its config.
    With `errors`, an effort the agent does not accept is appended there instead of raised.
    `light`: the kinds declared with no tools (`agent_task(tools=())`).

    Precedence, highest first, for agent, model, effort and credential:

      1. `overrides`       — an explicit override
      2. [tasks.<kind>]    — this kind's own task table
      3. [defaults]        — the run-wide default
      4. the built-in last resort (claude / no model / medium / ambient)

    A kind that names an agent this process has no backend for keeps the
    resolved default and says so, rather than becoming un-runnable.
    """
    run_agent, run_model, run_effort = overrides.run_defaults(defaults)
    light = set(light)
    out = dict(configs)
    efforts: dict[tuple[str, str], list[str]] = {}  # (agent, effort) -> kinds, checked once each
    for kind, rc in configs.items():
        name = kind_name(kind)
        table = tables.get(name, {})
        agent = overrides.agent or str(table.get("agent") or "") or run_agent
        if agent not in backends:
            # Never another agent in its place: a kind runs where the config says, or not at all.
            known = tuple(dict.fromkeys((*known_agents(), *backends)))
            if agent in known:
                problem = f"kind {name} runs on agent {agent}, which has no backend in this run; backends: {', '.join(backends)}"
            else:
                problem = f"kind {name} names unknown agent {agent!r}{did_you_mean(agent, known)}; known: {', '.join(known)}"
            _report(errors, problem)
        effort = overrides.effort or str(table.get("effort") or "") or run_effort
        efforts.setdefault((agent, effort), []).append(name)
        # KindConfig is frozen: the table is a replacement, not a patch.
        rest = {  # budgets, retries, model_failover ...
            k: v
            for k, v in table.items()
            if k in KindConfig.__dataclass_fields__ and k not in ("agent", "model", "effort", "settings", "credential", "requires", "light")
        }
        if "disallowed_tools" in rest:  # a list in TOML and in a declaration; the config holds a tuple
            rest["disallowed_tools"] = tuple(rest["disallowed_tools"])
        credential = overrides.credential or str(table.get("credential") or "") or str(defaults.get("credential") or "") or "ambient"
        out[kind] = dataclasses.replace(
            rc,
            agent=agent,
            model=overrides.model or str(table.get("model") or "") or run_model,
            effort=effort,
            credential=credential,
            requires=tuple((requirements or {}).get(name, ())),
            light=name in light,
            **rest,
        )
    for (agent, effort), names in efforts.items():
        message = effort_problem(names, agent, effort)
        if message:
            _report(errors, message)
    return out


def build_routers(
    configs: Mapping,
    tables: Mapping[str, dict],
    config: PipelineConfig,
    backends: Mapping[str, Backend],
    overrides: Overrides = Overrides(),
    errors: list[str] | None = None,
) -> dict:
    """One failover breaker per kind that has a chain.

    A breaker per kind, not per run: one kind's model answering 429 says
    nothing about another's, and a shared breaker would walk a healthy task
    onto a hop that was never rate limited. A kind that names
    `[[tasks.<kind>.fallbacks]]` uses exactly those; the rest share the
    run-wide `[[defaults.fallbacks]]`. Hops naming an agent with no backend
    here are dropped with a line. An `overrides` agent or model leaves every
    kind without a chain: it names where every kind runs, and a hop would run
    it elsewhere. The chains are still checked. An `overrides` credential
    replaces each hop's own.
    """
    # A name no coding agent answers to is a config error; a known name with no backend in
    # *this* run (omp-only host, say) is dropped below with a line, not an error.
    known = tuple(dict.fromkeys((*known_agents(), *backends)))
    try:
        global_chain = parse_chain(config.fallbacks(), f"{config.source} [[defaults.fallbacks]]:", known_agents=known)
    except ValueError as exc:  # a ConfigError too: the chain is not an array of tables
        _report(errors, str(exc))
        global_chain = ()
    routers: dict = {}
    pinned = overrides.agent or overrides.model
    ignored: list[str] = []
    for kind, rc in configs.items():
        name = kind_name(kind)
        table = tables.get(name) or {}
        own = "fallbacks" in table
        if own:
            try:
                chain = parse_chain(table["fallbacks"], f"{config.source} [[tasks.{name}.fallbacks]]:", known_agents=known)
            except ValueError as exc:
                _report(errors, str(exc))
                chain = ()
        else:
            chain = global_chain
        if pinned:
            if chain:
                ignored.append(name)
            continue
        dropped = [r for r in chain if r.agent not in backends]
        if dropped:
            _logger.warning(f"[route] {name}: dropping hop(s) {', '.join(str(r) for r in dropped)} — no such backend in this run")
        # A hop that names no credential keeps the kind's own; an overriding credential is every hop's.
        usable = tuple(Route(r.agent, r.model, overrides.credential or r.credential or rc.credential) for r in chain if r.agent in backends)
        router = Router(Route(agent=rc.agent, model=rc.model or overrides.model or "", credential=rc.credential), usable)
        if len(router.routes) == 1:
            if chain:
                _logger.warning(f"[route] {name}: no hop differs from its primary; a 429 ends the task")
            continue
        routers[kind] = router
    if ignored:
        what = ", ".join(f"{k}={v}" for k, v in (("agent", overrides.agent), ("model", overrides.model)) if v)
        _logger.warning(f"[route] {', '.join(sorted(ignored))}: no failover hops; the override {what} names where every kind runs")
    return routers


def check_credentials(
    configs: Mapping, routers: Mapping, credentials: Mapping, backends: Mapping[str, Backend], errors: list[str] | None = None
) -> None:
    """Every route of every kind must be able to launch on its credential, and that
    credential must be one the kind may use. With `errors`, every refusal is
    appended there (one per route) instead of the first raised.

    Checked for the primary and for every failover hop: a 429 must never move a
    task onto an identity it is not allowed to run under. For a kind that
    `requires` traits, the coding agent must also guarantee that nothing it loads
    by default is used instead (`CredentialBinding.isolated`).
    """
    for kind, rc in configs.items():
        name = kind_name(kind)
        router = routers.get(kind)
        routes = router.routes if router is not None else (Route(rc.agent, rc.model, rc.credential),)
        for i, route in enumerate(routes):
            problem = _route_problem(rc, route, credentials, backends)
            if problem:
                _report(errors, f"{name} hop {i + 1}/{len(routes)} {route}: {problem}")


def _route_problem(rc, route: Route, credentials: Mapping, backends: Mapping[str, Backend]) -> str | None:
    """Why `route` cannot carry a task of config `rc`, or None."""
    cred = credentials.get(route.credential or rc.credential)
    if cred is None:
        return f"no [credentials.{route.credential or rc.credential}]; defined: {', '.join(sorted(credentials))}"
    missing = sorted(set(rc.requires) - set(cred.traits))
    if missing:
        return f"the task requires {', '.join(missing)}; credential {cred.label} carries {', '.join(sorted(cred.traits)) or 'no traits'}"
    backend = backends.get(route.agent)
    if backend is None:
        return None
    if rc.light and not backend.light_launch:
        return f"the task has no tools (tools=()), and {route.agent} cannot launch without them and its own system prompt"
    if rc.disallowed_tools and (why := backend.tool_deny_problem(tuple(rc.disallowed_tools))):
        return f"the task denies {', '.join(rc.disallowed_tools)}, and {why}"
    for member in [credentials[m] for m in cred.members] if isinstance(cred, Pool) else [cred]:
        try:
            binding = backend.bind_credential(member, route.model, label="check")
        except CredentialError as exc:
            return str(exc)
        if rc.requires and not binding.isolated:
            return (
                f"the task requires {', '.join(rc.requires)}, and {route.agent} cannot guarantee it uses only "
                f"{member.label}: {binding.isolation}"
            )
    return None


@dataclass
class RoutingPlan:
    """How every kind of a run launches: its `KindConfig` and its failover `Router`.

    `configs` and `routers` are what an `AgentRunner` takes. A kind with no entry in
    `routers` has no failover chain and ends on its first 429.
    """

    config: PipelineConfig
    backends: Mapping[str, Backend]
    configs: dict = field(default_factory=dict)
    routers: dict = field(default_factory=dict)
    overrides: Overrides = Overrides()
    #: `[credentials.<name>]` by name, `ambient` included: what an `AgentRunner` takes as `credentials`.
    credentials: dict = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        config: PipelineConfig,
        kinds: Iterable,
        backends: Mapping[str, Backend],
        overrides: Overrides = Overrides(),
        *,
        declared: Mapping[str, Mapping] | None = None,
        requirements: Mapping[str, Iterable[str]] | None = None,
        light: Iterable[str] = (),
        budgets_required: bool = True,
        all_kinds: bool = True,
    ) -> RoutingPlan:
        """Resolve every kind in `kinds` against `config` and `overrides`.

        `declared` is each kind's own task table as its code declares it (the keys a
        `[tasks.<kind>]` table takes); the config file's table outranks it.
        With `budgets_required` (the default) a kind whose budgets
        (`max_turns`, `timeout_s`) neither set is refused: the generic
        `KindConfig` field defaults are not a budget. `requirements` are the
        traits each kind's credential must carry (`agent_task(requires=...)`).
        `light` names the kinds with no tools (`agent_task(tools=())`): a route whose
        coding agent cannot launch them so (`Backend.light_launch`) is refused, failover
        hops included.
        With `all_kinds` (the default) `kinds` are every kind of the run, and a task
        table naming none of them is logged (`check_task_tables`); False for a plan of
        some kinds only (a generator flow creates kinds as it runs).
        """
        kinds = list(kinds)
        errors: list[str] = []  # every problem, reported together
        config.unknown_tables(errors)
        defaults = config.defaults(errors)
        config.claim_capacity(errors)
        file_tables = config.task_tables(errors)
        if all_kinds:
            check_task_tables(file_tables, kinds)
        declared = declared or {}
        tables = {name: {**declared.get(name, {}), **file_tables.get(name, {})} for name in {*map(kind_name, kinds), *file_tables}}
        tables = {name: table for name, table in tables.items() if table}
        configs = configs_from_tables(kinds, tables)
        if budgets_required:
            errors += missing_budgets(configs, tables)
        configs = resolve_routing(configs, tables, defaults, backends, overrides, requirements, errors, light=light)
        routers = build_routers(configs, tables, config, backends, overrides, errors)
        credentials = config.credentials()
        check_credentials(configs, routers, credentials, backends, errors)
        if errors:
            raise RoutingError(*errors)
        return cls(config=config, backends=backends, configs=configs, routers=routers, overrides=overrides, credentials=credentials)

    def preflight(self) -> None:
        """Probe every route once and drop the ones that cannot answer.

        A kind whose own chain is gone entirely is moved onto a route that
        answered, and the log says so: a kind silently running somewhere
        other than where it was configured is the failure this check exists
        to prevent.
        """
        self.routers = apply_preflight(
            self.configs, self.routers, self.backends, self.credentials, model_failover=bool(self.config.defaults().get("model_failover"))
        )

    def routes(self) -> dict[str, str]:
        """How each kind will run, one line each, by kind name: coding agent/model,
        effort, budgets, credential and requirements, then its failover hops."""
        out = {}
        for kind, rc in sorted(self.configs.items(), key=lambda kv: kind_name(kv[0])):
            line = f"{rc.agent}/{rc.model or '(the agent default model)'} effort={rc.effort}"
            line += f" max_turns={rc.max_turns} timeout_s={rc.timeout_s:g}"
            line += f" max_budget_usd={rc.max_budget_usd:g}" if rc.max_budget_usd is not None else ""
            line += f" credential={rc.credential}" if rc.credential != "ambient" else ""
            line += f" requires={','.join(rc.requires)}" if rc.requires else ""
            router = self.routers.get(kind)
            line += "; on a 429: " + " then ".join(str(r) for r in router.routes[1:]) if router is not None else ""
            out[kind_name(kind)] = line
        return out

    def log(self) -> None:
        """How each kind will run, one `[route]` line each (INFO).

        A run that quietly launched a different model than planned is
        indistinguishable from one that did what it was told, so the plan is
        logged rather than inferred later from the journal.
        """
        for name, line in self.routes().items():
            _logger.info(f"[route] {name}: {line}")


def apply_preflight(
    configs: dict, routers: Mapping, backends: Mapping[str, Backend], credentials: Mapping | None = None, *, model_failover: bool = False
) -> dict:
    """Drop the routes the agents cannot answer on, and re-point what is left.

    Mutates `configs` for the kinds whose chain is gone; returns the
    surviving router map.
    """
    from contraagent.routing.preflight import run_preflight

    live = run_preflight(routers, configs, backends, credentials or {}, model_failover=model_failover)
    if not live:
        return live
    fallback = next(iter(live.values())).routes[0]
    for kind in list(configs):
        if kind in live:
            continue
        rc = configs[kind]
        _logger.warning(f"[preflight] {kind_name(kind)}: no route left; running on {fallback} instead of {rc.agent}/{rc.model}")
        if fallback.credential and fallback.credential != rc.credential:
            # Moving a kind onto another identity is the operator's call, never the preflight's.
            _logger.warning(
                f"[preflight] {kind_name(kind)}: the surviving route runs as {fallback.credential}, not {rc.credential}; left as configured"
            )
            continue
        configs[kind] = dataclasses.replace(rc, agent=fallback.agent, model=fallback.model)
    return live
