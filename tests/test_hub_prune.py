"""`Hub.prune`, the hub's retention: old runs go whole (records, transcripts' index rows,
segment objects and open segment files), live, unresponsive and recent runs stay, blobs go
by mark and sweep after their grace period, old heartbeats go; a dry run reports the same
and changes nothing; every step can be repeated after a crash.

`HUBS` lists the stores under test: everything in memory, and Postgres with S3 (RustFS)."""

import dataclasses
import hashlib
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from contraagent import rundir
from contraagent.hub.core import Hub
from contraagent.hub.protocol import DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent.hub.segment_objects import MemorySegmentObjects, S3SegmentObjects
from contraagent.hub.segments import MemorySegmentIndex, PostgresSegmentIndex, SegmentedStreamLogs
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that stops the containers
    postgres_dsn,
    s3_url,
)

pytestmark = pytest.mark.usefixtures("hub_services")

NOW = datetime.now(UTC).replace(microsecond=0)
OLD = NOW - timedelta(days=40)
RECENT = NOW - timedelta(days=1)
RETAIN = timedelta(days=30)
LOG, OTHER = rundir.stream("summarize-a"), rundir.stream("summarize-b")


def iso(at: datetime) -> str:
    return at.isoformat(timespec="milliseconds")


def _memory(tmp: Path) -> Hub:
    streams = SegmentedStreamLogs(tmp / "hot", MemorySegmentObjects(), MemorySegmentIndex(), block_bytes=1024, background=False)
    return Hub(MemoryHubStore(), MemoryBlobs(), streams=streams)


def _postgres_s3(tmp: Path) -> Hub:
    from contraagent.hub.postgres import PostgresHubStore
    from contraagent.hub.s3 import S3Blobs

    dsn = postgres_dsn()
    streams = SegmentedStreamLogs(tmp / "hot", S3SegmentObjects(s3_url()), PostgresSegmentIndex(dsn), block_bytes=1024, background=False)
    return Hub(PostgresHubStore(dsn), S3Blobs(s3_url()), streams=streams)


HUBS: dict[str, Callable[[Path], Hub]] = {"memory": _memory, "postgres-s3": _postgres_s3}


@pytest.fixture(params=sorted(HUBS))
def hub(request, tmp_path) -> Hub:
    return HUBS[request.param](tmp_path)


def segmented(hub: Hub) -> SegmentedStreamLogs:
    assert isinstance(hub.streams, SegmentedStreamLogs)
    return hub.streams


def blob(hub: Hub, data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    hub.put_blob(sha, data)
    return sha


def ship(hub: Hub, run_id: str, at: datetime, *, host: str = "h1", uid: str | None = None, files: dict[str, str] | None = None) -> str:
    """A run with records, a file ref per `files` (path: sha256), a sealed transcript (`LOG`)
    and an open one (`OTHER`), all received at `at`; its hub name."""
    ref = RunRef(host_id=host, run_id=run_id, run_uid=uid or f"uid-{run_id}")
    refs = [FileRef(path=p, sha256=sha, size=1, mtime="m") for p, sha in (files or {}).items()]
    docs = [DocumentPut(name=rundir.RUN_INFO, text=f'{{"run_id": "{run_id}"}}')]
    journal = LogChunk(log=rundir.JOURNAL, offset=0, lines=['{"key": "summarize-a", "ok": true}'])
    hub.store.put_batch(RecordBatch(run=ref, logs=[journal], documents=docs, files=refs), iso(at))
    streams = hub.streams
    streams.append(ref.name, ref.run_uid, LOG, 0, [f'{{"i": {i}, "pad": "{"x" * 50}"}}' for i in range(200)], iso(at))
    streams.close(ref.name, ref.run_uid, LOG)
    streams.append(ref.name, ref.run_uid, OTHER, 0, ["open"], iso(at))
    return ref.name


def heartbeat(hub: Hub, host: str, at: datetime, alive: list[str] = ()) -> None:
    runs = [RunLiveness(run=RunRef(host_id=host, run_id=r, run_uid=f"uid-{r}"), alive=True, snapshot={}) for r in alive]
    hub.store.put_heartbeat(Heartbeat(host_id=host, sent_at=iso(at), interval_s=3, runs=runs), iso(at))


def objects_of(hub: Hub, name: str) -> list[str]:
    return segmented(hub).objects.keys(f"{name}/")


def hot_files_of(hub: Hub, tmp_path: Path) -> list[Path]:
    return [p for p in (tmp_path / "hot").rglob("*.jsonl")]


# --- runs --------------------------------------------------------------------------------


def test_old_runs_go_and_live_unresponsive_and_recent_runs_stay(hub, tmp_path):
    old = ship(hub, "old", OLD)
    recent = ship(hub, "recent", RECENT)
    live = ship(hub, "live", OLD, host="h2")
    heartbeat(hub, "h2", NOW - timedelta(seconds=5), alive=["live"])
    unresponsive = ship(hub, "lost", OLD, host="h3")
    heartbeat(hub, "h3", OLD, alive=["lost"])
    finished = ship(hub, "finished", OLD, host="h4")  # its host's last heartbeat reported it alive, but run.json says it finished
    finished_info = DocumentPut(name=rundir.RUN_INFO, text='{"run_id": "finished", "finished_at": "x"}')
    hub.store.put_batch(
        RecordBatch(run=RunRef(host_id="h4", run_id="finished", run_uid="uid-finished"), documents=[finished_info]), iso(OLD)
    )
    heartbeat(hub, "h4", OLD, alive=["finished"])

    report = hub.prune(older_than=RETAIN, now=NOW)

    assert sorted(report.runs) == sorted([old, finished])
    assert report.kept_runs == {live: "live", unresponsive: "unresponsive"}
    assert sorted(e.name for e in hub.store.runs()) == sorted([recent, live, unresponsive])
    for name in (recent, live, unresponsive):
        uid = hub.store.entry(name).run_uid  # type: ignore[union-attr]
        assert hub.streams.count(name, uid, LOG) == 200 and hub.streams.read(name, uid, OTHER, 0) == (["open"], 1)
    # a second prune finds nothing more to remove
    again = hub.prune(older_than=RETAIN, now=NOW)
    assert again.runs == [] and again.segments == [] and again.transcripts == []


def test_a_removed_runs_transcripts_go_index_rows_objects_and_open_segment_files(hub, tmp_path):
    old = ship(hub, "old", OLD)
    kept = ship(hub, "kept", RECENT)
    streams = segmented(hub)
    sealed = objects_of(hub, old)
    assert sealed and streams.index.segments(old, "uid-old", LOG)
    assert any(quote_part(old) in p.parts for p in hot_files_of(hub, tmp_path))

    report = hub.prune(older_than=RETAIN, now=NOW)

    assert report.runs == [old] and report.segments == sealed
    assert objects_of(hub, old) == [] and streams.index.segments(old, "uid-old", LOG) == []
    assert streams.index.logs(old, "uid-old") == [] and streams.index.activity(old, "uid-old") is None
    assert (old, "uid-old") not in streams.runs()
    assert not any(quote_part(old) in p.parts for p in hot_files_of(hub, tmp_path))
    assert hub.source().activity(old) is None and hub.source().runs() == [kept]
    assert objects_of(hub, kept) and any(quote_part(kept) in p.parts for p in hot_files_of(hub, tmp_path))


def quote_part(name: str) -> str:
    from urllib.parse import quote

    return quote(name, safe="")


def test_a_run_with_no_activity_time_stays(tmp_path):
    hub = _memory(tmp_path)
    hub.store.put_batch(RecordBatch(run=RunRef(host_id="h", run_id="r", run_uid="u")), "")
    report = hub.prune(older_than=RETAIN, now=NOW)
    assert report.runs == [] and report.kept_runs == {"r@h": "no activity"}


def test_transcripts_of_a_replaced_run_uid_go_once_old(hub, tmp_path):
    name = ship(hub, "r", OLD, uid="first")
    ship(hub, "r", RECENT, uid="second")  # a new run under the same name replaces the records
    report = hub.prune(older_than=RETAIN, now=NOW)
    assert report.runs == [] and report.transcripts == [(name, "first")]
    assert hub.streams.count(name, "first", LOG) == -1 and objects_of(hub, f"{name}/first") == []
    assert hub.streams.count(name, "second", LOG) == 200


# --- blobs -------------------------------------------------------------------------------


def test_a_blob_shared_with_a_kept_run_stays(hub, tmp_path):
    shared, own = blob(hub, b"shared"), blob(hub, b"only the old run")
    ship(hub, "old", OLD, files={"/w/a": shared, "/w/b": own})
    ship(hub, "kept", RECENT, files={"/w/a": shared})
    later = NOW + timedelta(days=2)  # every blob is past its grace period
    report = hub.prune(older_than=RETAIN, now=later)
    assert report.runs == ["old@h1"] and report.blobs == [own] and report.blob_bytes == len(b"only the old run")
    assert hub.blobs.has(shared) and not hub.blobs.has(own)
    assert hub.source().file("kept@h1", "/w/a") == ("shared", 1, "m")


def test_an_unreferenced_blob_stays_while_young_and_goes_when_old(hub, tmp_path):
    young = blob(hub, b"uploaded before its file ref")
    assert hub.prune(older_than=RETAIN, now=NOW).blobs == []
    assert hub.blobs.has(young)
    report = hub.prune(older_than=RETAIN, now=NOW + timedelta(days=2))
    assert report.blobs == [young] and not hub.blobs.has(young)
    assert hub.prune(older_than=RETAIN, now=NOW + timedelta(days=2), blob_grace=timedelta(days=3)).blobs == []


# --- heartbeats --------------------------------------------------------------------------


def test_old_heartbeats_go_unless_they_report_an_unresponsive_run(hub, tmp_path):
    heartbeat(hub, "gone", OLD)
    heartbeat(hub, "up", NOW - timedelta(seconds=1))
    ship(hub, "lost", OLD, host="lost-host")
    heartbeat(hub, "lost-host", OLD, alive=["lost"])
    report = hub.prune(older_than=RETAIN, now=NOW)
    assert report.heartbeats == ["gone"] and report.kept_heartbeats == {"lost-host": "unresponsive run"}
    assert set(hub.store.heartbeats()) == {"up", "lost-host"}
    # once the unresponsive run is removed by hand, its host's heartbeat goes too
    hub.store.delete_run("lost@lost-host")
    assert hub.prune(older_than=RETAIN, now=NOW).heartbeats == ["lost-host"]


# --- a dry run ---------------------------------------------------------------------------


def test_a_dry_run_changes_nothing_and_reports_the_same(hub, tmp_path):
    shared, own, stray = blob(hub, b"shared"), blob(hub, b"own"), blob(hub, b"stray")
    ship(hub, "old", OLD, files={"/a": shared, "/b": own})
    ship(hub, "kept", RECENT, files={"/a": shared})
    ship(hub, "r", OLD, uid="first")
    ship(hub, "r", RECENT, uid="second")
    ship(hub, "lost", OLD, host="h3")
    heartbeat(hub, "h3", OLD, alive=["lost"])
    heartbeat(hub, "gone", OLD)
    later = NOW + timedelta(days=2)

    def state() -> tuple:
        streams = segmented(hub)
        runs = sorted(streams.runs())
        return (
            hub.store.runs(),
            {n: hub.store.activity(n) for n in (e.name for e in hub.store.runs())},
            runs,
            {r: (streams.logs(*r), streams.activity(*r), [streams.count(*r, lg) for lg in streams.logs(*r)]) for r in runs},
            streams.objects.keys(),
            sorted(hot_files_of(hub, tmp_path)),
            sorted(hub.store.heartbeats()),
            sorted(b.sha256 for b in hub.blobs.items()),
        )

    before = state()
    dry = hub.prune(older_than=RETAIN, now=later, dry_run=True)
    assert state() == before
    real = hub.prune(older_than=RETAIN, now=later)
    assert dataclasses.replace(dry, dry_run=False) == real
    assert real.runs == ["old@h1"] and real.transcripts == [("r@h1", "first")] and real.heartbeats == ["gone"]
    assert sorted(real.blobs) == sorted([own, stray]) and len(real.segments) == 2


# --- concurrency and crashes -------------------------------------------------------------


def test_a_prune_during_ingest_loses_nothing(hub, tmp_path):
    olds = [ship(hub, f"old{i}", OLD) for i in range(5)]
    ref = RunRef(host_id="h1", run_id="busy", run_uid="uid-busy")
    stop = threading.Event()
    sent = {"records": 0, "lines": 0}

    def ingest() -> None:
        while not stop.is_set() or sent["lines"] < 50:
            n = sent["lines"]
            hub.records(
                RecordBatch(
                    run=ref,
                    logs=[
                        LogChunk(log=rundir.PLAN, offset=n, lines=[f"plan {n}"]),
                        LogChunk(log=LOG, offset=n, lines=[f"line {n}"]),
                    ],
                )
            )
            sent["lines"] = n + 1

    worker = threading.Thread(target=ingest)
    worker.start()
    try:
        report = hub.prune(older_than=RETAIN)
    finally:
        stop.set()
        worker.join()
    assert sorted(report.runs) == sorted(olds)
    n = sent["lines"]
    assert hub.store.lines("busy@h1", rundir.PLAN) == ([f"plan {i}" for i in range(n)], n)
    assert hub.streams.read("busy@h1", "uid-busy", LOG, 0) == ([f"line {i}" for i in range(n)], n)
    assert hub.prune(older_than=RETAIN).runs == []


def test_appends_to_a_run_being_dropped_wait_and_start_anew(tmp_path):
    streams = SegmentedStreamLogs(tmp_path / "hot", MemorySegmentObjects(), MemorySegmentIndex(), block_bytes=256, background=False)
    errors: list[BaseException] = []

    def append_forever(stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                held = streams.held("r@h", "u", LOG).held
                streams.append("r@h", "u", LOG, held, [f"line {held}"], "t")
        except BaseException as e:  # reported below
            errors.append(e)

    stop = threading.Event()
    worker = threading.Thread(target=append_forever, args=(stop,))
    worker.start()
    try:
        for _ in range(20):
            streams.close("r@h", "u", LOG)
            streams.drop("r@h", "u")
    finally:
        stop.set()
        worker.join()
    assert errors == []
    lines, total = streams.read("r@h", "u", LOG, 0)
    assert lines == [f"line {i}" for i in range(total)]  # every line since the last drop, from line 0


class CrashAfterIndexDrop(MemorySegmentIndex):
    """A memory index whose `drop` deletes the rows and then fails: a crash before the objects go."""

    crash = True

    def drop(self, name, uid):
        super().drop(name, uid)
        if self.crash:
            raise RuntimeError("crash after the index delete")


def test_a_crash_after_the_index_delete_is_completed_by_a_second_prune(tmp_path):
    index = CrashAfterIndexDrop()
    streams = SegmentedStreamLogs(tmp_path / "hot", MemorySegmentObjects(), index, block_bytes=1024, background=False)
    hub = Hub(MemoryHubStore(), MemoryBlobs(), streams=streams)
    old = ship(hub, "old", OLD)
    sealed = objects_of(hub, old)
    with pytest.raises(RuntimeError):
        hub.prune(older_than=RETAIN, now=NOW)
    # the index rows are gone, so no reader follows one to an object; the records and objects remain
    assert index.segments(old, "uid-old", LOG) == [] and objects_of(hub, old) == sealed
    assert hub.store.entry(old) is not None
    index.crash = False
    report = hub.prune(older_than=RETAIN, now=NOW)
    assert report.runs == [old] and report.segments == sealed
    assert objects_of(hub, old) == [] and hub.store.entry(old) is None


def test_objects_left_by_a_crash_are_deleted_by_the_segment_sweep(tmp_path):
    index = CrashAfterIndexDrop()
    streams = SegmentedStreamLogs(tmp_path / "hot", MemorySegmentObjects(), index, block_bytes=1024, background=False)
    hub = Hub(MemoryHubStore(), MemoryBlobs(), streams=streams)
    old = ship(hub, "old", OLD)
    sealed = objects_of(hub, old)
    with pytest.raises(RuntimeError):
        hub.prune(older_than=RETAIN, now=NOW)
    assert streams.sweep() == sealed and objects_of(hub, old) == []
