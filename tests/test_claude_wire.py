"""Claude Code's event wire, read from recordings of a real Claude Code (`--output-format stream-json`).

`tests/fixtures/claude/<version>/json.jsonl` holds one launch (read a file, run `echo hi`,
reply "done"), slimmed by `fixtures/claude/record.py`. A newer Claude Code gets a new
directory recorded the same way; the tests run on every recording. A recording also checks
`READ_FIELDS`: each field it names is on every event of its kind there.
"""

import json
from pathlib import Path

import pytest

from contraagent._internal.backends.claude.wire import StreamReader
from contraagent.backends import Launch, LaunchResult, Stop, normalize_stream_line
from contraagent.config import Limits

FIXTURES = Path(__file__).parent / "fixtures" / "claude"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="claude-haiku-5-5")


def events(version: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() if line.strip()]


def read(evs: list[dict]) -> LaunchResult:
    reader = StreamReader(Limits())
    reader.read("".join(json.dumps(e) + "\n" for e in evs).encode())
    return reader.result(LAUNCH, "claude", exit_code=0, killed=None)


def changed(evs: list[dict], typ: str, change) -> list[dict]:
    """`evs` with `change(event)` applied to a copy of each event of type `typ`."""
    out = []
    for e in evs:
        e = json.loads(json.dumps(e))
        if e["type"] == typ:
            change(e)
        out.append(e)
    return out


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recorded_launch_reads_whole_and_counts_each_call_once(version):
    result = read(events(version))
    assert result.stop == Stop.COMPLETED and result.ok and not result.hollow and result.result_text == "done"
    assert result.tool_uses == {"Read": 1, "Bash": 1}
    # Claude Code sends one event per content block, each with its message's usage: two messages, two calls.
    assert len(result.usage.calls) == 2 and result.usage.output_total > 0 and result.cost_usd and result.cost_usd > 0
    assert result.session_id and result.cli_version == version and result.init_model == LAUNCH.model
    assert result.quota and result.context_window
    assert result.unread_events == {}, "Claude Code sends events this reader does not read"


@pytest.mark.parametrize("version", VERSIONS)
def test_the_monitor_shows_each_tool_call_of_a_recording(version):
    shown = [e for line in (FIXTURES / version / "json.jsonl").read_text().splitlines() for e in normalize_stream_line("claude", line)]
    starts = [e for e in shown if e["type"] == "tool_execution_start"]
    assert [e["tool"] for e in starts] == ["Read", "Bash"] and starts[1]["cmd"] == "echo hi"
    ends = [e for e in shown if e["type"] == "tool_execution_end"]
    assert len(ends) == 2 and ends[1]["out"] == "hi"


@pytest.mark.parametrize("version", VERSIONS)
def test_a_field_the_reader_reads_that_is_gone_is_an_unread_event(version):
    result = read(changed(events(version), "result", lambda e: e.pop("total_cost_usd")))
    assert result.unread_events == {"result.total_cost_usd": 1}
    assert result.stop == Stop.COMPLETED and result.cost_usd is None


@pytest.mark.parametrize("version", VERSIONS)
def test_a_field_of_another_type_is_an_unread_event(version):
    def nested(e):
        if e["subtype"] == "init":
            e["claude_code_version"] = {"semver": e["claude_code_version"]}

    result = read(changed(events(version), "system", nested))
    assert result.unread_events == {"system/init.claude_code_version": 1}


@pytest.mark.parametrize("version", VERSIONS)
def test_an_event_whose_reading_fails_is_skipped_and_counted(version):
    def odd(e):
        e["message"]["usage"]["input_tokens"] = {"total": 2}

    result = read(changed(events(version), "assistant", odd))
    # Three events; the reading fails on the first of each message, whose usage it reads.
    assert result.unread_events == {"assistant.message.usage.input_tokens": 3, "assistant: TypeError": 2}
    # The tool calls of those events were read before their tokens; the result's own facts stand.
    assert result.stop == Stop.COMPLETED and result.tool_uses == {"Read": 1, "Bash": 1} and result.cost_usd


def test_a_boolean_is_not_an_integer():
    result = read(
        [
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "num_turns": True,
                "session_id": "s",
                "total_cost_usd": 0,
                "usage": {},
            }
        ]
    )
    assert result.unread_events == {"result.num_turns": 1}
