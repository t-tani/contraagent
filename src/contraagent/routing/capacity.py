"""Claim capacities sized by the host: a `PerTask` entry of `claim_capacity` as the
`ClaimCapacity` the queue asks each time it tries to start a task that claims the name.

`HostCapacity` is the host's room, shared by every `PerTask` name of one queue: its free
memory, read from `/proc/meminfo`, less what tasks started in the last `STARTUP_S`
will still take, and its usable cores.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping

from contraagent import procfs
from contraagent.dispatch import ClaimCapacity
from contraagent.routing.config import PerTask

#: How long a started task's `memory_mb` counts against the free memory: a local server
#: takes its memory in its first seconds, before `MemAvailable` shows it.
STARTUP_S = 30.0

#: How long one reading of `/proc/meminfo` serves: one pass of the queue reads it once.
READ_EVERY_S = 0.5


class HostCapacity:
    """The host's room for tasks with a `PerTask` claim capacity: one per queue.

    `mem_available_mb()`: the free memory in MB, None where it is not known (not Linux);
    `cores`: the usable cores; `clock`: seconds, monotonic. Each is given in a test."""

    def __init__(
        self,
        *,
        mem_available_mb: Callable[[], int | None] = procfs.read_mem_available_mb,
        cores: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._read = mem_available_mb
        self.cores = cores if cores is not None else procfs.usable_cores()
        self._clock = clock
        self._starts: list[tuple[float, int]] = []  # (when, memory_mb) of each task started
        self._reading: tuple[float, int | None] | None = None  # (when, MB)

    def free_mb(self) -> int | None:
        """Free memory in MB: the latest reading, less `memory_mb` of each task started in
        the last `STARTUP_S`; None where the host does not report it."""
        now = self._clock()
        if self._reading is None or now - self._reading[0] >= READ_EVERY_S:
            self._reading = (now, self._read())
        available = self._reading[1]
        if available is None:
            return None
        self._starts = [(t, mb) for t, mb in self._starts if now - t < STARTUP_S]
        return available - sum(mb for _, mb in self._starts)

    def started(self, need: PerTask) -> None:
        if need.memory_mb:
            self._starts.append((self._clock(), need.memory_mb))

    def capacity(self, need: PerTask) -> ClaimCapacity:
        return _Sized(self, need)


class _Sized:
    """One `PerTask` entry over the host's room (`PerTask` has the rule)."""

    def __init__(self, host: HostCapacity, need: PerTask) -> None:
        self.host = host
        self.need = need

    def allowed(self, held: int) -> int:
        limits: list[int] = []
        if self.need.memory_mb:
            free = self.host.free_mb()
            if free is not None:
                limits.append(held + max(0, free) // self.need.memory_mb)
        if self.need.cores:
            limits.append(self.host.cores // self.need.cores)
        allowed = min(limits) if limits else sys.maxsize
        return max(allowed, 1) if held == 0 else allowed

    def started(self) -> None:
        self.host.started(self.need)


def sized(claim_capacity: Mapping[str, int | PerTask], host: HostCapacity | None = None) -> dict[str, int | ClaimCapacity]:
    """`claim_capacity` for a `WorkQueue`: each `PerTask` entry over one `HostCapacity`
    (`host`, else this host's), the numbers as they are."""
    out: dict[str, int | ClaimCapacity] = {}
    for name, value in claim_capacity.items():
        if isinstance(value, PerTask):
            host = host if host is not None else HostCapacity()
            out[name] = host.capacity(value)
        else:
            out[name] = value
    return out
