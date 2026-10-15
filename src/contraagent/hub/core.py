"""The hub, framework-free: what it does with each request, and the monitor it serves.

`contraagent hub` (`server.py`) is a thin HTTP shell over `Hub`, and serves the monitor
over `Hub.source()` and `Hub.liveness()`; `client.DirectClient` calls it in-process.

A batch is split by what its logs are: task transcripts (`streams.is_stream`) go to the
`StreamLogs`, everything else to the `HubStore`. A journal row in a batch ends its task, so
the task's transcript is closed (it will not grow, and may be sealed).

`Hub.prune` is the hub's retention: it removes old runs, the transcripts of runs the hub no
longer holds, heartbeats of hosts long gone, and blobs no file ref references.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from contraagent.hub.protocol import Accepted, Heartbeat, HeartbeatAck, LogChunk, RecordBatch
from contraagent.hub.source import DEFAULT_TTL_S, HeartbeatLiveness, HubSource
from contraagent.hub.store import BlobStore, HubStore
from contraagent.hub.streams import MemoryStreamLogs, StreamLogs, is_stream
from contraagent.runs import layout, times
from contraagent.runs.files import iter_rows
from contraagent.runs.times import now_iso, parse_iso

log_ = logging.getLogger(__name__)

#: How old a blob no file ref references must be before `Hub.prune` deletes it: a relay
#: uploads a blob before it sends the file ref that names it.
BLOB_GRACE = timedelta(days=1)


@dataclass
class PruneReport:
    """What `Hub.prune` removed, or with `dry_run` would remove, and the old runs and
    heartbeats it kept, with why."""

    dry_run: bool
    #: Activity before this time (ISO 8601) is old.
    cutoff: str
    #: The runs removed, by hub name.
    runs: list[str] = field(default_factory=list)
    #: (name, run uid) of the transcripts removed whose run the hub no longer held under
    #: that uid: the run was replaced by a new run uid, or its records were removed first.
    transcripts: list[tuple[str, str]] = field(default_factory=list)
    #: The object keys of the sealed segments removed, of both.
    segments: list[str] = field(default_factory=list)
    #: The blobs removed, by SHA-256, and their bytes in all.
    blobs: list[str] = field(default_factory=list)
    blob_bytes: int = 0
    #: The heartbeats removed, by host id.
    heartbeats: list[str] = field(default_factory=list)
    #: Old runs kept, and why: "live", "unresponsive", or "no activity" (it has no activity
    #: time at all, old or not).
    kept_runs: dict[str, str] = field(default_factory=dict)
    #: Old heartbeats kept, and why: "unresponsive run" (it reports a run alive that is
    #: unresponsive and held: the run's evidence).
    kept_heartbeats: dict[str, str] = field(default_factory=dict)


def _ended_tasks(chunk: LogChunk) -> set[str]:
    """The task keys whose journal rows a journal chunk carries."""
    return {key for row in iter_rows(chunk.lines) if isinstance(key := row.get("key"), str) and key}


class Hub:
    """Receives relays' batches, heartbeats and blobs, and serves the monitor over them."""

    def __init__(self, store: HubStore, blobs: BlobStore, *, streams: StreamLogs | None = None, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.store = store
        self.blobs = blobs
        self.streams: StreamLogs = streams if streams is not None else MemoryStreamLogs()
        self.ttl_s = ttl_s

    def records(self, batch: RecordBatch) -> Accepted:
        received = now_iso("milliseconds")
        transcripts = [c for c in batch.logs if is_stream(c.log)]
        rest = batch.model_copy(update={"logs": [c for c in batch.logs if not is_stream(c.log)]})
        accepted = self.store.put_batch(rest, received)
        logs = dict(accepted.logs)
        durable = {log: accepted.durable.get(log, n) for log, n in accepted.logs.items()}
        name, uid = batch.run.name, batch.run.run_uid
        for chunk in transcripts:
            held = self.streams.append(name, uid, chunk.log, chunk.offset, chunk.lines, received)
            logs[chunk.log], durable[chunk.log] = held.held, held.durable
        for chunk in rest.logs:
            if chunk.log == layout.JOURNAL:
                for key in _ended_tasks(chunk):
                    self.streams.close(name, uid, layout.stream(key))
        return Accepted(logs=logs, durable=durable)

    def heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        self.store.put_heartbeat(heartbeat, now_iso("milliseconds"))
        return HeartbeatAck(ttl_s=self.ttl_s)

    def has_blob(self, sha256: str) -> bool:
        return self.blobs.has(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        """Store a blob; `ValueError` when `data` does not hash to `sha256`."""
        self.blobs.put(sha256, data)

    def source(self) -> HubSource:
        """Every host's runs, as a run source (what the hub's monitor reads)."""
        return HubSource(self.store, self.blobs, self.streams)

    def liveness(self) -> HeartbeatLiveness:
        """Which of the runs are live, by their hosts' heartbeats."""
        return HeartbeatLiveness(self.store, self.ttl_s)

    # --- retention -------------------------------------------------------------------------

    def _activity(self, name: str, uid: str) -> datetime | None:
        times = [t for t in (parse_iso(self.store.activity(name)), parse_iso(self.streams.activity(name, uid))) if t]
        return max(times) if times else None

    def prune(
        self,
        *,
        older_than: timedelta,
        blob_grace: timedelta = BLOB_GRACE,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> PruneReport:
        """Remove what the hub holds of runs whose activity (`HubSource.activity`) is older
        than `older_than` before `now` (default: the current time), and what nothing
        references; with `dry_run`, remove nothing and report the same.

        * **Runs.** An old run is removed whole: its transcripts (`StreamLogs.drop`: index
          rows, then segment objects, then open segment files) and then its records
          (`HubStore.delete_run`, only while it still has the run uid read). Never removed:
          a live run, an unresponsive one (its host stopped reporting while it was alive:
          its records are the evidence; remove it by hand with `HubStore.delete_run`), and
          one with no activity time at all (logged).
        * **Transcripts** of a run the hub no longer holds under their run uid (replaced by
          a new run uid, or left by a prune that failed between the two steps) are removed
          once their activity is old.
        * **Heartbeats** older than `older_than` are removed, except one that reports an
          unresponsive run the hub still holds.
        * **Blobs** are removed by mark and sweep: every blob is listed first, then the file
          refs of the runs kept are read, then each blob none of them references is deleted
          when it is older than `blob_grace`. A file ref that arrives between the reading
          and the deleting and names an old blob already held loses its content.

        Every step can be repeated: an exception (a lost connection, a crash) leaves what
        a second call completes, or orphan segment objects that `SegmentedStreamLogs.sweep`
        deletes. A run that receives a batch while it is removed starts again from what its
        relay sends. Ingest goes on meanwhile; run it from one hub process at a time.

        How often: once a day, or every hour for a short `older_than`. Each call reads every
        run's activity and lists every blob; when nothing is old it does no more.
        """
        now = now or times.now()
        cutoff = now - older_than
        report = PruneReport(dry_run=dry_run, cutoff=cutoff.isoformat(timespec="milliseconds"))
        liveness = HeartbeatLiveness(self.store, self.ttl_s, clock=now.timestamp)
        live, unresponsive = liveness.live(), liveness.unresponsive()

        held: dict[str, str] = {}
        for entry in self.store.runs():
            name, uid = entry.name, entry.run_uid
            held[name] = uid
            at = self._activity(name, uid)
            if at is None:
                log_.warning("run %s has no activity time: kept", name)
                report.kept_runs[name] = "no activity"
                continue
            if at >= cutoff:
                continue
            if name in live or name in unresponsive:
                report.kept_runs[name] = "live" if name in live else "unresponsive"
                continue
            segments = self.streams.drop(name, uid, dry_run=dry_run)
            if dry_run or self.store.delete_run(name, uid):
                log_.info("%s run %s (last activity %s)", "would remove" if dry_run else "removed", name, at.isoformat())
                report.runs.append(name)
            report.segments.extend(segments)

        for name, uid in sorted(self.streams.runs()):
            if held.get(name) == uid:
                continue
            at = parse_iso(self.streams.activity(name, uid))
            if at is None:
                log_.warning("transcripts of %s (run uid %s) have no activity time: kept", name, uid)
                continue
            if at >= cutoff:
                continue
            entry = self.store.entry(name)
            if entry is not None and entry.run_uid == uid:  # a run that arrived after the listing
                continue
            report.segments.extend(self.streams.drop(name, uid, dry_run=dry_run))
            report.transcripts.append((name, uid))

        for host_id, (heartbeat, received_at) in sorted(self.store.heartbeats().items()):
            at = parse_iso(received_at)
            if at is None or at >= cutoff:
                continue
            if any(r.alive and r.run.name in unresponsive and r.run.name in held for r in heartbeat.runs):
                report.kept_heartbeats[host_id] = "unresponsive run"
                continue
            if not dry_run:
                self.store.delete_heartbeat(host_id)
            report.heartbeats.append(host_id)

        old_blobs = sorted(b for b in self.blobs.items() if b.modified < now - blob_grace)
        if old_blobs:
            referenced = self.store.referenced_blobs(excluding=report.runs)
            for blob in old_blobs:
                if blob.sha256 in referenced:
                    continue
                if not dry_run:
                    self.blobs.delete(blob.sha256)
                report.blobs.append(blob.sha256)
                report.blob_bytes += blob.size
        return report
