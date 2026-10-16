"""Run one task on a coding-agent backend, failing over on a rate limit.

`AgentRunner` is the `TaskRunner` (`dispatch/queue.py`) for agent tasks: the
queue holds one and calls `.run()` for each dispatched `Task`. Everything
domain-specific comes from a `TaskAdapter` (`execution/adapter.py`); the
runner owns only the generic loop:

    input check -> pick route -> build Launch -> run (validated) -> classify

`RetryingRunner` wraps it with progress-aware retry, so the queue always
sees one terminal `TaskResult` per `Task`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import random
import signal
import sys
import threading
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from contraagent._internal.backends.base import Backend
from contraagent._internal.backends.credentials import AMBIENT, Credential, Pool
from contraagent._internal.backends.launch import Launch, LaunchResult, Stop
from contraagent._internal.backends.process import signal_of
from contraagent._internal.contracts.contract import check_input, fold_spend, record_contracts, run_until_valid
from contraagent._internal.dispatch.interceptors import ResultEnricher, TaskScope, enriched
from contraagent._internal.dispatch.records import DeferralCause, Hop, Rest, SkippedHop, TokenUsage
from contraagent._internal.dispatch.task import STOP_DEFERRED, STOP_PARTIAL, Deferral, Task, TaskResult, kind_name
from contraagent._internal.execution.adapter import TaskAdapter
from contraagent._internal.execution.changes import ChangesEnricher
from contraagent._internal.execution.services import service_environment
from contraagent._internal.platform import envvars, telemetry
from contraagent._internal.platform.commands import commands
from contraagent._internal.routing.kind_config import KindConfig
from contraagent._internal.routing.pool import CredentialPool, pools_of
from contraagent._internal.routing.quota import QuotaRests
from contraagent._internal.routing.router import Route, Router
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import write_document

_logger = logging.getLogger(__name__)


def _texts(rests: Sequence[Rest]) -> list[str]:
    """Each rest (a skipped hop's) in one line, once each."""
    out: list[str] = []
    for r in rests:
        line = r.text()
        if line not in out:
            out.append(line)
    return out


def _rest_deferral(rests: Sequence[SkippedHop]) -> Deferral:
    """A task deferred because the credential of every hop it could take rests: `rest`,
    with each hop passed over and its rest."""
    return Deferral("; ".join(_texts(rests)), DeferralCause(cause="rest", rests=tuple(rests)))


def telemetry_line(task: Task, run_id: str, role: str | None) -> str:
    """The telemetry line of `task` (`contraagent._internal.platform.telemetry`), first in every prompt."""
    return telemetry.line(run_id, kind_name(task.kind), task.unit, task.key, role)


#: Failures another hop cannot fix: nothing was launched (an input is off-contract), or the
#: agent ran as another identity than the one chosen. Every other failure moves the task on.
NO_FAILOVER = frozenset({Stop.INVALID_INPUT.value, Stop.CREDENTIAL_MISMATCH.value})


def _fails_over(result: TaskResult) -> bool:
    """A failed launch moves its task to the next hop, unless another hop cannot fix it
    (`NO_FAILOVER`) or a signal ended it (the run is stopping)."""
    if result.ok or result.stop in NO_FAILOVER:
        return False
    o = result.launch_result
    return not (o is not None and signal_of(o.exit_code) is not None)


def _hop(label: str, result: TaskResult) -> Hop:
    """One launch on one route: where it ran, how it ended (its launch's stop: `timeout` for
    a partial result too) and what it spent. Taken before the hops
    after it fold their spend into the attempt's, so each hop holds its own (its rounds,
    and pool members tried on it, included)."""
    o = result.launch_result
    totals = o.usage.totals(o.context_window) if o is not None else None
    # Resident is the attempt's (its first call's), not a hop's.
    hop_usage = TokenUsage.model_validate(totals.model_dump(exclude={"resident"})) if totals is not None else None
    return Hop(
        route=label,
        agent=o.agent if o else "",
        model=o.model if o else "",
        credential=o.credential if o else "",
        stop=o.stop.value if o is not None else result.stop,
        wall_s=round(result.wall_s, 1),  # this hop, pool members tried on it included
        cost_usd=o.cost_usd if o else None,
        usage=hop_usage,
        other_models=dict(o.other_models) if o is not None else {},
    )


class AgentRunner:
    """One task to completion. Stateless across calls; safe from threads."""

    #: Class-level fallbacks so a stub built without `__init__` still works.
    scopes: Sequence[TaskScope] = ()
    enrichers: Sequence[ResultEnricher] = ()

    def __init__(
        self,
        backends: Backend | Mapping[str, Backend],
        configs: Mapping[str, KindConfig],
        *,
        run_dir: Path | str,
        run_id: str = "",
        adapter: TaskAdapter | None = None,
        routers: Mapping[str, Router] | None = None,
        model: str = "",
        model_failover: bool = False,
        credentials: Mapping[str, Credential] | None = None,
        env: Mapping[str, str] | None = None,
        keep_transcripts: bool = False,
        cwd: Path | str | None = None,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
        rests: QuotaRests | None = None,
    ):
        """
        `backends`: every coding agent a kind or a route may name, keyed by
        agent name (one `Backend` is shorthand for `{backend.name: backend}`).
        `configs`: one `KindConfig` per kind (`RoutingPlan.configs`).
        `routers`: one failover breaker per kind (`RoutingPlan.routers`). A kind
        with no entry never fails over: a task nobody configured a chain for
        should end on a 429 rather than wander.
        `run_dir` / `run_id`: where streams and records go, and the run the
        launches are attributed to (`Run.agent_runner()` fills both).
        `credentials`: the identities a kind or a route may name, by name
        (`RoutingPlan.credentials`); `ambient` is always there.
        `model`, `model_failover`, `env`: run-wide launch defaults a kind's own
        config outranks.
        `rests`: the run's quota rests (`QuotaRests`): a hop whose credential rests is
        skipped without a launch, a pool's resting members too, and a task with no hop
        left is deferred. Each launch's utilization readings are told to it.
        `scopes` / `enrichers`: wrap each dispatch (`TaskScope`, `ResultEnricher`). The
        task's changes (`TaskAdapter.changes`) are recorded by a built-in enricher that
        runs before them, so theirs see `TaskResult.changes`.
        """
        if isinstance(backends, Backend):
            backends = {backends.name: backends}
        if not backends:
            raise ValueError("AgentRunner needs at least one backend")
        # Resolved per task rather than held as one "current" backend: tasks
        # fan out across threads, and a fallback route varies it per task.
        self.backends: dict[str, Backend] = dict(backends)
        self.configs: Mapping[str, KindConfig] = configs
        self.routers: dict[str, Router] = dict(routers or {})
        self.adapter: TaskAdapter = adapter or TaskAdapter()
        self.run_id = run_id
        self.run_dir: Path = Path(run_dir)
        (self.run_dir / "streams").mkdir(parents=True, exist_ok=True)
        self.model = model
        self.model_failover = model_failover
        self.credentials: dict[str, Credential] = {"ambient": AMBIENT, **(credentials or {})}
        # Pool state is run-wide, like a Router: every worker thread shares it.
        self.pools: dict[str, CredentialPool] = pools_of(self.credentials)
        self.env: dict[str, str] = dict(env or {})
        self.keep_transcripts = keep_transcripts
        self.cwd: Path = Path(cwd) if cwd else Path.cwd()
        self.scopes = tuple(scopes)
        self.enrichers = tuple(enrichers)
        self.rests = rests
        self._changes = ChangesEnricher(self.adapter.changes, self.cwd, keep=self._keeps_failed_changes)
        self._defined: set[str] = set()
        # The account each coding agent bills as each credential for a model, asked once a run.
        self._accounts: dict[tuple[str, str, str], str] = {}
        self._accounts_lock = threading.Lock()
        # (kind, a task call's credential) -> (the kind's router it was made from, its own router).
        self._call_routers: dict[tuple[str, str], tuple[Router | None, Router | None]] = {}
        self._call_routers_lock = threading.Lock()

    # --- configuration -----------------------------------------------------

    def config(self, task: Task) -> KindConfig:
        """Per-kind config. A kind with none raises: a silent default would be
        a task launched with a budget nobody chose."""
        rc = self.configs.get(task.kind)
        if rc is None:
            raise KeyError(f"no [tasks.{kind_name(task.kind)}] in the config: every kind needs agent/model routing and budgets")
        return replace(rc, credential=task.credential) if task.credential and task.credential != rc.credential else rc

    def _keeps_failed_changes(self, task: Task) -> bool:
        rc = self.configs.get(task.kind)
        return rc is not None and rc.keep_failed_changes

    def router_for(self, task: Task) -> Router | None:
        """The kind's failover breaker; for a task whose call names a credential
        (`Task.credential`), one of the kind and that credential, over the kind's routes each
        on it (`Router.on_credential`), made once a run. None: the task has a single route."""
        router = self.routers.get(task.kind)
        if router is None or not task.credential or all(r.credential == task.credential for r in router.routes):
            return router
        with self._call_routers_lock:
            base, own = self._call_routers.get((task.kind, task.credential), (None, None))
            if base is not router:  # a kind routed again (`Pipeline`) gets a breaker of its new chain
                own = router.on_credential(task.credential)
                own = own if len(own.routes) > 1 else None
                self._call_routers[(task.kind, task.credential)] = (router, own)
            return own

    def backend_for_route(self, task: Task, route: Route | None) -> Backend:
        """The coding agent for this task on `route` (None: the kind's own).

        A route naming an agent with no backend here falls back to the kind's
        backend; a kind naming one falls back to the first backend given.
        """
        if route is not None and route.agent in self.backends:
            return self.backends[route.agent]
        named = self.backends.get(self.config(task).agent)
        return named if named is not None else next(iter(self.backends.values()))

    def launch(
        self, task: Task, route: Route | None = None, backend: Backend | None = None, credential: Credential | None = None
    ) -> Launch:
        """Build the backend launch: role, model, limits, prompt."""
        rc = self.config(task)
        be = backend or self.backend_for_route(task, route)
        role = self.adapter.role(task)
        # Precedence, highest first: the active failover route, the kind's own
        # model, then the run-wide model.
        model = route.model if route is not None and route.model else (rc.model or self.model)
        credential = credential or self.credential_for(task, route)
        plugin_dirs = self.adapter.plugin_dirs(task)
        tools = self.adapter.tools(task)
        settings = rc.settings if rc.settings and Path(rc.settings).exists() else None
        if tools == ():  # a light launch loads no settings: they could only add hooks to a launch with no tools
            settings = None
        bash = commands.bash()
        env = {
            envvars.PYTHON: sys.executable,
            **({envvars.BASH: bash} if bash and bash != "bash" else {}),
            **self.env,
            **self.adapter.env(task),
            **service_environment(),
            envvars.RUN: self.run_id,
            envvars.TASK: task.key,
            envvars.KIND: kind_name(task.kind),
            envvars.UNIT: task.unit,
            envvars.PARAMS: json.dumps({k: v for k, v in (task.params or {}).items() if isinstance(v, (str, int, float))}),
        }
        prompt = f"{telemetry_line(task, self.run_id, role)}\n\n{self.adapter.prompt(task, be)}"
        return Launch(
            prompt=prompt,
            label=task.key,
            role=role,
            model=model,
            effort=rc.effort,
            fallback_model=self._model_chain(task, route, be),
            settings=settings or (self.adapter.settings_path(task) if tools != () else None),
            mcp_config=self.adapter.mcp_config_path(task),
            tools=tools,
            system_prompt=self.adapter.system_prompt(task),
            exclude_dynamic_sections=rc.exclude_dynamic_sections,
            limits=rc.limits(),
            credential=credential,
            env=env,
            cwd=self.cwd,
            preamble=task.params.get("preamble"),
            context_files=self.adapter.context_files(task, be),
            plugin_dirs=plugin_dirs,
            stream_path=self.run_dir / layout.stream(task.key) if self.keep_transcripts else None,
        )

    def credential_for(self, task: Task, route: Route | None) -> Credential:
        """The identity this task launches as on `route`: the route's, else the kind's.
        An unknown name raises: launching under a different identity is never a fallback."""
        name = self._credential_name(task, route)
        cred = self.credentials.get(name)
        if cred is None:
            raise KeyError(f"no credential {name!r}; known: {', '.join(sorted(self.credentials))}")
        return cred

    def _credential_name(self, task: Task, route: Route | None) -> str:
        return (route.credential if route is not None and route.credential else "") or self.config(task).credential or "ambient"

    def account_of(self, backend: Backend, credential: Credential, model: str) -> str:
        """The account `backend` bills as `credential` for `model` (`Backend.account`), asked
        once a run; '' when it cannot tell."""
        key = (backend.name, credential.label, model)
        with self._accounts_lock:
            if key in self._accounts:
                return self._accounts[key]
        try:
            found = backend.account(credential, model)
        except Exception:  # an account that cannot be told only loses the distinction
            found = ""
        with self._accounts_lock:
            return self._accounts.setdefault(key, found)

    def _accounts_on(self, task: Task, route: Route | None) -> Callable[[str], str]:
        """`account(credential)` for a launch of this task on `route` (`QuotaRests.rests`)."""
        backend = self.backend_for_route(task, route)
        model = (route.model if route is not None and route.model else "") or self.config(task).model or self.model

        def account(name: str) -> str:
            cred = self.credentials.get(name)
            return self.account_of(backend, cred, model) if cred is not None else ""

        return account

    def _rest(self, task: Task, route: Route | None) -> list[Rest]:
        """Why `route`'s credential rests for this task now (`QuotaRests`), judged by the
        readings of the account a launch on it bills; empty when it does not."""
        if self.rests is None:
            return []
        return self.rests.rests(self._credential_name(task, route), kind_name(task.kind), self._accounts_on(task, route))

    def _usable(self, task: Task, route: Route, router: Router, skipped: list[SkippedHop]) -> Route | None:
        """`route`, or the first hop after it whose credential does not rest; None when every
        one rests. Each hop passed over is added to `skipped`: its label and model, and why
        its credential rests. Stateless for the router: a rest is the credential's, not a
        hop's 429."""
        here: Route | None = route
        while here is not None:
            why = self._rest(task, here)
            if not why:
                return here
            skipped += [r.skipped(router.label_of(here), here.model) for r in why]
            here = router.next_route_after(here)
        return None

    def deferral(self, task: Task) -> Deferral | None:
        """Why this task cannot launch now: every hop it could take, from the one its kind's
        router picks on, is on a resting credential. None when one is not, or nothing rests."""
        if self.rests is None:
            return None
        router = self.router_for(task)
        if router is None:
            why = self._rest(task, None)
            return _rest_deferral([SkippedHop(**r.to_dict()) for r in why]) if why else None
        route = router.pick()
        if route is None:  # every hop rate limited: the launch says so
            return None
        skipped: list[SkippedHop] = []
        return _rest_deferral(skipped) if self._usable(task, route, router, skipped) is None else None

    def _model_chain(self, task: Task, route: Route | None, backend: Backend) -> str | None:
        """The same-agent remainder to hand the agent's own failover flag, when asked.

        Opt-in per kind or per run: a task silently re-running on another
        model is a change of mind the operator did not ask for, and the
        journal would name a model nobody chose. Cross-agent hops are the
        Router's, and handing those to a same-CLI flag would fail at argv.
        """
        if not backend.drivable_model_chain or route is None:
            return None
        if not (self.model_failover or self.config(task).model_failover):
            return None
        router = self.router_for(task)
        same = router.same_agent_after(route) if router is not None else ()
        return (",".join(r.model for r in same if r.model) or None) if same else None

    # --- execution ---------------------------------------------------------

    def run(self, task: Task) -> TaskResult:
        """Run one task, failing over on a 429. A launch whose peak context passed its kind's
        `context_warn_pct` is noted (`TaskResult.notes["context_warned"]`).

        Brackets the whole dispatch (every failover hop) with every
        `TaskScope`, entered in order and exited in reverse; each
        `ResultEnricher` snapshots once before and enriches once after, the
        built-in one that records the task's changes first.
        """
        snapshots = [(e, e.snapshot(task)) for e in (self._changes, *self.enrichers)]
        with contextlib.ExitStack() as stack:
            for scope in self.scopes:
                stack.enter_context(scope(task))
            result = self._run(task)
        result = enriched(snapshots, task, result)
        o = result.launch_result
        if o is not None and o.context_warned:
            warned = {
                "peak_context": o.peak_context,
                "context_budget": o.context_budget,
                "context_warn_pct": self.config(task).context_warn_pct,
            }
            result = replace(result, notes={**result.notes, "context_warned": warned})
        return result

    def _record_contracts(self, task: Task) -> None:
        record_contracts(self.run_dir, task, list(self.adapter.output_contracts(task)), list(self.adapter.input_contracts(task)), self.cwd)
        self._record_definition(task)

    def _record_definition(self, task: Task) -> None:
        """Snapshot what defines this kind of task, once per kind per run, to
        `definitions/<kind>.json`: the monitor shows the definition the run actually used."""
        kind = kind_name(task.kind)
        if kind in self._defined:
            return
        self._defined.add(kind)
        try:
            body = {"kind": kind, **(self.adapter.definition(task) or {})}
            d = self.run_dir / layout.DEFINITIONS
            d.mkdir(parents=True, exist_ok=True)
            write_document(d / f"{layout.file_name(kind)}.json", json.dumps(body, default=str))
        except Exception:  # a definition the monitor cannot show must not fail a launch
            pass

    def _refuse(self, task: Task, stop: Stop, reason: str) -> TaskResult:
        launch_result = LaunchResult(
            label=task.key,
            agent=self.backend_for_route(task, None).name,
            stop=stop,
            ok=False,
            model=self.model or self.config(task).model,
            credential=self.config(task).credential,
            stderr_tail=reason[:400],
        )
        return TaskResult(task=task, launch_result=launch_result, ok=False, stop=stop.value, reason=reason[:240])

    def _run(self, task: Task) -> TaskResult:
        self._record_contracts(task)
        missing = self.adapter.missing_params(task)
        if missing:
            return self._refuse(task, Stop.LAUNCH_FAILED, f"missing required params: {', '.join(missing)}")
        bad: list[str] = []
        for contract in self.adapter.input_contracts(task):
            bad += check_input(contract, self.cwd)
        if bad:
            # Refused before launch: an input the task would read is off-contract.
            return self._refuse(task, Stop.INVALID_INPUT, f"invalid input: {'; '.join(bad)}")
        router = self.router_for(task)
        if router is None:
            rest = self._rest(task, None)
            if rest:
                return TaskResult.deferred(task, _rest_deferral([SkippedHop(**r.to_dict()) for r in rest]))
            result = self._run_once(task, None)
            o = result.launch_result
            if o is not None:
                label = Route(o.agent, o.model, o.credential).label(1, 1)
                result = replace(result, route=label, hops=(_hop(label, result),))
            return result
        return self._run_with_failover(task, router)

    def _run_with_failover(self, task: Task, router: Router) -> TaskResult:
        """Walk `router`'s chain: a 429 moves the shared breaker for every task; any
        other failure (`_fails_over`) moves only this task to the next hop."""
        hops = 0
        prior_reason = ""  # what an earlier hop already said about this task
        pinned = None  # this task's own walk after a failure other than a 429
        trail: list[Hop] = []
        spent: LaunchResult | None = None  # the hops so far: their tokens and cost
        skipped: list[SkippedHop] = []  # the hops passed over without a launch (a resting credential)
        last: TaskResult | None = None
        while True:
            route = pinned if pinned is not None else router.pick()
            if route is not None and self.rests is not None:
                seen = len(skipped)
                usable = self._usable(task, route, router, skipped)
                notes = _texts(skipped[seen:])
                if usable is None:
                    if last is None:  # nothing launched: deferred, not failed
                        return TaskResult.deferred(task, _rest_deferral(skipped))
                    return replace(last, reason="; ".join([prior_reason, *notes] if prior_reason else notes), skipped_hops=tuple(skipped))
                if usable != route:
                    prior_reason = "; ".join([prior_reason, *notes] if prior_reason else notes)
                    _logger.info(f"[route] {task.key}: {notes[-1]}; on {router.label_of(usable)}")
                    route = pinned = usable
            if route is None:
                # Every hop refused and the chain is spent: a plain error, not
                # a silent stall.
                result = self._refuse(task, Stop.RATE_LIMITED, "all hops rate limited")
                return replace(result, reason=f"{kind_name(task.kind)}: all {len(router.routes)} hops rate limited", hops=tuple(trail))
            label = router.label_of(route)
            if not trail and pinned is None and route != router.routes[0]:
                # Not this task's 429: the kind's breaker is still open after another task's.
                _logger.info(f"[route] {task.key}: starting on {label}; {router.label_of(router.routes[0])} rests after a 429")
            started = router.now()
            result = self._run_once(task, route)
            trail.append(_hop(label, result))
            # Tokens and cost of the hops before this one belong to the attempt too.
            if result.launch_result is not None:
                if spent is not None:
                    fold_spend(spent, result.launch_result)
                spent = result.launch_result
            own_reason = result.reason
            # The attempt's time is every hop's, not only the last one's: a model
            # switch after a rate limit still spent the time before it.
            result = last = replace(
                result,
                skipped_hops=tuple(skipped),
                hops=tuple(trail),
                wall_s=round(sum(h.wall_s for h in trail), 1),
                reason=prior_reason or result.reason,
            )
            if result.stop != Stop.RATE_LIMITED and _fails_over(result):
                nxt_route = router.next_route_after(route)
                if nxt_route is None:
                    return replace(result, route=label)
                what = "safeguard refusal" if result.stop == Stop.REFUSED else result.stop
                prior_reason = (
                    f"{what} on {label}" + (f" ({own_reason})" if own_reason else "") + f"; failing over to {router.label_of(nxt_route)}"
                )
                _logger.warning(f"[switch] {task.key}: {prior_reason}")
                last = replace(result, reason=prior_reason)
                pinned = nxt_route
                continue
            if result.stop != Stop.RATE_LIMITED:
                router.succeeded(route, started=started)
                return replace(result, route=label, reason=f"{prior_reason}; ran on {label}" if prior_reason else result.reason)
            hops += 1
            nxt = router.rate_limited(
                route,
                (
                    result.launch_result.quota_refusal.retry_after_s
                    if result.launch_result is not None and result.launch_result.quota_refusal is not None
                    else None
                ),
            )
            if not nxt or hops >= len(router.routes):
                reason = f"rate limited on {label} and {nxt}" if nxt else f"rate limited on {label}; no hop left of {len(router.routes)}"
                return replace(result, route=label, reason=reason)
            prior_reason = f"rate limited on {label}; failing over to {nxt}"
            _logger.warning(f"[switch] {task.key}: {prior_reason}")
            last = replace(result, reason=prior_reason)

    def _run_once(self, task: Task, route: Route | None) -> TaskResult:
        """One launch on one route; on a pool credential, as many as it takes to find a
        member that is not rate limited (`_run_pooled`)."""
        try:
            credential = self.credential_for(task, route)
        except KeyError as exc:
            return self._refuse(task, Stop.LAUNCH_FAILED, str(exc))
        pool = self.pools.get(credential.label) if isinstance(credential, Pool) else None
        if pool is not None:
            return self._run_pooled(task, route, pool)
        return self._run_as(task, route, credential)

    def _run_pooled(self, task: Task, route: Route | None, pool) -> TaskResult:
        """Walk the pool's members on this route: a member that answers 429 cools down and
        the next one launches at once. With every member cooling the result is rate
        limited, and the route's own failover (the Router) takes over."""
        tried: list[str] = []
        last: TaskResult | None = None
        spent = 0.0  # time on members that were rate limited, counted in the result
        model = (route.model if route is not None and route.model else "") or self.config(task).model or self.model
        # Members resting on their quota are passed over like those that answered 429.
        resting = (
            self.rests.resting_members(pool.name, kind_name(task.kind), self._accounts_on(task, route)) if self.rests is not None else set()
        )
        while True:
            member = pool.pick(model, exclude=[*tried, *resting])
            if member is None:
                if last is None:
                    last = self._refuse(task, Stop.RATE_LIMITED, f"every member of pool {pool.name} is cooling down")
                if tried:
                    reason = (f"pool {pool.name}: {', '.join(tried)} rate limited" + (f"; {last.reason}" if last.reason else ""))[:240]
                    last = replace(last, reason=reason)
                return last
            prior = last.launch_result if last is not None else None
            last = self._run_as(task, route, member)
            last = replace(last, wall_s=last.wall_s + spent)
            if prior is not None and last.launch_result is not None:
                fold_spend(prior, last.launch_result)  # members that were rate limited spent tokens too
            if last.stop != Stop.RATE_LIMITED:
                if tried:
                    note = f"pool {pool.name}: {', '.join(tried)} rate limited, ran on {member.label}"
                    last = replace(last, reason=f"{note}; {last.reason}" if last.reason else note)
                return last
            refusal = last.launch_result.quota_refusal if last.launch_result is not None else None
            pool.rate_limited(member, model, refusal.retry_after_s if refusal is not None else None)
            tried.append(member.label)
            spent = last.wall_s

    def _run_as(self, task: Task, route: Route | None, credential: Credential) -> TaskResult:
        """One launch on one route as one credential. `ok`/`stop` come straight from the
        backend's `LaunchResult`, but for a launch stopped on one of its kind's `partial_on`
        whose outputs passed every check (`LaunchResult.partial`): ok, stop `partial`, its
        reason the launch's stop (`timeout`, `stalled`). A domain's own progress verdict is a
        `ResultEnricher`'s job."""
        backend = self.backend_for_route(task, route)
        launch = self.launch(task, route, backend, credential)
        contracts = self.adapter.output_contracts(task)
        # With declared outputs the launch is resumed until every one holds,
        # or the kind's `max_corrections` are spent (then INVALID_OUTPUT, not ok).
        kc = self.config(task)
        if contracts:
            launch_result = run_until_valid(backend, launch, contracts, kc.max_corrections, partial_on=kc.partial_stops)
        else:
            launch_result = backend.run(launch)
        for i, reading in enumerate(launch_result.quota):  # whose account each quota reading is
            reading = launch_result.quota[i] = reading.model_copy(
                update={
                    "credential": reading.credential or launch_result.credential or credential.label,
                    "account": reading.account or self.account_of(backend, credential, launch.model),
                }
            )
            if self.rests is not None:
                self.rests.observe(reading)
        launch_result.context_budget = launch.limits.context_budget
        launch_result.context_warned = launch_result.context_warned or launch.limits.context_warned(launch_result.peak_context)
        reason = (launch_result.stderr_tail or "")[-200:].strip()
        if launch_result.stop == Stop.INVALID_OUTPUT and launch_result.round_errors:
            reason = "; ".join(launch_result.round_errors[-1])[:240]
        if launch_result.stop == Stop.REFUSED and launch_result.result_text:
            # A refusal is reported as the API error text in the result line,
            # not on stderr.
            reason = launch_result.result_text.strip()[:240]
        # A signal-terminated process (exit code 128+N) is almost always
        # external (teardown, an interrupted run), not the task's own logic.
        sig = signal_of(launch_result.exit_code)
        if sig is not None and not launch_result.partial:
            note = f"terminated by {signal.Signals(sig).name}"
            reason = f"{note}: {reason}" if reason else note
        if launch_result.partial:
            # Stopped for its time, and what it wrote passed every check: kept, as a partial result.
            return TaskResult(
                task=task,
                launch_result=launch_result,
                ok=True,
                wall_s=launch_result.wall_s,
                stop=STOP_PARTIAL,
                reason=launch_result.stop.value,
                rounds=launch_result.rounds,
                round_errors=tuple(tuple(errors) for errors in launch_result.round_errors),
            )
        return TaskResult(
            task=task,
            launch_result=launch_result,
            ok=launch_result.ok,
            wall_s=launch_result.wall_s,
            stop=launch_result.stop.value,
            reason=reason,
            rounds=launch_result.rounds,
            round_errors=tuple(tuple(errors) for errors in launch_result.round_errors),
            retryable=launch_result.retryable,
        )


def backoff_s(base: float, attempt: int) -> float:
    """The wait before the attempt after `attempt` (from 0): up to `base` seconds, doubled per
    attempt, with full jitter, so tasks that failed together do not all retry together."""
    return random.uniform(0, base * 2**attempt)


class RetryingRunner:
    """Wraps an `AgentRunner` so the queue sees one terminal `TaskResult` per `Task`.

    A failure *without* progress gets a fresh attempt, after full-jitter exponential
    backoff, up to the kind's `KindConfig.retries` of them after the first (`retries=2`:
    3 attempts at most); a safeguard refusal is not
    retried (the hop walk already tried every route). This sits beside the
    queue's own `retry_on`, which covers a launch that never ran.

    `max_concurrent_overrides` sizes a per-kind budget for one queue without
    mutating the shared `AgentRunner`. `on_attempt` sees EVERY attempt's result,
    so a retried-then-completed task still leaves its full trail in the
    journal. `on_exhausted` is told when the last attempt also failed.
    """

    #: The wait before a fresh attempt (`backoff_s`).
    backoff: Callable[[float, int], float] = staticmethod(backoff_s)

    def __init__(
        self,
        runner: AgentRunner,
        max_concurrent_overrides: dict[str, Any] | None = None,
        on_attempt: Callable[[TaskResult], None] | None = None,
        on_exhausted: Callable[[Task, TaskResult], None] | None = None,
    ):
        self._runner = runner
        self._overrides = max_concurrent_overrides or {}
        self._on_attempt = on_attempt
        self._on_exhausted = on_exhausted

    def config(self, task: Task) -> KindConfig:
        rc = self._runner.config(task)
        override = self._overrides.get(task.kind)
        return replace(rc, max_concurrent=override) if override is not None else rc

    def deferral(self, task: Task) -> Deferral | None:
        return self._runner.deferral(task)

    def run(self, task: Task) -> TaskResult:
        rc = self._runner.config(task)
        attempts = 1 + max(0, rc.retries)
        last: TaskResult | None = None
        notes: dict[str, Any] = {}  # every attempt's, for the one result the queue sees
        for attempt in range(attempts):
            task = replace(task, attempt=attempt)
            last = self._runner.run(task)
            notes.update(last.notes)
            last = replace(last, notes=dict(notes))
            if last.stop == STOP_DEFERRED:  # nothing launched: not an attempt, nothing to journal
                return last
            if self._on_attempt is not None:
                try:
                    self._on_attempt(last)
                except Exception:  # a journal write must never turn into
                    # "the launch failed", which the queue would retry and re-run a
                    # completed task.
                    traceback.print_exc()
            # A refusal was already tried on every route; an off-contract input is the same
            # file on the next attempt. Neither is worth another launch.
            if last.ok or last.stop in (Stop.REFUSED, Stop.INVALID_INPUT) or not last.retryable:
                break
            if attempt + 1 < attempts:
                time.sleep(self.backoff(rc.retry_backoff_base, attempt))
        assert last is not None
        if not last.ok and self._on_exhausted is not None:
            self._on_exhausted(task, last)
        return last
