"""Model failover: which (coding agent, model) a task runs on right now.

A provider quota is a run-length event, not a per-launch event. When
opencode-go answered `429 Go usage limit exceeded retry-after-ms=313534000`
mid-run, every later launch on that model died in ~2s: 644 tasks, zero
findings, and nothing in the journal said why. The remedy is not a retry
— the same model will keep refusing for days — it is a different route,
then a way back when the first one recovers.

So the router is a breaker, not a queue:

    primary ──429──▶ fallback[0] ──429──▶ fallback[1] ──429──▶ exhausted
       ▲                 │                    │
       └───── probe ok ──┴──── probe ok ──────┘

The breaker opens on the first 429 and stays open — the provider said
*days*, so a run that stayed on the primary would burn every remaining
task. Recovery is a half-open probe: once the provider's own stated
cool-off has elapsed, one task goes back to the primary; a success closes
the breaker for good, a 429 re-opens it and pushes the next probe out.
Providers that state no cool-off fall back to `probe_interval_s`, and each
further failure on the fallback widens that gap.

Exhausted means exhausted: with no route left, `pick()` returns None and
the caller lets the 429 surface as an error, which is the honest outcome
— the user asked for exactly that rather than a silent stall.
"""

from __future__ import annotations

import threading
import time
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from contraagent._internal.backends import known_agents as registered_agents
from contraagent._internal.backends.launch import Stop
from contraagent._internal.errors import did_you_mean
from contraagent._internal.routing.config import ConfigError

#: The stops a task fails over on: every stop but `completed` and the two no hop can fix
#: (`invalid_input`, `credential_mismatch`). A failover hop's `stops` are some of these.
FAILOVER_STOPS: tuple[str, ...] = tuple(s.value for s in Stop if s not in (Stop.COMPLETED, Stop.INVALID_INPUT, Stop.CREDENTIAL_MISMATCH))


@dataclass(frozen=True)
class Route:
    """One (coding agent, model, credential) the run may use. `credential` names a
    `[credentials.<name>]`; empty means the kind's own. `stops`: the stops of an earlier
    hop's launch a failover hop is for (some of `FAILOVER_STOPS`); empty, every one. A task
    whose launch ends on another stop passes the hop over. The primary is where every task
    starts, so its own `stops` are not read; they are not part of the route's identity."""

    agent: str
    model: str
    credential: str = ""
    stops: tuple[str, ...] = field(default=(), compare=False)

    def takes(self, stop: str) -> bool:
        """Whether a task whose launch ended on `stop` may fail over to this hop."""
        return not self.stops or stop in self.stops

    def __str__(self) -> str:
        base = f"{self.agent}/{self.model}" if self.model else self.agent
        return f"{base}@{self.credential}" if self.credential not in ("", "ambient") else base

    def label(self, hop: int, total: int) -> str:
        """`hop 2/3 omp/...` — the form every log and journal line uses.

        A bare `omp/model` cannot answer "which hop ran this?" once a run
        has failed over, and the ordinal is what makes the chain's order
        readable at the point of use rather than only in the config file.
        """
        return f"hop {hop}/{total} {self}"

    @property
    def identity(self) -> tuple[str, str, str]:
        """(agent, model, credential): two routes with the same identity are one hop."""
        return (self.agent, self.model, self.credential)


def on_credential(routes: Sequence[Route], credential: str) -> tuple[Route, ...]:
    """`routes` in order, each on `credential` (a task call's, `AgentTask.__call__`): a route
    that becomes the same as one before it is dropped, so no hop repeats another."""
    out: dict[tuple[str, str], Route] = {}
    for r in routes:
        out.setdefault((r.agent, r.model), replace(r, credential=credential))
    return tuple(out.values())


def parse_chain(entries, where: str, known_agents: tuple[str, ...] | None = None) -> tuple[Route, ...]:
    """Validate one ordered chain of `[[...fallbacks]]` tables.

    **The block order IS the failover order**: the first block is hop 2
    (hop 1 is whatever the chain's primary is), the second is hop 3, and
    so on. A separate order key would only be a second source of
    truth free to disagree with the order the operator can see. What is
    checked instead is that the chain has no repeats — a duplicated
    (agent, model, credential) would give one hop two ordinals and make
    "hop 2" ambiguous.

    `where` names the file and table in every error, so a message about
    hop 4 says which chain hop 4 belongs to.
    """
    if not entries:
        return ()
    if known_agents is None:
        # An unknown name is a config error, not a runtime surprise.
        known_agents = registered_agents()
    out: list[Route] = []
    for i, entry in enumerate(entries):
        hop = f"block {i + 1} (hop {i + 2})"
        if not isinstance(entry, dict):
            raise ValueError(f"{where} {hop} must be a table")
        agent = str(entry.get("agent") or "").strip()
        model = str(entry.get("model") or "").strip()
        if not agent:
            raise ValueError(f"{where} {hop} is missing 'agent'")
        if agent not in known_agents:
            raise ValueError(
                f"{where} {hop} names unknown agent {agent!r}{did_you_mean(agent, known_agents)}; known: {', '.join(known_agents)}"
            )
        if not model:
            raise ValueError(f"{where} {hop} is missing 'model'")
        out.append(Route(agent=agent, model=model, credential=str(entry.get("credential") or "").strip(), stops=_stops(entry, where, hop)))
    seen: dict[tuple[str, str, str], int] = {}
    for i, r in enumerate(out):
        if r.identity in seen:
            raise ValueError(
                f"{where} block {i + 1} (hop {i + 2}) repeats block {seen[r.identity] + 1} ({r}); failover order would be ambiguous"
            )
        seen[r.identity] = i
    return tuple(out)


def _stops(entry: dict, where: str, hop: str) -> tuple[str, ...]:
    """A block's `stops`: a non-empty list of `FAILOVER_STOPS`, in its order without repeats;
    () when the block names none."""
    if "stops" not in entry:
        return ()
    stops = entry["stops"]
    if not isinstance(stops, list) or not stops or not all(isinstance(s, str) for s in stops):
        raise ValueError(f'{where} {hop}: stops must be a non-empty list of stops, such as ["rate_limited", "api_error"]')
    for s in stops:
        if s not in FAILOVER_STOPS:
            known = ", ".join(FAILOVER_STOPS)
            raise ValueError(
                f"{where} {hop}: stops names {s!r}{did_you_mean(s, FAILOVER_STOPS)}, not a stop a task fails over on; known: {known}"
            )
    return tuple(dict.fromkeys(stops))


def load_fallbacks(path: Path | str) -> tuple[Route, ...]:
    """The `[[defaults.fallbacks]]` chain of a TOML file.

    An absent table or an empty array means "no failover". A missing or
    unparsable file, and a malformed entry, are hard errors: silently
    dropping a hop the operator wrote would fail later, mid-run, with a
    429 instead of a config complaint. Both raise `ConfigError`.
    """
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    defaults = raw.get("defaults")
    chain = defaults.get("fallbacks") if isinstance(defaults, dict) else None
    try:
        return parse_chain(chain, f"{path} [[defaults.fallbacks]]:")
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def _with_stops(route: Route, label: str, index: int) -> str:
    """`label`, and the stops of a failover hop for some stops only."""
    return f"{label} on {', '.join(route.stops)}" if index and route.stops else label


class Router:
    """Thread-safe active-route selection for one run.

    One router per run, shared by every worker thread. The driver fans
    tasks out four-wide, so two threads can hit a 429 at the same instant;
    both must see the same next hop, or one launch goes to a route the
    breaker just moved off. Every transition is therefore one critical
    section over (index, probe deadline, exhausted).
    """

    def __init__(
        self,
        primary: Route,
        fallbacks: tuple[Route, ...] = (),
        probe_interval_s: float = 900.0,
        max_probe_interval_s: float = 7200.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # A fallback identical to the primary is a no-op hop: drop it here
        # rather than discovering it as a wasted 1800s launch.
        self.routes: tuple[Route, ...] = (primary,) + tuple(f for f in fallbacks if f.identity != primary.identity)
        self.primary = primary
        self.probe_interval_s = probe_interval_s
        self.max_probe_interval_s = max_probe_interval_s
        self._clock = clock
        self._lock = threading.Lock()
        self._index = 0
        self._probe_at = 0.0
        self._interval = probe_interval_s
        self._exhausted = False
        # When the breaker last moved off a hop (`clock` time): a launch that began
        # before it says nothing about whether the limit has passed.
        self._opened_at = float("-inf")
        self._switches: list[tuple[str, str]] = []

    def on_credential(self, credential: str) -> Router:
        """A breaker of its own over this chain's routes, each on `credential` (`on_credential`):
        a 429 as one identity says nothing about another's, so it starts closed."""
        routes = on_credential(self.routes, credential)
        return Router(routes[0], routes[1:], self.probe_interval_s, self.max_probe_interval_s, self._clock)

    def _index_of(self, route: Route) -> int | None:
        return next((i for i, r in enumerate(self.routes) if r.identity == route.identity), None)

    def hop_of(self, route: Route) -> int:
        """1-based position of `route` in the failover chain, 0 if unknown."""
        idx = self._index_of(route)
        return 0 if idx is None else idx + 1

    def label_of(self, route: Route) -> str:
        """`hop 2/3 omp/...` for any route in this chain."""
        return route.label(self.hop_of(route), len(self.routes))

    def next_route_after(self, route: Route, stop: str = "") -> Route | None:
        """The first hop after `route` in chain order that is for `stop` (`Route.takes`;
        any hop with no `stop`), or None when there is none.

        Stateless on purpose: a per-task walk (a safeguard refusal is a
        property of the content, not of the provider) must not move the
        shared index, the exhaustion flag, or the probe timer that
        `rate_limited` maintains for every other task.
        """
        idx = self._index_of(route)
        if idx is None:
            return None
        return next((r for r in self.routes[idx + 1 :] if not stop or r.takes(stop)), None)

    def same_agent_after(self, route: Route) -> list[Route]:
        """Later hops on the same coding agent, in order.

        These are the model-level fallovers, and they belong to the agent
        when it has a mechanism for them: Claude Code's `--fallback-model`
        tries them inside one launch, so the task is not restarted and
        the Router never sees the refusal. An agent without one — omp has
        no equivalent flag — gets an empty list here and the Router walks
        the whole chain itself.
        """
        idx = self._index_of(route)
        if idx is None:
            return []
        # Same agent *and* same credential: the agent's own flag cannot switch identity. A hop
        # for some stops only is the Router's: the agent's flag would take it on any.
        return [r for r in self.routes[idx + 1 :] if r.agent == route.agent and r.credential == route.credential and not r.stops]

    def other_agents_after(self, route: Route) -> list[Route]:
        """Later hops that change coding agent. Always the Router's."""
        idx = self._index_of(route)
        if idx is None:
            return []
        return [r for r in self.routes[idx + 1 :] if r.agent != route.agent]

    def chain(self) -> str:
        """The whole failover order on one line, primary first; a hop for some stops only
        names them (`hop 2/2 omp/m2 on rate_limited, api_error`)."""
        return " -> ".join(_with_stops(r, r.label(i + 1, len(self.routes)), i) for i, r in enumerate(self.routes))

    # --- selection -------------------------------------------------------

    def pick(self) -> Route | None:
        """The route the next task should run on, or None when exhausted.

        While the breaker is open on a fallback and the cool-off has
        elapsed, this returns the primary — that single task is the probe.
        If it 429s, `rate_limited` re-opens the breaker; if it lands, the
        run is back on the primary for good.
        """
        with self._lock:
            if self._exhausted:
                return None
            if self._index == 0:
                return self.routes[0]
            if self._clock() >= self._probe_at:
                return self.routes[0]
            return self.routes[self._index]

    def active(self) -> Route | None:
        """The route in force right now, ignoring any due probe."""
        with self._lock:
            if self._exhausted:
                return None
            return self.routes[self._index]

    def now(self) -> float:
        """The router's clock: pass it as `started` to `succeeded` for a launch begun now."""
        return self._clock()

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return self._exhausted

    # --- transitions -----------------------------------------------------

    def rate_limited(self, route: Route | None, retry_after_s: float | None = None) -> str:
        """Record a 429 on `route`; return the route the next task uses.

        A 429 on the primary opens the breaker to fallback[0]. A 429 on a
        fallback that was only being probed means the primary is still
        down: stay on the fallback, never bounce back to a route we just
        learned is refusing. Otherwise advance one hop, or exhaust.
        """
        now = self._clock()
        with self._lock:
            probing = self._index != 0 and route is not None and route.identity == self.routes[0].identity
            if probing and self._index > 0:
                # The half-open probe failed. Hold the current hop and
                # schedule the next attempt; do not consume a fallback.
                self._probe_at = now + self._next_interval(retry_after_s)
                return str(self.routes[self._index])
            if route is not None and route.identity != self.routes[0].identity:
                # A fallback also refused: keep walking the chain.
                idx = self._index_of(route)
                self._index = self._index if idx is None else idx
            nxt = next((i for i in range(self._index + 1, len(self.routes)) if self.routes[i].takes(Stop.RATE_LIMITED.value)), None)
            if nxt is None:
                self._exhausted = True
                return ""
            here, self._index = self._index, nxt
            self._opened_at = now
            self._interval = self.probe_interval_s
            self._probe_at = now + self._interval
            n = len(self.routes)
            self._switches.append((self.routes[here].label(here + 1, n), self.routes[self._index].label(self._index + 1, n)))
            return self.routes[self._index].label(self._index + 1, n)

    def succeeded(self, route: Route | None, started: float | None = None) -> None:
        """A launch landed. On a probe, that closes the breaker. `started` (`now()` when the
        launch began): a launch that began before the breaker opened is no probe, so its
        success, which says nothing of the limit since, leaves the breaker as it is."""
        with self._lock:
            if started is not None and started < self._opened_at:
                return
            if route is not None and route.identity == self.routes[0].identity and self._index != 0:
                n = len(self.routes)
                self._switches.append((self.routes[0].label(self._index, n), self.routes[0].label(1, n) + " (primary recovered)"))
                self._index = 0
                self._interval = self.probe_interval_s
                self._probe_at = 0.0
            elif self._index == 0:
                self._interval = self.probe_interval_s
                self._probe_at = 0.0

    def _next_interval(self, retry_after_s: float | None) -> float:
        """Cool-off for the next primary probe, never shorter than the last.

        The provider's own number wins when it is longer — a quota that
        resets in three days must not be re-probed every fifteen minutes.
        A shorter provider claim is floored at the growing backoff, so a
        provider answering `retry-after-ms=1000` for a weekly quota cannot
        talk the router into a probe storm.
        """
        base = min(max(self._interval * 2, self.probe_interval_s), self.max_probe_interval_s)
        self._interval = base
        if retry_after_s:
            return max(base, min(retry_after_s, self.max_probe_interval_s))
        return base

    # --- visibility ------------------------------------------------------

    def describe(self) -> str:
        """One line for the log: current hop and the hops left after it."""
        with self._lock:
            n = len(self.routes)
            if self._exhausted:
                return f"exhausted after hop {n}/{n}"
            here = self.routes[self._index].label(self._index + 1, n)
            if self._index == 0:
                rest = " -> ".join(hop.label(i + 2, n) for i, hop in enumerate(self.routes[1:]) if hop.takes(Stop.RATE_LIMITED.value))
                return f"{here} primary; on 429: {rest or 'no hop'}"
            left = n - self._index - 1
            tail = f"; then {left} more" if left else "; last hop"
            return f"{here} fallback{tail}"

    def history(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self._switches)
