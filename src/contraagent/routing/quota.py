"""Quota rests: which credentials a run does not launch on now, because of their quota.

A subscription's utilization belongs to the account, not to a task: every task
that launches as the credential spends from the same 5-hour and weekly windows.
So a cap is the credential's (`[credentials.<name>] max_five_hour_pct`,
`max_seven_day_pct`), and so is a domain's own rule (`Pipeline(quota_rule=)`).
A credential past one **rests**: no task launches as it until the window the
reading names resets. The run goes on elsewhere, the way it does after a 429:

* a pool skips its resting members;
* the runner skips a hop whose credential rests, without launching it, and
  takes the next hop of the kind's failover chain (a gateway, an API key);
* a task with no hop left is deferred at once (`AgentRunner.deferral`), not
  failed: nothing was launched and nothing was spent.

Readings are what the coding agents reported (`RateLimit`, a launch's
`rate_limits`), newest per credential: those of recent runs, read when the run
starts, then each launch's as it ends. A reading says nothing past its window's
reset (`five_hour_resets_at`, `seven_day_resets_at`; without one, past the
window's length after `observed_at`). A credential with no reading (a gateway,
an API key) never rests here: only its 429s and budgets stop it.

`finishing_kinds` (the queue's) still launch on a resting credential for
`grace_s` after it began resting, as they do past a deadline.

Why a credential rests is a `Rest`: a sentence for logs (`Rest.text`) and the
same as data for the monitor (`Rest.to_dict`). `on_change("start" | "end", rest)`
is told when a credential begins and stops resting (`rests.jsonl`).

`QuotaRests` is one run's state, shared by every worker thread like a `Router`
and a `CredentialPool`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from contraagent.backends.credentials import CredentialBase, Pool
from contraagent.backends.launch import RateLimit

#: `quota_rule(credential, reading)`: a reason the credential rests now, or None.
QuotaRule = Callable[[str, RateLimit], "str | None"]

#: The two windows of a subscription: the name a cap and a reading give each, its name in
#: a sentence, and how long a reading of it stands when it names no reset.
WINDOWS = ("five_hour", "seven_day")
_WINDOWS = (("five_hour", "5-hour", timedelta(hours=5)), ("seven_day", "weekly", timedelta(days=7)))


def _time(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Rest:
    """Why credential `credential` rests: past a cap of one window (`window`, its reading
    `pct` and its cap `cap`), or by the quota rule (`rule`, what it said). `until`: when the
    window resets (ISO 8601); '' when unknown (a rule's rest lasts while the rule says so)."""

    credential: str
    window: str = ""
    pct: float | None = None
    cap: float | None = None
    rule: str = ""
    until: str = ""

    def text(self) -> str:
        """The rest in one line, for logs and the CLI: `personal rests: 5-hour usage 93%, max 90%`."""
        if self.rule:
            return f"{self.credential} rests: {self.rule}"
        words = dict((w, s) for w, s, _ in _WINDOWS).get(self.window, self.window)
        return f"{self.credential} rests: {words} usage {self.pct or 0:.0f}%, max {self.cap or 0:g}%"

    def to_dict(self) -> dict:
        return asdict(self)


def caps_of(credentials: Mapping[str, CredentialBase]) -> dict[str, dict[str, float]]:
    """Each credential's quota caps that are set, by name: `{"personal": {"five_hour_pct": 90}}`.
    A pool's member with no cap of its own takes the pool's."""
    out: dict[str, dict[str, float]] = {}
    pools = [c for c in credentials.values() if isinstance(c, Pool)]
    for name, cred in credentials.items():
        caps: dict[str, float] = {}
        for window in WINDOWS:
            cap = getattr(cred, f"max_{window}_pct", None)
            if cap is None:
                cap = next((getattr(p, f"max_{window}_pct", None) for p in pools if name in p.members), None)
            if cap is not None:
                caps[f"{window}_pct"] = float(cap)
        if caps:
            out[name] = caps
    return out


class QuotaRests:
    """The credentials of one run that rest, and why. Safe from worker threads.

    `credentials`: the run's, by name (`RoutingPlan.credentials`). `rule`: a domain's
    own `quota_rule`. `finishing_kinds`, `grace_s`: the queue's. `on_change(event, rest)`:
    told `start` when a credential begins resting, `end` (with the rest that ended) when
    it is found not resting again. `now` (wall clock, for resets) and `clock`
    (monotonic, for the grace window) are for tests."""

    def __init__(
        self,
        credentials: Mapping[str, CredentialBase],
        rule: QuotaRule | None = None,
        *,
        finishing_kinds: Iterable[str] = (),
        grace_s: float = 900.0,
        on_change: Callable[[str, Rest], None] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.credentials = dict(credentials)
        self.rule = rule
        self.finishing_kinds = frozenset(finishing_kinds)
        self.grace_s = grace_s
        self.on_change = on_change
        self._now = now
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: dict[str, RateLimit] = {}
        self._since: dict[str, float] = {}  # by credential: when it was first found resting
        self._resting: dict[str, Rest] = {}  # by credential: the rest it began with

    def observe(self, reading: RateLimit) -> None:
        """A reading the coding agent reported for `reading.credential`; the newest one counts."""
        if not reading.credential:
            return
        with self._lock:
            old = self._latest.get(reading.credential)
            if old is None or (_time(reading.observed_at) or datetime.max.replace(tzinfo=UTC)) >= (
                _time(old.observed_at) or datetime.min.replace(tzinfo=UTC)
            ):
                self._latest[reading.credential] = reading

    def latest(self, name: str) -> RateLimit | None:
        with self._lock:
            return self._latest.get(name)

    def rests(self, name: str, kind: str = "") -> list[Rest]:
        """Why credential `name` rests for a task of `kind` now: one `Rest`, or for a pool
        one per member when every member rests; empty when it does not rest."""
        cred = self.credentials.get(name)
        if isinstance(cred, Pool):
            why = [self._member_rest(m, cred, kind) for m in cred.members]
            return [w for w in why if w is not None] if why and all(why) else []
        one = self._member_rest(name, None, kind)
        return [one] if one is not None else []

    def reason(self, name: str, kind: str = "") -> str:
        """`rests` in one line; '' when it does not rest."""
        return "; ".join(r.text() for r in self.rests(name, kind))

    def resting_members(self, pool: str, kind: str = "") -> set[str]:
        """The members of pool `pool` that rest for a task of `kind` now."""
        cred = self.credentials.get(pool)
        if not isinstance(cred, Pool):
            return set()
        return {m for m in cred.members if self._member_rest(m, cred, kind) is not None}

    def _member_rest(self, name: str, pool: Pool | None, kind: str) -> Rest | None:
        reading = self.latest(name)
        rest = None
        if reading is not None:
            rest = self._capped(name, reading, pool)
            if rest is None and self.rule is not None:
                ruled = self.rule(name, reading)
                rest = Rest(name, rule=str(ruled)) if ruled else None
        event: tuple[str, Rest] | None = None
        since = 0.0
        with self._lock:
            if rest is None:
                self._since.pop(name, None)
                ended = self._resting.pop(name, None)
                event = ("end", ended) if ended is not None else None
            else:
                since = self._since.setdefault(name, self._clock())
                if name not in self._resting:
                    self._resting[name] = rest
                    event = ("start", rest)
        if event is not None and self.on_change is not None:
            try:
                self.on_change(*event)
            except Exception:  # a record that cannot be written must not stop a launch
                pass
        if rest is None:
            return None
        if kind in self.finishing_kinds and self._clock() - since < self.grace_s:
            return None
        return rest

    def _capped(self, name: str, reading: RateLimit, pool: Pool | None) -> Rest | None:
        cred = self.credentials.get(name)
        now = self._now()
        for window, _, length in _WINDOWS:
            cap = getattr(cred, f"max_{window}_pct", None) if cred is not None else None
            if cap is None and pool is not None:
                cap = getattr(pool, f"max_{window}_pct", None)
            pct = getattr(reading, f"{window}_pct")
            if cap is None or pct is None or pct < cap:
                continue
            resets = _time(getattr(reading, f"{window}_resets_at"))
            observed = _time(reading.observed_at)
            if resets is not None and resets <= now:
                continue  # the window this reading describes is over
            if resets is None and observed is not None and now - observed > length:
                continue
            until = resets if resets is not None else (observed + length if observed is not None else None)
            return Rest(name, window=window, pct=float(pct), cap=float(cap), until=until.isoformat() if until is not None else "")
        return None
