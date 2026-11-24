"""The wire between `contraagent relay` and `contraagent hub`: HTTP + JSON, so a relay in
another language can speak it.

    POST /ingest/records          RecordBatch -> Accepted
    POST /ingest/heartbeat        Heartbeat   -> HeartbeatAck
    HEAD /ingest/blobs/<sha256>   200 when the hub holds that content, else 404
    PUT  /ingest/blobs/<sha256>   the raw bytes; 204, or 400 when they do not hash to <sha256>
    GET  /healthz                 Health: 200 when every store answers, else 503 (no token)

Every ingest request carries `Authorization: Bearer <token>`, a token the hub was given for
ingest; a token bound to one host is refused (403) for another host's runs. A records or
heartbeat body may be sent with `Content-Encoding: gzip`. The full contract, with limits,
is `contraagent/_internal/hub/openapi.json`.

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

Every text of a request is made one the hub can hold (`text`) as the model is made, so
on the relay before it is sent and on the hub as it arrives: a lone surrogate is written
out as its escape, and a NUL outside a transcript's lines becomes SUB (U+001A). Both
keep the count of a log's lines.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from contraagent._internal.hub.streams import is_stream
from contraagent._internal.hub.text import SUB, record_text, record_value, wire_text

INGEST_RECORDS = "/ingest/records"
INGEST_HEARTBEAT = "/ingest/heartbeat"
INGEST_BLOB = "/ingest/blobs/{sha256}"
HEALTHZ = "/healthz"

#: A relay's TTL in heartbeat intervals, unless it is given one (`contraagent relay
#: --ttl`); the hub reads a heartbeat without a TTL as this many of its intervals.
TTL_INTERVALS = 4

WireText = Annotated[str, AfterValidator(wire_text)]
RecordText = Annotated[str, AfterValidator(record_text)]
RecordValue = Annotated[dict, AfterValidator(record_value)]


class RunRef(BaseModel):
    """Which run a batch or a liveness report is about."""

    host_id: RecordText
    run_id: RecordText
    run_uid: RecordText

    @property
    def name(self) -> str:
        """The run's name on the hub: `<run_id>@<host_id>`."""
        return hub_run_name(self.run_id, self.host_id)


def hub_run_name(run_id: str, host_id: str) -> str:
    """A run's name on the hub: `<run_id>@<host_id>`."""
    return f"{run_id}@{host_id}"


class LogChunk(BaseModel):
    """Complete lines of one append-only log, from line `offset` on."""

    log: RecordText = Field(description="the log's layout name: `journal.jsonl`, `streams/<key>.stream.jsonl`, ...")
    offset: int = Field(ge=0, description="the line index of `lines[0]` in the log")
    lines: list[WireText] = Field(description="complete lines, without their newline")

    @model_validator(mode="after")
    def _no_nul_outside_a_transcript(self) -> LogChunk:
        """A transcript is stored as bytes and keeps a NUL; any other log's lines are text."""
        if not is_stream(self.log):
            self.lines = [line.replace("\x00", SUB) for line in self.lines]
        return self


class DocumentPut(BaseModel):
    """A whole document of the run, or its removal."""

    name: RecordText = Field(description="the document's layout name: `run.json`, `contracts/<name>.json`, `inflight/<key>.json`, ...")
    text: RecordText | None = Field(description="the document's text; null when it was removed")


class FileRef(BaseModel):
    """A file one of the run's contracts names, as the run's host sees it."""

    path: RecordText = Field(description="the path as the contract names it")
    sha256: RecordText | None = Field(description="the content's SHA-256 (the blob's name); null when the file does not exist")
    size: int = 0
    mtime: RecordText = ""


class RecordBatch(BaseModel):
    """What changed in one run since the relay last sent it."""

    run: RunRef
    logs: list[LogChunk] = []
    documents: list[DocumentPut] = []
    files: list[FileRef] = []


class Accepted(BaseModel):
    """How many lines the hub holds of each log the batch named, after storing it, and how
    many of those are durable (in object storage or the database, so a hub that loses its
    own disk still has them). A relay resends from `logs`; lines past `durable` are on the
    hub's disk only."""

    logs: dict[str, int] = {}
    durable: dict[str, int] = {}


class RunLiveness(BaseModel):
    """One run the host drives, as its heartbeat reports it."""

    run: RunRef
    alive: bool
    snapshot: RecordValue = Field(description="the run's live processes, in `Liveness.snapshot`'s shape (`contraagent.monitor.Liveness`)")


class Heartbeat(BaseModel):
    """A host says it is up, and what its runs are doing. The hub counts the host as up
    for `ttl_s` seconds after it receives the heartbeat, by the hub's clock; the relay
    sets both `interval_s` and `ttl_s`."""

    host_id: RecordText
    sent_at: RecordText = Field(description="the host's clock, ISO 8601")
    interval_s: float = Field(gt=0, description="seconds until the next heartbeat")
    ttl_s: float = Field(
        gt=0,
        description="seconds the hub counts the host as up after it receives this heartbeat, more than interval_s; "
        f"a heartbeat without it is read as {TTL_INTERVALS} × interval_s",
    )
    runs: list[RunLiveness] = []

    @model_validator(mode="before")
    @classmethod
    def _default_ttl(cls, data: object) -> object:
        """A heartbeat without `ttl_s` has `TTL_INTERVALS` of its intervals."""
        if isinstance(data, dict) and "ttl_s" not in data and isinstance(interval := data.get("interval_s"), int | float):
            return {**data, "ttl_s": TTL_INTERVALS * interval}
        return data

    @model_validator(mode="after")
    def _ttl_past_interval(self) -> Heartbeat:
        if self.ttl_s <= self.interval_s:
            raise ValueError(f"ttl_s ({self.ttl_s:g}) must be more than interval_s ({self.interval_s:g})")
        return self


class HeartbeatAck(BaseModel):
    """The TTL the hub keeps for the heartbeat: how long it counts the host as up
    without another."""

    ttl_s: float


class Health(BaseModel):
    """Whether each of the hub's stores answered a trivial read: `ok` when all did, else
    `failing` with the stores that did not (`records`, `blobs`, `transcripts`) and the
    kind of error each raised."""

    status: Literal["ok", "failing"]
    failed: dict[str, str] = {}
