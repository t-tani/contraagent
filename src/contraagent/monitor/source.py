"""Where the monitor reads runs from, apart from what it makes of them.

`Monitor` (`core.py`) turns run records into views; it reads them only through two
ports, so the same views serve one host's `runs/` directory or any other store:

* `RunSource`: the records of each run, in the layout `contraagent.rundir` names:
  its run info, its append-only logs (by line offset), its documents, and the files
  its contracts name.
* `Liveness`: which runs are live, and one run's live processes (`procs.snapshot`'s shape).

`DirectorySource` and `ProcLiveness` read one host's `runs/` directory and `/proc`;
`MemorySource` and `StaticLiveness` hold records in memory (tests, and a second
implementation that keeps the ports honest). Every run id, task key and document name
is checked by `paths.check_name` in every implementation, so a bad name is
`paths.BadName` whatever the store.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Protocol

from contraagent import rundir
from contraagent.monitor import paths, procs


class RunSource(Protocol):
    """The records of runs, read-only."""

    def runs(self) -> list[str]:
        """Every run id this source holds, in name order."""
        ...

    def info(self, run: str) -> dict | None:
        """The run's `run.json`, or None."""
        ...

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        """Lines `since`.. of an append-only log, bounded as `page` bounds them (at most
        `limit` lines and `max_bytes` bytes, at least one line), and the log's line count.
        A log that does not exist has no lines and a count of 0."""
        ...

    def size(self, run: str, log: str) -> int:
        """A number that changes whenever the log grows (its byte size); -1 when it is absent."""
        ...

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """The log's `size` as soon as it is more than `beyond`, or after `timeout` seconds
        (whatever it is then). A live reader passes the `size` it last read up to."""
        ...

    def exists(self, run: str, name: str) -> bool:
        """Whether a log, document or folder of the run exists."""
        ...

    def document(self, run: str, name: str) -> str | None:
        """A document's text (`cursor.json`, `calls/<key>.json`), or None."""
        ...

    def folder(self, run: str, folder: str) -> list[str]:
        """The texts of every `*.json` document in a folder (`contracts`, `definitions`), by file name."""
        ...

    def activity(self, run: str) -> str | None:
        """When the run's records last changed (ISO 8601), or None when unknown."""
        ...

    def file(self, run: str, path: str) -> tuple[str | None, int, str] | None:
        """A file one of the run's contracts names (a task's input or output), as the host
        that drove the run sees it: its text (None when it is not text), its byte size and
        its modification time; None when it does not exist."""
        ...


#: A page of a transcript never carries more than this many bytes of lines (at least one
#: line), whatever its line limit: one line can be megabytes (an image).
PAGE_BYTES = 4 << 20


def page(lines, limit: int | None, max_bytes: int | None) -> list[str]:
    """The first lines of `lines`, at most `limit` of them and `max_bytes` of text (each
    line counts its UTF-8 length plus a newline), but always the first line."""
    out: list[str] = []
    used = 0
    for line in lines:
        if limit is not None and len(out) >= limit:
            break
        size = len(line.encode()) + 1
        if out and max_bytes is not None and used + size > max_bytes:
            break
        out.append(line)
        used += size
    return out


#: Seconds between two looks at a log's size while a `wait` polls it.
POLL_S = 0.1


async def poll_size(size: Callable[[], int], beyond: int, timeout: float, every: float = POLL_S) -> int:
    """`RunSource.wait` for a store that cannot notify: look at `size()` every `every`
    seconds until it is more than `beyond` or `timeout` seconds have passed."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        now = size()
        left = deadline - loop.time()
        if now > beyond or left <= 0:
            return now
        await asyncio.sleep(min(every, left))


class Liveness(Protocol):
    """Which runs are live, and their live processes."""

    def live(self) -> set[str]:
        """The ids of the runs whose driving process is alive."""
        ...

    def snapshot(self, run: str) -> dict:
        """One run's live processes, in `procs.snapshot`'s shape."""
        ...

    def unresponsive(self) -> set[str]:
        """The ids of the runs last reported alive whose host has stopped reporting."""
        ...

    def hosts(self) -> list[dict]:
        """The hosts that drive these runs: `{host_id, up, last_seen, interval_s}`;
        `last_seen` is when the host last reported (ISO 8601, "" when not reported)."""
        ...


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _plain(name: str) -> bool:
    try:
        paths.check_name(name)
    except paths.BadName:
        return False
    return True


def entry_parts(name: str) -> tuple[str, ...]:
    """A layout name (`streams/<key>.stream.jsonl`) as checked path parts."""
    return tuple(paths.check_name(p, "file name") for p in name.split("/"))


class DirectorySource:
    """The runs in one `runs/` directory, as `execution.Run` writes them."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def path(self, run: str, name: str = "") -> Path:
        """`root/<run>/<name>`, refused (`paths.BadName`) when a part is not a plain name."""
        parts = entry_parts(name) if name else ()
        return paths.under(self.root, paths.check_name(run, "run id"), *parts)

    def runs(self) -> list[str]:
        try:
            return sorted(d.name for d in self.root.iterdir() if d.is_dir() and _plain(d.name))
        except OSError:
            return []

    def info(self, run: str) -> dict | None:
        return procs.read_run_info(self.root, run)

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        path = self.path(run, log)
        try:
            # errors="replace": a transcript is an agent's raw output, not guaranteed UTF-8.
            with open(path, errors="replace") as f:
                if limit is None and max_bytes is None:
                    every = f.read().splitlines()
                    return every[since:], len(every)
                got = page((line.rstrip("\n") for line in islice(f, since, None)), limit, max_bytes)
            with open(path, "rb") as f:
                return got, sum(1 for _ in f)
        except OSError:
            return [], 0

    def size(self, run: str, log: str) -> int:
        try:
            return self.path(run, log).stat().st_size
        except OSError:
            return -1

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """Polls the file's size (`poll_size`): the standard library has no file notification."""
        self.path(run, log)
        return await poll_size(lambda: self.size(run, log), beyond, timeout)

    def exists(self, run: str, name: str) -> bool:
        return self.path(run, name).exists()

    def document(self, run: str, name: str) -> str | None:
        try:
            return self.path(run, name).read_text()
        except OSError:
            return None

    def folder(self, run: str, folder: str) -> list[str]:
        d = self.path(run, folder)
        out = []
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            try:
                out.append(f.read_text())
            except OSError:
                continue
        return out

    def activity(self, run: str) -> str | None:
        try:
            return _iso(self.path(run).stat().st_mtime)
        except OSError:
            return None

    def file(self, run: str, path: str) -> tuple[str | None, int, str] | None:
        paths.check_name(run, "run id")
        p = Path(path)
        try:
            st = p.stat()
        except OSError:
            return None
        try:
            text: str | None = p.read_text(encoding="utf-8")
        except (OSError, ValueError):
            text = None
        return text, st.st_size, _iso(st.st_mtime)


class ProcLiveness:
    """Live runs of one `runs/` directory on this host: the pid in `run.json`, checked in `/proc`."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def live(self) -> set[str]:
        return procs.live_runs(self.root)

    def snapshot(self, run: str) -> dict:
        return procs.snapshot(self.root, run)

    def unresponsive(self) -> set[str]:
        return set()

    def hosts(self) -> list[dict]:
        return [{"host_id": rundir.host_id(), "up": True, "last_seen": "", "interval_s": None}]


class MemorySource:
    """Run records held in memory: `{run: {name: text or list of lines}}`.

    A log (`journal.jsonl`, `streams/<key>.stream.jsonl`) is a list of lines; a document
    (`run.json`, `cursor.json`, `contracts/<name>.json`) is a str. `files` maps a run id
    to the files its contracts name, `{path: (text, modification time)}`, and `times` a
    run id to its last activity."""

    def __init__(
        self,
        records: Mapping[str, Mapping[str, str | list[str]]] | None = None,
        *,
        files: Mapping[str, Mapping[str, tuple[str, str]]] | None = None,
        times: Mapping[str, str] | None = None,
    ) -> None:
        self.records: dict[str, dict[str, str | list[str]]] = {r: dict(v) for r, v in (records or {}).items()}
        self.files = {r: dict(v) for r, v in (files or {}).items()}
        self.times = dict(times or {})

    def _run(self, run: str) -> dict[str, str | list[str]]:
        return self.records.get(paths.check_name(run, "run id"), {})

    def _get(self, run: str, name: str) -> str | list[str] | None:
        entry_parts(name)
        return self._run(run).get(name)

    def runs(self) -> list[str]:
        return sorted(r for r in self.records if _plain(r))

    def info(self, run: str) -> dict | None:
        text = self._get(run, rundir.RUN_INFO)
        try:
            return json.loads(text) if isinstance(text, str) else None
        except ValueError:
            return None

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        every = self._get(run, log)
        if not isinstance(every, list):
            return [], 0
        return page(every[since:], limit, max_bytes), len(every)

    def size(self, run: str, log: str) -> int:
        every = self._get(run, log)
        return sum(len(line) + 1 for line in every) if isinstance(every, list) else -1

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """Polls `size` (`poll_size`): the records are a plain mapping that anyone may change."""
        self._get(run, log)
        return await poll_size(lambda: self.size(run, log), beyond, timeout)

    def exists(self, run: str, name: str) -> bool:
        entry_parts(name)
        held = self._run(run)
        return name in held or any(k.startswith(name + "/") for k in held)

    def document(self, run: str, name: str) -> str | None:
        text = self._get(run, name)
        return text if isinstance(text, str) else None

    def folder(self, run: str, folder: str) -> list[str]:
        entry_parts(folder)
        held = self._run(run)
        prefix = folder + "/"
        names = sorted(k for k in held if k.startswith(prefix) and k.endswith(".json") and "/" not in k[len(prefix) :])
        return [v for v in (held[k] for k in names) if isinstance(v, str)]

    def activity(self, run: str) -> str | None:
        return self.times.get(paths.check_name(run, "run id"))

    def file(self, run: str, path: str) -> tuple[str | None, int, str] | None:
        got = self.files.get(paths.check_name(run, "run id"), {}).get(path)
        if got is None:
            return None
        text, mtime = got
        return text, len(text.encode()), mtime


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
        paths.check_name(run, "run id")
        if run in self._snapshots:
            return self._snapshots[run]
        return procs.empty_snapshot(run, self.source.info(run), run in self._live)

    def unresponsive(self) -> set[str]:
        return set()

    def hosts(self) -> list[dict]:
        return []
