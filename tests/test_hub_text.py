"""Text that a hub cannot hold as it is: a NUL, which Postgres takes in no text, and a lone
surrogate, which UTF-8 and so the wire has no form for.

A relay ships over the hub's real HTTP app, into each `HubStore`. One such character in one
run stops neither that run, the host's other runs nor the host's heartbeat."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")

from fastapi.testclient import TestClient

from contraagent._internal.hub import server
from contraagent._internal.hub.client import HttpClient
from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.relay import Relay
from contraagent._internal.hub.segment_objects import DirectorySegmentObjects
from contraagent._internal.hub.segments import MemorySegmentIndex, PostgresSegmentIndex, SegmentedStreamLogs
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore
from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import StaticLiveness
from contraagent.monitor import DirectorySource, Monitor
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that gives a test the services' credentials
    postgres_dsn,
)

pytestmark = pytest.mark.usefixtures("hub_services")

TOKEN = "ingest"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
ZEROS = b"\x00" * 16
#: What a byte that is not UTF-8 is in a name or an argument that Python reads from the OS.
NOT_UTF8 = "caf\udce9"


@pytest.fixture(params=["memory", "postgres"])
def hub(request, tmp_path) -> Iterator[Hub]:
    if request.param == "postgres":
        from contraagent._internal.hub.postgres import PostgresHubStore

        dsn = postgres_dsn()
        store, index = PostgresHubStore(dsn), PostgresSegmentIndex(dsn)
    else:
        store, index = MemoryHubStore(), MemorySegmentIndex()
    streams = SegmentedStreamLogs(tmp_path / "hot", DirectorySegmentObjects(tmp_path / "segments"), index, background=False)
    hub = Hub(store, MemoryBlobs(), streams=streams)
    yield hub
    hub.close()


@pytest.fixture
def web(hub) -> Iterator[TestClient]:
    app = server.create_hub_app(hub, ingest_tokens=[TOKEN], read_token=None)
    client = TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False)
    yield client
    client.close()


@pytest.fixture
def client(web) -> Iterator[HttpClient]:
    def forward(request: httpx2.Request) -> httpx2.Response:
        got = web.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
        return httpx2.Response(got.status_code, content=got.content)

    client = HttpClient("http://127.0.0.1", TOKEN, transport=httpx2.MockTransport(forward))
    yield client
    client.close()


@pytest.fixture
def runs(tmp_path) -> Path:
    """Two runs: `a`, which a test damages, and `z`, which a relay ships after it."""
    root = tmp_path / "runs"
    for run in ("a", "z"):
        (root / run / layout.STREAMS).mkdir(parents=True)
        info = {"run_id": run, "run_uid": f"uid-{run}", "format": 1, "finished_at": "2026-10-13T00:00:00+00:00"}
        (root / run / layout.RUN_INFO).write_text(json.dumps(info), encoding="utf-8")
        row = {"key": f"k-{run}", "kind": "k", "ok": True, "stop": "completed", "ts": "2026-10-13T00:00:00+00:00"}
        (root / run / layout.JOURNAL).write_bytes(json.dumps(row).encode() + b"\n")
    return root


def relay(client: HttpClient, runs: Path, live: StaticLiveness | None = None) -> Relay:
    liveness = live if live is not None else StaticLiveness(DirectorySource(runs))
    return Relay(client, runs, runs.parent / "progress.json", host_id="h", liveness=liveness)


def held(hub: Hub) -> list[str]:
    return sorted(run.name for run in hub.store.runs())


# --- NUL -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("log", "line"),
    [
        (layout.JOURNAL, ZEROS),
        (layout.JOURNAL, b'{"key": "torn' + ZEROS),
        (layout.JOURNAL, b'{"key": "a' + ZEROS + b'b", "ok": true}'),
        (layout.PLAN, ZEROS + b'{"key": "after zeros"}'),
        (layout.pipeline_log("notes"), ZEROS),
    ],
)
def test_a_line_with_a_nul_is_held_and_still_does_not_read(hub, client, runs, log, line):
    path = runs / "a" / log
    path.parent.mkdir(exist_ok=True)
    with open(path, "ab") as f:
        f.write(line + b"\n")
    with open(path, "ab") as f:  # what is appended after the damage arrives as well
        f.write(b'{"key": "later"}\n')
    assert relay(client, runs).pass_once()
    assert held(hub) == ["a@h", "z@h"]
    local, total = DirectorySource(runs).lines("a", log)
    remote, remote_total = hub.source().lines("a@h", log)
    assert remote_total == total and remote == [text.replace("\x00", "\x1a") for text in local]
    assert [len(text.encode()) for text in remote] == [len(text.encode()) for text in local]
    with pytest.raises(ValueError):  # as on its host: damage never becomes a row
        json.loads(remote[-2])
    assert json.loads(remote[-1]) == {"key": "later"}


def test_the_monitor_of_a_hub_skips_a_damaged_row_as_the_host_s_does(hub, client, runs):
    with open(runs / "a" / layout.JOURNAL, "ab") as f:
        f.write(b'{"key": "a' + ZEROS + b'b", "kind": "k", "ok": true, "stop": "completed"}\n')
    assert relay(client, runs).pass_once()
    assert server.hub_monitor(hub).journal("a@h", 0) == Monitor(runs).journal("a", 0)


def test_a_transcript_keeps_its_nul(hub, client, runs):
    log = layout.stream("k-a")
    (runs / "a" / log).write_bytes(b"binary\x00output\n")
    assert relay(client, runs).pass_once()
    assert hub.source().lines("a@h", log) == (["binary\x00output"], 1)


def test_an_escaped_nul_stays_as_the_host_wrote_it(hub, client, runs):
    text = json.dumps({"schema_version": "1.0", "run": "a\x00b"})
    (runs / "a" / layout.CURSOR).write_text(text, encoding="utf-8")
    assert relay(client, runs).pass_once()
    assert hub.source().document("a@h", layout.CURSOR) == text


def test_a_run_uid_with_a_nul_is_one_run_from_pass_to_pass(hub, client, runs):
    path = runs / "a" / layout.RUN_INFO
    path.write_text(json.dumps({**json.loads(path.read_text()), "run_uid": "u\x00x"}), encoding="utf-8")
    log = layout.stream("k-a")
    (runs / "a" / log).write_bytes(b"one\n")
    shipping = relay(client, runs)
    assert shipping.pass_once()
    with open(runs / "a" / log, "ab") as f:
        f.write(b"two\n")
    with open(runs / "a" / layout.JOURNAL, "ab") as f:
        f.write(b'{"key": "more"}\n')
    assert shipping.pass_once()
    source = hub.source()
    assert source.lines("a@h", log)[0] == ["one", "two"]  # the transcript is found under the uid the hub holds
    assert len(source.lines("a@h", layout.JOURNAL)[0]) == 2


def test_a_contract_s_path_with_a_nul_is_a_missing_file(hub, client, runs):
    path = "out/a\x00b.json"
    contract = runs / "a" / layout.task_entry(layout.CONTRACTS, "k-a")
    contract.parent.mkdir()
    contract.write_text(json.dumps({"key": "k-a", "outputs": [{"path": path}]}), encoding="utf-8")
    local = DirectorySource(runs)
    assert local.file("a", path) is None and local.file_stat("a", path) is None and local._file_head("a", path, 100) is None
    assert relay(client, runs).pass_once()
    assert held(hub) == ["a@h", "z@h"]
    source = hub.source()
    assert source.file("a@h", path) is None and source.file_stat("a@h", path) is None


def test_a_heartbeat_with_a_nul_is_taken(hub, client, runs):
    snapshot = {"alive": True, "launches": [{"key": "a\x00b", "children": [{"cmd": "x\x00y"}]}], "python_tasks": [], "tree": []}
    live = StaticLiveness(DirectorySource(runs), ["a"], {"a": snapshot})
    assert relay(client, runs, live).heartbeat_once()
    assert hub.liveness().live() == {"a@h"}
    [launch] = hub.liveness().snapshot("a@h")["launches"]
    assert launch == {"key": "a\x1ab", "children": [{"cmd": "x\x1ay"}]}


def test_a_hub_takes_a_nul_from_any_relay(hub, web):
    run = {"host_id": "h", "run_id": "r", "run_uid": "u"}
    body = {
        "run": run,
        "logs": [{"log": layout.JOURNAL, "offset": 0, "lines": ["\x00\x00", "{}"]}],
        "documents": [{"name": layout.CURSOR, "text": "\x00"}],
        "files": [{"path": "out/\x00", "sha256": None, "mtime": "\x00"}],
    }
    got = web.post("/ingest/records", content=json.dumps(body), headers=HEADERS)
    assert got.status_code == 200 and got.json()["logs"] == {layout.JOURNAL: 2}
    beat = {"host_id": "h", "sent_at": "\x00", "interval_s": 3, "runs": [{"run": run, "alive": True, "snapshot": {"\x00": "\x00"}}]}
    assert web.post("/ingest/heartbeat", content=json.dumps(beat), headers=HEADERS).status_code == 200


# --- lone surrogates -----------------------------------------------------------------------


def test_a_process_whose_arguments_are_not_utf8_does_not_stop_the_heartbeat(hub, client, runs):
    snapshot = {"alive": True, "launches": [], "python_tasks": [], "tree": [{"full_cmd": f"grep {NOT_UTF8}", "children": []}]}
    live = StaticLiveness(DirectorySource(runs), ["a"], {"a": snapshot})
    assert relay(client, runs, live).heartbeat_once()
    assert hub.liveness().snapshot("a@h")["tree"][0]["full_cmd"] == "grep caf\\udce9"


def test_a_contract_s_path_that_is_not_utf8_reaches_the_hub(hub, client, runs):
    path = f"out/{NOT_UTF8}\ud800.json"  # the second is in no file name of any OS
    contract = runs / "a" / layout.task_entry(layout.CONTRACTS, "k-a")
    contract.parent.mkdir()
    contract.write_text(json.dumps({"key": "k-a", "outputs": [{"path": path}]}), encoding="utf-8")
    assert relay(client, runs).pass_once()
    assert held(hub) == ["a@h", "z@h"]
    assert hub.store.file("a@h", "out/caf\\udce9\\ud800.json") is not None
    assert hub.source().file("a@h", path) is None


@pytest.mark.skipif(sys.platform != "linux", reason="a file name that is not UTF-8 (APFS and NTFS take none)")
def test_a_file_whose_path_is_not_utf8_is_shown_on_the_hub(hub, client, runs):
    path = str(runs.parent / f"{NOT_UTF8}.json")
    Path(path).write_bytes(b"{}")
    contract = runs / "a" / layout.task_entry(layout.CONTRACTS, "k-a")
    contract.parent.mkdir()
    contract.write_text(json.dumps({"key": "k-a", "outputs": [{"path": path}]}), encoding="utf-8")
    assert relay(client, runs).pass_once()
    got = hub.source().file("a@h", path)
    assert got is not None and got.data == b"{}"


@pytest.mark.skipif(sys.platform != "linux", reason="a file name that is not UTF-8 (APFS and NTFS take none)")
def test_a_name_that_is_not_utf8_is_left_out_and_warned_of_once(hub, client, runs, caplog):
    root = os.fsencode(runs)
    os.makedirs(root + b"/bad\xff")
    Path(os.fsdecode(root + b"/bad\xff/run.json")).write_text('{"run_id": "bad", "run_uid": "bad"}')
    os.makedirs(root + b"/a/pipeline")
    for name in (b"notes\xff.json", b"notes\xff.jsonl", b"kept.json"):
        Path(os.fsdecode(root + b"/a/pipeline/" + name)).write_text("{}\n")
    Path(os.fsdecode(root + b"/a/streams/t\xff.stream.jsonl")).write_text("{}\n")
    live = StaticLiveness(DirectorySource(runs), ["bad\udcff", "a"])
    shipping = relay(client, runs, live)
    with caplog.at_level("WARNING"):
        assert shipping.heartbeat_once()
        for _ in range(2):
            assert shipping.pass_once()
            assert shipping.fast_once()
    assert held(hub) == ["a@h", "z@h"] and hub.liveness().live() == {"a@h"}
    assert hub.source().document("a@h", layout.pipeline_document("kept")) == "{}\n"
    said = [r.getMessage() for r in caplog.records if "not UTF-8" in r.getMessage()]
    assert len(said) == 4 == len(set(said))


def test_a_hub_takes_a_lone_surrogate_from_any_relay(hub, web):
    run = {"host_id": "h", "run_id": "r", "run_uid": "u"}
    body = {"run": run, "logs": [{"log": layout.PLAN, "offset": 0, "lines": ["a\ud800b"]}]}
    assert web.post("/ingest/records", content=json.dumps(body), headers=HEADERS).status_code == 200
    assert hub.store.lines("r@h", layout.PLAN) == (["a\\ud800b"], 1)
    beat = {"host_id": "h", "sent_at": "s", "interval_s": 3, "runs": [{"run": run, "alive": True, "snapshot": {"x": ["\ud800"]}}]}
    assert web.post("/ingest/heartbeat", content=json.dumps(beat), headers=HEADERS).status_code == 200


def test_a_run_uid_that_is_not_utf8_does_not_break_the_hub_s_list_of_runs(hub, client, web, runs):
    path = runs / "a" / layout.RUN_INFO
    path.write_text(json.dumps({**json.loads(path.read_text()), "run_uid": NOT_UTF8}), encoding="utf-8")
    assert relay(client, runs).pass_once()
    assert web.get("/api/runs").status_code == 200
    info = hub.source().info("a@h")
    assert info is not None and info["run_uid"] == "caf\\udce9"
