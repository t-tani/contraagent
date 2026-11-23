"""The hub, framework-free: what it does with each request, and the monitor it serves.

`contraagent hub` (`server.py`) is a thin HTTP shell over `Hub`, and serves the monitor
over `Hub.source()` and `Hub.liveness()`; `client.DirectClient` calls it in-process.

A batch is split by what its logs are: task transcripts (`streams.is_stream`) go to the
`StreamLogs`, everything else to the `HubStore`. A journal row in a batch ends its task, so
the task's transcript is closed (it will not grow, and may be sealed).

`Hub.prune` is the hub's retention: it removes old runs, the transcripts of runs the hub no
longer holds, heartbeats of hosts long gone, and blobs no file ref references.

The host of a pruned run may still hold the run, and its relay asks from time to time how
many lines of each log the hub holds, to send the run again to a hub that lost lines. The
hub remembers each run it pruned (`HubStore.pruned`) and answers such a request without
storing the run again (`pruned_answer`). A request that brings a line the hub did not hold
when it pruned the run shows the run active again: the hub forgets the prune and stores
the run from its start, which the relay then sends.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from contraagent._internal.hub.protocol import Accepted, Heartbeat, HeartbeatAck, LogChunk, RecordBatch
from contraagent._internal.hub.source import HeartbeatLiveness, HubSource
from contraagent._internal.hub.store import BlobStore, HubStore, PrunedRun
from contraagent._internal.hub.streams import MemoryStreamLogs, StreamLogs, is_stream
from contraagent._internal.runs import layout, times
from contraagent._internal.runs.files import iter_rows
from contraagent._internal.runs.times import now_iso, parse_iso

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


def pruned_answer(pruned: PrunedRun, chunks: Sequence[LogChunk]) -> dict[str, int] | None:
    """What the hub answers a request for a run it pruned, without storing it: for each log
    the request names, the lines the hub held when it pruned the run, or the chunk's offset
    when that is more, so that the relay finds no line lost. None when a chunk brings a line
    past those the hub held: the run is active again, and is stored."""
    held: dict[str, int] = {}
    for chunk in chunks:
        was = pruned.logs.get(chunk.log, 0)
        if chunk.lines and chunk.offset + len(chunk.lines) > was:
            return None
        held[chunk.log] = max(was, chunk.offset)
    return held


class Hub:
    """Receives relays' batches, heartbeats and blobs, and serves the monitor over them."""

    def __init__(self, store: HubStore, blobs: BlobStore, *, streams: StreamLogs | None = None) -> None:
        self.store = store
        self.blobs = blobs
        self.streams: StreamLogs = streams if streams is not None else MemoryStreamLogs()

    def records(self, batch: RecordBatch) -> Accepted:
        received = now_iso("milliseconds")
        pruned = self.store.pruned(batch.run.name)
        if pruned is not None:
            held = pruned_answer(pruned, batch.logs) if pruned.run_uid == batch.run.run_uid else None
            if held is not None:
                return Accepted(logs=held, durable=dict(held))
            self.store.forget_pruned(batch.run.name)  # active again, or another run under the name
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
        return HeartbeatAck(ttl_s=heartbeat.ttl_s)

    def has_blob(self, sha256: str) -> bool:
        """Whether the hub holds the blob, for a relay that is about to send a file ref of
        it. A held blob is renewed (`BlobStore.renew`): the relay sends the file ref without
        the content, and retention keeps the blob for its grace from now, also while no
        file ref names it yet."""
        return self.blobs.renew(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        """Store a blob; `ValueError` when `data` does not hash to `sha256`."""
        self.blobs.put(sha256, data)

    def source(self) -> HubSource:
        """Every host's runs, as a run source (what the hub's monitor reads)."""
        return HubSource(self.store, self.blobs, self.streams)

    def liveness(self) -> HeartbeatLiveness:
        """Which of the runs are live, by their hosts' heartbeats."""
        return HeartbeatLiveness(self.store)

    def close(self) -> None:
        """Shut down the transcripts (`SegmentedStreamLogs.shutdown`, when they have one) and
        close the store; the hub is not used after."""
        shutdown = getattr(self.streams, "shutdown", None)
        try:
            if shutdown is not None:
                shutdown()
        finally:
            self.store.close()

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

        * **Runs.** An old run is removed whole: its records (`HubStore.prune_run`, only
          while it still has the run uid read), with which the hub remembers it as pruned,
          so that its relay does not send it again, and then its transcripts
          (`StreamLogs.drop`: index rows, then segment objects, then open segment files).
          Never removed:
          a live run, an unresponsive one (its host stopped reporting while it was alive:
          its records are the evidence; remove it by hand with `HubStore.delete_run`), and
          one with no activity time at all (logged).
        * **Transcripts** of a run the hub no longer holds under their run uid (replaced by
          a new run uid, or left by a prune that failed between the two steps) are removed
          once their activity is old.
        * **Heartbeats** older than `older_than` are removed, except that of a host that is
          up (within the heartbeat's TTL: the runs it reports are live by it) and one that
          reports an unresponsive run the hub still holds.
        * **Blobs** are removed by mark and sweep: every blob is listed first, then the file
          refs of the runs kept are read, then each blob none of them references is removed
          when it is still dated before `blob_grace` ago as it is removed
          (`BlobStore.expire`). A relay that names a blob the hub already holds asks for it
          first (`has_blob`), which renews the blob, so the blob stays while the file ref is
          on its way, however long the prune takes. A file ref loses its content only when
          it arrives more than `blob_grace` after its relay asked; or when its relay asks in
          the moment between the blob store's look at the blob's date and its removal
          (`DirectoryBlobs`, `S3Blobs`).

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
        liveness = HeartbeatLiveness(self.store, clock=now.timestamp)
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
            # The records go first, with the memory of the prune in the same step: from then on
            # the run's relay is answered by it (`pruned_answer`), also when the transcripts
            # are still to go. Their lines are counted before, for that answer.
            removed = dry_run
            if not dry_run:
                transcripts = {log: self.streams.count(name, uid, log) for log in self.streams.logs(name, uid)}
                removed = self.store.prune_run(name, uid, transcripts, now.isoformat(timespec="milliseconds"))
            segments = self.streams.drop(name, uid, dry_run=dry_run)
            if removed:
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

        up = {host["host_id"] for host in liveness.hosts() if host["up"]}
        for host_id, (heartbeat, received_at) in sorted(self.store.heartbeats().items()):
            at = parse_iso(received_at)
            if at is None or at >= cutoff or host_id in up:  # a host that is up keeps its runs live
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
                if not dry_run and not self.blobs.expire(blob.sha256, now - blob_grace):
                    continue  # renewed since it was listed: a relay asked for it, and its file ref is on its way
                report.blobs.append(blob.sha256)
                report.blob_bytes += blob.size
        return report
