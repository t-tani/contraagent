"""`contraagent hub` over HTTP: the ingest endpoints and their tokens and limits, the monitor
behind the read token, and runs shipped over the wire serving what the core computes."""

import asyncio
import gzip
import hashlib
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")

from fastapi.testclient import TestClient

from contraagent._internal.cli import main as cli_main
from contraagent._internal.hub import server
from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.protocol import (
    HEALTHZ,
    INGEST_HEARTBEAT,
    INGEST_RECORDS,
    Accepted,
    DocumentPut,
    Heartbeat,
    HeartbeatAck,
    LogChunk,
    RecordBatch,
    RunLiveness,
    RunRef,
)
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore
from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import empty_snapshot
from contraagent.monitor import Monitor
from test_hub_contract import ship

INGEST = "ingest-secret"
HOST_BOUND = "h2-secret"
READ = "read-secret"
AUTH = {"Authorization": f"Bearer {INGEST}", "Content-Type": "application/json"}
READ_AUTH = {"Authorization": f"Bearer {READ}"}
RUN = RunRef(host_id="h1", run_id="r1", run_uid="u1")


def make(read_token: str | None = READ, **kwargs) -> tuple[Hub, TestClient]:
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    app = server.create_hub_app(hub, ingest_tokens={INGEST: None, HOST_BOUND: "h2"}, read_token=read_token, **kwargs)
    return hub, TestClient(app, base_url="http://127.0.0.1")


class HttpClient:
    """A `HubClient` that speaks the protocol over the hub's HTTP endpoints."""

    def __init__(self, c: TestClient) -> None:
        self.c = c

    def send_records(self, batch: RecordBatch) -> Accepted:
        r = self.c.post(INGEST_RECORDS, content=batch.model_dump_json(), headers=AUTH)
        assert r.status_code == 200, r.text
        return Accepted.model_validate(r.json())

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        r = self.c.post(INGEST_HEARTBEAT, content=heartbeat.model_dump_json(), headers=AUTH)
        assert r.status_code == 200, r.text
        return HeartbeatAck.model_validate(r.json())

    def has_blob(self, sha256: str) -> bool:
        return self.c.head(f"/ingest/blobs/{sha256}", headers=AUTH).status_code == 200

    def put_blob(self, sha256: str, data: bytes) -> None:
        r = self.c.put(f"/ingest/blobs/{sha256}", content=data, headers=AUTH)
        assert r.status_code == 204, r.text


def records(lines: list[str], offset: int = 0, log: str = layout.JOURNAL) -> str:
    return RecordBatch(run=RUN, logs=[LogChunk(log=log, offset=offset, lines=lines)]).model_dump_json()


def raw(value) -> object:
    return json.loads(json.dumps(value, default=str))


# --- ingest ----------------------------------------------------------------------------


def test_a_batch_posts_and_the_gap_and_resend_rules_come_back():
    hub, c = make()
    assert c.post(INGEST_RECORDS, content=records(["a", "b"]), headers=AUTH).json() == {
        "logs": {layout.JOURNAL: 2},
        "durable": {layout.JOURNAL: 2},
    }
    assert c.post(INGEST_RECORDS, content=records(["b", "c"], 1), headers=AUTH).json() == {
        "logs": {layout.JOURNAL: 3},
        "durable": {layout.JOURNAL: 3},
    }
    assert c.post(INGEST_RECORDS, content=records(["z"], 9), headers=AUTH).json() == {
        "logs": {layout.JOURNAL: 3},
        "durable": {layout.JOURNAL: 3},
    }
    assert hub.store.lines("r1@h1", layout.JOURNAL) == (["a", "b", "c"], 3)


def test_a_body_that_is_not_a_batch_is_refused():
    _, c = make()
    assert c.post(INGEST_RECORDS, json={"run": {"host_id": "h1"}}, headers=AUTH).status_code == 422
    assert c.post(INGEST_RECORDS, content=b"not json", headers=AUTH).status_code == 422


def test_a_gzip_body_is_taken():
    hub, c = make()
    body = gzip.compress(records(["a"]).encode())
    r = c.post(INGEST_RECORDS, content=body, headers={**AUTH, "Content-Encoding": "gzip"})
    assert r.json() == {"logs": {layout.JOURNAL: 1}, "durable": {layout.JOURNAL: 1}}
    assert c.post(INGEST_RECORDS, content=b"\x1f\x8bnope", headers={**AUTH, "Content-Encoding": "gzip"}).status_code == 400
    assert c.post(INGEST_RECORDS, content=b"{}", headers={**AUTH, "Content-Encoding": "br"}).status_code == 415


def test_a_heartbeat_posts_and_returns_its_ttl():
    hub = Hub(MemoryHubStore(), MemoryBlobs(), ttl_s=21)
    c = TestClient(server.create_hub_app(hub, ingest_tokens=[INGEST], read_token=None), base_url="http://127.0.0.1")
    beat = Heartbeat(host_id="h1", sent_at="s", interval_s=3)
    assert c.post(INGEST_HEARTBEAT, content=beat.model_dump_json(), headers=AUTH).json() == {"ttl_s": 21}
    assert hub.store.heartbeats()["h1"][0] == beat


def test_blobs_are_checked_by_head_and_stored_by_put():
    hub, c = make()
    data = b'{"ok": true}'
    sha = hashlib.sha256(data).hexdigest()
    assert c.head(f"/ingest/blobs/{sha}", headers=AUTH).status_code == 404
    assert c.put(f"/ingest/blobs/{sha}", content=data, headers=AUTH).status_code == 204
    assert c.head(f"/ingest/blobs/{sha}", headers=AUTH).status_code == 200
    assert hub.blobs.get(sha) == data
    assert c.put(f"/ingest/blobs/{'0' * 64}", content=data, headers=AUTH).status_code == 400
    assert c.put("/ingest/blobs/not-a-hash", content=data, headers=AUTH).status_code == 400
    assert c.head("/ingest/blobs/not-a-hash", headers=AUTH).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Basic {INGEST}"}, READ_AUTH])
def test_ingest_without_an_ingest_token_is_401(headers):
    hub, c = make()
    data = b"x"
    sha = hashlib.sha256(data).hexdigest()
    assert c.post(INGEST_RECORDS, content=records(["a"]), headers=headers).status_code == 401
    assert (
        c.post(INGEST_HEARTBEAT, content=Heartbeat(host_id="h1", sent_at="s", interval_s=3).model_dump_json(), headers=headers).status_code
        == 401
    )
    assert c.head(f"/ingest/blobs/{sha}", headers=headers).status_code == 401
    assert c.put(f"/ingest/blobs/{sha}", content=data, headers=headers).status_code == 401
    assert hub.store.runs() == [] and not hub.blobs.has(sha)


def test_a_token_given_for_one_host_sends_only_that_hosts_runs():
    _, c = make()
    bound = {**AUTH, "Authorization": f"Bearer {HOST_BOUND}"}
    assert c.post(INGEST_RECORDS, content=records(["a"]), headers=bound).status_code == 403
    other = RecordBatch(run=RunRef(host_id="h2", run_id="r1", run_uid="u1")).model_dump_json()
    assert c.post(INGEST_RECORDS, content=other, headers=bound).status_code == 200
    beat = Heartbeat(host_id="h1", sent_at="s", interval_s=3).model_dump_json()
    assert c.post(INGEST_HEARTBEAT, content=beat, headers=bound).status_code == 403


def test_an_oversized_request_is_413():
    hub, c = make(max_records_bytes=1000, max_blob_bytes=10)
    assert c.post(INGEST_RECORDS, content=records(["x" * 2000]), headers=AUTH).status_code == 413
    assert c.post(INGEST_RECORDS, content=records(["x" * 100]), headers=AUTH).status_code == 200
    bomb = gzip.compress(records(["x" * 100_000]).encode())
    assert len(bomb) < 1000
    assert c.post(INGEST_RECORDS, content=bomb, headers={**AUTH, "Content-Encoding": "gzip"}).status_code == 413
    data = b"y" * 11
    assert c.put(f"/ingest/blobs/{hashlib.sha256(data).hexdigest()}", content=data, headers=AUTH).status_code == 413

    def chunked():  # no Content-Length: counted as it arrives
        yield b"y" * 6
        yield b"y" * 6

    assert c.put(f"/ingest/blobs/{'0' * 64}", content=chunked(), headers=AUTH).status_code == 413
    assert server.MAX_RECORDS_BYTES == 16 * 1024 * 1024


# --- the monitor over runs shipped by HTTP ---------------------------------------------


def test_every_endpoint_carries_what_the_core_computed(demo_runs):
    hub, c = make()
    ship(demo_runs, HttpClient(c), "h1")
    mon = server.hub_monitor(hub, title="contraagent hub")
    c.headers.update(READ_AUTH)
    assert c.get("/api/info").json()["title"] == "contraagent hub"
    runs = c.get("/api/runs").json()
    assert runs == raw(mon.runs()) and len(runs) == len(Monitor(demo_runs).runs())
    seen_streams = 0
    for run in [r["run"] for r in runs]:
        assert run.endswith("@h1")
        entries, total = mon.journal(run, 0)
        assert c.get(f"/api/runs/{run}/journal").json() == raw({"entries": entries, "total": total})
        for ep, want in (
            ("plan", mon.plan(run)),
            ("outputs", mon.outputs(run)),
            ("definitions", mon.definitions(run)),
            ("cursor", mon.cursor(run) or {}),
            ("procs", mon.procs(run)),
        ):
            assert c.get(f"/api/runs/{run}/{ep}").json() == raw(want), ep
        for key in {n["key"] for n in mon.plan(run)["nodes"]}:
            assert c.get(f"/api/runs/{run}/task/{key}").json() == raw(mon.task_detail(run, key))
        local = run.removesuffix("@h1")
        for f in sorted((demo_runs / local / "streams").glob("*.stream.jsonl")):
            key = f.name.removesuffix(".stream.jsonl")
            page, total = mon.stream(run, key, 0)
            got = c.get(f"/api/runs/{run}/stream/{key}").json()
            assert got == raw({**page, "total": total}) and got["events"]
            seen_streams += 1
    assert seen_streams
    assert c.get("/").status_code == 200 and "<html" in c.get("/").text.lower()


def test_a_heartbeat_reporting_a_run_alive_shows_it_running():
    hub, c = make()
    client = HttpClient(c)
    info = json.dumps({"run_id": "r1", "run_uid": "u1", "started_at": datetime.now(UTC).isoformat()})
    client.send_records(RecordBatch(run=RUN, documents=[DocumentPut(name=layout.RUN_INFO, text=info)]))
    c.headers.update(READ_AUTH)
    assert [r["running"] for r in c.get("/api/runs").json()] == [False]
    launch = {"pid": 9, "age_s": 4, "cmd": "claude -p", "full_cmd": "claude -p ...", "children": []}
    launch |= {"key": "review-a", "kind": "review", "unit": "a", "role": "", "model": "sonnet", "plugin": "p"}
    snap = empty_snapshot("r1", json.loads(info), True) | {"pid": 7, "launches": [launch]}
    report = RunLiveness(run=RUN, alive=True, snapshot=snap)
    assert client.send_heartbeat(Heartbeat(host_id="h1", sent_at="s", interval_s=3, runs=[report])).ttl_s == hub.ttl_s
    assert [(r["run"], r["running"]) for r in c.get("/api/runs").json()] == [("r1@h1", True)]
    got = c.get("/api/runs/r1@h1/procs").json()
    assert got == {**snap, "run": "r1@h1"}


# --- the read token --------------------------------------------------------------------


async def first_chunk(app, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
    """The status and the first body chunk of a GET, then a disconnect (an SSE feed never ends)."""
    path, _, query = path.partition("?")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [(b"host", b"127.0.0.1"), *((k.lower().encode(), v.encode()) for k, v in headers.items())],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 80),
    }
    got: dict = {}
    done = asyncio.Event()
    asked = False

    async def receive():
        nonlocal asked
        if not asked:
            asked = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            got["status"] = message["status"]
        elif message["type"] == "http.response.body" and "body" not in got and (message.get("body") or not message.get("more_body")):
            got["body"] = message.get("body", b"")
            done.set()

    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    return got["status"], got.get("body", b"")


def test_the_monitor_answers_401_without_the_read_token():
    _, c = make()
    for path in ("/api/runs", "/api/info", "/", "/events?run=r1", "/api/openapi.json"):
        assert c.get(path).status_code == 401, path
        assert c.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401, path
        assert c.get(path, headers=AUTH).status_code == 401, path  # an ingest token does not open it
    assert c.get("/api/runs", headers=READ_AUTH).status_code == 200


def test_login_sets_the_cookie_after_which_routes_and_feeds_work():
    hub, c = make()
    info = json.dumps({"run_id": "r1", "run_uid": "u1", "started_at": datetime.now(UTC).isoformat()})
    HttpClient(c).send_records(RecordBatch(run=RUN, documents=[DocumentPut(name=layout.RUN_INFO, text=info)]))
    assert c.get("/login?token=wrong", follow_redirects=False).status_code == 401
    assert server.COOKIE not in c.cookies
    r = c.get(f"/login?token={READ}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and READ not in cookie
    assert c.get("/api/runs").status_code == 200
    value = c.cookies[server.COOKIE]
    app = c.app
    status, body = asyncio.run(first_chunk(app, "/events?run=r1@h1", {"Cookie": f"{server.COOKIE}={value}"}))
    assert status == 200 and b"event: procs" in body
    status, _ = asyncio.run(first_chunk(app, "/events?run=r1@h1", {}))
    assert status == 401


def test_under_a_base_path_login_redirects_to_its_page_and_scopes_the_cookie():
    _, c = make(base_path="/monitor/")
    r = c.get(f"/login?token={READ}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/monitor/"
    assert "; Path=/monitor;" in r.headers["set-cookie"]
    # a browser sends it to /monitor/..., which reaches the hub as /... once the proxy took the base path off
    cookie = {"Cookie": f"{server.COOKIE}={r.cookies[server.COOKIE]}"}
    c.cookies.clear()
    assert c.get("/api/runs", headers=cookie).status_code == 200
    assert c.get("/monitor/api/runs", headers=cookie).status_code == 404  # only once the proxy took it off
    page = c.get("/", headers=cookie)
    assert '<ca-monitor base-url="/monitor"></ca-monitor>' in page.text and 'src="/monitor/app.js"' in page.text
    assert c.post(INGEST_RECORDS, content=records(["a"]), headers=AUTH).status_code == 200  # ingest stays at /
    _, open_hub = make(read_token=None, base_path="/monitor")
    assert open_hub.get("/login", follow_redirects=False).headers["location"] == "/monitor/"


def test_the_hub_refuses_a_base_path_that_is_not_a_path(capsys):
    with pytest.raises(ValueError, match="starts with /"):
        make(base_path="monitor")
    with pytest.raises(SystemExit) as exc:
        cli_main(["hub", "--ingest-token-file", "tokens", "--base-path", "https://example.com/monitor"])
    assert exc.value.code == 2
    assert "argument --base-path" in capsys.readouterr().err


def test_the_read_token_does_not_allow_ingest_and_no_read_token_opens_the_monitor():
    _, c = make()
    c.get(f"/login?token={READ}")
    assert c.post(INGEST_RECORDS, content=records(["a"]), headers=READ_AUTH).status_code == 401
    assert c.post(INGEST_RECORDS, content=records(["a"])).status_code == 401  # the cookie neither
    _, open_hub = make(read_token=None)
    assert open_hub.get("/api/runs").status_code == 200
    assert open_hub.get("/login", follow_redirects=False).status_code == 303


def test_the_host_header_check_still_applies():
    hub, _ = make()
    app = server.create_hub_app(hub, ingest_tokens=[INGEST], read_token=None, allowed_hosts=["hub.lan"])
    assert TestClient(app, base_url="http://attacker.example:8790").get("/api/runs").status_code == 400
    assert TestClient(app, base_url="http://attacker.example:8790").get(f"/login?token={READ}").status_code == 400
    assert TestClient(app, base_url="http://hub.lan:8790").get("/api/runs").status_code == 200
    assert TestClient(app, base_url="http://localhost:8790").get("/api/runs").status_code == 200


# --- /healthz ---------------------------------------------------------------------------


class _Broken:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError("the store is down")

        return fail


class _Hangs:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0

    def get(self, sha256):
        self.calls += 1
        self.release.wait(10)


def test_healthz_answers_ok_without_a_token_under_any_host_name():
    _, c = make()
    for client in (c, TestClient(c.app, base_url="http://hub.internal:8790")):
        r = client.get(HEALTHZ)
        assert r.status_code == 200 and r.json() == {"status": "ok", "failed": {}}


def test_healthz_answers_ok_over_segmented_transcripts(tmp_path):
    pytest.importorskip("zstandard")
    streams = server.open_streams(str(tmp_path / "hot"), None, "memory")
    try:
        hub = Hub(MemoryHubStore(), server.open_blobs(f"dir:{tmp_path / 'blobs'}"), streams=streams)
        c = TestClient(server.create_hub_app(hub, ingest_tokens=[INGEST], read_token=READ), base_url="http://127.0.0.1")
        assert c.get(HEALTHZ).json() == {"status": "ok", "failed": {}}
        (tmp_path / "hot").chmod(0o500)
        try:
            r = c.get(HEALTHZ)
        finally:
            (tmp_path / "hot").chmod(0o700)
        if sys.platform != "win32" and os.geteuid() != 0:  # root writes anywhere; Windows has no mode bits
            assert r.status_code == 503 and r.json()["failed"] == {"transcripts": "PermissionError"}
    finally:
        streams.shutdown()


def test_healthz_names_the_store_that_fails_and_its_error_kind(caplog):
    hub = Hub(_Broken(), MemoryBlobs())  # type: ignore[arg-type]
    c = TestClient(server.create_hub_app(hub, ingest_tokens=[INGEST], read_token=None), base_url="http://127.0.0.1")
    with caplog.at_level("WARNING", logger="contraagent._internal.hub.server"):
        for _ in range(3):
            r = c.get(HEALTHZ)
            assert r.status_code == 503
            assert r.json() == {"status": "failing", "failed": {"records": "ConnectionError"}}
    # the error, with its message, is logged once while the state holds
    logged = [m for m in caplog.messages if "the store is down" in m]
    assert logged == ["healthz: the records store fails: ConnectionError: the store is down"]


def test_healthz_bounds_a_hanging_store_to_one_thread(monkeypatch):
    blobs = _Hangs()
    hub = Hub(MemoryHubStore(), blobs)  # type: ignore[arg-type]
    monkeypatch.setattr(server, "HEALTH_TIMEOUT_S", 0.2)
    c = TestClient(server.create_hub_app(hub, ingest_tokens=[INGEST], read_token=None), base_url="http://127.0.0.1")
    try:
        for _ in range(3):
            r = c.get(HEALTHZ)
            # Only the hanging store is judged: on a busy runner a healthy one can miss 0.2 s too.
            assert r.status_code == 503 and r.json()["failed"]["blobs"] == "TimeoutError"
        assert blobs.calls == 1
    finally:
        blobs.release.set()
    assert _until_ok(c)


def _until_ok(c: TestClient) -> bool:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if c.get(HEALTHZ).status_code == 200:
            return True
        time.sleep(0.05)
    return False


def test_healthz_is_in_the_ingest_contract_only():
    _, c = make(read_token=None)
    assert HEALTHZ in json.loads(server.openapi_document())["paths"]
    assert HEALTHZ not in c.get("/api/openapi.json").text


# --- the contract and the command ------------------------------------------------------


def test_the_committed_openapi_document_is_current():
    assert server.OPENAPI_FILE.read_text() == server.openapi_document(), (
        "src/contraagent/_internal/hub/openapi.json is stale: run `contraagent hub --openapi src/contraagent/_internal/hub/openapi.json`"
    )
    doc = json.loads(server.openapi_document())
    assert set(doc["paths"]) == {INGEST_RECORDS, INGEST_HEARTBEAT, "/ingest/blobs/{sha256}", HEALTHZ}
    assert "security" not in doc["paths"][HEALTHZ]["get"]
    assert set(doc["paths"]["/ingest/blobs/{sha256}"]) == {"head", "put"}
    assert doc["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_openapi_flag_writes_the_document(tmp_path):
    out = tmp_path / "openapi.json"
    assert cli_main(["hub", "--openapi", str(out)]) == 0
    assert out.read_text() == server.openapi_document()


def test_token_files(tmp_path):
    f = tmp_path / "ingest"
    f.write_text("# hosts\nanyhost-token\n\nh2 h2-token\n")
    assert server.read_ingest_tokens(f) == {"anyhost-token": None, "h2-token": "h2"}
    f.write_text("a b c\n")
    with pytest.raises(ValueError):
        server.read_ingest_tokens(f)
    f.write_text("\n# none\n")
    with pytest.raises(ValueError):
        server.read_ingest_tokens(f)
    r = tmp_path / "read"
    r.write_text("\n  the-read-token  \n")
    assert server.read_read_token(r) == "the-read-token"


def test_store_and_blob_specs(tmp_path):
    assert isinstance(server.open_store("memory"), MemoryHubStore)
    assert isinstance(server.open_blobs("memory"), MemoryBlobs)
    assert server.open_blobs(f"dir:{tmp_path}").root == tmp_path  # type: ignore[attr-defined]
    for bad in ("mysql://x", "redis"):
        with pytest.raises(ValueError):
            server.open_store(bad)
    with pytest.raises(ValueError):
        server.open_blobs("ftp://x")


def test_the_command_refuses_to_start_without_ingest_tokens(capsys):
    with pytest.raises(SystemExit):
        cli_main(["hub"])
    assert "--ingest-token-file" in capsys.readouterr().err
