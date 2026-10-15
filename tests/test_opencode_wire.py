"""opencode's event wire, read from recordings of a real opencode (`opencode run --format json`).

`tests/fixtures/opencode/<version>/json.jsonl` holds one launch, recorded with the same prompt
(read a file, run `echo hi`, reply "done") and slimmed by `fixtures/opencode/record.py`. A newer
opencode gets a new directory recorded the same way; the tests run on every recording. The error
events and the log line are copied from real launches that failed.
"""

import json
from pathlib import Path

import pytest

from contraagent import Launch, Stop
from contraagent.backends.opencode.wire import EventReader, normalize_event, refusal_in_log
from contraagent.backends.streams import normalize_stream_line

FIXTURES = Path(__file__).parent / "fixtures" / "opencode"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="opencode/muse-spark-1.3-contributor-free")

#: `opencode run` on a free model whose system prompt was replaced (opencode 1.19.0).
FREE_TIER = {
    "type": "error",
    "sessionID": "ses_1",
    "error": {
        "name": "APIError",
        "data": {"message": "OpenCode's free tier can only be used from within OpenCode.", "statusCode": 403, "isRetryable": False},
    },
}
#: An unknown model name.
UNKNOWN = {
    "type": "error",
    "sessionID": "ses_1",
    "error": {"name": "UnknownError", "data": {"message": "Unexpected server error. Check server logs for details."}},
}
#: opencode's log, on stderr, of a 429 it then retries for as long as the provider asks.
QUOTA_LOG = (
    'timestamp=2026-10-14T14:47:52.409Z level=ERROR run=d94b0775 message="stream error" providerID=opencode-go '
    'modelID=glm-5.3-flash session.id=ses_1 small=false agent=build mode=primary error.error="AI_APICallError: Go usage limit exceeded"'
)


def events(version: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() if line.strip()]


def read(evs: list[dict], exit_code: int = 0):
    raw = "".join(json.dumps(e) + "\n" for e in evs).encode()
    return EventReader(LAUNCH.model).read(raw).result(LAUNCH, "opencode", exit_code=exit_code, killed=None)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_reads_whole(version):
    result = read(events(version))
    assert result.stop == Stop.COMPLETED and result.ok
    assert result.result_text.strip(".").lower() == "done"  # the last message only, not what came before a tool call
    assert result.tool_uses == {"read": 1, "bash": 1}
    assert len(result.usage.calls) == 3 and sum(c.output for c in result.usage.calls) > 0 and result.cost_usd is not None
    assert result.session_id.startswith("ses_")
    assert result.unread_events == {}, "opencode sends events this reader does not know"
    assert json.loads(result.raw_result["tool_args"]["bash"][0])["command"] == "echo hi"


@pytest.mark.parametrize("version", VERSIONS)
def test_the_monitor_shows_each_tool_call_with_its_result(version):
    shown = [ev for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() for ev in normalize_stream_line("opencode", line)]
    starts = [e for e in shown if e["type"] == "tool_execution_start"]
    ends = {e["call"]: e for e in shown if e["type"] == "tool_execution_end"}
    assert [s["tool"] for s in starts] == ["read", "bash"]
    assert starts[0]["cmd"] == "/work/note.txt" and starts[1]["cmd"] == "echo hi"
    assert all(ends[s["call"]]["out"] and not ends[s["call"]]["err"] for s in starts)  # each card gets its result
    assert any(e["type"] == "message_update" and "done" in e["delta"].lower() for e in shown)


def test_an_error_event_names_the_stop_and_its_cause():
    refused = read([FREE_TIER], exit_code=1)
    assert refused.stop == Stop.AUTH_FAILED and not refused.ok
    assert "free tier" in refused.stderr_tail
    assert read([UNKNOWN], exit_code=1).stop == Stop.API_ERROR
    quota = {**FREE_TIER, "error": {"name": "APIError", "data": {"message": "Too Many Requests", "statusCode": 429}}}
    limited = read([quota], exit_code=1)
    assert limited.stop == Stop.RATE_LIMITED and limited.quota_refusal is not None
    assert normalize_event(FREE_TIER) == {"type": "notice", "text": "error: OpenCode's free tier can only be used from within OpenCode."}


def test_nothing_read_is_a_failed_launch():
    assert read([], exit_code=1).stop == Stop.ERROR
    assert read([], exit_code=0).stop == Stop.LAUNCH_FAILED
    started = {"type": "step_start", "sessionID": "ses_1", "part": {"type": "step-start"}}
    assert read([started], exit_code=0).stop == Stop.NO_OUTPUT


def test_an_unknown_event_is_counted():
    reader = EventReader()
    reader.feed({"type": "compaction", "sessionID": "s"})
    assert reader.unread == {"compaction": 1}


def test_a_quota_refusal_is_read_from_the_log():
    assert refusal_in_log(QUOTA_LOG) == "AI_APICallError: Go usage limit exceeded"
    assert refusal_in_log(QUOTA_LOG.replace("Go usage limit exceeded", "Overloaded")) is None
    assert refusal_in_log('level=ERROR message=process error="rate limit"') is None  # not an API call's error


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_reports_its_peak_context(version):
    """The largest `step_finish`'s whole input: fresh input, cache read and cache write."""
    result = read(events(version))
    tokens = [e["part"]["tokens"] for e in events(version) if e.get("type") == "step_finish"]
    want = max(t["input"] + t["cache"]["read"] + t["cache"]["write"] for t in tokens)
    assert result.peak_context == want >= result.usage.resident > 0


def test_a_launch_that_reports_no_call_has_no_peak_context():
    assert read([{"type": "text", "sessionID": "ses_1", "part": {"messageID": "m", "text": "done"}}]).peak_context is None
