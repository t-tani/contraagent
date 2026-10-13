"""The hub, framework-free: what it does with each request, and the monitor it serves.

`contraagent hub` (`server.py`) is a thin HTTP shell over `Hub`; `client.DirectClient`
calls it in-process.

A batch is split by what its logs are: task transcripts (`streams.is_stream`) go to the
`StreamLogs`, everything else to the `HubStore`. A journal row in a batch ends its task, so
the task's transcript is closed (it will not grow, and may be sealed).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from contraagent import rundir
from contraagent.hub.protocol import Accepted, Heartbeat, HeartbeatAck, LogChunk, RecordBatch
from contraagent.hub.source import DEFAULT_TTL_S, HeartbeatLiveness, HubSource
from contraagent.hub.store import BlobStore, HubStore
from contraagent.hub.streams import MemoryStreamLogs, StreamLogs, is_stream
from contraagent.monitor import Monitor


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _ended_tasks(chunk: LogChunk) -> set[str]:
    """The task keys whose journal rows a journal chunk carries."""
    keys = set()
    for line in chunk.lines:
        try:
            key = json.loads(line).get("key")
        except (ValueError, AttributeError):
            continue
        if isinstance(key, str) and key:
            keys.add(key)
    return keys


class Hub:
    """Receives relays' batches, heartbeats and blobs, and serves the monitor over them."""

    def __init__(self, store: HubStore, blobs: BlobStore, *, streams: StreamLogs | None = None, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.store = store
        self.blobs = blobs
        self.streams: StreamLogs = streams if streams is not None else MemoryStreamLogs()
        self.ttl_s = ttl_s

    def records(self, batch: RecordBatch) -> Accepted:
        received = utcnow_iso()
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
            if chunk.log == rundir.JOURNAL:
                for key in _ended_tasks(chunk):
                    self.streams.close(name, uid, rundir.stream(key))
        return Accepted(logs=logs, durable=durable)

    def heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        self.store.put_heartbeat(heartbeat, utcnow_iso())
        return HeartbeatAck(ttl_s=self.ttl_s)

    def has_blob(self, sha256: str) -> bool:
        return self.blobs.has(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        """Store a blob; `ValueError` when `data` does not hash to `sha256`."""
        self.blobs.put(sha256, data)

    def source(self) -> HubSource:
        return HubSource(self.store, self.blobs, self.streams)

    def monitor(self, **kwargs) -> Monitor:
        """The monitor's views of every host's runs (`Monitor`'s keyword arguments pass through)."""
        return Monitor(source=self.source(), liveness=HeartbeatLiveness(self.store, self.ttl_s), **kwargs)
