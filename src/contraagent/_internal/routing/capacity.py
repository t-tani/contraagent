"""Claim capacities sized by the host: a `PerTask` entry of `claim_capacity` as the
`ClaimCapacity` the queue asks each time it tries to start a task that claims the name.

`HostCapacity` is the host's room, shared by every `PerTask` name of one queue. It holds,
for each running task with a `PerTask` claim, its declared memory `m` (the `memory_mb` of
its `PerTask` names, added up) and reads, once each time the queue begins to start tasks
(`refresh`), the free memory `F` (`processes.mem_available_mb`) and each such task's
usage `u`: the memory the processes of its agents' groups hold of their own
(`task_usage_mb`; each launch registers its group with its task's key,
`live_processes.register`). A task holds `h = max(m, u)`: its declaration until it takes
more. The baseline `B` is `F` read while no such task runs. Memory gone from the baseline
that these tasks do not account for is other work's, `other = max(0, B - F - sum(u))`. A task with `memory_mb` `n` starts only
when both hold:

* `sum(h) + n + other <= B`: the tasks' holds, the new one and other work fit in the
  baseline;
* `F >= n + sum(h - u)`: the free memory holds the new task and what the running ones
  hold but have not taken yet.

So a task that takes its memory late keeps it reserved until it does, one that took it is
counted once, one that takes more than it declared counts what it takes, and other work's
memory counts as it grows and shrinks. A task started since the reading counts with
`u = 0`: several start on one reading only as far as their declarations fit. Readings
err on the safe side where they cannot be exact: a process's own memory leaves out what
it shares with others, and memory a task holds outside its agents' groups (inside this
interpreter, as a Python task's; in a process that left its agent's group and tree) is
`other` while the task's declaration stays reserved too.

`cores` caps the name at the usable cores divided by it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Collection, Mapping

from contraagent._internal.backends import live_processes
from contraagent._internal.dispatch import ClaimCapacity
from contraagent._internal.platform import processes
from contraagent._internal.routing.config import PerTask


def task_usage_mb(keys: Collection[str]) -> dict[str, int]:
    """The memory in MB the processes of each task of `keys` hold of their own
    (`processes.own_mb`): the processes of the agents launched for it, as each launch
    registered its group (`live_processes.task_pids`). A task with no live agent is left
    out."""
    return {key: sum(processes.own_mb(pid) for pid in pids) for key, pids in live_processes.task_pids(keys).items()}


class HostCapacity:
    """The host's room for tasks with a `PerTask` claim capacity: one per queue.

    `mem_available_mb()`: the free memory in MB, None where the host does not report it;
    `usage_mb(keys)`: the memory in MB the processes of each task of `keys` hold
    (`task_usage_mb`); `cores`: the usable cores. Each is given in a test."""

    def __init__(
        self,
        *,
        mem_available_mb: Callable[[], int | None] = processes.mem_available_mb,
        usage_mb: Callable[[Collection[str]], Mapping[str, int]] | None = None,
        cores: int | None = None,
    ) -> None:
        self._free = mem_available_mb
        self._usage = usage_mb if usage_mb is not None else task_usage_mb
        self.cores = cores if cores is not None else processes.usable_cores()
        self.tasks: dict[str, list[int]] = {}  # key -> [memory_mb of its PerTask names, names]
        self.baseline_mb: int | None = None
        self._reading: tuple[int | None, Mapping[str, int], bool] | None = None  # F, u by key, read while none ran

    def refresh(self) -> None:
        """Read the host again at the next question: the queue begins to start tasks."""
        self._reading = None

    def _read(self) -> tuple[int | None, Mapping[str, int]]:
        if self._reading is None:
            free = self._free()
            idle = not self.tasks
            if idle and free is not None:
                self.baseline_mb = free
            usage = self._usage(tuple(self.tasks)) if self.tasks and free is not None else {}
            self._reading = (free, usage, idle)
        return self._reading[0], self._reading[1]

    def more(self, memory_mb: int) -> int:
        """How many more tasks that each declare `memory_mb` may start on this reading:
        sys.maxsize where the host does not report its free memory."""
        free, usage = self._read()
        if free is None or self.baseline_mb is None:
            return sys.maxsize
        held = taken = 0
        for key, (declared, _) in self.tasks.items():
            used = usage.get(key, 0)
            held += max(declared, used)
            taken += used
        other = max(0, self.baseline_mb - free - taken)
        room = min(self.baseline_mb - other - held, free - (held - taken))
        return max(0, room) // memory_mb

    def started(self, key: str, need: PerTask) -> None:
        if not self.tasks and not (self._reading is not None and self._reading[2]):
            self._reading = None
            self._read()  # the baseline, right before the first one starts
        entry = self.tasks.setdefault(key, [0, 0])
        entry[0] += need.memory_mb or 0
        entry[1] += 1

    def ended(self, key: str, need: PerTask) -> None:
        entry = self.tasks.get(key)
        if entry is None:
            return
        entry[0] -= need.memory_mb or 0
        entry[1] -= 1
        if entry[1] <= 0:
            del self.tasks[key]

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

    def refresh(self) -> None:
        self.host.refresh()

    def started(self, key: str) -> None:
        self.host.started(key, self.need)

    def ended(self, key: str) -> None:
        self.host.ended(key, self.need)


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
