"""Before the first task: is every route this run will use actually usable?

Two passes, cheapest first, and both provider-neutral — how an agent
lists its models is that backend's business, asked through
`Backend.catalogue()`.

**The catalogue.** Every model in the plan — the run default, each
`[tasks.<kind>].model`, every fallback hop — is checked against its
agent's own list. A local read, no network, and it catches the typo. It
does not catch a quota.

**A live probe.** One minimal launch per distinct (agent, model, credential)
the run will actually use, `max_turns=1` and a short timeout. This is the
pass that catches what cost a run its work before: a provider that
answers `429 Go usage limit exceeded` in about two seconds. The question
is not "did the launch succeed" but "is this route worth keeping" — a
route that cannot answer is dropped, and the surviving chain is rebuilt
around the ones that did.

Failure policy: a route that cannot answer is dropped and the run
proceeds on the rest. Only a plan left with no usable route at all is
fatal, because proceeding with nothing to run is not a degraded run.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from contraagent.backends.base import Backend
from contraagent.backends.credentials import AMBIENT, CredentialBase
from contraagent.backends.launch import Launch, LaunchResult, Limits, Stop
from contraagent.dispatch.task import kind_name
from contraagent.routing.pool import first_member
from contraagent.routing.router import Route, Router

_logger = logging.getLogger(__name__)

# One token of output is enough to know the route answers.
PROBE_TIMEOUT_S = 90
PROBE_PROMPT = "Reply with the single word: ok"
# A plan can name more distinct models than it is worth a launch each;
# past the cap the rest are left to fail their first task, loudly.
DEFAULT_CAP = 8


@dataclass
class RouteVerdict:
    """What the preflight learned about one route."""

    route: Route
    ok: bool
    reason: str
    wall_s: float = 0.0
    #: What the agent said about its own budget. Claude Code reports 5-hour
    #: and 7-day utilisation on every launch, so a probe that succeeds at
    #: 99% is a route that will fail mid-run — information no pass/fail
    #: can carry. None when the agent reports nothing.
    quota: str = ""


def _quota_note(launch_result: LaunchResult) -> str:
    """A short headroom line from whatever the agent reported."""
    rl = launch_result.rate_limit
    if rl is None:
        return ""
    bits = []
    for label, pct in (("5h", rl.five_hour_pct), ("7d", rl.seven_day_pct)):
        if pct is not None:
            # `:g` so 99.5 reads as 99.5% and not as a round 100% — the
            # difference between "nearly out" and "out".
            bits.append(f"{label} {pct:g}%")
    if rl.status:
        bits.insert(0, rl.status)
    if rl.retry_after_s:
        bits.append(f"retry in {rl.retry_after_s / 3600:.1f}h")
    return "  ".join(bits)


# A route answering on its last drop of headroom is a route that will fail
# partway through a run. Not fatal — a task may well fit — but it is the
# difference between a clean report and a 600-task surprise.
TIGHT_QUOTA_PCT = 95.0


def _tight(quota: str) -> bool:
    """True when any reported utilisation is at the point of running out."""
    for part in quota.replace("  ", " ").split():
        if part.endswith("%"):
            try:
                if float(part[:-1]) >= TIGHT_QUOTA_PCT:
                    return True
            except ValueError:
                continue
    return False


def catalogue_check(backend: Backend | None, route: Route) -> tuple[bool, str]:
    """(ok, reason) for the cheap pass. Unknown catalogue means "probe it"."""
    if backend is None:
        return True, f"no {route.agent} backend here; the probe decides"
    if not route.model:
        return True, "agent default model"
    catalogue = backend.catalogue()
    if catalogue is None:
        return True, f"{route.agent} lists no models; the probe decides"
    if route.model in catalogue:
        return True, "in catalogue"
    return False, f"not in the {route.agent} model list"


def probe(route: Route, backend: Backend, fallback: str | None = None, credential: CredentialBase = AMBIENT) -> RouteVerdict:
    """One minimal launch, shaped like the real one.

    `fallback` is the model-level chain the launch will actually carry
    (Claude Code's --fallback-model). Probing without it would answer a
    different question than the run will: a hop whose own model is dead
    but whose same-agent fallback answers is a route that works, and
    calling it dead would drop a chain the tasks would have survived on.
    """
    launch_result: LaunchResult = backend.run(
        Launch(
            prompt=PROBE_PROMPT,
            label=f"preflight-{route.agent}",
            model=route.model,
            fallback_model=fallback,
            credential=credential,
            limits=Limits(timeout_s=PROBE_TIMEOUT_S, max_turns=1),
        )
    )
    stop = launch_result.stop
    quota = _quota_note(launch_result)
    if stop == Stop.COMPLETED:
        return RouteVerdict(route, True, "answered", launch_result.wall_s, quota)
    if stop == Stop.RATE_LIMITED:
        return RouteVerdict(route, False, "rate limited", launch_result.wall_s, quota)
    text = (launch_result.result_text or launch_result.stderr_tail or "").strip()
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if stop == Stop.LAUNCH_FAILED and not first:
        first = "launch failed"
    return RouteVerdict(route, False, f"{stop.value}: {first[:70]}", launch_result.wall_s, quota)


def _wanted_routes(configs: Mapping, routers: Mapping) -> list[Route]:
    """Distinct (agent, model, credential) routes this run will actually launch.

    Per-Kind routers repeat the same pair for every kind that does not
    name its own model, so the union collapses to a handful of probes
    rather than one per kind.
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[Route] = []

    def add(r: Route) -> None:
        if r.identity not in seen:
            seen.add(r.identity)
            out.append(r)

    for rc in configs.values():
        add(Route(agent=rc.agent, model=rc.model, credential=rc.credential))
    for router in routers.values():
        for r in router.routes[1:]:
            add(r)
    return out


def _native_chain(route: Route, routers: Mapping, backend: Backend) -> str | None:
    """The model-level chain this route's launch will carry, if any.

    Only for an agent that declares `native_model_chain`. The first
    chain that mentions the route supplies it, which is enough: a route
    that appears in two chains with different same-agent remainders is a
    config the operator has not resolved, and the preflight reports what
    the first says.
    """
    if not backend.drivable_model_chain:
        return None
    for router in routers.values():
        same = router.same_agent_after(route)
        if same:
            return ",".join(r.model for r in same if r.model) or None
    return None


def _own_chain(backend: Backend, model: str) -> str:
    """What the agent's own model-level chain does for `model`.

    Only meaningful for an agent whose mechanism lives in its config
    rather than on argv, which today means omp: `retry.fallbackChains`
    is on by default but empty unless the operator filled it in, and an
    empty chain is a quota refusal walking past unimpeded.
    """
    chains = backend.model_chains()
    if chains is None:
        return "not available"
    return chains.describe(model)


def run_preflight(
    routers: Mapping,
    configs: Mapping,
    backends: Mapping[str, Backend],
    credentials: Mapping[str, CredentialBase] | None = None,
    cap: int = DEFAULT_CAP,
    model_failover: bool = False,
) -> dict:
    """Check every route the run will use; drop the ones that cannot answer.

    Returns the router map rebuilt on the surviving routes, and the live
    verdicts keyed by route. An empty result means nothing can run.
    """
    wanted = _wanted_routes(configs, routers)
    probes, skipped = wanted[:cap], wanted[cap:]
    if skipped:
        _logger.warning(f"[preflight] {len(skipped)} further route(s) not probed (cap {cap}); a bad one fails its first task instead")

    _logger.info(f"[preflight] 1/2 model catalogue: {len(probes)} route(s)")
    typed: dict[tuple[str, str, str], bool] = {}
    for r in probes:
        ok, why = catalogue_check(backends.get(r.agent), r)
        typed[r.identity] = ok
        if not ok:
            _logger.warning(f"[preflight]   {r}  DROPPED ({why})")
    if all(typed.values()):
        _logger.info(f"[preflight]   all {len(probes)} known to their agent")

    _logger.info("[preflight] 2/2 reachability")
    live: dict[tuple[str, str, str], RouteVerdict] = {}
    for r in probes:
        if not typed[r.identity]:
            continue
        be = backends.get(r.agent)
        if be is None:
            live[r.identity] = RouteVerdict(r, False, f"no {r.agent} backend in this run")
            _logger.warning(f"[preflight]   {r}  DROPPED (no backend)")
            continue
        native = _native_chain(r, routers, be)
        v = probe(r, be, native, first_member(credentials or {}, r.credential) or AMBIENT)
        live[r.identity] = v
        mark = "ok" if v.ok else f"DROPPED ({v.reason})"
        extra = f"  [{v.quota}]" if v.quota else ""
        if native:
            via = f"  (model chain: {native})"
        elif be.native_model_chain:
            # The agent owns its model-level failover, so what matters is
            # whether the operator configured it — and, if they asked
            # contraagent for it, that the request cannot be honoured here.
            own = _own_chain(be, r.model)
            via = f"  (own model chain: {own})"
            if model_failover and not be.drivable_model_chain:
                _logger.warning(
                    f"[preflight]   ^ model_failover is on, but contraagent does not drive {r.agent}'s; it is that agent's own setting"
                )
        else:
            via = ""
        _logger.log(logging.INFO if v.ok else logging.WARNING, f"[preflight]   {r}  {mark} ({v.wall_s:.1f}s){extra}{via}")
        if v.ok and _tight(v.quota):
            _logger.warning("[preflight]   ^ low headroom: this route will likely fail partway through the run")
    out: dict = {}
    rebuilt: dict[str, list[str]] = {}
    for kind, router in routers.items():
        kept = [r for r in router.routes if r.identity in live and live[r.identity].ok]
        if not kept:
            _logger.warning(f"[preflight] {kind_name(kind)}: every route failed; no chain left")
            continue
        if len(kept) == len(router.routes):
            out[kind] = router
            continue
        new = Router(kept[0], tuple(kept[1:]))
        for frm, to in router.history():
            new.history().append((frm, to))
        out[kind] = new
        rebuilt.setdefault(new.chain(), []).append(kind_name(kind))
    # Every kind that shared the global chain shares the trimmed one too,
    # so sixteen identical lines would say less than one.
    for chain, kinds in rebuilt.items():
        _logger.info(f"[preflight] {chain}   ({len(kinds)} kind(s): {', '.join(sorted(kinds))})")
    return out
