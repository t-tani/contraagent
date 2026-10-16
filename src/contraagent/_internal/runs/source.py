"""Where runs' records are read from: the run source.

`RunSource` is the one way to read runs: the monitor's views, a relay's passes, the
trends' digests and a panel's `RunRecords` all read through it, so the same code serves
one host's `runs/` directory, a hub's stores, or records held in memory. It names
records by their layout names (`contraagent._internal.runs.layout`) and gives:

* a run's info (`run.json`), its logs by line (`lines`) or by position (`lines_at`, for
  a reader that keeps its place, as a relay does), its documents, and which of each
  it has (`logs`, `documents`);
* a record's size and modification time (`stat`), and when the run last changed;
* the files its contracts name (`file`, `file_stat`), as the host that drove the run sees
  them (a relative path is under the run's `cwd`: `layout.file_path`);
* the run directory, where there is one (`dir`), and the trends digest a reader keeps
  of a finished run (`kept`, `keep`).

`DirectorySource` reads one host's `runs/` directory; `MemorySource` holds records in
memory (tests, and a second implementation that keeps the protocol honest); the hub's
`HubSource` reads its stores. Every run id, task key and layout name is checked by
`names.check_name` in every implementation, so a bad name is `names.BadName` whatever
the store. A log's lines are its complete lines (`files.read_lines`).
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from contraagent._internal.runs import layout
from contraagent._internal.runs.files import lines_at as read_lines_at
from contraagent._internal.runs.files import read_document, read_lines, seek_line, write_document
from contraagent._internal.runs.names import check_name, entry_parts, is_plain, under
from contraagent._internal.runs.times import iso_of, parse_iso


class Stat(NamedTuple):
    """A record's or a file's size in bytes and modification time (nanoseconds since the epoch)."""

    size: int
    mtime_ns: int

    @property
    def mtime(self) -> str:
        """The modification time, ISO 8601 in UTC, to the second."""
        return iso_of(self.mtime_ns / 1e9)


class LogPosition(NamedTuple):
    """A place in a log: a line number, and the byte offset where that line starts."""

    line: int
    offset: int

    def after(self, lines: Sequence[str]) -> LogPosition:
        """The position after `lines`, read from this one (each line counts its UTF-8
        length plus a newline)."""
        return LogPosition(self.line + len(lines), self.offset + sum(len(x.encode()) + 1 for x in lines))


class RunFile(NamedTuple):
    """A file a run's contract names, as the host that drove the run saw it."""

    data: bytes
    mtime: str

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def text(self) -> str | None:
        """Its content as UTF-8 text; None when it is not text."""
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError:
            return None


class RunSource(Protocol):
    """The records of runs, read-only but for the trends digest a reader keeps (`keep`)."""

    def runs(self) -> list[str]:
        """Every run id this source holds, in name order."""
        ...

    def info(self, run: str) -> dict[str, Any] | None:
        """The run's `run.json`, or None."""
        ...

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        """Lines `since`.. of an append-only log, bounded as `page` bounds them (at most
        `limit` lines and `max_bytes` bytes, at least one line), and the log's line count.
        A log that does not exist has no lines and a count of 0."""
        ...

    def lines_at(
        self, run: str, log: str, at: LogPosition, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], LogPosition]:
        """`lines` from a position a reader kept (`position`, or one this returned), and the
        position after the last line given; `([], at)` when no line follows."""
        ...

    def position(self, run: str, log: str, line: int) -> LogPosition:
        """Where line `line` of a log starts; when the log has fewer lines, where it ends."""
        ...

    def size(self, run: str, log: str) -> int:
        """A number that changes whenever the log grows; -1 when it is absent."""
        ...

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """The log's `size` as soon as it is more than `beyond`, or after `timeout` seconds
        (whatever it is then). A live reader passes the `size` it last read up to."""
        ...

    def exists(self, run: str, name: str) -> bool:
        """Whether a log, document or folder of the run exists."""
        ...

    def stat(self, run: str, name: str = "") -> Stat | None:
        """A record's size and modification time (of the run itself for `""`); None when absent."""
        ...

    def logs(self, run: str) -> list[str]:
        """The layout names of the run's logs: `layout.LOGS`, the transcripts, the pipeline logs."""
        ...

    def documents(self, run: str) -> list[str]:
        """The layout names of the run's documents: `run.json`, `cursor.json`, and those in
        `layout.FOLDERS`; never `layout.TRENDS`."""
        ...

    def document(self, run: str, name: str) -> str | None:
        """A document's text (`cursor.json`, `calls/<file>.json`), or None."""
        ...

    def folder(self, run: str, folder: str) -> list[str]:
        """The texts of every `*.json` document in a folder (`contracts`, `definitions`), by file name."""
        ...

    def activity(self, run: str) -> str | None:
        """When the run's records last changed (ISO 8601), or None when unknown."""
        ...

    def file(self, run: str, path: str) -> RunFile | None:
        """A file one of the run's contracts names (a task's input or output), by the path
        its contract record holds; None when it does not exist."""
        ...

    def file_stat(self, run: str, path: str) -> Stat | None:
        """`file`'s size and modification time, without its content."""
        ...

    def dir(self, run: str) -> Path | None:
        """The run's directory on this host; None when the runs are not in a directory here."""
        ...

    def kept(self, run: str) -> str | None:
        """The trends digest kept of the run (`layout.TRENDS`), or None."""
        ...

    def keep(self, run: str, text: str) -> None:
        """Keep a trends digest of the run, where this source can (best effort)."""
        ...


#: A page of a transcript never carries more than this many bytes of lines (at least one
#: line), whatever its line limit: one line can be megabytes (an image).
PAGE_BYTES = 4 << 20


class Pager:
    """Takes lines, at most `limit` of them and `max_bytes` of text (each line counts its
    UTF-8 length plus a newline), but always the first line; from several sources in turn."""

    def __init__(self, limit: int | None, max_bytes: int | None) -> None:
        self.limit = limit
        self.max_bytes = max_bytes
        self.out: list[str] = []
        self.used = 0
        self.full = limit is not None and limit <= 0

    def take(self, lines: Iterable[str]) -> None:
        for line in lines:
            if self.limit is not None and len(self.out) >= self.limit:
                self.full = True
                return
            size = len(line.encode()) + 1
            if self.out and self.max_bytes is not None and self.used + size > self.max_bytes:
                self.full = True
                return
            self.out.append(line)
            self.used += size

    def lines_wanted(self) -> int | None:
        return None if self.limit is None else self.limit - len(self.out)

    def bytes_wanted(self) -> int | None:
        return None if self.max_bytes is None else max(self.max_bytes - self.used, 1)


def page(lines: Iterable[str], limit: int | None, max_bytes: int | None) -> list[str]:
    """The first lines of `lines`, as a `Pager` takes them."""
    pager = Pager(limit, max_bytes)
    if not pager.full:
        pager.take(lines)
    return pager.out


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


def parse_info(text: str | None) -> dict[str, Any] | None:
    """A `run.json`'s text as a dict; None when absent, torn or not an object."""
    try:
        info = json.loads(text) if text is not None else None
    except ValueError:
        return None
    return info if isinstance(info, dict) else None


class DirectorySource:
    """The runs in one `runs/` directory, as `contraagent.engine.Run` writes them."""

    def __init__(self, root: str | Path) -> None:
        self.root: Path = Path(root).resolve()

    def path(self, run: str, name: str = "") -> Path:
        """`root/<run>/<name>`, refused (`names.BadName`) when a part is not a plain name
        or the path leaves the runs directory."""
        parts = entry_parts(name) if name else ()
        return under(self.root, check_name(run, "run id"), *parts)

    def _entry(self, run: str, name: str) -> tuple[str, os.stat_result | None]:
        """A record directly in the run's directory (the directory itself for `""`): its
        path and its `stat`, None when it is absent. With no symbolic link on the way it is
        checked by `lstat`s, not resolved (a period's trends ask for thousands); a link
        takes `path`'s full check."""
        # Joined as strings: with pathlib's `/` and `Path.lstat` one call took about three
        # times as long (3.6 µs against 1.3 µs for a present record, CPython 3.12).
        d = os.path.join(self.root, check_name(run, "run id"))
        p = os.path.join(d, check_name(name, "file name")) if name else d
        try:
            if name and stat.S_ISLNK(os.lstat(d).st_mode):
                return self._resolved(run, name)
            st = os.lstat(p)
        except OSError:
            return p, None
        return self._resolved(run, name) if stat.S_ISLNK(st.st_mode) else (p, st)

    def _resolved(self, run: str, name: str) -> tuple[str, os.stat_result | None]:
        path = str(self.path(run, name))
        try:
            return path, os.stat(path)
        except OSError:
            return path, None

    def runs(self) -> list[str]:
        try:
            return sorted(d.name for d in self.root.iterdir() if d.is_dir() and is_plain(d.name))
        except OSError:
            return []

    def info(self, run: str) -> dict[str, Any] | None:
        return parse_info(self.document(run, layout.RUN_INFO))

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        path = self.path(run, log)
        try:
            return read_lines(path, since, limit, max_bytes)
        except OSError:
            return [], 0

    def lines_at(
        self, run: str, log: str, at: LogPosition, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], LogPosition]:
        path = self.path(run, log)
        try:
            got, end = read_lines_at(path, at.offset, max_bytes, limit)
        except OSError:
            return [], at
        return got, LogPosition(at.line + len(got), end)

    def position(self, run: str, log: str, line: int) -> LogPosition:
        try:
            return LogPosition(*seek_line(self.path(run, log), line))
        except OSError:
            return LogPosition(0, 0)

    def stat(self, run: str, name: str = "") -> Stat | None:
        _, st = self._entry(run, name) if "/" not in name else self._resolved(run, name)
        return Stat(st.st_size, st.st_mtime_ns) if st is not None else None

    def size(self, run: str, log: str) -> int:
        st = self.stat(run, log)
        return st.size if st is not None else -1

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """Polls the file's size (`poll_size`): the standard library has no file notification."""
        self.path(run, log)
        return await poll_size(lambda: self.size(run, log), beyond, timeout)

    def exists(self, run: str, name: str) -> bool:
        return self.path(run, name).exists()

    def _names(self, run: str, folder: str, suffix: str) -> list[str]:
        """The plain names of the files in `folder` that end in `suffix`, without it."""
        try:
            entries = list(os.scandir(self.path(run, folder)))
        except OSError:
            return []
        return sorted(
            e.name[: -len(suffix)]
            for e in entries
            if e.name.endswith(suffix) and is_plain(e.name) and e.is_file() and len(e.name) > len(suffix)
        )

    def logs(self, run: str) -> list[str]:
        own = [log for log in layout.LOGS if self.path(run, log).is_file()]
        streams = [f"{layout.STREAMS}/{n}{layout.STREAM_SUFFIX}" for n in self._names(run, layout.STREAMS, layout.STREAM_SUFFIX)]
        mine = [f"{layout.PIPELINE}/{n}.jsonl" for n in self._names(run, layout.PIPELINE, ".jsonl")]
        return own + streams + mine

    def documents(self, run: str) -> list[str]:
        out = [d for d in (layout.RUN_INFO, layout.CURSOR) if self.path(run, d).is_file()]
        for folder in layout.FOLDERS:
            out += [layout.entry(folder, n) for n in self._names(run, folder, ".json")]
        return out

    def document(self, run: str, name: str) -> str | None:
        path = self._entry(run, name)[0] if "/" not in name else self.path(run, name)
        try:
            return read_document(path)
        except OSError:
            return None

    def folder(self, run: str, folder: str) -> list[str]:
        out = []
        for n in self._names(run, folder, ".json"):
            text = self.document(run, layout.entry(folder, n))
            if text is not None:
                out.append(text)
        return out

    def activity(self, run: str) -> str | None:
        st = self.stat(run)
        return st.mtime if st is not None else None

    def _file(self, run: str, path: str) -> Path:
        info = self.info(run) or {}
        cwd = info.get("cwd")
        return layout.file_path(path, cwd if isinstance(cwd, str) else None)

    def file(self, run: str, path: str) -> RunFile | None:
        where = self._file(run, path)
        try:
            with open(where, "rb") as f:
                st = os.fstat(f.fileno())
                data = f.read()
        except OSError:
            return None
        return RunFile(data, iso_of(st.st_mtime))

    def file_stat(self, run: str, path: str) -> Stat | None:
        try:
            st = self._file(run, path).stat()
        except OSError:
            return None
        return Stat(st.st_size, st.st_mtime_ns)

    def dir(self, run: str) -> Path | None:
        return self.path(run)

    def kept(self, run: str) -> str | None:
        return self.document(run, layout.TRENDS)

    def keep(self, run: str, text: str) -> None:
        """Writes `trends.json`; a runs directory this process cannot write keeps nothing."""
        try:
            write_document(self.path(run, layout.TRENDS), text)
        except OSError:
            pass


def _in_folder(name: str, folder: str, suffix: str) -> bool:
    prefix = folder + "/"
    return name.startswith(prefix) and name.endswith(suffix) and "/" not in name[len(prefix) :]


class MemorySource:
    """Run records held in memory: `{run: {name: text or list of lines}}`.

    A log (`journal.jsonl`, `streams/<file>.stream.jsonl`) is a list of lines; a document
    (`run.json`, `cursor.json`, `contracts/<name>.json`) is a str. `files` maps a run id
    to the files its contracts name, `{path: (text, modification time)}`, and `times` a
    run id to its last activity. A trends digest kept (`keep`) is held as a document."""

    def __init__(
        self,
        records: Mapping[str, Mapping[str, str | list[str]]] | None = None,
        *,
        files: Mapping[str, Mapping[str, tuple[str, str]]] | None = None,
        times: Mapping[str, str] | None = None,
    ) -> None:
        self.records: dict[str, dict[str, str | list[str]]] = {r: dict(v) for r, v in (records or {}).items()}
        self.files: dict[str, dict[str, tuple[str, str]]] = {r: dict(v) for r, v in (files or {}).items()}
        self.times: dict[str, str] = dict(times or {})

    def _run(self, run: str) -> dict[str, str | list[str]]:
        return self.records.get(check_name(run, "run id"), {})

    def _get(self, run: str, name: str) -> str | list[str] | None:
        entry_parts(name)
        return self._run(run).get(name)

    def _log(self, run: str, log: str) -> list[str]:
        every = self._get(run, log)
        return every if isinstance(every, list) else []

    def runs(self) -> list[str]:
        return sorted(r for r in self.records if is_plain(r))

    def info(self, run: str) -> dict[str, Any] | None:
        return parse_info(self.document(run, layout.RUN_INFO))

    def lines(self, run: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        every = self._log(run, log)
        return page(every[since:], limit, max_bytes), len(every)

    def lines_at(
        self, run: str, log: str, at: LogPosition, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], LogPosition]:
        got = page(self._log(run, log)[at.line :], limit, max_bytes)
        return got, at.after(got)

    def position(self, run: str, log: str, line: int) -> LogPosition:
        every = self._log(run, log)
        return LogPosition(0, 0).after(every[: max(line, 0)])

    def size(self, run: str, log: str) -> int:
        every = self._get(run, log)
        return LogPosition(0, 0).after(every).offset if isinstance(every, list) else -1

    async def wait(self, run: str, log: str, beyond: int, timeout: float) -> int:
        """Polls `size` (`poll_size`): the records are a plain mapping that anyone may change."""
        self._get(run, log)
        return await poll_size(lambda: self.size(run, log), beyond, timeout)

    def exists(self, run: str, name: str) -> bool:
        entry_parts(name)
        held = self._run(run)
        return name in held or any(k.startswith(name + "/") for k in held)

    def stat(self, run: str, name: str = "") -> Stat | None:
        if not name:
            if check_name(run, "run id") not in self.records:
                return None
            at = parse_iso(self.times.get(run))
            return Stat(0, int(at.timestamp() * 1e9) if at else 0)
        held = self._get(run, name)
        if held is None:
            return None
        at = parse_iso(self.times.get(run))
        size = LogPosition(0, 0).after(held).offset if isinstance(held, list) else len(held.encode())
        return Stat(size, int(at.timestamp() * 1e9) if at else 0)

    def logs(self, run: str) -> list[str]:
        held = self._run(run)
        own = [log for log in layout.LOGS if isinstance(held.get(log), list)]
        streams = sorted(n for n, v in held.items() if isinstance(v, list) and _in_folder(n, layout.STREAMS, layout.STREAM_SUFFIX))
        mine = sorted(n for n, v in held.items() if isinstance(v, list) and _in_folder(n, layout.PIPELINE, ".jsonl"))
        return own + streams + mine

    def documents(self, run: str) -> list[str]:
        held = self._run(run)
        out = [d for d in (layout.RUN_INFO, layout.CURSOR) if isinstance(held.get(d), str)]
        for folder in layout.FOLDERS:
            out += sorted(n for n, v in held.items() if isinstance(v, str) and _in_folder(n, folder, ".json"))
        return out

    def document(self, run: str, name: str) -> str | None:
        text = self._get(run, name)
        return text if isinstance(text, str) else None

    def folder(self, run: str, folder: str) -> list[str]:
        entry_parts(folder)
        held = self._run(run)
        names = sorted(k for k in held if _in_folder(k, folder, ".json"))
        return [v for v in (held[k] for k in names) if isinstance(v, str)]

    def activity(self, run: str) -> str | None:
        return self.times.get(check_name(run, "run id"))

    def file(self, run: str, path: str) -> RunFile | None:
        got = self.files.get(check_name(run, "run id"), {}).get(path)
        if got is None:
            return None
        text, mtime = got
        return RunFile(text.encode(), mtime)

    def file_stat(self, run: str, path: str) -> Stat | None:
        got = self.file(run, path)
        if got is None:
            return None
        at = parse_iso(got.mtime)
        return Stat(got.size, int(at.timestamp() * 1e9) if at else 0)

    def dir(self, run: str) -> Path | None:
        check_name(run, "run id")
        return None

    def kept(self, run: str) -> str | None:
        return self.document(run, layout.TRENDS)

    def keep(self, run: str, text: str) -> None:
        if check_name(run, "run id") in self.records:
            self.records[run][layout.TRENDS] = text
