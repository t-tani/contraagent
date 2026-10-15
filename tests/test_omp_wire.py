"""omp's event wire, read from recordings of a real omp: `--mode json` lines and RPC frames.

`tests/fixtures/omp/<version>/` holds one launch per wire, recorded with the same prompt
(read a file, run `echo hi`, one `web_search`, reply "done") and slimmed (long strings cut,
paths replaced) by `fixtures/omp/record.py`. A newer omp gets a new directory recorded the
same way; the tests run on every recording.
"""

import json
from pathlib import Path

import pytest

from contraagent._internal.backends.omp.rpc import RpcReader
from contraagent._internal.backends.omp.wire import TraceReader, normalize_event
from contraagent.backends import Launch, Stop

FIXTURES = Path(__file__).parent / "fixtures" / "omp"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="anthropic/claude-haiku-5-5")


def events(version: str, wire: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / f"{wire}.jsonl").read_text().splitlines() if line.strip()]


def via_json(version: str):
    return TraceReader().read((FIXTURES / version / "json.jsonl").read_bytes()).result(LAUNCH, "omp", exit_code=0, killed=None)


def via_rpc(version: str):
    rpc = RpcReader("t")
    for frame in events(version, "rpc"):
        rpc.feed(frame)
        if rpc.done:
            break
    return rpc.result(LAUNCH, "omp-rpc", exit_code=None, killed=None)


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("read", [via_json, via_rpc], ids=["json", "rpc"])
def test_a_recorded_launch_reads_whole_and_counts_each_call_once(version, read):
    result = read(version)
    assert result.stop == Stop.COMPLETED and result.ok and result.result_text == "done"
    assert result.tool_uses == {"read": 1, "bash": 1, "web_search": 1}
    assert result.web_queries == ["oh-my-pi coding agent"]
    assert len(result.usage.calls) >= 2 and sum(c.output for c in result.usage.calls) > 0 and result.cost_usd and result.cost_usd > 0
    assert result.unread_events == {}, "omp sends events this reader does not know"
    assert json.loads(result.raw_result["tool_args"]["bash"][0])["command"] == "echo hi"


@pytest.mark.parametrize("version", VERSIONS)
def test_both_wires_read_the_same_launch_alike(version):
    a, b = via_json(version), via_rpc(version)
    assert (a.tool_uses, a.web_queries, a.result_text) == (b.tool_uses, b.web_queries, b.result_text)
    assert len(a.usage.calls) == len(b.usage.calls)
    assert a.session_id  # `--mode json` names its session; the RPC launch ran with --no-session


@pytest.mark.parametrize("version", VERSIONS)
def test_the_monitor_shows_each_tool_call_of_a_recording(version):
    shown = [normalize_event(e) for e in events(version, "json")]
    starts = [e for e in shown if e["type"] == "tool_execution_start"]
    assert [e["tool"] for e in starts] == ["read", "bash", "web_search"]
    assert starts[1]["cmd"] == "echo hi" and "web_query" not in starts[1]
    assert starts[2]["cmd"] == starts[2]["web_query"] == "oh-my-pi coding agent"
    ends = [e for e in shown if e["type"] == "tool_execution_end"]
    assert len(ends) == 3 and "hi" in ends[1]["out"]


def test_an_event_this_reader_does_not_know_is_counted():
    reader = TraceReader()
    reader.feed({"type": "brand_new_event"})
    reader.feed({"type": "message_update", "assistantMessageEvent": {"type": "sparkle_delta"}})
    assert reader.result(LAUNCH, "omp", exit_code=0, killed=None).unread_events == {
        "brand_new_event": 1,
        "message_update/sparkle_delta": 1,
    }


def test_an_error_omp_retried_past_is_not_the_outcome():
    reader = TraceReader()
    failed = {"role": "assistant", "content": [], "errorStatus": 429, "errorMessage": "rate limit exceeded"}
    reader.feed({"type": "message_end", "message": failed})
    reader.feed({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "done"}})
    reader.feed({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}})
    assert reader.result(LAUNCH, "omp", exit_code=0, killed=None).stop == Stop.COMPLETED
    reader.feed({"type": "message_end", "message": failed})
    assert reader.result(LAUNCH, "omp", exit_code=0, killed=None).stop == Stop.RATE_LIMITED


def test_a_provider_error_is_the_launchs_reason():
    reader = TraceReader()
    refused = {"role": "assistant", "content": [], "stopReason": "error", "errorMessage": "403 free tier only in OpenCode"}
    reader.feed({"type": "message_end", "message": refused})
    result = reader.result(LAUNCH, "omp", exit_code=1, killed=None)
    assert result.stop == Stop.ERROR and result.stderr_tail == "403 free tier only in OpenCode"


def test_unread_events_reach_the_journal_summed_over_rounds(tmp_path):
    from contraagent import Task, TaskResult
    from contraagent._internal.contracts.contract import fold_spend
    from contraagent._internal.execution.journal import Journal
    from contraagent.backends import LaunchResult

    first = LaunchResult(label="t", unread_events={"session_settled": 1})
    last = fold_spend(first, LaunchResult(label="t", unread_events={"session_settled": 1, "new_thing": 2}))
    journal = Journal(tmp_path / "j.jsonl", tmp_path / "l.jsonl", run_id="r", run_group="r", unit_of=lambda t: t.unit)
    row = journal.row(TaskResult(task=Task("k", key="t"), ok=False, stop="error", launch_result=last))
    assert row.unread_events == {"session_settled": 2, "new_thing": 2}


def test_a_launch_that_names_no_model_leaves_the_journals_model_empty(tmp_path):
    """The route (`hop 1/1 stub`) is not a model name."""
    from contraagent import Task, TaskResult
    from contraagent._internal.execution.journal import Journal
    from contraagent.backends import LaunchResult

    journal = Journal(tmp_path / "j.jsonl", tmp_path / "l.jsonl", run_id="r", run_group="r", unit_of=lambda t: t.unit)
    result = TaskResult(task=Task("k", key="t"), ok=True, stop="completed", launch_result=LaunchResult(label="t"), route="hop 1/1 stub")
    row = journal.row(result)
    assert row.model == "" and row.route == "hop 1/1 stub"


def recorded_peak(version: str, wire: str) -> int:
    """The largest whole input of one assistant `message_end` of a recording, read apart from the reader."""
    usages = [
        e["message"]["usage"]
        for e in events(version, wire)
        if e.get("type") == "message_end"
        and e.get("message", {}).get("role") == "assistant"
        and isinstance(e["message"].get("usage"), dict)
    ]
    return max(u.get("input", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0) for u in usages)


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize(("read", "wire"), [(via_json, "json"), (via_rpc, "rpc")], ids=["json", "rpc"])
def test_a_recorded_launch_reports_its_peak_context(version, read, wire):
    result = read(version)
    assert result.peak_context == recorded_peak(version, wire) >= result.usage.resident > 0
