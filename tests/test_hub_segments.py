"""What `SegmentedStreamLogs` keeps beyond the `StreamLogs` contract: the segment format,
the index and its rebuild from the objects, when segments are sealed, recovery after a
crash at any step, and reads that cost one ranged read per page."""

import random
import threading

import pytest
import zstandard

from contraagent._internal.hub import segment_format as fmt
from contraagent._internal.hub.segment_objects import DirectorySegmentObjects, MemorySegmentObjects, S3SegmentObjects
from contraagent._internal.hub.segments import (
    BlockCache,
    MemorySegmentIndex,
    PostgresSegmentIndex,
    Segment,
    SegmentedStreamLogs,
    from_spec,
    object_key,
    parse_object_key,
    rebuild_index,
)
from contraagent._internal.runs import layout
from contraagent._internal.runs.source import page
from hub_services import (
    hub_services,  # noqa: F401  # the fixture that stops the containers
    postgres_dsn,
    s3_url,
)

pytestmark = pytest.mark.usefixtures("hub_services")

LOG = layout.stream("summarize-a")
NAME, UID = "r@h", "u1"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class CountingObjects:
    """`SegmentObjects` that counts its ranged reads and can fail its next index commit."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.gets = 0
        self.puts = 0

    def put(self, key, data):
        self.puts += 1
        self.inner.put(key, data)

    def get_range(self, key, start, end):
        self.gets += 1
        return self.inner.get_range(key, start, end)

    def delete(self, key):
        self.inner.delete(key)

    def keys(self, prefix=""):
        return self.inner.keys(prefix)


class FailingIndex(MemorySegmentIndex):
    """A memory index whose `add` fails while `fail` is set: a crash between put and commit."""

    fail = False

    def add(self, segment, activity):
        if self.fail:
            raise RuntimeError("crash before the index commit")
        super().add(segment, activity)


def lines_of(n: int, seed: int = 0) -> list[str]:
    rnd = random.Random(seed)
    return [f'{{"i": {i}, "t": "{"x" * rnd.randint(0, 400)}"}}' for i in range(n)]


def hot_files(tmp_path) -> list:
    return sorted(p for p in (tmp_path / "hot").rglob("*") if p.is_file())


def make(tmp_path, objects=None, index=None, **kwargs) -> SegmentedStreamLogs:
    kwargs.setdefault("background", False)
    return SegmentedStreamLogs(
        tmp_path / "hot",
        objects if objects is not None else MemorySegmentObjects(),
        index if index is not None else MemorySegmentIndex(),
        **kwargs,
    )


def read_all(logs, log=LOG) -> list[str]:
    out: list[str] = []
    while True:
        got, total = logs.read(NAME, UID, log, len(out), limit=777, max_bytes=100_000)
        out.extend(got)
        if len(out) >= total:
            return out


# --- the format --------------------------------------------------------------------------


def segment_bytes(lines: list[str], first: int = 0, block_bytes: int = fmt.BLOCK_BYTES) -> tuple[bytes, list[fmt.Block]]:
    raw = b"".join(line.encode() + b"\n" for line in lines)
    return fmt.encode(raw, fmt.cut(raw, first, block_bytes), len(lines))


def decode_all(data: bytes, blocks: list[fmt.Block]) -> list[str]:
    return [line for b in blocks for line in fmt.decode(data[b.offset : b.offset + b.compressed])]


def test_a_segment_round_trips_with_a_huge_line_alone_in_its_block():
    huge = "h" * (5 << 20)
    lines = ["a", "b" * 300_000, "c", huge, "d", "é" * 10]
    data, blocks = segment_bytes(lines, first=40)
    assert decode_all(data, blocks) == lines
    assert [b.first_line for b in blocks] == [40, 41, 42, 43, 44]  # a line longer than a block makes its own
    assert blocks[3].size == len(huge) + 1
    footer = data[-fmt.footer_length(data[-fmt.TAIL_BYTES :]) :]
    assert fmt.parse_footer(footer) == (blocks, len(lines))
    assert fmt.unpack_blocks(fmt.pack_blocks(blocks)) == blocks
    # plain zstd decompresses the whole object into the lines, skipping the footer
    with zstandard.ZstdDecompressor().stream_reader(data, read_across_frames=True) as reader:
        assert reader.read().decode().split("\n")[:-1] == lines


def test_a_segment_of_200k_lines_cuts_blocks_near_the_block_size():
    lines = lines_of(200_000)
    data, blocks = segment_bytes(lines)
    assert decode_all(data, blocks) == lines
    assert len(blocks) > 100 and all(b.size <= fmt.BLOCK_BYTES for b in blocks)
    assert all(b.size > fmt.BLOCK_BYTES - 1000 for b in blocks[:-1])
    assert fmt.parse_footer(data[-fmt.footer_length(data[-9:]) :]) == (blocks, 200_000)
    assert sum(b.compressed for b in blocks) < len(data) < sum(b.compressed for b in blocks) + 25 * len(blocks)


def test_a_damaged_footer_is_refused():
    data, _ = segment_bytes(["a", "b"])
    with pytest.raises(fmt.BadSegment):
        fmt.footer_length(data[:-1] + b"\x00")
    footer = bytearray(data[-fmt.footer_length(data[-9:]) :])
    footer[0] ^= 0xFF
    with pytest.raises(fmt.BadSegment):
        fmt.parse_footer(bytes(footer))


def test_object_keys_name_the_log_and_its_first_line():
    key = object_key(NAME, UID, LOG, 1200)
    assert key == f"r@h/u1/{LOG}/1200.seg"
    assert parse_object_key(key) == (NAME, UID, LOG, 1200)
    assert parse_object_key("r@h/u1/x.seg") is None and parse_object_key(f"r@h/u1/{LOG}/x.seg") is None


# --- seals -------------------------------------------------------------------------------


def test_a_segment_seals_when_it_reaches_its_size(tmp_path):
    objects = CountingObjects(MemorySegmentObjects())
    logs = make(tmp_path, objects, block_bytes=1000, segment_bytes=10_000)
    every = lines_of(300)
    for i in range(0, 300, 10):
        logs.append(NAME, UID, LOG, i, every[i : i + 10], "t")
    held = logs.held(NAME, UID, LOG)
    assert held.held == 300 and held.durable > 0
    assert len(objects.keys()) == objects.puts > 3
    rows = logs.index.segments(NAME, UID, LOG)
    assert [r.first_line for r in rows] == sorted(r.first_line for r in rows) and rows[0].first_line == 0
    assert all(rows[i].first_line + rows[i].line_count == rows[i + 1].first_line for i in range(len(rows) - 1))
    assert read_all(logs) == every


def test_a_segment_seals_when_its_log_is_closed(tmp_path):
    logs = make(tmp_path)
    logs.append(NAME, UID, LOG, 0, ["a", "b"], "t")
    assert logs.held(NAME, UID, LOG) == (2, 0)
    assert hot_files(tmp_path)
    logs.close(NAME, UID, LOG)
    assert logs.held(NAME, UID, LOG) == (2, 2)
    assert not hot_files(tmp_path)
    logs.append(NAME, UID, LOG, 2, ["c"], "t")  # a closed log that grows again opens a new segment
    assert logs.read(NAME, UID, LOG, 0) == (["a", "b", "c"], 3) and logs.held(NAME, UID, LOG) == (3, 2)


def test_a_segment_seals_after_its_idle_time_and_after_its_age(tmp_path):
    clock = Clock()
    logs = make(tmp_path, idle_s=600, age_s=3600, clock=clock)
    logs.append(NAME, UID, LOG, 0, ["a"], "t")
    clock.now += 599
    logs.tick()
    assert logs.held(NAME, UID, LOG).durable == 0
    clock.now += 1
    logs.tick()
    assert logs.held(NAME, UID, LOG) == (1, 1)
    # appends every 5 minutes keep it from idling; its age seals it
    other = layout.stream("summarize-b")
    for i in range(13):
        logs.append(NAME, UID, other, i, [str(i)], "t")
        clock.now += 300
        logs.tick()
        if logs.held(NAME, UID, other).durable:
            break
    assert logs.held(NAME, UID, other) == (12, 12) and i == 11


def test_seals_run_in_the_background(tmp_path):
    logs = SegmentedStreamLogs(tmp_path / "hot", MemorySegmentObjects(), MemorySegmentIndex(), segment_bytes=1000)
    every = lines_of(200)
    for i in range(0, 200, 20):
        logs.append(NAME, UID, LOG, i, every[i : i + 20], "t")
    logs.close(NAME, UID, LOG)
    assert read_all(logs) == every
    logs.shutdown()
    assert logs.held(NAME, UID, LOG) == (200, 200)


def test_a_seal_that_finishes_during_a_read_keeps_the_file_until_the_read_ends(tmp_path):
    """A read holds the files of the segments in its snapshot: a seal that finishes
    meanwhile leaves the file for the read, which deletes it when it ends."""
    logs = SegmentedStreamLogs(tmp_path / "hot", MemorySegmentObjects(), MemorySegmentIndex(), background=False)
    every = lines_of(50)
    logs.append(NAME, UID, LOG, 0, every, "t")
    (path,) = hot_files(tmp_path)
    reading, sealed = threading.Event(), threading.Event()
    real = logs._read_hot

    def slow_read_hot(*args, **kwargs):
        reading.set()
        assert sealed.wait(5)
        return real(*args, **kwargs)

    logs._read_hot = slow_read_hot  # type: ignore[method-assign]
    got: list = []
    reader = threading.Thread(target=lambda: got.append(logs.read(NAME, UID, LOG, 0)))
    reader.start()
    assert reading.wait(5)
    logs.close(NAME, UID, LOG)  # seals inline, while the read holds the file
    assert logs.held(NAME, UID, LOG) == (50, 50)
    assert path.exists()
    sealed.set()
    reader.join(5)
    assert got == [(every, 50)]
    assert not path.exists()
    logs.shutdown()


def test_appends_reads_and_background_seals_from_many_threads(tmp_path):
    logs = SegmentedStreamLogs(
        tmp_path / "hot", MemorySegmentObjects(), MemorySegmentIndex(), block_bytes=500, segment_bytes=5000, cache_bytes=20_000
    )
    every = lines_of(1000)
    names = [layout.stream(f"t{i}") for i in range(4)]
    errors: list[BaseException] = []
    done = threading.Event()

    def ingest(log: str, seed: int) -> None:
        rnd = random.Random(seed)
        held = 0
        try:
            while held < len(every):
                start = max(0, held - rnd.randint(0, 5))
                held = logs.append(NAME, UID, log, start, every[start : start + rnd.randint(1, 40)], "t").held
            logs.close(NAME, UID, log)
        except BaseException as e:
            errors.append(e)

    def watch() -> None:
        rnd = random.Random(9)
        try:
            while not done.is_set():
                log = rnd.choice(names)
                since = rnd.randint(0, 1000)
                got, total = logs.read(NAME, UID, log, since, limit=rnd.randint(1, 200), max_bytes=rnd.choice([None, 3000]))
                assert got == every[since : since + len(got)] and (got or since >= total)
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=ingest, args=(log, i)) for i, log in enumerate(names)]
    readers = [threading.Thread(target=watch) for _ in range(2)]
    for t in threads + readers:
        t.start()
    for t in threads:
        t.join()
    done.set()
    for t in readers:
        t.join()
    logs.shutdown()
    assert not errors, errors
    for log in names:
        assert logs.held(NAME, UID, log) == (1000, 1000) and read_all(logs, log) == every


# --- recovery ----------------------------------------------------------------------------


def test_a_restart_resumes_open_segments_and_serves_every_line(tmp_path):
    objects, index = DirectorySegmentObjects(tmp_path / "objects"), MemorySegmentIndex()
    logs = make(tmp_path, objects, index, block_bytes=2000, segment_bytes=20_000)
    every = lines_of(500)
    logs.append(NAME, UID, LOG, 0, every[:400], "t1")
    logs.shutdown()
    durable = logs.held(NAME, UID, LOG).durable
    assert 0 < durable < 400
    again = make(tmp_path, objects, index, block_bytes=2000, segment_bytes=20_000)
    assert again.held(NAME, UID, LOG) == (400, durable)
    assert read_all(again) == every[:400]
    assert again.append(NAME, UID, LOG, 350, every[350:], "t2").held == 500
    again.close(NAME, UID, LOG)
    assert read_all(again) == every and again.held(NAME, UID, LOG) == (500, 500)
    assert again.logs(NAME, UID) == [LOG]


def test_a_torn_last_line_is_cut_on_restart(tmp_path):
    logs = make(tmp_path)
    logs.append(NAME, UID, LOG, 0, ["a", "b"], "t")
    logs.shutdown()
    (hot,) = hot_files(tmp_path)
    with open(hot, "ab") as f:
        f.write(b'{"half')
    again = make(tmp_path, logs.objects, logs.index)
    assert again.read(NAME, UID, LOG, 0) == (["a", "b"], 2)
    assert again.append(NAME, UID, LOG, 2, ["c"], "t").held == 3
    assert hot.read_bytes() == b"a\nb\nc\n"


def test_a_crash_between_put_and_index_commit_loses_nothing(tmp_path):
    objects, index = MemorySegmentObjects(), FailingIndex()
    logs = make(tmp_path, objects, index)
    logs.append(NAME, UID, LOG, 0, ["a", "b", "c"], "t")
    index.fail = True
    logs.close(NAME, UID, LOG)  # the object is put, the commit fails: a crash at this step
    assert objects.keys() == [object_key(NAME, UID, LOG, 0)] and index.keys() == set()
    assert logs.held(NAME, UID, LOG) == (3, 0)
    logs.shutdown()
    index.fail = False
    again = make(tmp_path, objects, index)
    assert again.sweep() == [object_key(NAME, UID, LOG, 0)]  # the orphan
    assert objects.keys() == []
    assert again.read(NAME, UID, LOG, 0) == (["a", "b", "c"], 3)
    again.close(NAME, UID, LOG)
    assert again.held(NAME, UID, LOG) == (3, 3) and objects.keys() == [object_key(NAME, UID, LOG, 0)]
    assert again.sweep() == []


def test_a_failed_seal_is_retried_at_the_next_tick(tmp_path):
    index = FailingIndex()
    logs = make(tmp_path, index=index)
    logs.append(NAME, UID, LOG, 0, ["a"], "t")
    index.fail = True
    logs.close(NAME, UID, LOG)
    logs.append(NAME, UID, LOG, 1, ["b"], "t")
    assert logs.read(NAME, UID, LOG, 0) == (["a", "b"], 2)
    index.fail = False
    logs.tick()
    assert logs.held(NAME, UID, LOG) == (2, 1)
    logs.close(NAME, UID, LOG)
    assert logs.held(NAME, UID, LOG) == (2, 2) and read_all(logs) == ["a", "b"]


def test_a_crash_after_the_index_commit_drops_the_sealed_file_on_restart(tmp_path):
    logs = make(tmp_path)
    logs.append(NAME, UID, LOG, 0, ["a", "b"], "t")
    (hot,) = hot_files(tmp_path)
    kept = hot.read_bytes()
    logs.close(NAME, UID, LOG)
    logs.shutdown()
    hot.write_bytes(kept)  # the file was not deleted before the crash
    again = make(tmp_path, logs.objects, logs.index)
    assert not hot.exists()
    assert again.read(NAME, UID, LOG, 0) == (["a", "b"], 2) and again.held(NAME, UID, LOG) == (2, 2)


def test_an_open_segment_whose_rows_were_lost_resumes_after_the_objects_that_continue_it(tmp_path):
    objects = DirectorySegmentObjects(tmp_path / "objects")
    logs = make(tmp_path, objects, segment_bytes=500)
    every = lines_of(40)
    logs.append(NAME, UID, LOG, 0, every[:30], "t")  # one segment sealed by size
    logs.append(NAME, UID, LOG, 30, every[30:], "t")  # open
    logs.shutdown()
    durable = logs.held(NAME, UID, LOG).durable
    assert 0 < durable < 40
    again = make(tmp_path, objects, MemorySegmentIndex(), segment_bytes=500)  # the index is lost
    assert read_all(again) == every and again.held(NAME, UID, LOG) == (40, durable)


def test_an_open_segment_past_every_line_held_is_dropped_and_resent(tmp_path):
    logs = make(tmp_path, segment_bytes=500)
    every = lines_of(40)
    logs.append(NAME, UID, LOG, 0, every[:30], "t")
    logs.append(NAME, UID, LOG, 30, every[30:], "t")
    logs.shutdown()
    again = make(tmp_path)  # objects and index lost: lines 0..29 are gone, so 30.. cannot stand
    assert again.held(NAME, UID, LOG) == (0, 0) and not hot_files(tmp_path)
    assert again.append(NAME, UID, LOG, 0, every, "t").held == 40
    assert read_all(again) == every


def test_activity_survives_a_restart(tmp_path):
    logs = make(tmp_path)
    logs.append(NAME, UID, LOG, 0, ["a"], "t1")
    logs.tick()
    again = make(tmp_path, logs.objects, logs.index)
    assert again.activity(NAME, UID) == "t1"
    again.append(NAME, UID, LOG, 1, ["b"], "t2")
    assert again.activity(NAME, UID) == "t2"


def test_the_index_rebuilds_from_the_objects_alone(tmp_path):
    objects = DirectorySegmentObjects(tmp_path / "objects")
    logs = make(tmp_path, objects, block_bytes=1000, segment_bytes=8000)
    for log in (LOG, layout.stream("summarize-b")):
        logs.append(NAME, UID, log, 0, lines_of(150), "t")
        logs.close(NAME, UID, log)
    rebuilt = MemorySegmentIndex()
    assert rebuild_index(objects, rebuilt) == len(objects.keys()) > 2
    for log in (LOG, layout.stream("summarize-b")):
        assert rebuilt.segments(NAME, UID, log) == logs.index.segments(NAME, UID, log)
    # from_spec rebuilds a memory index on start, and keeps every object
    again = from_spec(tmp_path / "hot", str(tmp_path / "objects"), None, background=False)
    assert read_all(again) == lines_of(150) and len(objects.keys()) == len(rebuilt.keys())


# --- reads -------------------------------------------------------------------------------


def test_a_page_within_a_segment_costs_one_ranged_read_and_none_when_cached(tmp_path):
    objects = CountingObjects(MemorySegmentObjects())
    logs = make(tmp_path, objects)
    every = lines_of(20_000)
    logs.append(NAME, UID, LOG, 0, every, "t")
    logs.close(NAME, UID, LOG)
    (row,) = logs.index.segments(NAME, UID, LOG)
    assert len(fmt.unpack_blocks(row.blocks)) > 10
    for since in range(0, 20_000, 1500):
        logs.cache = BlockCache()
        objects.gets = 0
        lines, total = logs.read(NAME, UID, LOG, since, limit=1500, max_bytes=4 << 20)
        assert lines == every[since : since + 1500] and total == 20_000
        assert objects.gets == 1  # cold: one ranged read per page
    assert logs.read(NAME, UID, LOG, 3000, limit=1500)[0] == every[3000:4500]
    objects.gets = 0
    assert logs.read(NAME, UID, LOG, 3000, limit=1500)[0] == every[3000:4500]
    assert objects.gets == 0  # warm
    # a page bounded by bytes reads only the blocks it needs
    logs.cache = BlockCache()
    assert logs.read(NAME, UID, LOG, 100, max_bytes=1000)[0] == page(every[100:], None, 1000)
    assert len(logs.cache) <= 2


def test_a_page_across_segments_and_the_open_segment(tmp_path):
    objects = CountingObjects(MemorySegmentObjects())
    logs = make(tmp_path, objects, block_bytes=1000, segment_bytes=10_000)
    every = lines_of(300)
    logs.append(NAME, UID, LOG, 0, every, "t")
    assert logs.held(NAME, UID, LOG).durable < 300
    for since in (0, 17, 150, 290, 299, 300, 400):
        for limit in (None, 1, 33, 1000):
            for max_bytes in (None, 10, 2500, 50_000):
                got = logs.read(NAME, UID, LOG, since, limit, max_bytes)
                assert got == (page(every[since:], limit, max_bytes), 300), (since, limit, max_bytes)


def test_the_block_cache_drops_the_least_recently_used_block():
    cache = BlockCache(max_bytes=100)
    cache.put(("k", 0), ["a"], 40)
    cache.put(("k", 1), ["b"], 40)
    assert cache.get(("k", 0)) == ["a"]  # now the most recent
    cache.put(("k", 2), ["c"], 40)
    assert cache.get(("k", 1)) is None and cache.get(("k", 0)) == ["a"] and cache.get(("k", 2)) == ["c"]
    assert cache.bytes == 80 and len(cache) == 2
    cache.put(("k", 3), ["huge"], 101)  # larger than the whole cache: not kept
    assert cache.get(("k", 3)) is None and len(cache) == 2
    assert cache.hits == 3 and cache.misses == 2


def test_count_reads_no_data(tmp_path):
    objects = CountingObjects(MemorySegmentObjects())
    logs = make(tmp_path, objects)
    logs.append(NAME, UID, LOG, 0, ["a", "b"], "t")
    logs.close(NAME, UID, LOG)
    again = make(tmp_path, objects, logs.index)
    objects.gets = 0
    assert again.count(NAME, UID, LOG) == 2 and again.held(NAME, UID, LOG) == (2, 2)
    assert objects.gets == 0


# --- Postgres and S3 ---------------------------------------------------------------------


def test_postgres_index_rows_and_activity():
    index = PostgresSegmentIndex(postgres_dsn())
    row = Segment(NAME, UID, LOG, 0, 3, object_key(NAME, UID, LOG, 0), fmt.pack_blocks([fmt.Block(0, 0, 10, 20)]))
    index.add(row, "t1")
    index.add(row._replace(line_count=4), None)  # the same segment again replaces its row
    assert index.segments(NAME, UID, LOG) == [row._replace(line_count=4)]
    assert index.logs(NAME, UID) == [LOG] and index.logs(NAME, "u2") == []
    assert index.keys() == {row.key} and index.activity(NAME, UID) == "t1"
    index.set_activity(NAME, UID, "t2")
    assert index.activity(NAME, UID) == "t2" and index.activity(NAME, "u2") is None
    PostgresSegmentIndex(index.dsn)  # the tables exist already
    index.close()


def test_a_restart_on_postgres_and_s3(tmp_path):
    objects, index = CountingObjects(S3SegmentObjects(s3_url())), PostgresSegmentIndex(postgres_dsn())
    logs = make(tmp_path, objects, index, block_bytes=2000, segment_bytes=20_000)
    every = lines_of(400)
    logs.append(NAME, UID, LOG, 0, every[:300], "t1")
    logs.shutdown()
    again = make(tmp_path, objects, PostgresSegmentIndex(index.dsn), block_bytes=2000, segment_bytes=20_000)
    assert again.sweep() == []
    again.append(NAME, UID, LOG, 300, every[300:], "t2")
    again.close(NAME, UID, LOG)
    assert again.held(NAME, UID, LOG) == (400, 400) and again.activity(NAME, UID) == "t2"
    objects.gets = 0
    assert again.read(NAME, UID, LOG, 10, limit=50)[0] == every[10:60] and objects.gets == 1
    assert read_all(again) == every
    rebuilt = MemorySegmentIndex()
    rebuild_index(objects, rebuilt)
    assert rebuilt.segments(NAME, UID, LOG) == again.index.segments(NAME, UID, LOG)
