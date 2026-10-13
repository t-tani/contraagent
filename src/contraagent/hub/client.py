"""How a relay reaches a hub: `HubClient`. `DirectClient` calls a `Hub` in the same
process (tests, a relay and a hub in one program)."""

from __future__ import annotations

from typing import Protocol

from contraagent.hub.core import Hub
from contraagent.hub.protocol import Accepted, Heartbeat, HeartbeatAck, RecordBatch


class HubClient(Protocol):
    """The four requests of the protocol (`protocol.py`)."""

    def send_records(self, batch: RecordBatch) -> Accepted: ...

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck: ...

    def has_blob(self, sha256: str) -> bool: ...

    def put_blob(self, sha256: str, data: bytes) -> None: ...


class DirectClient:
    """A `HubClient` that calls a `Hub` in-process."""

    def __init__(self, hub: Hub) -> None:
        self.hub = hub

    def send_records(self, batch: RecordBatch) -> Accepted:
        return self.hub.records(RecordBatch.model_validate(batch.model_dump()))

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        return self.hub.heartbeat(Heartbeat.model_validate(heartbeat.model_dump()))

    def has_blob(self, sha256: str) -> bool:
        return self.hub.has_blob(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        self.hub.put_blob(sha256, data)
