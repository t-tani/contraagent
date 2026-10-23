"""Before the first task: is every route this run will use actually usable?

Two passes, cheapest first, and both provider-neutral — how an agent
lists its models is that backend's business, asked through
`Backend.catalogue()`.

**The catalogue.** Every model in the plan — the run default, each
`[tasks.<kind>].model`, every fallback hop — is checked against its
agent's own list. A local read, no network, and it catches the typo. It
does not catch a quota.

**A live probe.** One minimal launch per distinct (agent, model, credential)
the run will actually use, `max_turns=1`, all of them at once. This is the
pass that catches what cost a run its work before: a provider that
answers `429 Go usage limit exceeded` in about two seconds. The question
is not "did the launch succeed" but "is this route worth keeping" — a
route that cannot answer is dropped, and the surviving chain is rebuilt
around the ones that did. A probe has the time of the longest `timeout_s`
among the kinds whose chain holds its route: a route that cannot answer one
word in that time cannot finish any of their tasks either.

A route that cannot answer is dropped and each chain is rebuilt on the
rest. What happens to a kind left with no route that answered is the
preflight policy (`PreflightPolicy`): `substitute` moves it onto the first
route that answered, when that route runs as the kind's own credential;
`stop` refuses the run before its first launch (`PreflightStopped`); `off`
probes nothing. `PreflightRecord` is what the preflight did, as `run.json`
records it (`preflight`).
"""

from __future__ import annotations

import contextvars
import dataclasses
import logging
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, get_args

from pydantic import ConfigDict, Field

from contraagent._internal.backends.base import Backend
from contraagent._internal.backends.credentials import AMBIENT, Credential
from contraagent._internal.backends.launch import Launch, LaunchResult, Limits, Stop
from contraagent._internal.dispatch.records import RecordModel
from contraagent._internal.dispatch.task import kind_name
from contraagent._internal.errors import ContraagentError
from contraagent._internal.routing.pool import first_member
from contraagent._internal.routing.router import Route, Router

_logger = logging.getLogger(__name__)

#: What the preflight does with a kind left with no route that answered: `substitute`
#: (run it on the first route that answered, of the same credential), `stop` (refuse
#: the run: `PreflightStopped`), `off` (probe nothing).
PreflightPolicy = Literal["substitute", "stop", "off"]
PREFLIGHT_POLICIES: tuple[str, ...] = get_args(PreflightPolicy)

# One token of output is enough to know the route answers.
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
    reading = launch_result.quota[-1] if launch_result.quota else None
    refusal = launch_result.quota_refusal
    bits = []
    if reading is not None:
        for label, pct in (("5h", reading.five_hour_pct), ("7d", reading.seven_day_pct)):
            if pct is not None:
                # `:g` so 99.5 reads as 99.5% and not as a round 100% — the
                # difference between "nearly out" and "out".
                bits.append(f"{label} {pct:g}%")
        if reading.status:
            bits.insert(0, reading.status)
    elif refusal is not None:
        bits.append("quota")
    if refusal is not None and refusal.retry_after_s:
        bits.append(f"retry in {refusal.retry_after_s / 3600:.1f}h")
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


def catalogue_check(backend: Backend | None, route: Route, cwd: Path | None = None) -> tuple[bool, str]:
    """(ok, reason) for the cheap pass, with the agent's list as it reads it in `cwd`, the
    run's working directory (None: this process's). Unknown catalogue means "probe it"."""
    if backend is None:
        return True, f"no {route.agent} backend here; the probe decides"
    if not route.model:
        return True, "agent default model"
    catalogue = backend._catalogue_in(cwd if cwd is not None else Path.cwd())
    if catalogue is None:
        return True, f"{route.agent} lists no models; the probe decides"
    if route.model in catalogue:
        return True, "in catalogue"
    return False, f"not in the {route.agent} model list"


def probe(
    route: Route,
    backend: Backend,
    timeout_s: float,
    fallback: str | None = None,
    credential: Credential = AMBIENT,
    cwd: Path | None = None,
) -> RouteVerdict:
    """One minimal launch, shaped like the real one, stopped after `timeout_s`: the
    longest `timeout_s` of the kinds whose chain holds `route` (`_wanted_routes`).
    It runs in `cwd`, the run's working directory (None: this process's), as the run's
    tasks do: an agent reads its project's config and `.env` there.

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
            limits=Limits(timeout_s=timeout_s, max_turns=1),
            cwd=cwd if cwd is not None else Path.cwd(),
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


def _wanted_routes(configs: Mapping, routers: Mapping) -> dict[tuple[str, str, str], tuple[Route, float]]:
    """Distinct (agent, model, credential) routes this run will actually launch, by
    `Route.identity`, each with the longest `timeout_s` of the kinds whose chain holds it:
    the time its probe has.

    Per-Kind routers repeat the same pair for every kind that does not
    name its own model, so the union collapses to a handful of probes
    rather than one per kind. The kinds' own routes come first, then their hops.
    """
    out: dict[tuple[str, str, str], tuple[Route, float]] = {}

    def add(r: Route, timeout_s: float) -> None:
        held = out.get(r.identity)
        out[r.identity] = (r, timeout_s if held is None else max(held[1], timeout_s))

    for rc in configs.values():
        add(Route(agent=rc.agent, model=rc.model, credential=rc.credential), rc.timeout_s)
    for kind, rc in configs.items():
        router = routers.get(kind)
        for r in router.routes[1:] if router is not None else ():
            add(r, rc.timeout_s)
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


def _own_chain(backend: Backend, model: str, cwd: Path | None) -> str:
    """What the agent's own model-level chain does for `model`, launched in `cwd`.

    Only meaningful for an agent whose mechanism lives in its config
    rather than on argv, which today means omp: `retry.fallbackChains`
    is on by default but empty unless the operator filled it in, and an
    empty chain is a quota refusal walking past unimpeded. The preflight
    probes routes, not tasks, so `cwd` is the run's working directory: a
    task whose call names another directory gets omp's config of that one.
    """
    chains = backend.model_chains(cwd)
    if chains is None:
        return "not available"
    return chains.describe(model)


class DroppedRoute(RecordModel):
    """A route the preflight dropped: not in its agent's model list, or its probe did not
    complete. `kinds`: the kinds whose chain held it."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    agent: str
    model: str = Field(description="empty: the coding agent's default model")
    credential: str
    reason: str = Field(
        description="not in its coding agent's model list, or how its probe ended (`rate limited`, `timeout: ...`: no answer "
        "within the longest `timeout_s` of the kinds whose chain held it, ...)"
    )
    kinds: tuple[str, ...] = Field(description="the kinds whose chain held it")

    def __str__(self) -> str:
        return f"{Route(self.agent, self.model, self.credential)} ({self.reason})"


class Substitution(RecordModel):
    """A kind with no route left, run on the first route that answered (`substitute`)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: str
    from_agent: str
    from_model: str
    to_agent: str
    to_model: str


class KeptKind(RecordModel):
    """A kind with no route left, run as configured all the same (`substitute`), and why."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: str
    agent: str
    model: str
    reason: str


class PreflightRecord(RecordModel):
    """What a preflight did, as `run.json` records it (`preflight`): its policy, the routes
    it dropped, and, for each kind left with no route, its substitution, the kind kept
    as configured, or the kind that stopped the run (`stopped`)."""

    policy: PreflightPolicy = Field(description="`Pipeline(preflight=)`; `off`: no route was probed")
    dropped: list[DroppedRoute] = Field(default_factory=list)
    substituted: list[Substitution] = Field(default_factory=list)
    kept: list[KeptKind] = Field(default_factory=list)
    stopped: list[str] = Field(default_factory=list, description="the kinds with no route left that stopped the run (policy `stop`)")


class PreflightStopped(ContraagentError):
    """A kind has no route that answered the preflight, and the policy is `stop`: nothing
    was launched. The message names each such kind and why each of its routes was
    dropped; `record` is what the preflight did (`run.json` `preflight`)."""

    def __init__(self, record: PreflightRecord) -> None:
        lines = [f"preflight: {len(record.stopped)} kind(s) have no route that answered (preflight stop); nothing was launched"]
        for name in record.stopped:
            lines.append(f"  {name}: " + "; ".join(str(d) for d in record.dropped if name in d.kinds))
        super().__init__("\n".join(lines))
        self.record = record


def check_policy(policy: object, where: str) -> PreflightPolicy:
    """`policy` when it is a preflight policy; else `ValueError` naming `where` (the setting) and the policies."""
    if isinstance(policy, str) and policy in PREFLIGHT_POLICIES:
        return policy  # type: ignore[return-value]
    raise ValueError(f"{where} = {policy!r} is not one of {', '.join(PREFLIGHT_POLICIES)}")


def run_preflight(
    routers: Mapping,
    configs: Mapping,
    backends: Mapping[str, Backend],
    credentials: Mapping[str, Credential] | None = None,
    cap: int = DEFAULT_CAP,
    model_failover: bool = False,
    cwd: Path | None = None,
) -> dict[tuple[str, str, str], RouteVerdict]:
    """Check every route the run will use, cheapest first, launched in `cwd`, the run's
    working directory (None: this process's).

    Returns a verdict per route checked, by `Route.identity`: a route not in its
    agent's model list, or whose probe did not complete, is not `ok`. A route past
    `cap` has no verdict: its first task tells.
    """
    wanted = list(_wanted_routes(configs, routers).values())
    probes, skipped = wanted[:cap], wanted[cap:]
    if skipped:
        _logger.warning(f"[preflight] {len(skipped)} further route(s) not probed (cap {cap}); a bad one fails its first task instead")

    _logger.info(f"[preflight] 1/2 model catalogue: {len(probes)} route(s)")
    verdicts: dict[tuple[str, str, str], RouteVerdict] = {}
    for r, _ in probes:
        ok, why = catalogue_check(backends.get(r.agent), r, cwd)
        if not ok:
            verdicts[r.identity] = RouteVerdict(r, False, why)
            _logger.warning(f"[preflight]   {r}  DROPPED ({why})")
    if not verdicts:
        _logger.info(f"[preflight]   all {len(probes)} known to their agent")

    _logger.info("[preflight] 2/2 reachability")
    launched: list[tuple[Route, Backend, str | None, float]] = []
    for r, timeout_s in probes:
        if r.identity in verdicts:
            continue
        be = backends.get(r.agent)
        if be is None:
            verdicts[r.identity] = RouteVerdict(r, False, f"no {r.agent} backend in this run")
            _logger.warning(f"[preflight]   {r}  DROPPED (no backend)")
            continue
        launched.append((r, be, _native_chain(r, routers, be), timeout_s))

    def launch(one: tuple[Route, Backend, str | None, float]) -> RouteVerdict:
        r, be, native, timeout_s = one
        return probe(r, be, timeout_s, native, first_member(credentials or {}, r.credential) or AMBIENT, cwd)

    # The probes run at once, each in a copy of this context: each waits on its own provider,
    # so the preflight takes as long as its slowest probe.
    contexts = [contextvars.copy_context() for _ in launched]
    with ThreadPoolExecutor(max_workers=max(1, len(launched)), thread_name_prefix="preflight") as pool:
        answers = list(pool.map(lambda context, one: context.run(launch, one), contexts, launched))
    for (r, be, native, _), v in zip(launched, answers, strict=True):
        verdicts[r.identity] = v
        mark = "ok" if v.ok else f"DROPPED ({v.reason})"
        extra = f"  [{v.quota}]" if v.quota else ""
        if native:
            via = f"  (model chain: {native})"
        elif be.native_model_chain:
            # The agent owns its model-level failover, so what matters is
            # whether the operator configured it — and, if they asked
            # contraagent for it, that the request cannot be honoured here.
            own = _own_chain(be, r.model, cwd)
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
    return {r.identity: verdicts[r.identity] for r, _ in probes}


def apply_preflight(
    configs: dict,
    routers: Mapping,
    backends: Mapping[str, Backend],
    credentials: Mapping | None = None,
    *,
    policy: PreflightPolicy,
    model_failover: bool = False,
    cwd: Path | None = None,
) -> tuple[dict, PreflightRecord]:
    """Probe the routes of `configs` and `routers` in `cwd`, the run's working directory,
    drop the ones that cannot answer and rebuild each chain on the rest, then apply
    `policy` to each kind left with no route.

    Returns the router map and what was done. `substitute` mutates `configs` for the
    kinds it moves; `stop` raises `PreflightStopped`; `off` probes nothing and returns
    `routers` as they are.
    """
    record = PreflightRecord(policy=policy)
    if policy == "off":
        return dict(routers), record
    verdicts = run_preflight(routers, configs, backends, credentials or {}, model_failover=model_failover, cwd=cwd)

    def answered(r: Route) -> bool:
        v = verdicts.get(r.identity)
        return v is None or v.ok  # a route past the cap is not known to be dead

    out: dict = {}
    left: dict = {}  # kind -> its routes that were not dropped
    held: dict[tuple[str, str, str], list[str]] = {}  # route -> the kinds whose chain held it
    rebuilt: dict[str, list[str]] = {}
    for kind, rc in configs.items():
        router = routers.get(kind)
        # The kind's own route is what was probed for its chain's first (`_wanted_routes`).
        primary = Route(agent=rc.agent, model=rc.model, credential=rc.credential)
        routes = router.routes if router is not None else (primary,)
        probed = (primary, *routes[1:])
        for r in probed:
            held.setdefault(r.identity, []).append(kind_name(kind))
        left[kind] = kept = [r for r, p in zip(routes, probed, strict=True) if answered(p)]
        if router is None or not kept:
            continue
        if len(kept) == len(routes):
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
    record.dropped = [
        DroppedRoute(
            agent=v.route.agent, model=v.route.model, credential=v.route.credential, reason=v.reason, kinds=tuple(held.get(identity, ()))
        )
        for identity, v in verdicts.items()
        if not v.ok
    ]
    dead = [kind for kind in configs if not left[kind]]
    for kind in dead:
        _logger.warning(f"[preflight] {kind_name(kind)}: every route failed; no chain left")
    if policy == "stop":
        if dead:
            record.stopped = [kind_name(kind) for kind in dead]
            raise PreflightStopped(record)
        return out, record
    fallback = next((left[kind][0] for kind in configs if left[kind]), None)
    for kind in dead:
        rc = configs[kind]
        name = kind_name(kind)
        if fallback is None:
            record.kept.append(KeptKind(kind=name, agent=rc.agent, model=rc.model, reason="no route of the run answered"))
            continue
        if fallback.credential and fallback.credential != rc.credential:
            # Moving a kind onto another identity is the operator's call, never the preflight's.
            why = f"the first route that answered ({fallback}) runs as {fallback.credential}, not {rc.credential}"
            _logger.warning(f"[preflight] {name}: {why}; left as configured")
            record.kept.append(KeptKind(kind=name, agent=rc.agent, model=rc.model, reason=why))
            continue
        _logger.warning(f"[preflight] {name}: no route left; running on {fallback} instead of {rc.agent}/{rc.model}")
        record.substituted.append(
            Substitution(kind=name, from_agent=rc.agent, from_model=rc.model, to_agent=fallback.agent, to_model=fallback.model)
        )
        configs[kind] = dataclasses.replace(rc, agent=fallback.agent, model=fallback.model)
    return out, record
