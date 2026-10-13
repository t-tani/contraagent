"""The hub, framework-free: what it does with each request, and the monitor it serves.

`contraagent hub` (`server.py`) is a thin HTTP shell over `Hub`; `client.DirectClient`
calls it in-process.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contraagent.hub.protocol import Accepted, Heartbeat, HeartbeatAck, RecordBatch
from contraagent.hub.source import DEFAULT_TTL_S, HeartbeatLiveness, HubSource
from contraagent.hub.store import BlobStore, HubStore
from contraagent.monitor import Monitor


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Hub:
    """Receives relays' batches, heartbeats and blobs, and serves the monitor over them."""

    def __init__(self, store: HubStore, blobs: BlobStore, *, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.store = store
        self.blobs = blobs
        self.ttl_s = ttl_s

    def records(self, batch: RecordBatch) -> Accepted:
        return self.store.put_batch(batch, utcnow_iso())

    def heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        self.store.put_heartbeat(heartbeat, utcnow_iso())
        return HeartbeatAck(ttl_s=self.ttl_s)

    def has_blob(self, sha256: str) -> bool:
        return self.blobs.has(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        """Store a blob; `ValueError` when `data` does not hash to `sha256`."""
        self.blobs.put(sha256, data)

    def monitor(self, **kwargs) -> Monitor:
        """The monitor's views of every host's runs (`Monitor`'s keyword arguments pass through)."""
        return Monitor(source=HubSource(self.store, self.blobs), liveness=HeartbeatLiveness(self.store, self.ttl_s), **kwargs)
