"""The contract of `StreamLogs`: every implementation appends by offset, pages by lines and
bytes, counts, wakes live waiters, and reports activity. `STREAMS` lists the
implementations under test; another joins by adding a factory."""

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from contraagent.hub.client import DirectClient
from contraagent.hub.core import Hub
from contraagent.hub.protocol import LogChunk, RecordBatch, RunRef
from contraagent.hub.segment_objects import DirectorySegmentObjects, MemorySegmentObjects, S3SegmentObjects
from contraagent.hub.segments import MemorySegmentIndex, PostgresSegmentIndex, SegmentedStreamLogs
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.hub.streams import MemoryStreamLogs, StreamLogs
from contraagent.runs import layout
from contraagent.runs.source import PAGE_BYTES, page
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that stops the containers
    postgres_dsn,
    s3_url,
)

pytestmark = pytest.mark.usefixtures("hub_services")

STREAMS: dict[str, Callable[[Path], StreamLogs]] = {
    "memory": lambda tmp: MemoryStreamLogs(),
    # small blocks and segments, so that the tests cross both
    "segments-memory": lambda tmp: SegmentedStreamLogs(
        tmp / "hot", MemorySegmentObjects(), MemorySegmentIndex(), block_bytes=2048, segment_bytes=20_000
    ),
    "segments-directory": lambda tmp: SegmentedStreamLogs(
        tmp / "hot", DirectorySegmentObjects(tmp / "objects"), MemorySegmentIndex(), block_bytes=4096, background=False
    ),
    "segments-postgres-s3": lambda tmp: SegmentedStreamLogs(
        tmp / "hot", S3SegmentObjects(s3_url()), PostgresSegmentIndex(postgres_dsn()), block_bytes=4096, segment_bytes=30_000
    ),
}

LOG = layout.stream("summarize-a")


@pytest.fixture(params=sorted(STREAMS))
def streams(request, tmp_path) -> StreamLogs:
    return STREAMS[request.param](tmp_path)


def test_append_keeps_each_line_once_and_refuses_gaps(streams):
    assert streams.append("r@h", "u", LOG, 0, ["a", "b"], "t1").held == 2
    streams.append("r@h", "u", LOG, 1, ["b", "c"], "t2")
    assert streams.read("r@h", "u", LOG, 0) == (["a", "b", "c"], 3)
    assert streams.append("r@h", "u", LOG, 9, ["z"], "t3").held == 3
    assert streams.count("r@h", "u", LOG) == 3
    assert streams.held("r@h", "u", LOG).durable <= 3


def test_read_pages_by_lines_and_by_bytes(streams):
    big = "x" * 1000
    streams.append("r@h", "u", LOG, 0, [f"{i}:{big}" for i in range(50)], "t1")
    lines, total = streams.read("r@h", "u", LOG, 10, limit=5)
    assert total == 50 and lines == [f"{i}:{big}" for i in range(10, 15)]
    lines, _ = streams.read("r@h", "u", LOG, 0, limit=50, max_bytes=3500)
    assert len(lines) == 3
    huge = "y" * (PAGE_BYTES + 10)
    streams.append("r@h", "u", LOG, 50, [huge, "after"], "t2")
    assert streams.read("r@h", "u", LOG, 50, limit=10, max_bytes=PAGE_BYTES)[0] == [huge]


def test_absent_logs_runs_and_a_new_uid(streams):
    assert streams.read("r@h", "u", LOG, 0) == ([], 0)
    assert streams.count("r@h", "u", LOG) == -1 and streams.held("r@h", "u", LOG) == (0, 0)
    streams.append("r@h", "u1", LOG, 0, ["old"], "t1")
    assert streams.count("r@h", "u2", LOG) == -1
    assert streams.logs("r@h", "u1") == [LOG] and streams.logs("r@h", "u2") == []


def test_activity_is_the_last_append_that_added_lines(streams):
    assert streams.activity("r@h", "u") is None
    streams.append("r@h", "u", LOG, 0, ["a"], "t1")
    streams.append("r@h", "u", LOG, 0, ["a"], "t2")
    assert streams.activity("r@h", "u") == "t1"


def test_a_waiter_wakes_when_another_thread_appends(streams):
    streams.append("r@h", "u", LOG, 0, ["a"], "t1")

    async def watch() -> int:
        threading.Timer(0.05, lambda: streams.append("r@h", "u", LOG, 1, ["b"], "t2")).start()
        return await streams.wait("r@h", "u", LOG, beyond=1, timeout=5)

    assert asyncio.run(watch()) == 2
    # nothing new: the wait ends at its timeout with the count unchanged
    assert asyncio.run(streams.wait("r@h", "u", LOG, beyond=2, timeout=0.05)) == 2


def test_close_keeps_every_line_readable(streams):
    streams.append("r@h", "u", LOG, 0, [f"{i}" for i in range(100)], "t1")
    streams.close("r@h", "u", LOG)
    assert streams.read("r@h", "u", LOG, 90) == ([f"{i}" for i in range(90, 100)], 100)


def test_drop_removes_a_runs_transcripts_and_activity(streams):
    other = layout.stream("summarize-b")
    streams.append("r@h", "u", LOG, 0, [f"{i}" for i in range(100)], "t1")
    streams.close("r@h", "u", LOG)
    streams.append("r@h", "u", other, 0, ["x"], "t1")
    streams.append("r@h", "u2", LOG, 0, ["another run uid"], "t1")
    streams.append("k@h", "u", LOG, 0, ["keep"], "t2")
    assert {("r@h", "u"), ("r@h", "u2"), ("k@h", "u")} <= streams.runs()
    streams.drop("r@h", "u", dry_run=True)
    assert streams.count("r@h", "u", LOG) == 100 and streams.activity("r@h", "u") == "t1"
    streams.drop("r@h", "u")
    assert streams.read("r@h", "u", LOG, 0) == ([], 0) and streams.count("r@h", "u", other) == -1
    assert streams.logs("r@h", "u") == [] and streams.activity("r@h", "u") is None
    assert ("r@h", "u") not in streams.runs()
    assert streams.drop("r@h", "u") == [] and streams.drop("never@h", "u") == []
    assert streams.read("k@h", "u", LOG, 0) == (["keep"], 1)
    assert streams.read("r@h", "u2", LOG, 0) == (["another run uid"], 1)
    # an append after the drop starts the log anew
    assert streams.append("r@h", "u", LOG, 100, ["late"], "t3").held == 0
    assert streams.append("r@h", "u", LOG, 0, ["a"], "t3").held == 1
    assert streams.read("r@h", "u", LOG, 0) == (["a"], 1)


def test_page_bounds():
    assert page(["a", "b", "c"], 2, None) == ["a", "b"]
    assert page(["aaaa", "b"], None, 3) == ["aaaa"]
    assert page([], 5, 5) == []


def test_the_hub_sends_transcripts_to_the_stream_logs_and_closes_them_with_the_journal(streams):
    hub = Hub(MemoryHubStore(), MemoryBlobs(), streams=streams)
    client = DirectClient(hub)
    run = RunRef(host_id="h", run_id="r", run_uid="u")
    got = client.send_records(RecordBatch(run=run, logs=[LogChunk(log=LOG, offset=0, lines=["e1", "e2"])]))
    assert got.logs[LOG] == 2 and got.durable[LOG] <= 2
    assert hub.store.count("r@h", LOG) == -1  # not in the record store
    source = hub.source()
    assert source.lines("r@h", LOG) == (["e1", "e2"], 2) and source.size("r@h", LOG) == 2
    assert source.exists("r@h", layout.STREAMS) and source.exists("r@h", LOG)
    journal = LogChunk(log=layout.JOURNAL, offset=0, lines=['{"key": "summarize-a", "ok": true}'])
    assert client.send_records(RecordBatch(run=run, logs=[journal])).durable[layout.JOURNAL] == 1
    assert source.activity("r@h") is not None
