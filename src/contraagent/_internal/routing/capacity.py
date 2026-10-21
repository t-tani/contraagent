"""Claim capacities sized by the host: a `PerTask` entry of `claim_capacity` as the
`ClaimCapacity` the queue asks each time it tries to start a task that claims the name.

`HostCapacity` is the host's room, shared by every `PerTask` name of one queue. A task
with `memory_mb` starts only when two conditions hold, as Kubernetes requests and YARN
containers are placed:

* declared: `memory_mb` of the running `PerTask` tasks plus its own is at most the
  baseline, the free memory (`processes.mem_available_mb`) read while no `PerTask` task
  runs. A task's `memory_mb` stays reserved from its start to its end, however soon or
  late it takes the memory.
* measured: the free memory now is at least its `memory_mb`, so memory that other work
  took since the baseline counts too.

`cores` caps the name at the usable cores divided by it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping

from contraagent._internal.dispatch import ClaimCapacity
from contraagent._internal.platform import processes
from contraagent._internal.routing.config import PerTask


class HostCapacity:
    """The host's room for tasks with a `PerTask` claim capacity: one per queue.

    `mem_available_mb()`: the free memory in MB, None where the host does not report it;
    `cores`: the usable cores. Each is given in a test."""

    def __init__(
        self,
        *,
        mem_available_mb: Callable[[], int | None] = processes.mem_available_mb,
        cores: int | None = None,
    ) -> None:
        self._read = mem_available_mb
        self.cores = cores if cores is not None else processes.usable_cores()
        self.running = 0  # running tasks with a PerTask claim
        self.reserved_mb = 0  # their memory_mb
        self.baseline_mb: int | None = None  # the free memory read while none of them ran

    def free_mb(self) -> int | None:
        """The free memory in MB now, None where the host does not report it; read while no
        `PerTask` task runs, it is the new baseline."""
        free = self._read()
        if self.running == 0 and free is not None:
            self.baseline_mb = free
        return free

    def more(self, memory_mb: int) -> int:
        """How many more tasks that each take `memory_mb` may start now, by memory:
        sys.maxsize where the host does not report its free memory."""
        free = self.free_mb()
        if free is None or self.baseline_mb is None:
            return sys.maxsize
        if free < memory_mb:
            return 0
        return max(0, self.baseline_mb - self.reserved_mb) // memory_mb

    def started(self, need: PerTask) -> None:
        if self.running == 0:
            self.free_mb()  # the baseline, right before the first one starts
        self.running += 1
        self.reserved_mb += need.memory_mb or 0

    def ended(self, need: PerTask) -> None:
        self.running -= 1
        self.reserved_mb -= need.memory_mb or 0

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
            more = self.host.more(self.need.memory_mb)
            if more != sys.maxsize:
                limits.append(held + more)
        if self.need.cores:
            limits.append(self.host.cores // self.need.cores)
        allowed = min(limits) if limits else sys.maxsize
        return max(allowed, 1) if held == 0 else allowed

    def started(self) -> None:
        self.host.started(self.need)

    def ended(self) -> None:
        self.host.ended(self.need)


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
