"""pi's event wire, read from recordings of a real pi (`pi --mode json`).

`tests/fixtures/pi/<version>/json.jsonl` holds one launch (read a file, run `echo hi`,
reply "done"), slimmed by `fixtures/pi/record.py`. A newer pi gets a new directory
recorded the same way; the tests run on every recording.
"""

import json
from pathlib import Path

import pytest

from contraagent import Launch, Stop
from contraagent.backends.omp.wire import normalize_event
from contraagent.backends.pi.wire import PiTraceReader
from contraagent.backends.streams import normalize_stream_line

FIXTURES = Path(__file__).parent / "fixtures" / "pi"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="openai/gpt-5.6-luna")


def events(version: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() if line.strip()]


def refusal(message: str) -> dict:
    """An assistant `message_end` as pi sends one for a provider's refusal (shape of a real one)."""
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0, "cost": {"total": 0}}
    shape = {"role": "assistant", "content": [], "model": "claude-haiku-5-5", "usage": usage, "stopReason": "error"}
    return {"type": "message_end", "message": {**shape, "errorMessage": message}}


def read(*evs: dict):
    reader = PiTraceReader()
    for e in evs:
        reader.feed(e)
    return reader.result(LAUNCH, "pi", exit_code=0, killed=None)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_reads_whole_and_counts_each_call_once(version):
    result = PiTraceReader().read((FIXTURES / version / "json.jsonl").read_bytes()).result(LAUNCH, "pi", exit_code=0, killed=None)
    assert result.stop == Stop.COMPLETED and result.ok and result.result_text == "done"
    assert result.tool_uses == {"read": 1, "bash": 1}
    assert result.usage.n_calls == 3 and result.usage.output > 0 and result.cost_usd and result.cost_usd > 0
    assert result.session_id
    assert result.unread_events == {}, "pi sends events this reader does not know"
    assert json.loads(result.raw_result["tool_args"]["bash"][0])["command"] == "echo hi"


@pytest.mark.parametrize("version", VERSIONS)
def test_the_monitor_shows_each_tool_call_of_a_recording(version):
    shown = [e for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() for e in normalize_stream_line("pi", line)]
    starts = [e for e in shown if e["type"] == "tool_execution_start"]
    assert [e["tool"] for e in starts] == ["read", "bash"] and starts[1]["cmd"] == "echo hi"
    ends = [e for e in shown if e["type"] == "tool_execution_end"]
    assert len(ends) == 2 and "hi" in ends[1]["out"]
    assert not [e for e in shown if e.get("role") == "system"], "pi's system prompt is not a message to show"


def test_a_spent_quota_is_a_rate_limit_whatever_its_status():
    """Anthropic answers a subscription with no extra usage left with a 400 (from a real pi launch)."""
    said = "You're out of extra usage. Add more at claude.ai/settings/usage and keep going."
    body = json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": said}})
    result = read(refusal(f"400 {body}"))
    assert result.stop == Stop.RATE_LIMITED and not result.ok and result.rate_limit is not None
    assert "out of extra usage" in result.stderr_tail
    assert read(refusal("429 Too Many Requests")).stop == Stop.RATE_LIMITED


@pytest.mark.parametrize(("message", "stop"), [("401 invalid x-api-key", Stop.AUTH_FAILED), ("500 internal error", Stop.API_ERROR)])
def test_a_provider_refusal_is_read_from_the_last_assistant_message(message, stop):
    """pi exits 0 after a refusal: the message says how the launch ended."""
    result = read(refusal(message))
    assert result.stop == stop and result.stderr_tail == message


def test_a_refusal_pi_retried_past_is_not_the_outcome():
    ok = {
        "type": "message_end",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}], "model": "m", "usage": {"input": 1, "output": 1}},
    }
    done = {"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "done"}}
    result = read(refusal("529 overloaded"), {"type": "auto_retry_start", "attempt": 1, "errorMessage": "529 overloaded"}, done, ok)
    assert result.stop == Stop.COMPLETED and result.result_text == "done"


def test_an_event_this_reader_does_not_know_is_counted():
    result = read({"type": "brand_new_event"}, {"type": "message_update", "assistantMessageEvent": {"type": "sparkle_delta"}})
    assert result.unread_events == {"brand_new_event": 1, "message_update/sparkle_delta": 1}


def test_omp_and_pi_render_alike():
    """The stream format `pi` renders with omp's normalizer: the wire is the one omp forked."""
    e = {"type": "tool_execution_start", "toolName": "bash", "toolCallId": "c1", "args": {"command": "ls"}}
    assert normalize_stream_line("pi", json.dumps(e)) == [normalize_event(e)]


def test_a_turn_that_ends_on_an_empty_message_completes():
    """GPT-5.6 Luna, having written its output file, ends with an empty text block (seen live)."""
    end = {"role": "assistant", "content": [{"type": "text", "text": ""}], "model": "gpt-5.6-luna", "usage": {}, "stopReason": "stop"}
    result = read({"type": "message_end", "message": end})
    assert result.stop == Stop.COMPLETED and result.ok and result.result_text == ""
    cut = {**end, "stopReason": "toolUse"}
    assert read({"type": "message_end", "message": cut}).stop == Stop.NO_OUTPUT


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_reports_its_peak_context(version):
    result = PiTraceReader().read((FIXTURES / version / "json.jsonl").read_bytes()).result(LAUNCH, "pi", exit_code=0, killed=None)
    usages = [
        e["message"]["usage"]
        for e in events(version)
        if e.get("type") == "message_end"
        and e.get("message", {}).get("role") == "assistant"
        and isinstance(e["message"].get("usage"), dict)
    ]
    want = max(u.get("input", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0) for u in usages)
    assert result.peak_context == want >= result.usage.resident > 0
