"""The watchdog of `live_processes`: a script run in a process of its own, on POSIX only,
as `python -I watchdog.py <path of platform/processes.py>`.

It reads lines on its stdin, a socket: `+<pgid> <start>` when an agent group starts,
`-<pgid>` when it ends. At the end of file (the interpreter that started it is gone) it
stops the groups still listed: SIGTERM, a grace period, then SIGKILL.

A group is known by its number, and a number is reused once its process is gone. So each
group is listed with the start of its leader, the agent process whose pid is the pgid,
as `processes.start_ticks` read it when the agent was registered. Before each signal the
watchdog reads the start again (`ours`) and signals the group only when it is the same.
When no process has that pid any more, the leader is gone but the group may live on in
the processes the agent started. POSIX does not reuse a process group id while the group
exists, so the group with that number is still the agent's own, and it is signalled. A
pid whose start cannot be read while the process exists is not trusted, as
`processes.identity_ok` does not trust a pid without its start, and a group whose start
was not read at registration is not listed at all.

The script imports nothing of the package but `platform/processes.py`, which it loads
from its path: importing `contraagent` would load the whole package into a process that
only waits.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import sys
import time
from collections.abc import Callable

#: How long the groups get to exit after SIGTERM before SIGKILL (`live_processes._TERM_GRACE_S`).
GRACE_S = 5.0

#: Reads a process's start, as `processes.start_ticks` does: None when it cannot be read.
Starts = Callable[[int], "int | None"]
#: Sends a signal to a process group, as `os.killpg` does: OSError when there is no such group.
SendGroup = Callable[[int, int], None]


def read_groups(fd: int) -> dict[int, int]:
    """Read lines from `fd` until its end of file; the groups still listed, each with its
    leader's start. A line that cannot be read is skipped."""
    groups: dict[int, int] = {}
    buf = b""
    while True:
        try:
            data = os.read(fd, 4096)
        except InterruptedError:
            continue
        except OSError:
            data = b""
        if not data:
            return groups
        buf += data
        *lines, buf = buf.split(b"\n")
        for line in lines:
            try:
                if line[:1] == b"+":
                    pgid, start = line[1:].split()
                    groups[int(pgid)] = int(start)
                elif line[:1] == b"-":
                    groups.pop(int(line[1:]), None)
            except ValueError:
                pass


def exists(pid: int) -> bool:
    """True when some process has `pid`, whoever owns it."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def ours(pgid: int, start: int, starts: Starts, exists: Callable[[int], bool] = exists) -> bool:
    """True when the group `pgid` is still the agent's: its leader has the recorded
    `start`, or no process has the leader's pid (the group id is not reused while the
    group lives)."""
    now = starts(pgid)
    if now is not None:
        return now == start
    return not exists(pgid)


def stop(
    groups: dict[int, int],
    starts: Starts,
    send: SendGroup,
    term: int,
    kill: int,
    *,
    exists: Callable[[int], bool] = exists,
    grace_s: float = GRACE_S,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> list[int]:
    """Stop the groups that are still the agents' (`ours`): `term`, then `kill` to what is
    left after `grace_s`. Returns the groups sent `term`."""

    def signal_ours(pgid: int, signum: int) -> bool:
        if not ours(pgid, groups[pgid], starts, exists):
            return False
        try:
            send(pgid, signum)
        except OSError:
            return False
        return True

    termed = [g for g in list(groups) if signal_ours(g, term)]
    left = set(termed)
    end = clock() + grace_s
    while left and clock() < end:
        pause(0.1)
        left = {g for g in left if signal_ours(g, 0)}
    for g in left:
        signal_ours(g, kill)
    return termed


def _load_processes(path: str):
    """`platform/processes.py`, loaded from its path."""
    spec = importlib.util.spec_from_file_location("_contraagent_watchdog_processes", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> None:
    if sys.platform == "win32":
        raise SystemExit("the watchdog runs on POSIX only")
    starts: Starts = _load_processes(argv[1]).start_ticks
    stop(read_groups(0), starts, os.killpg, signal.SIGTERM, signal.SIGKILL)


if __name__ == "__main__":
    main(sys.argv)
