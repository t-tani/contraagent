"""The monitor's ports over a hub: `HubSource` reads every host's runs from a `HubStore`,
its task transcripts from `StreamLogs`, and file contents from a `BlobStore`;
`HeartbeatLiveness` counts a run live while its host's heartbeats keep arriving and report
it alive.

A run's name is its hub name, `<run_id>@<host_id>`; everything else the monitor reads is
the run's own records, as its host wrote them.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime

from contraagent import rundir
from contraagent.hub.store import BlobStore, HubStore
from contraagent.hub.streams import StreamLogs, is_stream
from contraagent.monitor import paths, procs
from contraagent.monitor.source import entry_parts, page

#: Seconds without a heartbeat after which a host's runs no longer count as live.
DEFAULT_TTL_S = 15.0


def _seconds(iso: str) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


class HubSource:
    """A `RunSource` over a hub's stores."""

    def __init__(self, store: HubStore, blobs: BlobStore, streams: StreamLogs) -> None:
        self.store = store
        self.blobs = blobs
        self.streams = streams

    @staticmethod
    def _name(run: str) -> str:
        return paths.check_name(run, "run id")

    def _uid(self, run: str) -> str:
        entry = self.store.entry(self._name(run))
        return entry.run_uid if entry else ""

    def runs(self) -> list[str]:
        return [e.name for e in self.store.runs()]

    def info(self, run: str) -> dict | None:
        text = self.store.document(self._name(run), rundir.RUN_INFO)
        try:
            info = json.loads(text) if text is not None else None
        except ValueError:
            return None
        return info if isinstance(info, dict) else None

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        entry_parts(log)
        if is_stream(log):
            return self.streams.read(self._name(run), self._uid(run), log, since, limit, max_bytes)
        got, total = self.store.lines(self._name(run), log, since, limit)
        return page(got, None, max_bytes), total

    def size(self, run: str, log: str) -> int:
        entry_parts(log)
        if is_stream(log):
            return self.streams.count(self._name(run), self._uid(run), log)
        return self.store.count(self._name(run), log)

    def exists(self, run: str, name: str) -> bool:
        entry_parts(name)
        if name == rundir.STREAMS or is_stream(name):
            logs = self.streams.logs(self._name(run), self._uid(run))
            return name in logs if is_stream(name) else bool(logs)
        return self.store.exists(self._name(run), name)

    def document(self, run: str, name: str) -> str | None:
        entry_parts(name)
        return self.store.document(self._name(run), name)

    def folder(self, run: str, folder: str) -> list[str]:
        entry_parts(folder)
        return self.store.folder(self._name(run), folder)

    def activity(self, run: str) -> str | None:
        times = [t for t in (self.store.activity(self._name(run)), self.streams.activity(self._name(run), self._uid(run))) if t]
        return max(times) if times else None

    def file(self, run: str, path: str) -> tuple[str | None, int, str] | None:
        ref = self.store.file(self._name(run), path)
        if ref is None or ref.sha256 is None:
            return None
        data = self.blobs.get(ref.sha256)
        try:
            text = data.decode("utf-8") if data is not None else None
        except UnicodeDecodeError:
            text = None
        return text, ref.size, ref.mtime


class HeartbeatLiveness:
    """A run is live while its host's latest heartbeat is younger than `ttl_s` and reports
    the run alive; its snapshot is the one that heartbeat carried."""

    def __init__(self, store: HubStore, ttl_s: float = DEFAULT_TTL_S, clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.ttl_s = ttl_s
        self.clock = clock

    def _reports(self) -> dict[str, dict]:
        """Each live run's snapshot, by hub name, from the heartbeats still within the TTL."""
        now = self.clock()
        out: dict[str, dict] = {}
        for heartbeat, received_at in self.store.heartbeats().values():
            at = _seconds(received_at)
            if at is None or now - at > self.ttl_s:
                continue
            for report in heartbeat.runs:
                if report.alive:
                    out[report.run.name] = {**report.snapshot, "run": report.run.name, "alive": True}
        return out

    def live(self) -> set[str]:
        return set(self._reports())

    def snapshot(self, run: str) -> dict:
        paths.check_name(run, "run id")
        got = self._reports().get(run)
        if got is not None:
            return got
        text = self.store.document(run, rundir.RUN_INFO)
        try:
            info = json.loads(text) if text is not None else None
        except ValueError:
            info = None
        return procs.empty_snapshot(run, info if isinstance(info, dict) else None, False)
