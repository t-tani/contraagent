"""The hub's contract: every `HubStore` and `BlobStore` keeps the protocol's storing rules,
and the monitor makes the same views of runs shipped to a hub as of their directory.

`STORES` and `BLOBS` list the implementations under test; another implementation joins by
adding a factory (one that cannot run here skips itself)."""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from contraagent import rundir
from contraagent.hub.client import DirectClient, HubClient
from contraagent.hub.core import Hub
from contraagent.hub.protocol import DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent.hub.source import HeartbeatLiveness
from contraagent.hub.store import BlobStore, DirectoryBlobs, HubStore, MemoryBlobs, MemoryHubStore
from contraagent.monitor import Monitor
from contraagent.monitor.source import DirectorySource
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that stops the containers
    postgres_dsn,
    s3_url,
)

pytestmark = pytest.mark.usefixtures("hub_services")


def _postgres(tmp: Path) -> HubStore:
    from contraagent.hub.postgres import PostgresHubStore

    return PostgresHubStore(postgres_dsn())


def _s3(tmp: Path) -> BlobStore:
    from contraagent.hub.s3 import S3Blobs

    return S3Blobs(s3_url())


STORES: dict[str, Callable[[Path], HubStore]] = {"memory": lambda tmp: MemoryHubStore(), "postgres": _postgres}
BLOBS: dict[str, Callable[[Path], BlobStore]] = {
    "memory": lambda tmp: MemoryBlobs(),
    "directory": lambda tmp: DirectoryBlobs(tmp / "blobs"),
    "s3": _s3,
}

RUN = RunRef(host_id="h1", run_id="r1", run_uid="u1")


@pytest.fixture(params=sorted(STORES))
def store(request, tmp_path) -> HubStore:
    return STORES[request.param](tmp_path)


@pytest.fixture(params=sorted(BLOBS))
def blobs(request, tmp_path) -> BlobStore:
    return BLOBS[request.param](tmp_path)


def batch(*logs: LogChunk, documents=(), files=(), run: RunRef = RUN) -> RecordBatch:
    return RecordBatch(run=run, logs=list(logs), documents=list(documents), files=list(files))


# --- HubStore --------------------------------------------------------------------------


def test_a_log_keeps_each_line_once_in_order(store):
    assert store.put_batch(batch(LogChunk(log=rundir.JOURNAL, offset=0, lines=["a", "b"])), "t1").logs == {rundir.JOURNAL: 2}
    # resent and overlapping: the held lines are dropped, the new one kept
    assert store.put_batch(batch(LogChunk(log=rundir.JOURNAL, offset=1, lines=["b", "c"])), "t2").logs == {rundir.JOURNAL: 3}
    assert store.lines("r1@h1", rundir.JOURNAL) == (["a", "b", "c"], 3)
    assert store.lines("r1@h1", rundir.JOURNAL, 1, 1) == (["b"], 3)
    assert store.count("r1@h1", rundir.JOURNAL) == 3


def test_a_chunk_that_leaves_a_gap_is_refused_and_says_where_to_resume(store):
    store.put_batch(batch(LogChunk(log=rundir.PLAN, offset=0, lines=["a"])), "t1")
    assert store.put_batch(batch(LogChunk(log=rundir.PLAN, offset=5, lines=["f"])), "t2").logs == {rundir.PLAN: 1}
    assert store.lines("r1@h1", rundir.PLAN) == (["a"], 1)


def test_documents_are_replaced_whole_and_removed_by_null(store):
    marker = rundir.entry(rundir.INFLIGHT, "k")
    first = [DocumentPut(name=rundir.RUN_INFO, text='{"run_id": "r1"}'), DocumentPut(name=marker, text="{}")]
    store.put_batch(batch(documents=first), "t1")
    assert store.exists("r1@h1", rundir.INFLIGHT) and store.document("r1@h1", marker) == "{}"
    second = [DocumentPut(name=rundir.RUN_INFO, text='{"run_id": "r1", "x": 1}'), DocumentPut(name=marker, text=None)]
    store.put_batch(batch(documents=second), "t2")
    assert store.document("r1@h1", rundir.RUN_INFO) == '{"run_id": "r1", "x": 1}'
    assert store.document("r1@h1", marker) is None and not store.exists("r1@h1", rundir.INFLIGHT)


def test_a_folder_lists_its_own_documents_by_name(store):
    docs = [DocumentPut(name=rundir.entry(rundir.DEFINITIONS, n), text=n) for n in ("b", "a")]
    store.put_batch(batch(documents=[*docs, DocumentPut(name="definitions/x/deeper.json", text="no")]), "t1")
    assert store.folder("r1@h1", rundir.DEFINITIONS) == ["a", "b"]
    assert store.folder("r1@h1", rundir.CONTRACTS) == []


def test_files_runs_and_activity(store):
    ref = FileRef(path="/w/out/a.json", sha256="0" * 64, size=3, mtime="m")
    store.put_batch(batch(files=[ref]), "2026-10-13T00:00:00+00:00")
    store.put_batch(batch(run=RunRef(host_id="h2", run_id="r1", run_uid="u9")), "2026-10-13T00:00:01+00:00")
    assert store.file("r1@h1", "/w/out/a.json") == ref and store.file("r1@h2", "/w/out/a.json") is None
    assert [(e.name, e.run_uid, e.host_id, e.run_id) for e in store.runs()] == [("r1@h1", "u1", "h1", "r1"), ("r1@h2", "u9", "h2", "r1")]
    assert store.activity("r1@h1") == "2026-10-13T00:00:00+00:00" and store.activity("nope@h1") is None


def test_a_new_run_uid_under_a_name_replaces_the_old_run(store):
    store.put_batch(batch(LogChunk(log=rundir.JOURNAL, offset=0, lines=["old"])), "t1")
    store.put_batch(batch(LogChunk(log=rundir.JOURNAL, offset=0, lines=["new"]), run=RunRef(host_id="h1", run_id="r1", run_uid="u2")), "t2")
    assert store.lines("r1@h1", rundir.JOURNAL) == (["new"], 1)
    assert [e.run_uid for e in store.runs()] == ["u2"]


def test_absent_things_are_empty(store):
    assert store.lines("nope@h1", rundir.JOURNAL) == ([], 0)
    assert store.count("nope@h1", rundir.JOURNAL) == -1
    assert store.document("nope@h1", rundir.RUN_INFO) is None
    assert store.folder("nope@h1", rundir.CONTRACTS) == [] and not store.exists("nope@h1", rundir.STREAMS)


def test_the_latest_heartbeat_of_each_host_is_kept(store):
    store.put_heartbeat(Heartbeat(host_id="h1", sent_at="s1", interval_s=3), "t1")
    store.put_heartbeat(Heartbeat(host_id="h1", sent_at="s2", interval_s=3), "t2")
    (hb, at) = store.heartbeats()["h1"]
    assert hb.sent_at == "s2" and at == "t2"


# --- BlobStore -------------------------------------------------------------------------


def test_a_blob_is_stored_by_its_hash_and_refused_otherwise(blobs):
    data = b'{"ok": true}'
    sha = hashlib.sha256(data).hexdigest()
    assert not blobs.has(sha) and blobs.get(sha) is None
    blobs.put(sha, data)
    blobs.put(sha, data)  # again: nothing changes
    assert blobs.has(sha) and blobs.get(sha) == data
    with pytest.raises(ValueError):
        blobs.put("0" * 64, data)
    with pytest.raises(ValueError):
        blobs.put("../etc", data)


# --- liveness --------------------------------------------------------------------------


def test_a_run_is_live_while_its_host_heartbeats_report_it(store):
    hub = Hub(store, MemoryBlobs(), ttl_s=15)
    store.put_batch(batch(documents=[DocumentPut(name=rundir.RUN_INFO, text='{"run_id": "r1", "pid": 7}')]), "t0")
    snap = {"run": "r1", "alive": True, "launches": [{"key": "k"}], "tree": [], "python_tasks": []}
    report = RunLiveness(run=RUN, alive=True, snapshot=snap)
    store.put_heartbeat(Heartbeat(host_id="h1", sent_at="s", interval_s=3, runs=[report]), "2026-10-13T00:00:00+00:00")
    t0 = 1_791_849_600.0  # 2026-10-13T00:00:00Z
    fresh = HeartbeatLiveness(hub.store, 15, clock=lambda: t0 + 10)
    assert fresh.live() == {"r1@h1"}
    assert fresh.snapshot("r1@h1")["launches"] == [{"key": "k"}] and fresh.snapshot("r1@h1")["run"] == "r1@h1"
    stale = HeartbeatLiveness(hub.store, 15, clock=lambda: t0 + 16)
    assert stale.live() == set()
    assert stale.snapshot("r1@h1") | {} == {**stale.snapshot("r1@h1"), "alive": False, "pid": 7, "launches": []}


# --- the monitor over a hub ------------------------------------------------------------


def ship(root: Path, client: HubClient, host_id: str) -> None:
    """Every record of every run under `root`, sent once (the relay sends them incrementally)."""
    source = DirectorySource(root)
    for run in source.runs():
        info = source.info(run) or {}
        ref = RunRef(host_id=host_id, run_id=run, run_uid=info.get("run_uid") or run)
        logs, documents, files = [], [], []
        for path in sorted((root / run).rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(root / run).as_posix()
            text = path.read_text(errors="replace")
            if name.endswith(".jsonl"):
                logs.append(LogChunk(log=name, offset=0, lines=text.splitlines()))
            else:
                documents.append(DocumentPut(name=name, text=text))
        for text in source.folder(run, rundir.CONTRACTS):
            rec = json.loads(text)
            for spec in rec.get("outputs", []) + rec.get("inputs", []):
                p = Path(spec["path"])
                if not p.is_file():
                    files.append(FileRef(path=spec["path"], sha256=None))
                    continue
                data = p.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                if not client.has_blob(sha):
                    client.put_blob(sha, data)
                got = source.file(run, spec["path"])
                files.append(FileRef(path=spec["path"], sha256=sha, size=len(data), mtime=got[2] if got else ""))
        client.send_records(RecordBatch(run=ref, logs=logs, documents=documents, files=files))


@pytest.fixture(scope="module")
def demo_runs(tmp_path_factory) -> Path:
    from contraagent.docs.examples.demo import run as demo

    where = tmp_path_factory.mktemp("demo")
    old = Path.cwd()
    os.chdir(where)
    try:
        demo.main(["--no-serve", "--fast"])
    finally:
        os.chdir(old)
    return where / "demo-runs"


def views(mon: Monitor, run: str) -> dict:
    plan = mon.plan(run)
    keys = [n["key"] for n in plan["nodes"]]
    out = {
        "journal": mon.journal(run, 0),
        "plan": plan,
        "outputs": mon.outputs(run),
        "definitions": mon.definitions(run),
        "cursor": mon.cursor(run),
        "task": {k: mon.task_detail(run, k) for k in keys},
        "stream": {k: mon.stream(run, k, 0, limit=5) for k in keys},
    }
    return json.loads(json.dumps(out, default=str, sort_keys=True))


def test_runs_shipped_to_a_hub_have_every_view_of_their_directory(demo_runs, store, blobs):
    hub = Hub(store, blobs)
    ship(demo_runs, DirectClient(hub), "h1")
    local, remote = Monitor(demo_runs), hub.monitor()
    names = [r["run"] for r in local.runs()]
    assert names and sorted(r["run"] for r in remote.runs()) == sorted(f"{n}@h1" for n in names)
    for name in names:
        assert views(remote, f"{name}@h1") == views(local, name), name
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ("run", "last_ts")} for r in sorted(rows, key=lambda r: r["run"])]
    assert strip(remote.runs()) == strip(local.runs())
