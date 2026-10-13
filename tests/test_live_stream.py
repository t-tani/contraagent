"""The live path of a task transcript: a coding agent's stream file, the relay, the hub's
`StreamLogs`, and a viewer of `/events/stream`, with resume by `Last-Event-ID` and pages
that hand over by line offset."""

from __future__ import annotations

import asyncio
import gc
import json
import os
import socket
import statistics
import threading
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
pytest.importorskip("httpx")

import httpx

from contraagent import rundir
from contraagent.hub import server as hub_server
from contraagent.hub.client import DirectClient, HttpClient
from contraagent.hub.core import Hub
from contraagent.hub.protocol import DocumentPut, LogChunk, RecordBatch, RunRef
from contraagent.hub.relay import Relay
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.monitor import Monitor
from contraagent.monitor.server import stream_feed
from contraagent.monitor.source import DirectorySource, StaticLiveness

KEY = "t1"
LOG = rundir.stream(KEY)
RUN = RunRef(host_id="h1", run_id="r1", run_uid="u1")
TOKEN = "ingest"


async def connected() -> bool:
    return False


def texts(page: dict) -> list[str]:
    """The lines a page carries: each plain-text line is one omp `text_delta` event."""
    return [e["delta"].rstrip("\n") for e in page["events"]]


def new_hub(lines: int = 0) -> Hub:
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    info = json.dumps({"run_id": RUN.run_id, "run_uid": RUN.run_uid})
    hub.records(RecordBatch(run=RUN, documents=[DocumentPut(name=rundir.RUN_INFO, text=info)]))
    append(hub, 0, lines)
    return hub


def append(hub: Hub, first: int, n: int) -> None:
    lines = [f"line {i}" for i in range(first, first + n)]
    hub.records(RecordBatch(run=RUN, logs=[LogChunk(log=LOG, offset=first, lines=lines)]))


# --- waiting on a log ----------------------------------------------------------------------


def test_a_waiter_wakes_promptly_on_an_append_from_another_thread():
    hub = new_hub(10)
    source = hub.source()

    async def wait() -> tuple[int, float]:
        threading.Timer(0.1, append, (hub, 10, 1)).start()
        began = time.monotonic()
        got = await source.wait(RUN.name, LOG, 10, 5.0)
        return got, time.monotonic() - began - 0.1

    got, late = asyncio.run(wait())
    assert got == 11
    assert late < 0.1


def test_a_wait_returns_after_its_timeout_when_nothing_grows(tmp_path):
    (tmp_path / "r1" / "streams").mkdir(parents=True)
    (tmp_path / "r1" / LOG).write_text("a\n")
    source = DirectorySource(tmp_path)

    async def wait() -> tuple[int, float]:
        began = time.monotonic()
        return await source.wait("r1", LOG, 2, 0.3), time.monotonic() - began

    size, took = asyncio.run(wait())
    assert size == 2 and 0.25 < took < 0.6


def test_a_directory_wait_wakes_on_a_write(tmp_path):
    (tmp_path / "r1" / "streams").mkdir(parents=True)
    path = tmp_path / "r1" / LOG
    path.touch()
    source = DirectorySource(tmp_path)

    def write() -> None:
        with open(path, "a") as f:
            f.write("a\n")

    async def wait() -> tuple[int, float]:
        threading.Timer(0.1, write).start()
        began = time.monotonic()
        got = await source.wait("r1", LOG, 0, 5.0)
        return got, time.monotonic() - began - 0.1

    got, late = asyncio.run(wait())
    assert got == 2 and late < 0.2


# --- the transcript feed -------------------------------------------------------------------


def test_the_tail_page_then_live_lines_carry_each_line_once():
    hub = new_hub(3000)
    mon = hub.monitor()

    async def watch() -> list[dict]:
        got: list[dict] = []
        feed = stream_feed(mon, RUN.name, KEY, None, connected)

        def writer() -> None:
            n = 3000
            for size in (1, 7, 2000, 9000, 3):  # 9000 lines are more than one page
                append(hub, n, size)
                n += size
                time.sleep(0.02)

        async for msg in feed:
            got.append(msg)
            if len(got) == 1:
                threading.Thread(target=writer).start()
            if int(msg["id"]) == 3000 + 1 + 7 + 2000 + 9000 + 3:
                await feed.aclose()
                return got
        raise AssertionError("the feed ended")

    msgs = asyncio.run(watch())
    pages = [json.loads(m["data"]) for m in msgs]
    assert pages[0]["behind"] == 1500 and msgs[0]["id"] == "3000"
    seen = [t for p in pages for t in texts(p)]
    assert seen == [f"line {i}" for i in range(1500, 3000 + 1 + 7 + 2000 + 9000 + 3)]
    ids = [int(m["id"]) for m in msgs]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_a_feed_resumes_at_its_start_line_with_no_tail_page():
    hub = new_hub(50)
    mon = hub.monitor()

    async def first(start: int | None) -> dict:
        feed = stream_feed(mon, RUN.name, KEY, start, connected)
        try:
            return await anext(feed)
        finally:
            await feed.aclose()

    msg = asyncio.run(first(20))
    page = json.loads(msg["data"])
    assert msg["id"] == "50" and page["behind"] == 0
    assert texts(page) == [f"line {i}" for i in range(20, 50)]
    # A start past the log's end: another log under the run's name; it starts over with its tail.
    msg = asyncio.run(first(80))
    assert msg["id"] == "50" and texts(json.loads(msg["data"]))[0] == "line 0"


def test_a_slow_viewer_does_not_grow_memory():
    """Feeds that stopped reading hold only their line offset: appending to the log
    costs the same memory with 20 of them as with none, and each one catches up a page
    at a time."""
    lines = 100_000

    def grown(viewers: int) -> tuple[int, list]:
        hub = new_hub(10)
        mon = hub.monitor()
        loop = asyncio.new_event_loop()
        feeds = [stream_feed(mon, RUN.name, KEY, None, connected) for _ in range(viewers)]
        for feed in feeds:
            loop.run_until_complete(anext(feed))
        gc.collect()
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        for n in range(10, 10 + lines, 5000):
            append(hub, n, 5000)
        after = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        caught = [loop.run_until_complete(anext(feed)) for feed in feeds]
        for feed in feeds:
            loop.run_until_complete(feed.aclose())
        loop.close()
        return after - before, caught

    alone, _ = grown(0)
    watched, caught = grown(20)
    assert watched < alone * 1.2
    for msg in caught:
        page = json.loads(msg["data"])
        assert texts(page)[0] == "line 10" and len(page["events"]) == 1500 and msg["id"] == str(10 + 1500)


def test_the_local_monitors_transcript_feed_follows_a_file(tmp_path):
    run = tmp_path / "r1"
    (run / "streams").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"run_id": "r1"}))
    path = run / LOG
    path.write_text("line 0\nline 1\n")
    mon = Monitor(tmp_path)

    def writer() -> None:
        with open(path, "a") as f:
            f.write("line 2\n")
            f.flush()
            time.sleep(0.2)
            f.write('{"type": "message_')  # a JSON line half written
            f.flush()
            time.sleep(0.3)
            f.write('update"}\nline 3\n')

    async def watch() -> list[tuple[dict, float]]:
        got = []
        feed = stream_feed(mon, "r1", KEY, None, connected)
        began = time.monotonic()
        async for msg in feed:
            got.append((msg, time.monotonic() - began))
            if len(got) == 1:
                threading.Thread(target=writer).start()
            if msg["id"] == "5":
                await feed.aclose()
                return got
        raise AssertionError("the feed ended")

    got = asyncio.run(asyncio.wait_for(watch(), 10))
    pages = [json.loads(m["data"]) for m, _ in got]
    assert texts(pages[0]) == ["line 0", "line 1"]
    assert texts(pages[1]) == ["line 2"] and got[1][1] < 0.5
    assert [m["id"] for m, _ in got] == ["2", "3", "5"]  # the half-written line was not read until complete
    assert len(pages[2]["events"]) == 2 and texts(pages[2])[-1] == "line 3"


# --- over HTTP: the hub's SSE endpoint, the relay -----------------------------------------


@contextmanager
def serving(hub: Hub) -> Iterator[str]:
    """The hub's ASGI app on a free local port, in a thread of its own."""
    import uvicorn

    app = hub_server.create_hub_app(hub, ingest_tokens=[TOKEN], read_token=None)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not srv.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.should_exit = True
        thread.join(5)
        sock.close()


def sse(response) -> Iterator[dict]:
    """The messages of a `text/event-stream` response, as `{field: value}`."""
    msg: dict = {}
    for line in response.iter_lines():
        if not line:
            if "data" in msg:
                yield msg
            msg = {}
        elif not line.startswith(":"):
            field, _, value = line.partition(":")
            msg[field] = value[1:] if value.startswith(" ") else value


def test_the_sse_endpoint_resumes_with_last_event_id_with_no_gap_or_duplicate():
    hub = new_hub(10)
    seen: list[str] = []
    with serving(hub) as base, httpx.Client(base_url=base, timeout=10) as c:
        url = f"/events/stream?run={RUN.name}&key={KEY}"
        with c.stream("GET", url) as r:
            messages = sse(r)
            first = next(messages)
            assert first["event"] == "stream" and first["id"] == "10"
            seen += texts(json.loads(first["data"]))
            append(hub, 10, 5)
            msg = next(messages)
            seen += texts(json.loads(msg["data"]))
            last = msg["id"]
        assert last == "15"
        append(hub, 15, 7)  # written while no one watches
        with c.stream("GET", url, headers={"Last-Event-ID": last}) as r:
            msg = next(sse(r))
            page = json.loads(msg["data"])
            assert page["behind"] == 0 and msg["id"] == "22"
            seen += texts(page)
        with c.stream("GET", url + "&from=20") as r:
            assert texts(json.loads(next(sse(r))["data"])) == ["line 20", "line 21"]
    assert seen == [f"line {i}" for i in range(22)]


def runs_dir(tmp_path: Path, *runs: str) -> Path:
    root = tmp_path / "runs"
    for run in runs:
        (root / run / "streams").mkdir(parents=True)
        (root / run / "run.json").write_text(json.dumps({"run_id": run, "run_uid": f"uid-{run}"}))
        (root / run / LOG).write_text("line 0\n")
    return root


def held(hub: Hub, run: str) -> int:
    return hub.streams.count(f"{run}@h1", f"uid-{run}", LOG)


def until(check, timeout: float) -> float:
    """Seconds until `check()` is true; fails after `timeout`."""
    began = time.monotonic()
    while not check():
        if time.monotonic() - began > timeout:
            raise AssertionError("not within the time")
        time.sleep(0.005)
    return time.monotonic() - began


def test_the_relay_ships_an_active_transcript_fast_and_an_idle_run_at_its_interval(tmp_path):
    root = runs_dir(tmp_path, "busy", "idle")
    old = time.time() - 60
    os.utime(root / "idle" / LOG, (old, old))
    snapshot = {"run": "busy", "alive": True, "launches": [{"key": KEY}], "python_tasks": []}
    liveness = StaticLiveness(DirectorySource(root), live={"busy", "idle"}, snapshots={"busy": snapshot})
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    relay = Relay(DirectClient(hub), root, tmp_path / "progress.json", host_id="h1", interval_s=30, liveness=liveness)
    stop = threading.Event()
    thread = threading.Thread(target=relay.serve, args=(stop,))
    thread.start()
    try:
        until((tmp_path / "progress.json").exists, 5)  # the first pass is over
        assert held(hub, "busy") == held(hub, "idle") == 1
        until(lambda: bool(relay._running), 5)
        # The idle run's transcript grows with an old modification time (written aside, then
        # renamed), so no fast look sees it written recently.
        aside = root / "idle" / "streams" / "aside"
        aside.write_text("line 0\nline 1\n")
        os.utime(aside, (old, old))
        aside.replace(root / "idle" / LOG)
        with open(root / "busy" / LOG, "a") as f:
            f.write("line 1\n")
        assert until(lambda: held(hub, "busy") == 2, 2) < 0.5
        time.sleep(1.0)
        assert held(hub, "idle") == 1
    finally:
        stop.set()
        thread.join(5)
    relay.pass_once()
    assert held(hub, "idle") == 2


def test_latency_from_append_to_sse_delivery(tmp_path):
    """A line appended to a stream file reaches a viewer of the hub's SSE endpoint through
    the relay (`HttpClient`, its fast path) and the hub, well within a second."""
    root = runs_dir(tmp_path, "r1")
    path = root / "r1" / LOG
    snapshot = {"run": "r1", "alive": True, "launches": [{"key": KEY}], "python_tasks": []}
    liveness = StaticLiveness(DirectorySource(root), live={"r1"}, snapshots={"r1": snapshot})
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    count = 120
    written: dict[int, float] = {}
    delivered: dict[int, float] = {}
    with serving(hub) as base:
        client = HttpClient(base, TOKEN)
        relay = Relay(client, root, tmp_path / "progress.json", host_id="h1", interval_s=3.0, liveness=liveness)
        stop = threading.Event()
        relaying = threading.Thread(target=relay.serve, args=(stop,))
        relaying.start()
        until(lambda: held(hub, "r1") == 1, 5)
        ready = threading.Event()

        def view() -> None:
            with httpx.Client(base_url=base, timeout=30) as c, c.stream("GET", f"/events/stream?run=r1@h1&key={KEY}") as r:
                for msg in sse(r):
                    now = time.monotonic()
                    ready.set()
                    for text in texts(json.loads(msg["data"])):
                        if text.startswith("at "):
                            delivered[int(text.split()[1])] = now
                    if len(delivered) == count:
                        return

        viewer = threading.Thread(target=view)
        viewer.start()
        ready.wait(5)
        try:
            with open(path, "a") as f:
                for i in range(count):
                    written[i] = time.monotonic()
                    f.write(f"at {i}\n")
                    f.flush()
                    time.sleep(0.013 * (1 + i % 5))  # bursts and pauses, 0.013 to 0.065 s apart
            viewer.join(10)
        finally:
            stop.set()
            relaying.join(5)
            client.close()
    latencies = sorted(delivered[i] - written[i] for i in written if i in delivered)
    assert len(latencies) == count
    p50 = statistics.median(latencies)
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    worst = latencies[-1]
    print(f"\nappend to SSE delivery over {count} lines: p50 {p50 * 1000:.0f} ms, p95 {p95 * 1000:.0f} ms, max {worst * 1000:.0f} ms")
    assert p95 < 1.0
