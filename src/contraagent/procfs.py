"""Generic `/proc` introspection: read one known PID's identity and footprint, and
the host's free memory and usable cores.

A plain `/proc/<pid>/stat` parse, a cmdline/environ read, a PID-reuse
identity check, an RSS sum over a process group, and `MemAvailable` of
`/proc/meminfo`. A leaf module with no imports from the rest of the package.

`proc_root` is injectable on every function so callers can point it at a
fake directory tree in tests, instead of the real `/proc`.
"""

from __future__ import annotations

import os
import resource
from pathlib import Path

_PAGE_KB = resource.getpagesize() // 1024


def read_proc_stat(pid: int, proc_root: str = "/proc") -> dict | None:
    """Parse `/proc/<pid>/stat` into `{state, ppid, pgrp, session, starttime}`.

    Returns None when the process is gone. The comm field can contain spaces
    and parentheses, so fields are read after the final ')' rather than by a
    naive split. `starttime` (field 22) is the process start time in clock
    ticks since boot — stable for the life of a pid and the discriminator that
    detects pid reuse.
    """
    try:
        data = Path(proc_root, str(pid), "stat").read_text()
    except (FileNotFoundError, ProcessLookupError, NotADirectoryError):
        return None
    rp = data.rfind(")")
    if rp < 0:
        return None
    rest = data[rp + 2 :].split()
    if len(rest) < 20:
        return None
    return {
        "state": rest[0],
        "ppid": int(rest[1]),
        "pgrp": int(rest[2]),
        "session": int(rest[3]),
        "starttime": int(rest[19]),
    }


def read_cmdline(pid: int, proc_root: str = "/proc") -> str:
    """Return the process command line with NULs turned into spaces, or an
    empty string when the process is gone."""
    try:
        raw = Path(proc_root, str(pid), "cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError, NotADirectoryError):
        return ""
    return raw.replace(b"\x00", b" ").decode(errors="replace").strip()


def read_environ(pid: int, proc_root: str = "/proc") -> str:
    """Return the process environment with NULs turned into spaces, or an empty
    string when it is gone or unreadable."""
    try:
        raw = Path(proc_root, str(pid), "environ").read_bytes()
    except (FileNotFoundError, ProcessLookupError, NotADirectoryError, PermissionError):
        return ""
    return raw.replace(b"\x00", b" ").decode(errors="replace").strip()


def proc_alive(pid: int, proc_root: str = "/proc") -> bool:
    """True when the process exists and is not a zombie. A zombie (state Z) has
    already terminated; its `/proc` entry lingers only until its parent reaps
    it, so it counts as gone for liveness."""
    st = read_proc_stat(pid, proc_root)
    return st is not None and st["state"] != "Z"


def pid_start_ticks(pid: int, proc_root: str = "/proc") -> int | None:
    st = read_proc_stat(pid, proc_root)
    return st["starttime"] if st else None


def pid_identity_ok(
    pid: int | None,
    expected_start_ticks: int | None,
    proc_root: str = "/proc",
    *,
    expect_substrings: tuple = (),
) -> bool:
    """True when `pid` is alive and is the process we started.

    The process start time is the authoritative discriminator: a reused pid
    gets a later start time (they are recorded in clock ticks since boot), so
    a recorded start time that still matches proves the pid was not recycled.
    When a start time was recorded it decides the answer on its own. Only a
    legacy record that carries no start time falls back to the command line or
    environment, which must then contain every `expect_substrings` token to
    vouch for identity. A zombie or absent pid is never trusted; with neither
    signal available the pid is not trusted.
    """
    if pid is None:
        return False
    st = read_proc_stat(pid, proc_root)
    if st is None or st["state"] == "Z":
        return False
    if expected_start_ticks is not None:
        return st["starttime"] == expected_start_ticks
    if expect_substrings:
        haystack = f"{read_cmdline(pid, proc_root)} {read_environ(pid, proc_root)}"
        return all(s in haystack for s in expect_substrings)
    return False


def read_rss_kb(pid: int, proc_root: str = "/proc") -> int:
    """Resident set size of one process in kB, read from `/proc/<pid>/statm`
    (field 2, resident pages). Returns 0 when the process is gone."""
    try:
        parts = Path(proc_root, str(pid), "statm").read_text().split()
    except (FileNotFoundError, ProcessLookupError, NotADirectoryError):
        return 0
    if len(parts) < 2:
        return 0
    return int(parts[1]) * _PAGE_KB


def pgid_members(pgid: int, proc_root: str = "/proc") -> list:
    """Pids whose process-group id is `pgid`."""
    members = []
    try:
        entries = os.listdir(proc_root)
    except FileNotFoundError:
        return members
    for name in entries:
        if not name.isdigit():
            continue
        st = read_proc_stat(int(name), proc_root)
        if st is not None and st["pgrp"] == pgid and st["state"] != "Z":
            members.append(int(name))
    return members


def sample_pgid_rss_kb(pgid: int, proc_root: str = "/proc") -> int:
    """Sum the RSS of every process in `pgid`'s group. A server's Java, uv,
    and shell processes share the group leader's pgid, so this captures the
    whole tree's footprint."""
    return sum(read_rss_kb(pid, proc_root) for pid in pgid_members(pgid, proc_root))


def read_mem_available_mb(proc_root: str = "/proc") -> int | None:
    """The host's available memory in MB: `MemAvailable` of `/proc/meminfo` (the kernel's
    estimate of what new work may use without swapping). None where there is no such
    file or field (not Linux)."""
    try:
        text = Path(proc_root, "meminfo").read_text()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // 1024
    return None


def usable_cores() -> int:
    """The cores this process may run on: its CPU affinity where the platform has one,
    else every core of the host; at least 1."""
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    return max(1, os.cpu_count() or 1)
