"""`contraagent relay`: what `Relay` ships to a hub, pass after pass, and `HttpClient`'s wire."""

import gzip
import hashlib
import json
import logging
import os
import shutil
from pathlib import Path

import httpx
import pytest

from contraagent import rundir
from contraagent.hub.client import DirectClient, HttpClient, HubRefused, HubUnavailable
from contraagent.hub.core import Hub
from contraagent.hub.protocol import Accepted, DocumentPut, FileRef, Heartbeat, HeartbeatAck, LogChunk, RecordBatch, RunRef
from contraagent.hub.relay import Relay, default_progress_path, main, read_lines, seek_line
from contraagent.hub.source import HeartbeatLiveness
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.monitor import Monitor
from contraagent.monitor.source import DirectorySource, StaticLiveness

T0 = 1_791_849_600.0  # 2026-10-13T00:00:00Z


class Recording:
    """A `HubClient` that passes every request to `inner` and keeps what was sent."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.batches: list[RecordBatch] = []
        self.heartbeats: list[Heartbeat] = []
        self.blobs: list[str] = []

    def send_records(self, batch: RecordBatch) -> Accepted:
        self.batches.append(batch)
        return self.inner.send_records(batch)

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        self.heartbeats.append(heartbeat)
        return self.inner.send_heartbeat(heartbeat)

    def has_blob(self, sha256: str) -> bool:
        return self.inner.has_blob(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        self.blobs.append(sha256)
        self.inner.put_blob(sha256, data)

    def lines(self) -> list[tuple[str, str]]:
        return [(c.log, line) for b in self.batches for c in b.logs for line in c.lines]

    def documents(self) -> list[tuple[str, str | None]]:
        return [(d.name, d.text) for b in self.batches for d in b.documents]

    def files(self) -> list[FileRef]:
        return [f for b in self.batches for f in b.files]

    def clear(self) -> None:
        self.batches.clear()
        self.heartbeats.clear()
        self.blobs.clear()


class Down:
    """A hub that takes no request."""

    def send_records(self, batch):
        raise ConnectionError("connection refused")

    send_heartbeat = has_blob = send_records

    def put_blob(self, sha256, data):
        raise ConnectionError("connection refused")


def new_hub() -> Hub:
    return Hub(MemoryHubStore(), MemoryBlobs())


def relay(client, runs: Path, **kw) -> Relay:
    kw.setdefault("liveness", StaticLiveness(DirectorySource(runs)))
    kw.setdefault("clock", lambda: T0)
    return Relay(client, runs, runs.parent / "progress.json", host_id="h1", **kw)


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


def assert_same_views(hub: Hub, runs: Path) -> None:
    local, remote = Monitor(runs), hub.monitor()
    names = [r["run"] for r in local.runs()]
    assert names and sorted(r["run"] for r in remote.runs()) == sorted(f"{n}@h1" for n in names)
    for name in names:
        assert views(remote, f"{name}@h1") == views(local, name), name


def test_one_pass_gives_the_hub_every_view_of_the_runs(demo_runs, tmp_path):
    hub = new_hub()
    # small requests, so the demo's logs take several of them
    r = relay(DirectClient(hub), demo_runs, batch_bytes=4096, batch_lines=50)
    r.progress_path = tmp_path / "progress.json"
    assert r.pass_once()
    assert_same_views(hub, demo_runs)


@pytest.fixture
def runs(demo_runs, tmp_path) -> Path:
    """A copy of one demo run, `analyse`, to change."""
    where = tmp_path / "runs"
    where.mkdir()
    shutil.copytree(demo_runs / "analyse", where / "analyse")
    return where


def first(runs: Path) -> Path:
    return runs / "analyse"


def a_stream(run: Path) -> Path:
    return sorted((run / rundir.STREAMS).iterdir())[0]


def test_each_pass_sends_only_complete_lines_that_are_new(runs):
    hub, rec = new_hub(), None
    rec = Recording(DirectClient(hub))
    r = relay(rec, runs)
    assert r.pass_once()
    rec.clear()
    assert r.pass_once() and rec.batches == []  # nothing changed

    run = first(runs)
    stream = a_stream(run)
    log = f"{rundir.STREAMS}/{stream.name}"
    with open(run / rundir.JOURNAL, "a") as f:
        f.write('{"new": 1}\n{"partial": ')
    with open(stream, "a") as f:
        f.write('{"type": "x"}\n')
    assert r.pass_once()
    assert sorted(rec.lines()) == sorted([(rundir.JOURNAL, '{"new": 1}'), (log, '{"type": "x"}')])
    assert rec.documents() == [] and rec.files() == []

    rec.clear()
    assert r.pass_once() and rec.lines() == []  # the partial line waits
    with open(run / rundir.JOURNAL, "a") as f:
        f.write("2}\n")
    assert r.pass_once() and rec.lines() == [(rundir.JOURNAL, '{"partial": 2}')]
    held, count = hub.store.lines("analyse@h1", rundir.JOURNAL)
    assert held == (run / rundir.JOURNAL).read_text().splitlines() and held[-2:] == ['{"new": 1}', '{"partial": 2}']


def test_a_removed_in_flight_marker_is_removed_on_the_hub(runs):
    hub = new_hub()
    rec = Recording(DirectClient(hub))
    r = relay(rec, runs)
    marker = first(runs) / rundir.entry(rundir.INFLIGHT, "classify-east-0")
    marker.write_text('{"key": "classify-east-0"}')
    assert r.pass_once()
    assert hub.store.document("analyse@h1", "inflight/classify-east-0.json") == '{"key": "classify-east-0"}'
    rec.clear()
    marker.unlink()
    assert r.pass_once()
    assert rec.documents() == [("inflight/classify-east-0.json", None)]
    assert hub.store.document("analyse@h1", "inflight/classify-east-0.json") is None


def test_a_half_written_document_waits_for_the_next_pass(runs):
    hub = new_hub()
    r = relay(DirectClient(hub), runs)
    cursor = first(runs) / rundir.CURSOR
    cursor.write_text('{"stage": "do')
    assert r.pass_once()
    assert hub.store.document("analyse@h1", rundir.CURSOR) is None
    cursor.write_text('{"stage": "done"}')
    assert r.pass_once()
    assert hub.store.document("analyse@h1", rundir.CURSOR) == '{"stage": "done"}'


def test_a_changed_output_file_is_hashed_again_and_served(runs):
    hub = new_hub()
    rec = Recording(DirectClient(hub))
    r = relay(rec, runs)
    assert r.pass_once()
    contract = json.loads((first(runs) / "contracts" / "classify-east-0.json").read_text())
    path = contract["outputs"][0]["path"]
    # the copy's contracts name the demo's files; the hub serves them as the host sees them
    assert hub.monitor().source.file("analyse@h1", path)[0] == Path(path).read_text()
    rec.clear()
    assert r.pass_once() and rec.files() == [] and rec.blobs == []

    src = hub.monitor().source
    original = Path(path).read_text()
    try:
        Path(path).write_text('{"changed": true}')
        assert r.pass_once()
        [ref] = rec.files()
        assert ref.path == path and ref.sha256 == hashlib.sha256(b'{"changed": true}').hexdigest()
        assert src.file("analyse@h1", path)[:2] == ('{"changed": true}', 17)
        Path(path).unlink()
        rec.clear()
        assert r.pass_once()
        assert [f.sha256 for f in rec.files()] == [None] and src.file("analyse@h1", path) is None
    finally:
        Path(path).write_text(original)


def test_a_restarted_relay_sends_nothing_new(runs):
    hub = new_hub()
    assert relay(DirectClient(hub), runs).pass_once()
    rec = Recording(DirectClient(hub))
    again = relay(rec, runs)
    assert again.pass_once()
    # it asks the hub what it holds (empty chunks), and sends no line, document, file or blob
    assert rec.lines() == [] and rec.documents() == [] and rec.files() == [] and rec.blobs == []
    rec.clear()
    assert again.pass_once() and rec.batches == []


def test_a_relay_that_lost_its_progress_continues_from_what_the_hub_holds(runs):
    hub = new_hub()
    r = relay(DirectClient(hub), runs)
    assert r.pass_once()
    r.progress_path.unlink()
    rec = Recording(DirectClient(hub))
    assert relay(rec, runs, batch_lines=1).pass_once()
    # one request of one line (each other log named without lines); the hub's counts move
    # the relay to the end of every log
    assert len(rec.batches) == 1 and len(rec.lines()) == 1
    assert rec.blobs == []


def test_a_hub_that_lost_everything_is_sent_every_run_again(runs):
    hub = new_hub()
    r = relay(DirectClient(hub), runs, resync_s=60)
    assert r.pass_once()
    hub.store = MemoryHubStore()  # the hub restarted without its records
    r.clock = lambda: T0 + 61
    assert r.pass_once()
    assert_same_views(hub, runs)


def test_an_unavailable_hub_does_not_stop_the_relay(runs, caplog):
    hub = new_hub()
    r = relay(Down(), runs, interval_s=3)
    caplog.set_level(logging.WARNING, logger="contraagent.hub.relay")
    assert not r.pass_once() and not r.pass_once() and not r.heartbeat_once()
    assert [m for m in caplog.messages if "hub unavailable" in m].__len__() == 1  # once per outage
    assert r.delay() == 12  # 3s doubled for each of two failed passes
    r.client = DirectClient(hub)
    assert r.pass_once() and r.delay() == 3
    assert_same_views(hub, runs)


def test_the_heartbeat_carries_the_live_runs(runs):
    hub = new_hub()
    snap = {"run": "analyse", "alive": True, "launches": [{"key": "classify-east-0"}], "tree": [], "python_tasks": []}
    live = StaticLiveness(DirectorySource(runs), live=["analyse"], snapshots={"analyse": snap})
    rec = Recording(DirectClient(hub))
    r = relay(rec, runs, liveness=live, interval_s=3)
    assert r.heartbeat_once()
    [beat] = rec.heartbeats
    uid = json.loads((first(runs) / rundir.RUN_INFO).read_text())["run_uid"]
    assert beat.host_id == "h1" and beat.interval_s == 3 and beat.sent_at.startswith("2026-10-13T00:00:00")
    assert [(b.run, b.alive, b.snapshot) for b in beat.runs] == [(RunRef(host_id="h1", run_id="analyse", run_uid=uid), True, snap)]
    assert HeartbeatLiveness(hub.store).live() == {"analyse@h1"}


def test_since_leaves_out_old_runs_not_shipped_yet(runs):
    hub = new_hub()
    old = T0 - 30 * 86400
    for p in [first(runs), *first(runs).iterdir()]:
        os.utime(p, (old, old))
    assert relay(DirectClient(hub), runs, since_days=7).pass_once()
    assert hub.store.runs() == []
    assert relay(DirectClient(hub), runs, since_days=60).pass_once()
    assert [e.name for e in hub.store.runs()] == ["analyse@h1"]


def test_a_new_run_uid_sends_the_run_again(runs):
    hub = new_hub()
    r = relay(DirectClient(hub), runs)
    assert r.pass_once()
    info_path = first(runs) / rundir.RUN_INFO
    info_path.write_text(json.dumps({**json.loads(info_path.read_text()), "run_uid": "other"}))
    assert r.pass_once()
    assert [e.run_uid for e in hub.store.runs()] == ["other"]
    assert_same_views(hub, runs)


def test_the_progress_file_is_next_to_the_runs_directory(tmp_path):
    assert default_progress_path(tmp_path / "runs") == tmp_path / "runs.relay.json"


def test_lines_are_read_by_byte_offset(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_bytes("a\nbé\n".encode() + b"c" * 100 + b"\nd")
    assert read_lines(path, 0) == (["a", "bé"] + ["c" * 100], 107)
    assert read_lines(path, 0, max_lines=1) == (["a"], 2)
    assert read_lines(path, 0, max_bytes=4) == (["a"], 2)
    assert read_lines(path, 2, max_bytes=4) == (["bé"], 6)
    assert read_lines(path, 6, max_bytes=4) == (["c" * 100], 107)  # a longer line goes alone
    assert read_lines(path, 107) == ([], 107)  # "d" has no newline yet
    assert seek_line(path, 0) == (0, 0) and seek_line(path, 2) == (2, 6) and seek_line(path, 9) == (3, 107)


# --- HttpClient ------------------------------------------------------------------------


def test_http_client_speaks_the_protocol():
    seen: list[httpx.Request] = []
    blobs: set[str] = set()

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer s3cret"
        path = request.url.path
        if request.method == "POST":
            assert request.headers["content-encoding"] == "gzip"
            body = gzip.decompress(request.content)
        if path == "/ingest/records":
            batch = RecordBatch.model_validate_json(body)
            return httpx.Response(200, json={"logs": {c.log: c.offset + len(c.lines) for c in batch.logs}})
        if path == "/ingest/heartbeat":
            Heartbeat.model_validate_json(body)
            return httpx.Response(200, json={"ttl_s": 15})
        sha = path.rsplit("/", 1)[1]
        if request.method == "HEAD":
            return httpx.Response(200 if sha in blobs else 404)
        if hashlib.sha256(request.content).hexdigest() != sha:
            return httpx.Response(400, text="content does not hash")
        blobs.add(sha)
        return httpx.Response(204)

    client = HttpClient("http://hub:8790/", "s3cret", 5, transport=httpx.MockTransport(handle))
    ref = RunRef(host_id="h", run_id="r", run_uid="u")
    batch = RecordBatch(
        run=ref, logs=[LogChunk(log=rundir.JOURNAL, offset=2, lines=["x"])], documents=[DocumentPut(name="run.json", text="{}")]
    )
    assert client.send_records(batch) == Accepted(logs={rundir.JOURNAL: 3})
    assert client.send_heartbeat(Heartbeat(host_id="h", sent_at="s", interval_s=3)).ttl_s == 15
    sha = hashlib.sha256(b"data").hexdigest()
    assert not client.has_blob(sha)
    client.put_blob(sha, b"data")
    assert client.has_blob(sha)
    with pytest.raises(HubUnavailable, match="HTTP 400: content does not hash"):
        client.put_blob("0" * 64, b"data")
    assert [str(r.url) for r in seen][:2] == ["http://hub:8790/ingest/records", "http://hub:8790/ingest/heartbeat"]


@pytest.mark.parametrize(
    "answer",
    [
        lambda request: httpx.Response(401, text="bad token"),
        lambda request: httpx.Response(200, text="not json"),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused", request=request)),
    ],
)
def test_http_client_failures_are_hub_unavailable(answer):
    client = HttpClient("http://hub:8790", "t", transport=httpx.MockTransport(answer))
    with pytest.raises(HubUnavailable):
        client.send_records(RecordBatch(run=RunRef(host_id="h", run_id="r", run_uid="u")))


def test_main_ships_once_over_http(runs, tmp_path, monkeypatch):
    hub = new_hub()

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        if request.url.path == "/ingest/records":
            batch = RecordBatch.model_validate_json(gzip.decompress(request.content))
            return httpx.Response(200, content=hub.records(batch).model_dump_json())
        sha = request.url.path.rsplit("/", 1)[1]
        if request.method == "HEAD":
            return httpx.Response(200 if hub.has_blob(sha) else 404)
        hub.put_blob(sha, request.content)
        return httpx.Response(204)

    real = HttpClient.__init__

    def mocked(self, base_url, token="", timeout=30.0, *, transport=None):
        real(self, base_url, token, timeout, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(HttpClient, "__init__", mocked)
    monkeypatch.setenv("CONTRAAGENT_HUB_TOKEN", "tok")
    progress = tmp_path / "p.json"
    assert main(["--runs-dir", str(runs), "--hub", "http://hub:8790", "--host-id", "h1", "--once", "--progress-file", str(progress)]) == 0
    assert_same_views(hub, runs)
    assert json.loads(progress.read_text())["hub"] == "http://hub:8790"


def test_main_needs_a_token(runs, monkeypatch, capsys):
    monkeypatch.delenv("CONTRAAGENT_HUB_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main(["--runs-dir", str(runs), "--hub", "http://hub:8790", "--once"])
    assert "no ingest token" in capsys.readouterr().err


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_token_is_an_error_retried_slowly(runs, caplog, status):
    client = HttpClient("http://hub:8790", "t", transport=httpx.MockTransport(lambda request: httpx.Response(status, text="no")))
    with pytest.raises(HubRefused):
        client.send_heartbeat(Heartbeat(host_id="h", sent_at="s", interval_s=3))
    r = relay(client, runs, interval_s=3)
    caplog.set_level(logging.WARNING, logger="contraagent.hub.relay")
    assert not r.pass_once() and not r.heartbeat_once() and not r.pass_once()
    errors = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert len(errors) == 1 and "hub refused the relay" in errors[0].getMessage() and f"HTTP {status}" in errors[0].getMessage()
    assert r.delay() == 60 and r.heartbeat_delay() == 60
