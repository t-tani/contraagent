"""`contraagent hub`'s choice of where transcripts are kept, and how it stops."""

import queue
import re
import signal
import subprocess
import sys
import threading
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


@pytest.mark.skipif(sys.platform == "win32", reason="a graceful stop is SIGTERM, which Windows does not send")
def test_sigterm_stops_the_hub_gracefully_with_its_open_segments_shut_down(tmp_path):
    """uvicorn raises SIGTERM again after its graceful stop; the hub's own handler turns it
    into a normal exit, so the `finally` that shuts the open segments down runs."""
    (tmp_path / "tokens").write_text("t\n")
    # Port 0: the hub binds a free port itself and logs its address.
    argv = [sys.executable, "-m", "contraagent", "hub", "--port", "0", "--ingest-token-file", str(tmp_path / "tokens")]
    with subprocess.Popen([*argv, "--streams-dir", str(tmp_path / "hot")], stderr=subprocess.PIPE, text=True) as hub:
        lines: queue.Queue[str] = queue.Queue()
        assert hub.stderr is not None
        threading.Thread(target=_read_lines, args=(hub.stderr, lines), daemon=True).start()
        try:
            seen: list[str] = []
            deadline = time.monotonic() + 30
            while not (found := re.search(r" on (http://\S+)", "".join(seen))):
                assert hub.poll() is None, "".join(seen)
                left = deadline - time.monotonic()
                assert left > 0, f"the hub did not log its address: {''.join(seen)}"
                try:
                    seen.append(lines.get(timeout=min(left, 1)))
                except queue.Empty:
                    pass
            base = found.group(1)
            while True:
                assert hub.poll() is None, "".join(seen)
                try:
                    urllib.request.urlopen(f"{base}/api/info", timeout=1).close()
                    break
                except (urllib.error.URLError, OSError):
                    assert time.monotonic() < deadline, "the hub did not answer"
                    time.sleep(0.1)
            hub.send_signal(signal.SIGTERM)
            assert hub.wait(15) == 0, "".join(seen + list(lines.queue))
        finally:
            hub.kill()


def _read_lines(stream, lines: queue.Queue[str]) -> None:
    for line in stream:
        lines.put(line)
