"""Credential pools at run time: which member the next launch uses.

A `Pool` credential (`[credentials.<name>] type = "pool"`) names several
credentials used as one. `CredentialPool` is its state for one run, shared by
every worker thread like a `Router`: which member is next, and which are
cooling down after a 429. A cool-down is per member *and model*: a quota can be
per model (a weekly Opus limit), and when it is account-wide the next model
answers 429 at once and cools down too.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Collection, Mapping

from contraagent._internal.backends.credentials import Credential, Pool


class CredentialPool:
    def __init__(self, pool: Pool, members: list[Credential], clock: Callable[[], float] = time.monotonic) -> None:
        self.pool = pool
        self.members = list(members)
        self._clock = clock
        self._lock = threading.Lock()
        self._next = 0
        self._cooling_until: dict[tuple[str, str], float] = {}

    @property
    def name(self) -> str:
        return self.pool.label

    def pick(self, model: str = "", exclude: Collection[str] = ()) -> Credential | None:
        """The member the next launch of `model` uses, or None when every one is cooling or excluded."""
        now = self._clock()
        with self._lock:
            n = len(self.members)
            start = self._next if self.pool.strategy == "round_robin" else 0
            for i in range(n):
                member = self.members[(start + i) % n]
                if member.label in exclude or self._cooling_until.get((member.label, model), 0.0) > now:
                    continue
                if self.pool.strategy == "round_robin":
                    self._next = (start + i + 1) % n
                return member
            return None

    def rate_limited(self, member: Credential, model: str = "", retry_after_s: float | None = None) -> None:
        """`member` answered 429 on `model`: rest it for the provider's stated time, or the pool's cooldown."""
        wait = retry_after_s or self.pool.cooldown_s
        with self._lock:
            self._cooling_until[(member.label, model)] = self._clock() + wait

    def describe(self) -> str:
        now = self._clock()
        with self._lock:
            cooling = {(m, mod): until for (m, mod), until in self._cooling_until.items() if until > now}
            parts = [
                m.label
                + "".join(f" (cooling on {mod or 'default'} {until - now:.0f}s)" for (who, mod), until in cooling.items() if who == m.label)
                for m in self.members
            ]
        return f"{self.name} [{self.pool.strategy}]: " + ", ".join(parts)


def pools_of(credentials: Mapping[str, Credential], clock: Callable[[], float] = time.monotonic) -> dict[str, CredentialPool]:
    """A `CredentialPool` for every pool in `credentials`."""
    return {name: CredentialPool(c, [credentials[m] for m in c.members], clock) for name, c in credentials.items() if isinstance(c, Pool)}


def first_member(credentials: Mapping[str, Credential], name: str) -> Credential | None:
    """`name`'s credential, or a pool's first member: what a single probe launches as."""
    c = credentials.get(name)
    if isinstance(c, Pool):
        return credentials.get(c.members[0])
    return c
