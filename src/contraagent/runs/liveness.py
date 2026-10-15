"""Which runs are live, and their live processes: the liveness beside a run source.

`Liveness` is the port; `procs.ProcLiveness` reads one host's `/proc`, `StaticLiveness`
is given its answers (tests, a source with no live run), and the hub's
`HeartbeatLiveness` counts a run live while its host's heartbeats report it.

A snapshot (`Liveness.snapshot`) is one run's live processes: `run`, `alive`, what
`run.json` says (`pid`, `argv`, `started_at`, `max_workers`, `run_group`), and its
`launches`, process `tree` and running `python_tasks`; `empty_snapshot` is one with no
processes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from contraagent.runs.names import check_name
from contraagent.runs.source import RunSource


class Liveness(Protocol):
    """Which runs are live, and their live processes."""

    def live(self) -> set[str]:
        """The ids of the runs whose driving process is alive."""
        ...

    def snapshot(self, run: str) -> dict:
        """One run's live processes (see the module's docstring)."""
        ...

    def unresponsive(self) -> set[str]:
        """The ids of the runs last reported alive whose host has stopped reporting."""
        ...

    def hosts(self) -> list[dict]:
        """The hosts that drive these runs: `{host_id, up, last_seen, interval_s}`;
        `last_seen` is when the host last reported (ISO 8601, "" when not reported)."""
        ...


def empty_snapshot(run: str, info: dict | None, alive: bool) -> dict:
    """A snapshot with no processes: what `run.json` says about the run, and whether it is live."""
    info = info or {}
    return {
        "run": run,
        "alive": alive,
        "pid": info.get("pid"),
        "argv": info.get("argv", []),
        "started_at": info.get("started_at", ""),
        "max_workers": info.get("max_workers"),
        "run_group": info.get("run_group", run),
        "launches": [],
        "tree": [],
        "python_tasks": [],
    }


class StaticLiveness:
    """Liveness given outright: the live run ids and each run's snapshot. A run with no
    snapshot given has no processes, and the run facts its `source` holds."""

    def __init__(self, source: RunSource, live: Iterable[str] = (), snapshots: Mapping[str, dict] | None = None) -> None:
        self.source = source
        self._live = set(live)
        self._snapshots = dict(snapshots or {})

    def live(self) -> set[str]:
        return set(self._live)

    def snapshot(self, run: str) -> dict:
        check_name(run, "run id")
        if run in self._snapshots:
            return self._snapshots[run]
        return empty_snapshot(run, self.source.info(run), run in self._live)

    def unresponsive(self) -> set[str]:
        return set()

    def hosts(self) -> list[dict]:
        return []
