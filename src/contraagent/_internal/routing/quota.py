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

Readings are what the coding agents reported (`QuotaReading`, a launch's
`quota`), newest per credential and account: those of recent runs, read
when the run starts, then each launch's as it ends. One credential may bill two
accounts (`ambient` is each coding agent's own login; a credential's token may be
replaced), so a hop is judged by the readings of the account it bills
(`Backend.account`): a reading of another account, an earlier token's, does not
rest it. A reading that names no account (one an older contraagent wrote) counts
for every account of its credential. A reading says nothing past its window's
reset (`five_hour_resets_at`, `seven_day_resets_at`; without one, past the
window's length after `observed_at`). A credential with no reading (a gateway,
an API key) never rests here: only its 429s and budgets stop it.

A rest by the quota rule lasts until the time the rule gives with its reason
(`("over the daily pace", tomorrow_17_jst)`): the credential rests to then, and the rule
is not asked again before it. A rule that gives a reason alone rests the credential while
the reading it judged stands: until the earliest reset among that reading's windows
(or, for a window that names none, its length after `observed_at`). Nothing launches on
a resting credential, so no newer reading arrives; past that time the stale reading no
longer counts, the credential does not rest, and the next launch brings a reading for
the rule to judge again. The rest records the reading (`Rest.reading`) and its end
(`Rest.until`).

`finishing_kinds` (the queue's) still launch on a resting credential for
`grace_s` after it began resting, as they do past a deadline.

Why a credential rests is a `Rest` (`dispatch.records`): a sentence for logs
(`Rest.text`) and the same as data for the monitor. `on_change("start" | "end", rest)`
is told when a credential begins and stops resting (`rests.jsonl`).

`QuotaRests` is one run's state, shared by every worker thread like a `Router`
and a `CredentialPool`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict

from contraagent._internal.backends.credentials import Credential, Pool
from contraagent._internal.dispatch.queue import GRACE_S
from contraagent._internal.dispatch.records import WINDOWS, QuotaReading, Rest, window_spec
from contraagent._internal.runs.times import parse_iso


class QuotaRule(Protocol):
    """A rule that rests a credential on its quota reading, beside the config's caps
    (`max_five_hour_pct`, `max_seven_day_pct`): `rule(credential, reading)`
    (`Pipeline(quota_rule=)`).

    `credential`: the credential's name, the `<name>` of its `[credentials.<name>]` table
    (`"ambient"` for the built-in one; a pool's member by its own name). `reading`: the
    latest `QuotaReading` its coding agent reported for it. It returns None when the
    credential may launch; a reason (`"5-hour usage past 85%"`) when it rests now, until
    the reading stops standing (the earliest reset among its windows); or the reason and the
    `datetime` the rest ends (one with no time zone is UTC). A resting credential is not
    launched on: its tasks take the next hop of their failover chain, or are deferred."""

    def __call__(self, credential: str, reading: QuotaReading, /) -> str | tuple[str, datetime] | None: ...


class AccountOf(Protocol):
    """`account(credential)`: the account a launch as credential `credential` (its name)
    bills now, as `Backend.account` gives it; '' when unknown."""

    def __call__(self, credential: str, /) -> str: ...


def _aware(t: datetime) -> datetime:
    """`t` with a time zone: UTC when it names none."""
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def stale_at(reading: QuotaReading) -> datetime | None:
    """When `reading` stops standing: the earliest reset among its windows, a window that
    names no reset standing for its length after `observed_at` (a window not in `WINDOWS`,
    the shortest's); None when it says neither."""
    observed = parse_iso(reading.observed_at)
    shortest = min(spec.length for spec in WINDOWS.values())
    ends: list[datetime] = []
    for name, w in reading.named_windows().items():
        resets = parse_iso(w.resets_at)
        if resets is not None:
            ends.append(resets)
        elif observed is not None:
            spec = window_spec(name)
            ends.append(observed + (spec.length if spec is not None else shortest))
    return min(ends) if ends else None


def reading_of(reading: QuotaReading) -> dict:
    """A reading as a rest records it: when it arrived and each window's utilization and reset."""
    windows = {k: w.model_dump(mode="json") for k, w in reading.named_windows().items()}
    return {"observed_at": reading.observed_at, "windows": windows}


class QuotaCap(BaseModel):
    """One credential's quota caps (`[credentials.<name>] max_five_hour_pct`, `max_seven_day_pct`):
    the utilization (%) of a window past which it rests; None for a window with no cap."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    credential: str
    five_hour_pct: float | None = None
    seven_day_pct: float | None = None


def caps_of(credentials: Mapping[str, Credential]) -> list[QuotaCap]:
    """The quota caps of each credential that has one. A pool's member with no cap of its
    own takes the pool's."""
    out: list[QuotaCap] = []
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
            out.append(QuotaCap(credential=name, **caps))
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
        credentials: Mapping[str, Credential],
        rule: QuotaRule | None = None,
        *,
        finishing_kinds: Iterable[str] = (),
        grace_s: float = GRACE_S,
        on_change: Callable[[str, Rest], None] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.credentials: dict[str, Credential] = dict(credentials)
        self.rule = rule
        self.finishing_kinds: frozenset[str] = frozenset(finishing_kinds)
        self.grace_s = grace_s
        self.on_change = on_change
        self._now = now
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: dict[tuple[str, str], QuotaReading] = {}  # by credential and account
        self._since: dict[tuple[str, str], float] = {}  # by credential and account: when it was first found resting
        self._resting: dict[tuple[str, str], Rest] = {}  # by credential and account: the rest it began with
        self._ruled: dict[tuple[str, str], tuple[Rest, datetime]] = {}  # rests the rule gave an end, and that end

    def observe(self, reading: QuotaReading) -> None:
        """A reading the coding agent reported for `reading.credential` and `reading.account`;
        the newest one of each account counts."""
        if not reading.credential:
            return
        key = (reading.credential, reading.account)
        with self._lock:
            old = self._latest.get(key)
            if old is None or (parse_iso(reading.observed_at) or datetime.max.replace(tzinfo=UTC)) >= (
                parse_iso(old.observed_at) or datetime.min.replace(tzinfo=UTC)
            ):
                self._latest[key] = reading

    def latest(self, name: str, account: str | None = None) -> QuotaReading | None:
        """The newest reading of credential `name` for `account`: of that account, or of none
        named. `account` '' or None (not known): the newest of any account."""
        with self._lock:
            found = [r for (n, a), r in self._latest.items() if n == name and (not account or a in (account, ""))]
        return max(found, key=lambda r: parse_iso(r.observed_at) or datetime.min.replace(tzinfo=UTC)) if found else None

    def rests(self, name: str, kind: str = "", account: AccountOf | None = None) -> list[Rest]:
        """Why credential `name` rests for a task of `kind` now: one `Rest`, or for a pool
        one per member when every member rests; empty when it does not rest. `account(name)`
        is the account a launch as that credential bills now (`Backend.account`); without
        it, the newest reading of any account counts."""
        cred = self.credentials.get(name)
        if isinstance(cred, Pool):
            why = [self._member_rest(m, cred, kind, account) for m in cred.members]
            return [w for w in why if w is not None] if why and all(why) else []
        one = self._member_rest(name, None, kind, account)
        return [one] if one is not None else []

    def reason(self, name: str, kind: str = "", account: AccountOf | None = None) -> str:
        """`rests` in one line; '' when it does not rest."""
        return "; ".join(r.text() for r in self.rests(name, kind, account))

    def resting_members(self, pool: str, kind: str = "", account: AccountOf | None = None) -> set[str]:
        """The members of pool `pool` that rest for a task of `kind` now."""
        cred = self.credentials.get(pool)
        if not isinstance(cred, Pool):
            return set()
        return {m for m in cred.members if self._member_rest(m, cred, kind, account) is not None}

    def _member_rest(self, name: str, pool: Pool | None, kind: str, account: AccountOf | None) -> Rest | None:
        with self._lock:
            read = any(n == name for n, _ in self._latest)
        acct = account(name) if account is not None and read else ""  # asked only of a credential with readings
        reading = self.latest(name, acct)
        key = (name, acct)
        rest = None
        with self._lock:
            held = self._ruled.get(key)
            if held is not None and self._now() >= held[1]:
                del self._ruled[key]
                held = None
        if held is not None:  # the rule said until when: it is not asked again before
            rest = held[0]
        elif reading is not None:
            rest = self._capped(name, reading, pool)
            if rest is None and self.rule is not None:
                ends = stale_at(reading)
                # A reading that no longer stands is no ground for a rest: the next launch brings a new one.
                if ends is None or self._now() < ends:
                    ruled = self.rule(name, reading)
                    said, given = ruled if isinstance(ruled, tuple) else (ruled, None)
                    if said:
                        given = _aware(given) if given is not None else None
                        end = given or ends
                        until = end.isoformat() if end is not None else ""
                        rest = Rest(credential=name, rule=str(said), until=until, account=reading.account, reading=reading_of(reading))
                        if given is not None and self._now() < given:
                            with self._lock:
                                self._ruled[key] = (rest, given)
        event: tuple[str, Rest] | None = None
        since = 0.0
        with self._lock:
            if rest is None:
                self._since.pop(key, None)
                ended = self._resting.pop(key, None)
                event = ("end", ended) if ended is not None else None
            else:
                since = self._since.setdefault(key, self._clock())
                if key not in self._resting:
                    self._resting[key] = rest
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

    def _capped(self, name: str, reading: QuotaReading, pool: Pool | None) -> Rest | None:
        cred = self.credentials.get(name)
        now = self._now()
        for window, spec in WINDOWS.items():
            length = spec.length
            cap = getattr(cred, f"max_{window}_pct", None) if cred is not None else None
            if cap is None and pool is not None:
                cap = getattr(pool, f"max_{window}_pct", None)
            pct = getattr(reading, f"{window}_pct")
            if cap is None or pct is None or pct < cap:
                continue
            resets = parse_iso(getattr(reading, f"{window}_resets_at"))
            observed = parse_iso(reading.observed_at)
            if resets is not None and resets <= now:
                continue  # the window this reading describes is over
            if resets is None and observed is not None and now - observed > length:
                continue
            until = resets if resets is not None else (observed + length if observed is not None else None)
            ends = until.isoformat() if until is not None else ""
            return Rest(credential=name, window=window, pct=float(pct), cap=float(cap), until=ends, account=reading.account)
        return None
