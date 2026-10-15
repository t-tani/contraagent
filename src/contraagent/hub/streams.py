"""Transcripts on a hub: one append-only log per task (`streams/<key>.stream.jsonl`), kept
apart from the run's other records because they are large, written in bursts, and read
both live and by page.

`StreamLogs` is what the hub needs of them:

* `append`: compare-and-append by line offset, as the protocol says (drop held lines,
  refuse a gap); the answer is a `Held`: how many lines the hub holds (`held`, on its own
  disk) and how many of those are durable (`durable`, in object storage and indexed).
* `read`: a page of lines from any line number, bounded by lines and by bytes.
* `count`: the log's line count (-1 when it has none).
* `wait`: an asyncio wait until the log has more than a given number of lines; a live
  viewer keeps only its own line offset and reads what is new.
* `close`: the task ended, so the log will not grow; its open segment may be sealed.
* `activity`: when an append last added lines to any of the run's transcripts.
* `runs`: every run (name and `run_uid`) the hub holds transcripts or activity of.
* `drop`: remove everything held of a run's transcripts (retention, `core.Hub.prune`).

A log is named by its run's hub name, the run's `run_uid` (a new run under the same name
starts new logs) and its layout name. `MemoryStreamLogs` is the reference implementation
(everything held is durable); `segments.SegmentedStreamLogs` keeps open segments on local
disk and seals them into object storage.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from typing import NamedTuple, Protocol

from contraagent.runs import layout
from contraagent.runs.source import page


def is_stream(log: str) -> bool:
    """Whether a log's layout name is a task transcript (`streams/<key>.stream.jsonl`)."""
    return log.startswith(layout.STREAMS + "/")


class Held(NamedTuple):
    """How many lines of a log the hub holds, and how many of those are durable."""

    held: int
    durable: int


class StreamLogs(Protocol):
    """Every transcript a hub holds."""

    def append(self, name: str, uid: str, log: str, offset: int, lines: Sequence[str], received_at: str) -> Held:
        """Append `lines`, whose first is line `offset`: lines already held are dropped, a
        chunk that leaves a gap stores nothing. Waiters on the log wake when it grows, and
        the run's activity becomes `received_at`."""
        ...

    def read(
        self, name: str, uid: str, log: str, since: int, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], int]:
        """Lines `since`.. bounded as `page` bounds them, and the log's line count; ([], 0) when absent."""
        ...

    def count(self, name: str, uid: str, log: str) -> int:
        """The log's line count; -1 when the hub holds no such log."""
        ...

    def held(self, name: str, uid: str, log: str) -> Held:
        """`Held` for the log; (0, 0) when absent."""
        ...

    def logs(self, name: str, uid: str) -> list[str]:
        """The layout names of the run's transcripts, sorted."""
        ...

    async def wait(self, name: str, uid: str, log: str, beyond: int, timeout: float) -> int:
        """Return the line count as soon as it exceeds `beyond`, or after `timeout` seconds."""
        ...

    def close(self, name: str, uid: str, log: str) -> None:
        """The log's task ended: it will not grow."""
        ...

    def activity(self, name: str, uid: str) -> str | None:
        """When an append last added lines to one of the run's transcripts, or None."""
        ...

    def runs(self) -> set[tuple[str, str]]:
        """(name, uid) of every run the hub holds a transcript or an activity of."""
        ...

    def drop(self, name: str, uid: str, *, dry_run: bool = False) -> list[str]:
        """Remove the run's transcripts and activity; the keys of the sealed segments'
        objects removed, sorted (none where there are no objects). With `dry_run`, remove
        nothing and return the keys that would be removed. Dropping again, or dropping a
        run that holds nothing, is harmless; an append after the drop starts the log anew."""
        ...


class Waiters:
    """Wakes asyncio waiters from any thread when a log grows: ingest runs in worker
    threads, live viewers in the event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._waiting: dict[tuple, list[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = {}

    def wake(self, key: tuple) -> None:
        with self._lock:
            waiting = self._waiting.pop(key, [])
        for loop, event in waiting:
            loop.call_soon_threadsafe(event.set)

    async def wait(self, key: tuple, ready, timeout: float) -> None:
        """Wait until `ready()` is true, `key` is woken, or `timeout` passes."""
        event = asyncio.Event()
        with self._lock:
            self._waiting.setdefault(key, []).append((asyncio.get_running_loop(), event))
        if ready():
            return
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except TimeoutError:
            pass


class MemoryStreamLogs:
    """`StreamLogs` in memory: every line held is durable. Safe across threads."""

    def __init__(self) -> None:
        self._logs: dict[tuple[str, str, str], list[str]] = {}
        self._closed: set[tuple[str, str, str]] = set()
        self._activity: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()
        self._waiters = Waiters()

    def append(self, name: str, uid: str, log: str, offset: int, lines: Sequence[str], received_at: str) -> Held:
        key = (name, uid, log)
        with self._lock:
            held = self._logs.setdefault(key, [])
            new = list(lines[len(held) - offset :]) if offset <= len(held) else []
            held.extend(new)
            n = len(held)
            if new:
                self._activity[(name, uid)] = received_at
        if new:
            self._waiters.wake(key)
        return Held(n, n)

    def read(
        self, name: str, uid: str, log: str, since: int, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], int]:
        with self._lock:
            every = self._logs.get((name, uid, log), [])
            return page(every[since:], limit, max_bytes), len(every)

    def count(self, name: str, uid: str, log: str) -> int:
        with self._lock:
            every = self._logs.get((name, uid, log))
            return len(every) if every is not None else -1

    def held(self, name: str, uid: str, log: str) -> Held:
        n = max(self.count(name, uid, log), 0)
        return Held(n, n)

    def logs(self, name: str, uid: str) -> list[str]:
        with self._lock:
            return sorted(log for (n, u, log) in self._logs if n == name and u == uid)

    async def wait(self, name: str, uid: str, log: str, beyond: int, timeout: float) -> int:
        await self._waiters.wait((name, uid, log), lambda: self.count(name, uid, log) > beyond, timeout)
        return self.count(name, uid, log)

    def close(self, name: str, uid: str, log: str) -> None:
        with self._lock:
            self._closed.add((name, uid, log))

    def activity(self, name: str, uid: str) -> str | None:
        with self._lock:
            return self._activity.get((name, uid))

    def runs(self) -> set[tuple[str, str]]:
        with self._lock:
            return {(n, u) for (n, u, _) in self._logs} | set(self._activity)

    def drop(self, name: str, uid: str, *, dry_run: bool = False) -> list[str]:
        if dry_run:
            return []
        with self._lock:
            for key in [k for k in self._logs if k[:2] == (name, uid)]:
                del self._logs[key]
                self._closed.discard(key)
            self._activity.pop((name, uid), None)
        return []
