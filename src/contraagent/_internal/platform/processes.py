"""The host's processes and room: one known pid's identity, the processes running, and the
host's free memory and usable cores. Every read of another process's state in the package
is here.

Linux, macOS and Windows alike, read through `psutil`, but for a process's start: a
pid is recycled once its process is gone, so a pid is trusted only together with its
start, recorded when it was seen (`start_ticks`) and compared when it is checked again
(`identity_ok`). The start must read the same from any process at any later time, so
each OS gives the value it keeps for the process itself:

* Linux: the start in clock ticks after boot, field 22 of `/proc/<pid>/stat`, which a
  change to the system clock does not move (`LinuxStarts`).
* macOS and Windows: the start the kernel records for the process, in microseconds
  after the epoch (`psutil.Process.create_time`; `PsutilStarts`).

Both are integers compared only for equality, and only on the host that wrote them.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import NamedTuple, Protocol

import psutil


class Starts(Protocol):
    """How this OS reads a process's start (`start_ticks`): an integer that stays the same
    for the life of the process, and differs for a later process given the same pid."""

    def __call__(self, pid: int, /) -> int | None: ...


class LinuxStarts:
    """The start of a process in clock ticks after boot (field 22 of `/proc/<pid>/stat`).
    `proc_root` is given in a test."""

    def __init__(self, proc_root: str = "/proc") -> None:
        self.proc_root = proc_root

    def __call__(self, pid: int, /) -> int | None:
        try:
            data = Path(self.proc_root, str(pid), "stat").read_text(encoding="utf-8")
        except (OSError, ValueError):
            return None
        # The command name can hold spaces and parentheses: the fields after it follow the last ')'.
        rest = data[data.rfind(")") + 2 :].split()
        if len(rest) < 20 or not rest[19].isdigit():
            return None
        return int(rest[19])


class PsutilStarts:
    """The start of a process as the kernel records it, in microseconds after the epoch
    (`psutil.Process.create_time`)."""

    def __call__(self, pid: int, /) -> int | None:
        try:
            return round(psutil.Process(pid).create_time() * 1_000_000)
        except (psutil.Error, OSError, ValueError):
            return None


#: The start of a process as this OS records it.
start_ticks: Starts = LinuxStarts() if sys.platform == "linux" else PsutilStarts()


def alive(pid: int) -> bool:
    """True when the process exists and has not ended. A zombie has ended: its entry
    stays only until its parent collects its exit status. On Windows an ended process
    stays while a handle to it is open (a `Popen` holds one), so a wait of no time
    decides there."""
    try:
        proc = psutil.Process(pid)
        if sys.platform == "win32":
            try:
                proc.wait(timeout=0)
            except psutil.TimeoutExpired:
                return True
            return False
        return proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.Error, OSError, ValueError):
        return False


def identity_ok(pid: int | None, expected_start_ticks: int | None, *, starts: Starts | None = None) -> bool:
    """True when `pid` is alive and is the process whose start was recorded as
    `expected_start_ticks`: a later process given the same pid has a later start. With
    no start recorded the pid is not trusted. `starts` is given in a test."""
    if pid is None or expected_start_ticks is None or not alive(pid):
        return False
    return (starts or start_ticks)(pid) == expected_start_ticks


class Proc(NamedTuple):
    """One process of the host: its parent, its command line (the arguments joined by
    spaces) and when it started, in seconds after the epoch."""

    pid: int
    ppid: int
    cmd: str
    started: float


def scan() -> dict[int, Proc]:
    """The processes of the host that have a command line and have not ended, by pid. A
    process this user may not read (another user's, a system process) is left out."""
    out: dict[int, Proc] = {}
    for p in psutil.process_iter(["ppid", "cmdline", "create_time", "status"]):
        info = p.info
        if info.get("status") == psutil.STATUS_ZOMBIE:
            continue
        cmd = " ".join(info.get("cmdline") or ()).strip()
        if not cmd:
            continue
        out[p.pid] = Proc(p.pid, info.get("ppid") or 0, cmd, info.get("create_time") or time.time())
    return out


def environ(pid: int, prefix: str = "") -> dict[str, str]:
    """The environment of a process, the variables whose names start with `prefix`; empty
    when the process is gone or its environment is not readable (another user's)."""
    try:
        env = psutil.Process(pid).environ()
    except (psutil.Error, OSError, ValueError):
        return {}
    return {k: v for k, v in env.items() if k.startswith(prefix)}


def mem_available_mb() -> int | None:
    """The host's available memory in MB: what new work may use without swapping (on Linux
    `MemAvailable` of `/proc/meminfo`); None when the host does not report it."""
    try:
        return psutil.virtual_memory().available // (1024 * 1024)
    except (psutil.Error, OSError, RuntimeError):
        return None


def usable_cores() -> int:
    """The cores this process may run on: its CPU affinity where the OS has one, else
    every core of the host; at least 1."""
    if sys.platform == "linux":
        return max(1, len(os.sched_getaffinity(0)))
    return max(1, os.cpu_count() or 1)
