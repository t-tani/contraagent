"""`contraagent hub`'s choice of where transcripts are kept, and how it stops."""

import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("zstandard")

from contraagent._internal.hub.segments import SegmentedStreamLogs
from contraagent._internal.hub.server import open_streams
from contraagent._internal.hub.streams import MemoryStreamLogs


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


def test_sigterm_stops_the_hub_gracefully_with_its_open_segments_shut_down(tmp_path):
    """uvicorn raises SIGTERM again after its graceful stop; the hub's own handler turns it
    into a normal exit, so the `finally` that shuts the open segments down runs."""
    (tmp_path / "tokens").write_text("t\n")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    argv = [sys.executable, "-m", "contraagent", "hub", "--port", str(port), "--ingest-token-file", str(tmp_path / "tokens")]
    hub = subprocess.Popen([*argv, "--streams-dir", str(tmp_path / "hot")], stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 30
        while True:
            assert hub.poll() is None, hub.communicate()[1]
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=1)
                break
            except (urllib.error.URLError, OSError):
                assert time.monotonic() < deadline, "the hub did not answer"
                time.sleep(0.1)
        hub.send_signal(signal.SIGTERM)
        assert hub.wait(15) == 0, hub.communicate()[1]
    finally:
        hub.kill()
        hub.wait()
