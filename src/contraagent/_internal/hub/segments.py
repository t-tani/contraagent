"""`SegmentedStreamLogs`: the hub's durable `StreamLogs`. Each transcript is a series of
segments: sealed ones are objects in a `SegmentObjects` store (format in `segment_format`)
listed in a `SegmentIndex`; the open one is a file on the hub's local disk.

* **Open segment.** A raw append-only file per log, `<hot_dir>/<name>/<uid>/<log>/<first
  line>.jsonl` (each part percent-encoded), with its block table built in memory as lines
  arrive. An append writes the file (no fsync) and nothing else: lines in it are `held`,
  and the relay keeps them until they are `durable`.
* **Seal.** The open segment is sealed when it reaches `segment_bytes`, when its log is
  closed, after `idle_s` with no append, or `age_s` after it opened (`tick` checks the
  last two). Sealing builds the object, puts it under its deterministic key
  (`object_key`), commits its index row, and then deletes the file; new appends go to a
  new open segment meanwhile. A crash at any step loses nothing: the file stays until
  its row is committed, an object without a row is an orphan that `sweep` deletes, and
  a sealed file left behind is deleted on start.
* **Start.** Each file is recovered: a torn last line (no newline) is cut, its block
  table is rebuilt by a scan, and it is resumed if it continues what the index holds of
  its log (a log the index does not hold continues from line 0); one that starts past
  that end is first joined by any objects of the log the index lacks, and dropped when
  still not contiguous (the relay resends from `held`). Files that follow one another
  are sealed but the last, which stays open.
* **Read.** Pages are bounded as `runs.source.page` bounds them. Sealed lines come
  through the block table with one ranged read per segment a page touches (normally
  one), and decompressed blocks are kept in an LRU of `cache_bytes`; open lines are read
  from the file. `count` and `held` read no data.
* **Activity.** The `received_at` of the last append that added lines to one of a run's
  transcripts, kept in memory and written to the index with each seal, each close and
  each `tick`, so it survives a restart.
* **Drop.** `drop` removes a run's transcripts (retention): appends to the run wait while
  it runs, and reads find nothing. It forgets the logs in memory (after any seal of
  theirs finishes), deletes their open segments' files, then their index rows and the
  run's activity, then their objects (the index's and any under the run's key prefix). A
  crash before the objects are deleted leaves orphans, which `sweep` deletes and a
  second `drop` finds by prefix.

Ingest calls `append` from worker threads while reads run in the event loop's threads: a
lock per log orders appends and the snapshots reads take. Seals run in a background
thread pool (or inline, `background=False`); a seal that fails is retried at the next
`tick`.

`SegmentIndex` keeps one row per sealed segment; `MemorySegmentIndex` and
`PostgresSegmentIndex` implement it. `rebuild_index` rebuilds one from the objects alone.
`from_spec` builds the whole from a hot directory, an objects URL and an index DSN.
"""

from __future__ import annotations

import bisect
import logging
import os
import shutil
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, LiteralString, NamedTuple, Protocol
from urllib.parse import quote, unquote

from contraagent._internal.hub import segment_format as fmt
from contraagent._internal.hub.segment_objects import SegmentObjects, open_objects
from contraagent._internal.hub.streams import Held, Waiters
from contraagent._internal.runs.files import BINARY
from contraagent._internal.runs.source import Pager

if TYPE_CHECKING:
    import psycopg

log_ = logging.getLogger(__name__)

#: When an open segment is sealed: at this many uncompressed bytes, after this long with
#: no append, and this long after it opened (seconds).
SEGMENT_BYTES = 64 << 20
IDLE_S = 600.0
AGE_S = 3600.0

#: How many bytes of decompressed blocks a `SegmentedStreamLogs` keeps in memory.
CACHE_BYTES = 256 << 20

#: How often the background thread calls `tick` (seconds).
TICK_S = 30.0

_LogKey = tuple[str, str, str]


def object_key(name: str, uid: str, log: str, first_line: int) -> str:
    """The object key of the segment of a log that starts at `first_line`."""
    return f"{name}/{uid}/{log}/{first_line}.seg"


def parse_object_key(key: str) -> tuple[str, str, str, int] | None:
    """(name, uid, log, first line) of an `object_key`; None for any other key."""
    parts = key.split("/")
    if len(parts) < 4 or not parts[-1].endswith(".seg"):
        return None
    stem = parts[-1][: -len(".seg")]
    if not stem.isdigit():
        return None
    return parts[0], parts[1], "/".join(parts[2:-1]), int(stem)


# --- the index ---------------------------------------------------------------------------


class Segment(NamedTuple):
    """One sealed segment, as its index row: the log, its lines, its object and its block
    table (`segment_format.pack_blocks`)."""

    name: str
    uid: str
    log: str
    first_line: int
    line_count: int
    key: str
    blocks: bytes


class SegmentIndex(Protocol):
    """The sealed segments of every log, one row each, and each run's activity."""

    def add(self, segment: Segment, activity: str | None) -> None:
        """Commit a segment's row (replacing one at the same log and first line) and, when
        given, the run's activity, together."""
        ...

    def segments(self, name: str, uid: str, log: str) -> list[Segment]:
        """The log's segments by first line."""
        ...

    def logs(self, name: str, uid: str) -> list[str]:
        """The run's logs that have a segment, sorted."""
        ...

    def keys(self) -> set[str]:
        """The object key of every segment."""
        ...

    def set_activity(self, name: str, uid: str, at: str) -> None:
        """Record the run's activity."""
        ...

    def activity(self, name: str, uid: str) -> str | None:
        """The run's recorded activity, or None."""
        ...

    def runs(self) -> set[tuple[str, str]]:
        """(name, uid) of every run with a segment or a recorded activity."""
        ...

    def drop(self, name: str, uid: str) -> None:
        """Delete the run's rows and its activity, together."""
        ...

    def close(self) -> None:
        """Release what the index holds open (connections); the index is not used after."""
        ...


class MemorySegmentIndex:
    """`SegmentIndex` in memory. Safe across threads."""

    def __init__(self) -> None:
        self._rows: dict[_LogKey, dict[int, Segment]] = {}
        self._activity: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def add(self, segment: Segment, activity: str | None) -> None:
        with self._lock:
            self._rows.setdefault((segment.name, segment.uid, segment.log), {})[segment.first_line] = segment
            if activity is not None:
                self._activity[(segment.name, segment.uid)] = activity

    def segments(self, name: str, uid: str, log: str) -> list[Segment]:
        with self._lock:
            rows = self._rows.get((name, uid, log), {})
            return [rows[k] for k in sorted(rows)]

    def logs(self, name: str, uid: str) -> list[str]:
        with self._lock:
            return sorted(lg for (n, u, lg), rows in self._rows.items() if n == name and u == uid and rows)

    def keys(self) -> set[str]:
        with self._lock:
            return {s.key for rows in self._rows.values() for s in rows.values()}

    def set_activity(self, name: str, uid: str, at: str) -> None:
        with self._lock:
            self._activity[(name, uid)] = at

    def activity(self, name: str, uid: str) -> str | None:
        with self._lock:
            return self._activity.get((name, uid))

    def runs(self) -> set[tuple[str, str]]:
        with self._lock:
            return {(n, u) for (n, u, _), rows in self._rows.items() if rows} | set(self._activity)

    def drop(self, name: str, uid: str) -> None:
        with self._lock:
            for key in [k for k in self._rows if k[:2] == (name, uid)]:
                del self._rows[key]
            self._activity.pop((name, uid), None)

    def close(self) -> None:
        pass


# An arbitrary 64-bit key for the advisory lock held while the segment tables are created.
_SCHEMA_LOCK = 0x7365676D656E7473

_SCHEMA: list[LiteralString] = [
    """CREATE TABLE IF NOT EXISTS stream_segments (
        name text COLLATE "C" NOT NULL,
        uid text COLLATE "C" NOT NULL,
        log text COLLATE "C" NOT NULL,
        first_line bigint NOT NULL,
        line_count bigint NOT NULL,
        object_key text COLLATE "C" NOT NULL,
        blocks bytea NOT NULL,
        PRIMARY KEY (name, uid, log, first_line)
    )""",
    """CREATE TABLE IF NOT EXISTS stream_activity (
        name text COLLATE "C" NOT NULL,
        uid text COLLATE "C" NOT NULL,
        received_at text NOT NULL,
        PRIMARY KEY (name, uid)
    )""",
]


class PostgresSegmentIndex:
    """`SegmentIndex` in the Postgres database at `dsn`, beside `PostgresHubStore`'s tables:

        stream_segments  name, uid, log, first_line, line_count, object_key, blocks (bytea)
        stream_activity  name, uid, received_at

    The tables are created on first use under an advisory lock. Safe across threads: each
    call takes a connection of its own from a small pool; `close()` closes them.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._idle: list[psycopg.Connection] = []
        self._lock = threading.Lock()
        with self._conn() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK,))
            for statement in _SCHEMA:
                conn.execute(statement)

    @contextmanager
    def _conn(self) -> Iterator[psycopg.Connection]:
        import psycopg

        with self._lock:
            conn = self._idle.pop() if self._idle else None
        if conn is None or conn.closed:
            conn = psycopg.connect(self.dsn, autocommit=True)
        try:
            yield conn
        except BaseException:
            conn.close()
            raise
        if conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
            with self._lock:
                self._idle.append(conn)
        else:
            conn.close()

    def close(self) -> None:
        with self._lock:
            idle, self._idle = self._idle, []
        for conn in idle:
            conn.close()

    def add(self, segment: Segment, activity: str | None) -> None:
        with self._conn() as conn, conn.transaction():
            conn.execute(
                "INSERT INTO stream_segments (name, uid, log, first_line, line_count, object_key, blocks) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (name, uid, log, first_line) DO UPDATE SET "
                "line_count = EXCLUDED.line_count, object_key = EXCLUDED.object_key, blocks = EXCLUDED.blocks",
                tuple(segment),
            )
            if activity is not None:
                self._upsert_activity(conn, segment.name, segment.uid, activity)

    @staticmethod
    def _upsert_activity(conn: psycopg.Connection, name: str, uid: str, at: str) -> None:
        conn.execute(
            "INSERT INTO stream_activity (name, uid, received_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (name, uid) DO UPDATE SET received_at = EXCLUDED.received_at",
            (name, uid, at),
        )

    def segments(self, name: str, uid: str, log: str) -> list[Segment]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT name, uid, log, first_line, line_count, object_key, blocks FROM stream_segments "
                "WHERE name = %s AND uid = %s AND log = %s ORDER BY first_line",
                (name, uid, log),
            ).fetchall()
        return [Segment(r[0], r[1], r[2], r[3], r[4], r[5], bytes(r[6])) for r in rows]

    def logs(self, name: str, uid: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT log FROM stream_segments WHERE name = %s AND uid = %s ORDER BY log", (name, uid)
            ).fetchall()
        return [r[0] for r in rows]

    def keys(self) -> set[str]:
        with self._conn() as conn:
            return {r[0] for r in conn.execute("SELECT object_key FROM stream_segments").fetchall()}

    def set_activity(self, name: str, uid: str, at: str) -> None:
        with self._conn() as conn:
            self._upsert_activity(conn, name, uid, at)

    def activity(self, name: str, uid: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT received_at FROM stream_activity WHERE name = %s AND uid = %s", (name, uid)).fetchone()
        return row[0] if row else None

    def runs(self) -> set[tuple[str, str]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT name, uid FROM stream_segments UNION SELECT name, uid FROM stream_activity").fetchall()
        return {(r[0], r[1]) for r in rows}

    def drop(self, name: str, uid: str) -> None:
        with self._conn() as conn, conn.transaction():
            conn.execute("DELETE FROM stream_segments WHERE name = %s AND uid = %s", (name, uid))
            conn.execute("DELETE FROM stream_activity WHERE name = %s AND uid = %s", (name, uid))


def read_segment(objects: SegmentObjects, key: str) -> Segment | None:
    """The index row of the object at `key`, from its footer alone (two ranged reads); None
    when the key is not an `object_key` or the object is not a segment."""
    parsed = parse_object_key(key)
    if parsed is None:
        return None
    try:
        size = fmt.footer_length(objects.get_range(key, -fmt.TAIL_BYTES, None))
        blocks, count = fmt.parse_footer(objects.get_range(key, -size, None))
    except fmt.BadSegment:
        return None
    name, uid, log, first = parsed
    if not blocks or blocks[0].first_line != first:
        return None
    return Segment(name, uid, log, first, count, key, fmt.pack_blocks(blocks))


def rebuild_index(objects: SegmentObjects, index: SegmentIndex) -> int:
    """Add a row to `index` for every segment object in `objects`; the number added."""
    added = 0
    for key in objects.keys():
        segment = read_segment(objects, key)
        if segment is not None:
            index.add(segment, None)
            added += 1
    return added


# --- the block cache ---------------------------------------------------------------------


class BlockCache:
    """Decompressed blocks of sealed segments by (object key, block number), least recently
    used first out once they pass `max_bytes` (each counts its uncompressed size). Sealed
    blocks never change, so an entry is never stale. Safe across threads."""

    def __init__(self, max_bytes: int = CACHE_BYTES) -> None:
        self.max_bytes = max_bytes
        self.bytes = 0
        self.hits = 0
        self.misses = 0
        self._blocks: OrderedDict[tuple[str, int], tuple[list[str], int]] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._blocks)

    def get(self, key: tuple[str, int]) -> list[str] | None:
        with self._lock:
            got = self._blocks.get(key)
            if got is None:
                self.misses += 1
                return None
            self.hits += 1
            self._blocks.move_to_end(key)
            return got[0]

    def put(self, key: tuple[str, int], lines: list[str], size: int) -> None:
        if size > self.max_bytes:
            return
        with self._lock:
            if key in self._blocks:
                return
            self._blocks[key] = (lines, size)
            self.bytes += size
            while self.bytes > self.max_bytes:
                _, (_, dropped) = self._blocks.popitem(last=False)
                self.bytes -= dropped


# --- open and sealed segments ------------------------------------------------------------


class _Sealed:
    """A sealed segment with its block table unpacked."""

    __slots__ = ("first_line", "line_count", "key", "blocks", "firsts", "sizes")

    def __init__(self, segment: Segment) -> None:
        self.first_line = segment.first_line
        self.line_count = segment.line_count
        self.key = segment.key
        self.blocks = fmt.unpack_blocks(segment.blocks)
        self.firsts = [b.first_line for b in self.blocks]
        self.sizes = [b.size for b in self.blocks]

    @property
    def end(self) -> int:
        return self.first_line + self.line_count


class _Hot:
    """A segment on local disk, open (appended to) or waiting to be sealed."""

    def __init__(self, path: Path, first_line: int, block_bytes: int, opened_at: float) -> None:
        self.path = path
        self.first_line = first_line
        self.cutter = fmt.BlockCutter(first_line, block_bytes)
        self.opened_at = opened_at
        self.fd: int | None = None
        #: Reads that took this segment in their snapshot and have not finished; its file is
        #: deleted only when none is left, so a read never finds it gone.
        self.readers = 0
        #: Sealed (its lines are in an object), so its file goes once no read holds it.
        self.retired = False

    @property
    def lines(self) -> int:
        return self.cutter.lines

    @property
    def size(self) -> int:
        return self.cutter.size

    @classmethod
    def create(cls, path: Path, first_line: int, block_bytes: int, now: float) -> _Hot:
        path.parent.mkdir(parents=True, exist_ok=True)
        hot = cls(path, first_line, block_bytes, now)
        hot.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND | BINARY, 0o644)
        return hot

    @classmethod
    def recover(cls, path: Path, first_line: int, block_bytes: int, now: float) -> _Hot:
        """The segment in an existing file, its torn last line cut."""
        data = path.read_bytes()
        whole = data.rfind(b"\n") + 1
        if whole < len(data):
            os.truncate(path, whole)
            data = data[:whole]
        hot = cls(path, first_line, block_bytes, now)
        pos = 0
        add = hot.cutter.add
        while pos < whole:
            end = data.index(b"\n", pos) + 1
            add(end - pos)
            pos = end
        return hot

    def reopen(self) -> None:
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | BINARY)

    def append(self, raw: Sequence[bytes], segment_bytes: int) -> int:
        """Write lines until the segment holds `segment_bytes` (at least one line); how many."""
        assert self.fd is not None
        cutter = self.cutter
        taken = 0
        for line in raw:
            cutter.add(len(line) + 1)
            taken += 1
            if cutter.size >= segment_bytes:
                break
        data = memoryview(b"\n".join(raw[:taken]) + b"\n")
        while data:
            data = data[os.write(self.fd, data) :]
        return taken

    def stop(self) -> None:
        """No more appends: close the file for writing."""
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def view(self) -> _HotView:
        return _HotView(self.path, self.first_line, self.lines, self.size, self.cutter.starts, len(self.cutter.starts))


class _HotView(NamedTuple):
    """What a read needs of a segment on disk, as it was when the read began: the block
    table's list only grows, so its first `nblocks` entries stay as they are."""

    path: Path
    first_line: int
    line_count: int
    size: int
    starts: list[tuple[int, int]]
    nblocks: int


class _Log:
    """What the hub holds of one log: its sealed segments, the segments on disk waiting to
    be sealed, its open segment, and its line counts."""

    def __init__(self, sealed: list[_Sealed]) -> None:
        self.lock = threading.Lock()
        self.seal_lock = threading.Lock()
        self.sealed = sealed
        self.sealing: list[_Hot] = []
        self.hot: _Hot | None = None
        self.durable = sealed[-1].end if sealed else 0
        self.count = self.durable
        self.last_append = 0.0
        self.closed = False
        self.scheduled = False
        self.dropped = False

    def rotate(self) -> bool:
        """Stop the open segment and queue it to be sealed; whether there was one."""
        hot = self.hot
        if hot is None:
            return False
        hot.stop()
        self.sealing.append(hot)
        self.hot = None
        return True


def _contiguous(segments: Sequence[Segment]) -> list[_Sealed]:
    out: list[_Sealed] = []
    for segment in segments:
        if segment.first_line == (out[-1].end if out else 0) and segment.line_count > 0:
            out.append(_Sealed(segment))
    return out


def _span(firsts: Sequence[int], sizes: Sequence[int], pos: int, lines: int | None, nbytes: int | None) -> tuple[int, int]:
    """The blocks (first, last, inclusive) that hold line `pos` and at least `lines` lines
    and `nbytes` bytes after it, as far as the blocks reach."""
    b0 = bisect.bisect_right(firsts, pos) - 1
    b1 = b0
    after = 0
    while b1 + 1 < len(firsts):
        if lines is not None and firsts[b1 + 1] >= pos + lines:
            break
        if nbytes is not None and after >= nbytes:
            break
        b1 += 1
        after += sizes[b1]
    return b0, b1


# --- the stream logs ---------------------------------------------------------------------


class SegmentedStreamLogs:
    """`StreamLogs` with open segments in `hot_dir`, sealed ones in `objects`, listed in `index`.

    `block_bytes`, `segment_bytes`, `idle_s` and `age_s` set the blocks and when a segment
    is sealed; `cache_bytes` the decompressed-block LRU; `clock` the monotonic time the
    idle and age rules use. With `background` (the default) seals run in a thread pool of
    `seal_workers` and a thread calls `tick` every `tick_s` seconds; without it seals run
    in the call that starts them and `tick` runs only when called. The open segments in
    `hot_dir` are recovered on construction; call `sweep` after it to delete orphan
    objects, and `shutdown` to stop the background threads.
    """

    def __init__(
        self,
        hot_dir: str | os.PathLike[str],
        objects: SegmentObjects,
        index: SegmentIndex,
        *,
        block_bytes: int = fmt.BLOCK_BYTES,
        segment_bytes: int = SEGMENT_BYTES,
        idle_s: float = IDLE_S,
        age_s: float = AGE_S,
        cache_bytes: int = CACHE_BYTES,
        clock: Callable[[], float] = time.monotonic,
        background: bool = True,
        seal_workers: int = 2,
        tick_s: float = TICK_S,
    ) -> None:
        self.hot_dir = Path(hot_dir)
        self.objects = objects
        self.index = index
        self.block_bytes = block_bytes
        self.segment_bytes = segment_bytes
        self.idle_s = idle_s
        self.age_s = age_s
        self.cache = BlockCache(cache_bytes)
        self.clock = clock
        self._logs: dict[_LogKey, _Log] = {}
        self._activity: dict[tuple[str, str], str] = {}
        self._dirty: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._undropped = threading.Condition(self._lock)
        self._dropping: set[tuple[str, str]] = set()
        self._drops = 0
        self._flush_lock = threading.Lock()
        self._keys_lock = threading.Lock()
        self._inflight: set[str] = set()
        self._waiters = Waiters()
        self._executor = ThreadPoolExecutor(seal_workers, thread_name_prefix="seal") if background else None
        self._stop = threading.Event()
        self.hot_dir.mkdir(parents=True, exist_ok=True)
        self._recover()
        if background:
            threading.Thread(target=_ticker, args=(weakref.ref(self), self._stop, tick_s), daemon=True, name="seal-tick").start()

    # --- logs in memory --------------------------------------------------------------------

    def _hot_path(self, key: _LogKey, first_line: int) -> Path:
        name, uid, log = key
        return self.hot_dir / quote(name, safe="") / quote(uid, safe="") / quote(log, safe="") / f"{first_line}.jsonl"

    def _run_dir(self, name: str, uid: str) -> Path:
        return self.hot_dir / quote(name, safe="") / quote(uid, safe="")

    def _get(self, key: _LogKey, create: bool = False) -> _Log | None:
        """The log's state, loaded from the index when not in memory. While its run is being
        dropped, a read finds nothing and an append waits for the drop to end."""
        while True:
            with self._lock:
                while key[:2] in self._dropping:
                    if not create:
                        return None
                    self._undropped.wait()
                st = self._logs.get(key)
                drops = self._drops
            if st is not None:
                return st
            sealed = _contiguous(self.index.segments(*key))
            if not sealed and not create:
                return None
            with self._lock:
                if self._drops == drops:  # else a drop ran meanwhile: what was read may be gone
                    return self._logs.setdefault(key, _Log(sealed))

    # --- writes ----------------------------------------------------------------------------

    def append(self, name: str, uid: str, log: str, offset: int, lines: Sequence[str], received_at: str) -> Held:
        key = (name, uid, log)
        seal = False
        while True:
            st = self._get(key, create=True)
            assert st is not None
            with st.lock:
                if st.dropped:
                    continue
                new = lines[st.count - offset :] if offset <= st.count else []
                if new:
                    raw = [line.encode() for line in new]
                    if any(b"\n" in r for r in raw):
                        raise ValueError("a transcript line holds a newline")
                    now = self.clock()
                    st.last_append = now
                    while raw:
                        if st.hot is None:
                            st.hot = _Hot.create(self._hot_path(key, st.count), st.count, self.block_bytes, now)
                        taken = st.hot.append(raw, self.segment_bytes)
                        st.count += taken
                        raw = raw[taken:]
                        if st.hot.size >= self.segment_bytes:
                            seal = st.rotate() or seal
                    with self._lock:  # under the log's lock, so that a drop never misses it
                        self._activity[(name, uid)] = received_at
                        self._dirty.add((name, uid))
                held = Held(st.count, st.durable)
                break
        if new:
            self._waiters.wake(key)
        if seal:
            self._schedule(key, st)
        return held

    def close(self, name: str, uid: str, log: str) -> None:
        key = (name, uid, log)
        st = self._get(key)
        if st is None:
            return
        with st.lock:
            st.closed = True
            seal = st.rotate()
        if seal:
            self._schedule(key, st)
        self._flush_activity({(name, uid)})

    def tick(self) -> None:
        """Seal each open segment that has been idle for `idle_s` or open for `age_s`, retry
        failed seals, and write activity to the index."""
        now = self.clock()
        with self._lock:
            logs = list(self._logs.items())
        for key, st in logs:
            with st.lock:
                hot = st.hot
                if hot is not None and (now - st.last_append >= self.idle_s or now - hot.opened_at >= self.age_s):
                    st.rotate()
                pending = bool(st.sealing)
            if pending:
                self._schedule(key, st)
        self._flush_activity(None)

    def _flush_activity(self, runs: set[tuple[str, str]] | None) -> None:
        with self._flush_lock:
            with self._lock:
                due = set(self._dirty) if runs is None else self._dirty & runs
                self._dirty -= due
                writes = [(run, self._activity[run]) for run in due if run in self._activity]
            for (name, uid), at in writes:
                try:
                    self.index.set_activity(name, uid, at)
                except Exception:
                    log_.exception("writing the activity of %s/%s", name, uid)
                    with self._lock:
                        self._dirty.add((name, uid))

    # --- seals -----------------------------------------------------------------------------

    def _schedule(self, key: _LogKey, st: _Log) -> None:
        with st.lock:
            if st.scheduled:
                return
            st.scheduled = True
        if self._executor is not None:
            try:
                self._executor.submit(self._seal_all, key, st)
                return
            except RuntimeError:  # shut down
                with st.lock:
                    st.scheduled = False
                return
        self._seal_all(key, st)

    def _seal_all(self, key: _LogKey, st: _Log) -> None:
        with st.lock:
            st.scheduled = False
        with st.seal_lock:
            while True:
                with st.lock:
                    hot = st.sealing[0] if st.sealing else None
                if hot is None:
                    return
                try:
                    self._seal(key, st, hot)
                except Exception:
                    log_.exception("sealing %s from line %d; retried at the next tick", "/".join(key), hot.first_line)
                    return

    def _seal(self, key: _LogKey, st: _Log, hot: _Hot) -> None:
        """Seal one segment: build its object, put it, commit its row, delete its file."""
        name, uid, log = key
        with open(hot.path, "rb") as f:
            raw = f.read(hot.size)
        data, blocks = fmt.encode(raw, hot.cutter.starts, hot.lines)
        objkey = object_key(name, uid, log, hot.first_line)
        segment = Segment(name, uid, log, hot.first_line, hot.lines, objkey, fmt.pack_blocks(blocks))
        with self._keys_lock:
            self._inflight.add(objkey)
        try:
            self.objects.put(objkey, data)
            with self._lock:
                activity = self._activity.get((name, uid))
            self.index.add(segment, activity)
        finally:
            with self._keys_lock:
                self._inflight.discard(objkey)
        sealed = _Sealed(segment)
        with st.lock:
            st.sealing.remove(hot)
            st.sealed.append(sealed)
            st.durable = sealed.end
            hot.retired = True
            unread = hot.readers == 0
        if unread:  # else the last read that holds it deletes it
            hot.path.unlink(missing_ok=True)

    def sweep(self) -> list[str]:
        """Delete every object that no index row references and no seal is writing; the keys deleted."""
        listed = self.objects.keys()
        deleted = []
        with self._keys_lock:
            referenced = self.index.keys()
            for key in listed:
                if key not in referenced and key not in self._inflight:
                    self.objects.delete(key)
                    deleted.append(key)
        return deleted

    # --- retention -------------------------------------------------------------------------

    def runs(self) -> set[tuple[str, str]]:
        with self._lock:
            mine = {(n, u) for (n, u, _) in self._logs} | set(self._activity)
        return mine | self.index.runs()

    def _run_keys(self, name: str, uid: str) -> list[str]:
        """The object keys of the run's segments: the index's, and any under its key prefix."""
        keys = set(self.objects.keys(f"{name}/{uid}/"))
        for log in self.index.logs(name, uid):
            keys.update(s.key for s in self.index.segments(name, uid, log))
        return sorted(keys)

    def drop(self, name: str, uid: str, *, dry_run: bool = False) -> list[str]:
        """See `StreamLogs.drop`; the order of its steps is in the module's docstring."""
        if dry_run:
            return self._run_keys(name, uid)
        run = (name, uid)
        with self._lock:
            while run in self._dropping:
                self._undropped.wait()
            self._dropping.add(run)
            self._drops += 1
            logs = [(key, st) for key, st in self._logs.items() if key[:2] == run]
            for key, _ in logs:
                del self._logs[key]
        try:
            for key, st in logs:
                with st.seal_lock, st.lock:
                    st.dropped = True
                    for hot in [*st.sealing, *([st.hot] if st.hot else [])]:
                        hot.stop()
                    st.sealing, st.hot = [], None
                self._waiters.wake(key)
            where = self._run_dir(name, uid)
            shutil.rmtree(where, ignore_errors=True)
            try:
                where.parent.rmdir()
            except OSError:  # another run under the name, or already gone
                pass
            keys = self._run_keys(name, uid)
            with self._flush_lock:
                with self._lock:
                    self._activity.pop(run, None)
                    self._dirty.discard(run)
                self.index.drop(name, uid)
            for key in keys:
                self.objects.delete(key)
            return keys
        finally:
            with self._lock:
                self._dropping.discard(run)
                self._undropped.notify_all()

    def shutdown(self, wait: bool = True) -> None:
        """Stop the background threads (waiting for running seals with `wait`), close the
        open files and then the index. The open segments stay on disk, recovered by the next
        start."""
        self._stop.set()
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
        self._flush_activity(None)
        with self._lock:
            logs = list(self._logs.values())
        for st in logs:
            with st.lock:
                if st.hot is not None:
                    st.hot.stop()
        self.index.close()

    # --- recovery --------------------------------------------------------------------------

    def _recover(self) -> None:
        found: dict[_LogKey, list[tuple[int, Path]]] = {}
        for path in self.hot_dir.glob("*/*/*/*.jsonl"):
            if not path.stem.isdigit():
                continue
            q_name, q_uid, q_log = path.parts[-4:-1]
            found.setdefault((unquote(q_name), unquote(q_uid), unquote(q_log)), []).append((int(path.stem), path))
        now = self.clock()
        for key, files in found.items():
            files.sort()
            st = self._get(key, create=True)
            assert st is not None
            if files[-1][0] > st.count:
                self._adopt(key, st)
            hots: list[_Hot] = []
            for first, path in files:
                hot = _Hot.recover(path, first, self.block_bytes, now)
                if first == st.count and hot.lines:
                    hots.append(hot)
                    st.count += hot.lines
                    continue
                if first + hot.lines > st.count and hot.lines:
                    log_.warning("dropping %s: it starts at line %d, past the %d lines held", path, first, st.count)
                path.unlink()
            if hots:
                st.sealing = hots[:-1]
                st.hot = hots[-1]
                st.hot.reopen()
                st.last_append = now
            if st.sealing:
                self._schedule(key, st)

    def _adopt(self, key: _LogKey, st: _Log) -> None:
        """Add to the index the log's objects that continue what it holds (a log whose rows
        were lost), so that the files after them can resume."""
        name, uid, log = key
        prefix = f"{name}/{uid}/{log}/"
        keys = {parse_object_key(k): k for k in self.objects.keys(prefix)}
        by_first = {p[3]: k for p, k in keys.items() if p is not None and p[2] == log}
        while st.count in by_first:
            segment = read_segment(self.objects, by_first[st.count])
            if segment is None or segment.line_count == 0:
                return
            self.index.add(segment, None)
            sealed = _Sealed(segment)
            st.sealed.append(sealed)
            st.durable = st.count = sealed.end

    # --- reads -----------------------------------------------------------------------------

    def read(
        self, name: str, uid: str, log: str, since: int, limit: int | None = None, max_bytes: int | None = None
    ) -> tuple[list[str], int]:
        since = max(since, 0)
        for _ in range(5):
            st = self._get((name, uid, log))
            if st is None:
                return [], 0
            with st.lock:
                total = st.count
                sealed = list(st.sealed)
                pinned = [*st.sealing, *([st.hot] if st.hot is not None else [])]
                for h in pinned:
                    h.readers += 1
                hot = [h.view() for h in pinned]
            try:
                return self._read(sealed, hot, since, limit, max_bytes), total
            except FileNotFoundError:
                continue  # the run was dropped meanwhile: the next look finds nothing
            finally:
                self._unpin(st, pinned)
        raise RuntimeError(f"{name}/{uid}/{log}: its files kept disappearing during a read")

    @staticmethod
    def _unpin(st: _Log, pinned: list[_Hot]) -> None:
        """End a read's hold on segments on disk; delete the files of sealed ones it held last."""
        gone = []
        with st.lock:
            for h in pinned:
                h.readers -= 1
                if h.retired and h.readers == 0:
                    gone.append(h.path)
        for path in gone:
            path.unlink(missing_ok=True)

    def _read(self, sealed: list[_Sealed], hot: list[_HotView], pos: int, limit: int | None, max_bytes: int | None) -> list[str]:
        pager = Pager(limit, max_bytes)
        if limit is not None and limit <= 0:
            return []
        start = bisect.bisect_right([s.first_line for s in sealed], pos) - 1
        for s in sealed[max(start, 0) :]:
            if pos >= s.end:
                continue
            got = self._read_sealed(s, pos, pager.lines_wanted(), pager.bytes_wanted())
            pager.take(got)
            pos += len(got)
            if pager.full:
                return pager.out
        for h in hot:
            if pos >= h.first_line + h.line_count or pos < h.first_line:
                continue
            got = self._read_hot(h, pos, pager.lines_wanted(), pager.bytes_wanted())
            pager.take(got)
            pos += len(got)
            if pager.full:
                break
        return pager.out

    def _read_sealed(self, s: _Sealed, pos: int, lines: int | None, nbytes: int | None) -> list[str]:
        b0, b1 = _span(s.firsts, s.sizes, pos, lines, nbytes)
        got: dict[int, list[str]] = {}
        missing = []
        for i in range(b0, b1 + 1):
            cached = self.cache.get((s.key, i))
            if cached is None:
                missing.append(i)
            else:
                got[i] = cached
        if missing:
            lo, hi = s.blocks[missing[0]], s.blocks[missing[-1]]
            data = memoryview(self.objects.get_range(s.key, lo.offset, hi.offset + hi.compressed))
            for i in range(missing[0], missing[-1] + 1):
                b = s.blocks[i]
                if i not in got:
                    block = fmt.decode(data[b.offset - lo.offset : b.offset - lo.offset + b.compressed])
                    self.cache.put((s.key, i), block, b.size)
                    got[i] = block
        out: list[str] = []
        for i in range(b0, b1 + 1):
            block = got[i]
            out.extend(block[pos - s.firsts[i] :] if i == b0 else block)
        return out

    def _read_hot(self, h: _HotView, pos: int, lines: int | None, nbytes: int | None) -> list[str]:
        firsts = [h.starts[i][0] for i in range(h.nblocks)]
        offsets = [h.starts[i][1] for i in range(h.nblocks)] + [h.size]
        sizes = [offsets[i + 1] - offsets[i] for i in range(h.nblocks)]
        b0, b1 = _span(firsts, sizes, pos, lines, nbytes)
        with open(h.path, "rb") as f:
            f.seek(offsets[b0])
            raw = f.read(offsets[b1 + 1] - offsets[b0])
        got = raw.decode().split("\n")[:-1]
        end = min(len(got), h.first_line + h.line_count - firsts[b0])
        return got[pos - firsts[b0] : end]

    def count(self, name: str, uid: str, log: str) -> int:
        st = self._get((name, uid, log))
        if st is None:
            return -1
        with st.lock:
            return st.count

    def held(self, name: str, uid: str, log: str) -> Held:
        st = self._get((name, uid, log))
        if st is None:
            return Held(0, 0)
        with st.lock:
            return Held(st.count, st.durable)

    def logs(self, name: str, uid: str) -> list[str]:
        with self._lock:
            mine = {lg for (n, u, lg) in self._logs if n == name and u == uid}
        return sorted(mine.union(self.index.logs(name, uid)))

    async def wait(self, name: str, uid: str, log: str, beyond: int, timeout: float) -> int:
        await self._waiters.wait((name, uid, log), lambda: self.count(name, uid, log) > beyond, timeout)
        return self.count(name, uid, log)

    def activity(self, name: str, uid: str) -> str | None:
        with self._lock:
            if (name, uid) in self._dropping:
                return None
            at = self._activity.get((name, uid))
            drops = self._drops
        if at is not None:
            return at
        at = self.index.activity(name, uid)
        if at is not None:
            with self._lock:
                if self._drops == drops:
                    self._activity.setdefault((name, uid), at)
        return at


def _ticker(ref: weakref.ref[SegmentedStreamLogs], stop: threading.Event, every: float) -> None:
    """Call `tick` every `every` seconds until `stop` is set or the logs are gone."""
    while not stop.wait(every):
        logs = ref()
        if logs is None:
            return
        try:
            logs.tick()
        except Exception:
            log_.exception("tick")
        del logs


def from_spec(
    hot_dir: str | os.PathLike[str], objects_url: str | None, index_dsn: str | None, *, sweep: bool = True, **kwargs
) -> SegmentedStreamLogs:
    """`SegmentedStreamLogs` over `hot_dir`, the objects at `objects_url` (`open_objects`) and
    the index at `index_dsn` (a Postgres DSN, or None or `memory:` for a `MemorySegmentIndex`
    rebuilt from the objects), its orphan objects swept unless `sweep` is false. Keyword
    arguments pass through to `SegmentedStreamLogs`."""
    objects = open_objects(objects_url)
    index: SegmentIndex
    if index_dsn in (None, "memory:"):
        index = MemorySegmentIndex()
        rebuild_index(objects, index)
    else:
        index = PostgresSegmentIndex(str(index_dsn))
    logs = SegmentedStreamLogs(hot_dir, objects, index, **kwargs)
    if sweep:
        logs.sweep()
    return logs
