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

`QuotaRests` is one run's state, shared by every worker thread like a `Router`
and a `CredentialPool`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta

from contraagent.backends.credentials import CredentialBase, Pool
from contraagent.backends.launch import RateLimit

#: `quota_rule(credential, reading)`: a reason the credential rests now, or None.
QuotaRule = Callable[[str, RateLimit], "str | None"]

#: How long a reading of each window stands when it names no reset.
_WINDOWS = (("five_hour", "5-hour", timedelta(hours=5)), ("seven_day", "weekly", timedelta(days=7)))


def _time(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


class QuotaRests:
    """The credentials of one run that rest, and why. Safe from worker threads.

    `credentials`: the run's, by name (`RoutingPlan.credentials`). `rule`: a domain's
    own `quota_rule`. `finishing_kinds`, `grace_s`: the queue's. `now` (wall clock, for
    resets) and `clock` (monotonic, for the grace window) are for tests."""

    def __init__(
        self,
        credentials: Mapping[str, CredentialBase],
        rule: QuotaRule | None = None,
        *,
        finishing_kinds: Iterable[str] = (),
        grace_s: float = 900.0,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.credentials = dict(credentials)
        self.rule = rule
        self.finishing_kinds = frozenset(finishing_kinds)
        self.grace_s = grace_s
        self._now = now
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: dict[str, RateLimit] = {}
        self._since: dict[str, float] = {}  # by credential: when it was first found resting

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

    def reason(self, name: str, kind: str = "") -> str:
        """Why credential `name` rests for a task of `kind` now; '' when it does not.
        A pool rests when every member does."""
        cred = self.credentials.get(name)
        if isinstance(cred, Pool):
            why = [self._member_reason(m, cred, kind) for m in cred.members]
            return "; ".join(why) if why and all(why) else ""
        return self._member_reason(name, None, kind)

    def resting_members(self, pool: str, kind: str = "") -> set[str]:
        """The members of pool `pool` that rest for a task of `kind` now."""
        cred = self.credentials.get(pool)
        if not isinstance(cred, Pool):
            return set()
        return {m for m in cred.members if self._member_reason(m, cred, kind)}

    def _member_reason(self, name: str, pool: Pool | None, kind: str) -> str:
        reading = self.latest(name)
        if reading is None:
            return ""
        why = self._capped(name, reading, pool)
        if not why and self.rule is not None:
            ruled = self.rule(name, reading)
            why = f"{name} rests: {ruled}" if ruled else ""
        with self._lock:
            if not why:
                self._since.pop(name, None)
                return ""
            since = self._since.setdefault(name, self._clock())
        if kind in self.finishing_kinds and self._clock() - since < self.grace_s:
            return ""
        return why

    def _capped(self, name: str, reading: RateLimit, pool: Pool | None) -> str:
        cred = self.credentials.get(name)
        now = self._now()
        for window, words, length in _WINDOWS:
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
            return f"{name} rests: {words} usage {pct:.0f}%, max {cap:g}%"
        return ""
