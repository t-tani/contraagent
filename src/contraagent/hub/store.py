"""What a hub holds: the records of every host's runs (`HubStore`) and file contents by
SHA-256 (`BlobStore`).

A `HubStore` stores what relays send (`protocol.RecordBatch`, `protocol.Heartbeat`) and
answers the reads `source.HubSource` needs, by the run's hub name (`<run_id>@<host_id>`).
Its storing rules are the protocol's: a log keeps every line once, in order, and refuses a
chunk that leaves a gap; a document is replaced whole; a batch whose `run_uid` differs from
the one held under the same name is a new run, which replaces the old one's records.

A run's activity (`HubStore.activity`) is when a batch last changed what the hub holds of
it: a new run or a new `run_uid`, a log not held before, new lines, a document whose text
differs or one removed that was held, or a file ref that differs. A batch that stores
nothing new (a relay asking how many lines are held, a resend) leaves it as it was.

Retention (`core.Hub.prune`) removes old runs (`HubStore.delete_run`), heartbeats of hosts
long gone (`HubStore.delete_heartbeat`), and blobs no file ref references
(`HubStore.referenced_blobs`, `BlobStore.items`, `BlobStore.delete`).

`MemoryHubStore` and `MemoryBlobs` keep everything in memory (tests, a single-process
hub); `DirectoryBlobs` keeps blobs as files. The Postgres store and the S3 blobs are in
`postgres` and `s3`.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple, Protocol

from contraagent.hub.protocol import Accepted, FileRef, Heartbeat, RecordBatch, RunRef
from contraagent.runs.files import write_document
from contraagent.runs.source import page


class HubStore(Protocol):
    """The records of every host's runs."""

    def put_batch(self, batch: RecordBatch, received_at: str) -> Accepted:
        """Store a batch by the protocol's rules; how many lines of each log it named are held."""
        ...

    def put_heartbeat(self, heartbeat: Heartbeat, received_at: str) -> None:
        """Keep a host's latest heartbeat, and when it arrived."""
        ...

    def runs(self) -> list[RunRef]:
        """Every run held, by name."""
        ...

    def entry(self, name: str) -> RunRef | None:
        """The run held under `name`, or None."""
        ...

    def lines(self, name: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        """Lines `since`.. of a run's log, bounded as `runs.source.page` bounds them, and how
        many it holds; ([], 0) when none."""
        ...

    def logs(self, name: str) -> list[str]:
        """The layout names of the run's logs held here, sorted."""
        ...

    def documents(self, name: str) -> list[str]:
        """The layout names of the run's documents, sorted."""
        ...

    def count(self, name: str, log: str) -> int:
        """How many lines of the log are held; -1 when the run has no such log."""
        ...

    def document(self, name: str, doc: str) -> str | None:
        """A document's text, or None."""
        ...

    def folder(self, name: str, folder: str) -> list[str]:
        """The texts of the documents directly in `folder`, by document name."""
        ...

    def exists(self, name: str, entry: str) -> bool:
        """Whether a log, a document, or a folder holding one is held for the run."""
        ...

    def file(self, name: str, path: str) -> FileRef | None:
        """The latest `FileRef` the run's host sent for `path`, or None."""
        ...

    def activity(self, name: str) -> str | None:
        """When a batch last changed what the hub holds of the run (ISO 8601), or None."""
        ...

    def heartbeats(self) -> dict[str, tuple[Heartbeat, str]]:
        """Each host's latest heartbeat and when it arrived."""
        ...

    def delete_run(self, name: str, run_uid: str | None = None) -> bool:
        """Remove everything held of the run under `name` (its logs, documents, file refs
        and activity); with `run_uid`, only while the run held under `name` has that uid.
        Whether a run was removed; removing an absent run does nothing."""
        ...

    def delete_heartbeat(self, host_id: str) -> bool:
        """Remove the host's latest heartbeat; whether there was one."""
        ...

    def referenced_blobs(self, excluding: Collection[str] = ()) -> set[str]:
        """The SHA-256 of every file ref of every run held, except the runs named in `excluding`."""
        ...


class BlobItem(NamedTuple):
    """One blob as a listing gives it: its SHA-256, its size in bytes, and when it was stored."""

    sha256: str
    size: int
    modified: datetime


class BlobStore(Protocol):
    """File contents, named by their SHA-256."""

    def has(self, sha256: str) -> bool: ...

    def put(self, sha256: str, data: bytes) -> None:
        """Store `data`; `ValueError` when it does not hash to `sha256`. Storing a blob already
        held changes nothing, its `modified` included."""
        ...

    def get(self, sha256: str) -> bytes | None: ...

    def items(self) -> Iterator[BlobItem]:
        """Every blob held, in no particular order; `modified` is timezone-aware."""
        ...

    def delete(self, sha256: str) -> None:
        """Remove the blob; nothing happens when there is none."""
        ...


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha(sha256: str) -> bool:
    return len(sha256) == 64 and all(c in "0123456789abcdef" for c in sha256)


def _check(sha256: str, data: bytes) -> None:
    if not _is_sha(sha256):
        raise ValueError(f"not a SHA-256 in hex: {sha256!r}")
    if sha256_of(data) != sha256:
        raise ValueError(f"content does not hash to {sha256}")


@dataclass
class _Run:
    entry: RunRef
    logs: dict[str, list[str]] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)
    files: dict[str, FileRef] = field(default_factory=dict)
    received_at: str = ""


def _in_folder(doc: str, folder: str) -> bool:
    prefix = folder + "/"
    return doc.startswith(prefix) and "/" not in doc[len(prefix) :]


class MemoryHubStore:
    """A `HubStore` in memory; safe across threads."""

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}
        self._heartbeats: dict[str, tuple[Heartbeat, str]] = {}
        self._lock = threading.Lock()

    def put_batch(self, batch: RecordBatch, received_at: str) -> Accepted:
        ref = batch.run
        with self._lock:
            run = self._runs.get(ref.name)
            changed = run is None or run.entry.run_uid != ref.run_uid
            if run is None or changed:
                run = self._runs[ref.name] = _Run(ref.model_copy())
            held: dict[str, int] = {}
            for chunk in batch.logs:
                changed |= chunk.log not in run.logs
                lines = run.logs.setdefault(chunk.log, [])
                if chunk.offset <= len(lines):
                    new = chunk.lines[len(lines) - chunk.offset :]
                    changed |= bool(new)
                    lines.extend(new)
                held[chunk.log] = len(lines)
            for doc in batch.documents:
                if doc.text is None:
                    changed |= run.documents.pop(doc.name, None) is not None
                elif run.documents.get(doc.name) != doc.text:
                    run.documents[doc.name] = doc.text
                    changed = True
            for ref_file in batch.files:
                if run.files.get(ref_file.path) != ref_file:
                    run.files[ref_file.path] = ref_file
                    changed = True
            if changed:
                run.received_at = received_at
            return Accepted(logs=held)

    def put_heartbeat(self, heartbeat: Heartbeat, received_at: str) -> None:
        with self._lock:
            self._heartbeats[heartbeat.host_id] = (heartbeat, received_at)

    def runs(self) -> list[RunRef]:
        with self._lock:
            return [self._runs[n].entry for n in sorted(self._runs)]

    def entry(self, name: str) -> RunRef | None:
        with self._lock:
            run = self._runs.get(name)
            return run.entry if run else None

    def lines(self, name: str, log: str, since: int = 0, limit: int | None = None, max_bytes: int | None = None) -> tuple[list[str], int]:
        with self._lock:
            run = self._runs.get(name)
            every = run.logs.get(log, []) if run else []
            return page(every[since:], limit, max_bytes), len(every)

    def logs(self, name: str) -> list[str]:
        with self._lock:
            run = self._runs.get(name)
            return sorted(run.logs) if run else []

    def documents(self, name: str) -> list[str]:
        with self._lock:
            run = self._runs.get(name)
            return sorted(run.documents) if run else []

    def count(self, name: str, log: str) -> int:
        with self._lock:
            run = self._runs.get(name)
            return len(run.logs[log]) if run and log in run.logs else -1

    def document(self, name: str, doc: str) -> str | None:
        with self._lock:
            run = self._runs.get(name)
            return run.documents.get(doc) if run else None

    def folder(self, name: str, folder: str) -> list[str]:
        with self._lock:
            run = self._runs.get(name)
            if run is None:
                return []
            return [run.documents[d] for d in sorted(run.documents) if _in_folder(d, folder)]

    def exists(self, name: str, entry: str) -> bool:
        with self._lock:
            run = self._runs.get(name)
            if run is None:
                return False
            held = [*run.logs, *run.documents]
            return entry in held or any(k.startswith(entry + "/") for k in held)

    def file(self, name: str, path: str) -> FileRef | None:
        with self._lock:
            run = self._runs.get(name)
            return run.files.get(path) if run else None

    def activity(self, name: str) -> str | None:
        with self._lock:
            run = self._runs.get(name)
            return run.received_at or None if run else None

    def heartbeats(self) -> dict[str, tuple[Heartbeat, str]]:
        with self._lock:
            return dict(self._heartbeats)

    def delete_run(self, name: str, run_uid: str | None = None) -> bool:
        with self._lock:
            run = self._runs.get(name)
            if run is None or (run_uid is not None and run.entry.run_uid != run_uid):
                return False
            del self._runs[name]
            return True

    def delete_heartbeat(self, host_id: str) -> bool:
        with self._lock:
            return self._heartbeats.pop(host_id, None) is not None

    def referenced_blobs(self, excluding: Collection[str] = ()) -> set[str]:
        skip = set(excluding)
        with self._lock:
            return {f.sha256 for n, run in self._runs.items() if n not in skip for f in run.files.values() if f.sha256}


class MemoryBlobs:
    """A `BlobStore` in memory; `clock` (epoch seconds) dates each blob as it is stored. Safe
    across threads."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._blobs: dict[str, tuple[bytes, float]] = {}
        self._clock = clock or time.time
        self._lock = threading.Lock()

    def has(self, sha256: str) -> bool:
        with self._lock:
            return sha256 in self._blobs

    def put(self, sha256: str, data: bytes) -> None:
        _check(sha256, data)
        with self._lock:
            self._blobs.setdefault(sha256, (bytes(data), self._clock()))

    def get(self, sha256: str) -> bytes | None:
        with self._lock:
            got = self._blobs.get(sha256)
        return got[0] if got else None

    def items(self) -> Iterator[BlobItem]:
        with self._lock:
            held = list(self._blobs.items())
        for sha, (data, at) in held:
            yield BlobItem(sha, len(data), datetime.fromtimestamp(at, UTC))

    def delete(self, sha256: str) -> None:
        with self._lock:
            self._blobs.pop(sha256, None)


class DirectoryBlobs:
    """A `BlobStore` in a directory: `<root>/<sha[:2]>/<sha>`, written atomically
    (`write_document`)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, sha256: str) -> Path:
        if not _is_sha(sha256):
            raise ValueError(f"not a SHA-256 in hex: {sha256!r}")
        return self.root / sha256[:2] / sha256

    def has(self, sha256: str) -> bool:
        return self._path(sha256).is_file()

    def put(self, sha256: str, data: bytes) -> None:
        _check(sha256, data)
        path = self._path(sha256)
        if path.is_file():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        write_document(path, data)

    def get(self, sha256: str) -> bytes | None:
        try:
            return self._path(sha256).read_bytes()
        except OSError:
            return None

    def items(self) -> Iterator[BlobItem]:
        """Every blob file, dated by its modification time; temporary files are skipped."""
        if not self.root.is_dir():
            return
        for sub in os.scandir(self.root):
            if not sub.is_dir() or len(sub.name) != 2:
                continue
            for entry in os.scandir(sub.path):
                if not (entry.name.startswith(sub.name) and _is_sha(entry.name)):
                    continue
                try:
                    st = entry.stat()
                except FileNotFoundError:  # deleted meanwhile
                    continue
                yield BlobItem(entry.name, st.st_size, datetime.fromtimestamp(st.st_mtime, UTC))

    def delete(self, sha256: str) -> None:
        self._path(sha256).unlink(missing_ok=True)
