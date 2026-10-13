"""`contraagent hub`'s choice of where transcripts are kept."""

import pytest

pytest.importorskip("zstandard")

from contraagent.hub.segments import SegmentedStreamLogs
from contraagent.hub.server import open_streams
from contraagent.hub.streams import MemoryStreamLogs


def test_without_a_streams_dir_transcripts_are_kept_in_memory():
    assert isinstance(open_streams(None, None, "memory"), MemoryStreamLogs)


def test_a_streams_dir_keeps_open_segments_there_and_seals_beside_it(tmp_path):
    logs = open_streams(str(tmp_path / "hot"), None, "memory")
    try:
        assert isinstance(logs, SegmentedStreamLogs)
        logs.append("r@h", "u", "streams/k.stream.jsonl", 0, ["a", "b"], "t1")
        logs.close("r@h", "u", "streams/k.stream.jsonl")
        assert logs.read("r@h", "u", "streams/k.stream.jsonl", 0) == (["a", "b"], 2)
    finally:
        logs.shutdown()
    again = open_streams(str(tmp_path / "hot"), None, "memory")
    try:
        assert again.read("r@h", "u", "streams/k.stream.jsonl", 0) == (["a", "b"], 2)
    finally:
        again.shutdown()


def test_segments_need_a_streams_dir():
    with pytest.raises(ValueError, match="--segments needs --streams-dir"):
        open_streams(None, "s3://bucket/prefix", "memory")
