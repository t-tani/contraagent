"""The wire between `contraagent relay` and `contraagent hub`: HTTP + JSON, so a relay in
another language can speak it.

    POST /ingest/records          RecordBatch -> Accepted
    POST /ingest/heartbeat        Heartbeat   -> HeartbeatAck
    HEAD /ingest/blobs/<sha256>   200 when the hub holds that content, else 404
    PUT  /ingest/blobs/<sha256>   the raw bytes; 204, or 400 when they do not hash to <sha256>

Every request carries `Authorization: Bearer <token>`, a token the hub was given for
ingest.

Delivery is at least once, and storing is idempotent:

* A log chunk (`LogChunk`) names the line offset of its first line. The hub keeps the
  lines it does not hold yet, drops the ones it does, and refuses a chunk that would
  leave a gap. `Accepted.logs` tells the relay how many lines the hub holds of each log
  it sent, which is where the relay continues from.
* A document (`DocumentPut`) replaces the hub's copy whole; `text: null` removes it
  (an in-flight marker that is gone).
* A file a contract names (`FileRef`) is sent as its SHA-256; its content goes to the
  blob store once, by hash.

A run is named on the hub `<run_id>@<host_id>` (`RunRef.name`), a plain name no run of
another host has.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

INGEST_RECORDS = "/ingest/records"
INGEST_HEARTBEAT = "/ingest/heartbeat"
INGEST_BLOB = "/ingest/blobs/{sha256}"


class RunRef(BaseModel):
    """Which run a batch or a liveness report is about."""

    host_id: str
    run_id: str
    run_uid: str

    @property
    def name(self) -> str:
        """The run's name on the hub: `<run_id>@<host_id>`."""
        return hub_run_name(self.run_id, self.host_id)


def hub_run_name(run_id: str, host_id: str) -> str:
    """A run's name on the hub: `<run_id>@<host_id>`."""
    return f"{run_id}@{host_id}"


class LogChunk(BaseModel):
    """Complete lines of one append-only log, from line `offset` on."""

    log: str = Field(description="the log's layout name: `journal.jsonl`, `streams/<key>.stream.jsonl`, ...")
    offset: int = Field(ge=0, description="the line index of `lines[0]` in the log")
    lines: list[str] = Field(description="complete lines, without their newline")


class DocumentPut(BaseModel):
    """A whole document of the run, or its removal."""

    name: str = Field(description="the document's layout name: `run.json`, `contracts/<name>.json`, `inflight/<key>.json`, ...")
    text: str | None = Field(description="the document's text; null when it was removed")


class FileRef(BaseModel):
    """A file one of the run's contracts names, as the run's host sees it."""

    path: str = Field(description="the path as the contract names it")
    sha256: str | None = Field(description="the content's SHA-256 (the blob's name); null when the file does not exist")
    size: int = 0
    mtime: str = ""


class RecordBatch(BaseModel):
    """What changed in one run since the relay last sent it."""

    run: RunRef
    logs: list[LogChunk] = []
    documents: list[DocumentPut] = []
    files: list[FileRef] = []


class Accepted(BaseModel):
    """How many lines the hub holds of each log the batch named, after storing it."""

    logs: dict[str, int] = {}


class RunLiveness(BaseModel):
    """One run the host drives, as its heartbeat reports it."""

    run: RunRef
    alive: bool
    snapshot: dict = Field(description="the run's live processes, in `monitor.procs.snapshot`'s shape")


class Heartbeat(BaseModel):
    """A host says it is up, and what its runs are doing."""

    host_id: str
    sent_at: str = Field(description="the host's clock, ISO 8601")
    interval_s: float = Field(gt=0, description="seconds until the next heartbeat")
    runs: list[RunLiveness] = []


class HeartbeatAck(BaseModel):
    """How long the hub counts the host as up without another heartbeat."""

    ttl_s: float
