"""agy's events, read from recordings of a real agy (`agy -p --output-format stream-json`).

`tests/fixtures/agy/<version>/` holds a launch (`json.jsonl`), a launch that resumed its
conversation (`resume.jsonl`) and one whose task denied a command (`denied.jsonl`), slimmed
by `fixtures/agy/record.py`. A newer agy gets a new directory recorded the same way; the
tests run on every recording. The refusals below are what agy 1.5.9 printed in live runs.
"""

import json
from pathlib import Path

import pytest

from contraagent._internal.backends.agy import hooks as agy_hooks
from contraagent._internal.backends.agy.wire import StreamReader, call_usage, normalize_event, resets_in
from contraagent._internal.backends.streams import normalize_stream_line
from contraagent.backends import AgyBackend, Launch, LaunchResult, LimitsWatch, Stop
from contraagent.config import Limits

FIXTURES = Path(__file__).parent / "fixtures" / "agy"
VERSIONS = sorted(p.parent.name for p in FIXTURES.glob("*/json.jsonl"))
LAUNCH = Launch(prompt="x", label="t", model="gemini-3.8-flash-low")
CONVERSATION = "7db11684-2a25-4839-96bb-e8dc7dbcef6d"


def events(version: str, name: str) -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / version / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def read(evs: list[dict], *, exit_code: int | None = 0, launch: Launch = LAUNCH, **reader) -> LaunchResult:
    fold = StreamReader(launch.limits, **reader)
    for ev in evs:
        fold.feed_line(json.dumps(ev))
    return fold.result(launch, "agy", exit_code=exit_code, killed=None)


def responses(evs: list[dict]) -> list[dict]:
    """The last update of each response of the model: one per turn, with that call's tokens."""
    steps = [e["step_update"] for e in evs if e["event"] == "step_update"]
    return [s for s in steps if s["step_type"] == "agent_response" and s["state"] == "DONE"]


def init(conversation: str = CONVERSATION) -> dict:
    return {
        "event": "init",
        "conversation_id": conversation,
        "init": {"model": "gemini-3.8-flash-low", "cwd": "/work", "tools": ["run_command"]},
    }


def step(index: int, kind: str, state: str = "DONE", conversation: str = CONVERSATION, **fields) -> dict:
    return {
        "event": "step_update",
        "step_update": {"conversation_id": conversation, "step_index": index, "state": state, "step_type": kind, **fields},
    }


def result(status: str = "SUCCESS", conversation: str = CONVERSATION, **fields) -> dict:
    return {"event": "result", "result": {"conversation_id": conversation, "status": status, "response": "", "num_turns": 1, **fields}}


def usage(fresh: int, out: int, cached: int = 0, thinking: int = 0, total: int | None = None) -> dict:
    total = fresh + out if total is None else total
    return {"input_tokens": fresh, "output_tokens": out, "thinking_tokens": thinking, "cache_read_tokens": cached, "total_tokens": total}


def test_there_is_a_recording():
    assert VERSIONS


@pytest.mark.parametrize("version", VERSIONS)
def test_a_launch_is_read_whole(version):
    evs = events(version, "json")
    r = read(evs)
    assert (r.stop, r.ok, r.unread_events) == (Stop.COMPLETED, True, {})
    assert r.session_id == evs[0]["conversation_id"] and r.init_model == evs[0]["init"]["model"]
    assert r.init_tools == len(evs[0]["init"]["tools"])
    assert r.result_text.strip() == "done"
    assert r.tool_uses == {"read_file": 1, "run_command": 1}
    assert json.loads(r.raw_result["tool_args"]["run_command"][0]) == {"CommandLine": "echo hi"}
    calls = responses(evs)
    assert r.num_turns == len(calls) == len(r.usage.calls)  # a turn is one response of the model
    assert [c.input for c in r.usage.calls] == [s["usage"]["input_tokens"] for s in calls]
    assert [c.cache_read for c in r.usage.calls] == [s["usage"]["cache_read_tokens"] for s in calls]
    # A new conversation's totals are those of its steps.
    total = evs[-1]["result"]["usage"]
    assert sum(c.input for c in r.usage.calls) == total["input_tokens"]
    assert sum(c.cache_read for c in r.usage.calls) == total["cache_read_tokens"]
    assert r.usage.output_total == total["output_tokens"]
    assert r.peak_context == max(s["usage"]["input_tokens"] + s["usage"]["cache_read_tokens"] for s in calls)
    assert r.cost_usd is None and r.context_window is None


@pytest.mark.parametrize("version", VERSIONS)
def test_a_resumed_launch_counts_its_own_responses_not_the_conversation_s(version):
    first, evs = events(version, "json"), events(version, "resume")
    r = read(evs, launch=Launch(prompt="x", label="t", model="m", resume=first[0]["conversation_id"]), resume=first[0]["conversation_id"])
    assert (r.stop, r.ok, r.unread_events) == (Stop.COMPLETED, True, {})
    assert r.session_id == first[0]["conversation_id"]
    calls = responses(evs)
    assert r.num_turns == len(calls) == 1
    conversation = evs[-1]["result"]["usage"]  # the result's totals hold the first launch's too
    assert sum(c.input for c in r.usage.calls) == calls[0]["usage"]["input_tokens"] < conversation["input_tokens"]
    assert conversation["input_tokens"] == first[-1]["result"]["usage"]["input_tokens"] + calls[0]["usage"]["input_tokens"]


@pytest.mark.parametrize("version", VERSIONS)
def test_a_denied_tool_call_is_a_permission_denial(version):
    evs = events(version, "denied")
    r = read(evs)
    assert r.stop is Stop.COMPLETED and r.unread_events == {}
    assert r.permission_denials and all(d["tool_name"] == "run_command" for d in r.permission_denials)
    assert all(d["tool_input"]["CommandLine"].startswith("ls") for d in r.permission_denials)  # the task's `Bash(ls:*)`
    # Past `max_denials` the reader ends the launch at the denial.
    fold = StreamReader(Limits(max_denials=0))
    stops = [fold.feed_line(json.dumps(ev)) for ev in evs]
    assert Stop.DENIED in stops and stops.index(Stop.DENIED) == next(
        i for i, ev in enumerate(evs) if (ev.get("step_update") or {}).get("state") == "ERROR"
    )


@pytest.mark.parametrize("version", VERSIONS)
def test_the_monitor_renders_a_recording(version):
    lines = [json.dumps(ev) for ev in events(version, "json")]
    shown = [e for line in lines for e in normalize_stream_line("agy", line)]
    assert shown[0]["type"] == "notice" and shown[0]["text"].startswith("session started: ")
    starts = [e for e in shown if e["type"] == "tool_execution_start"]
    ends = [e for e in shown if e["type"] == "tool_execution_end"]
    assert [e["tool"] for e in starts] == ["read_file", "run_command"]
    assert [e["cmd"] for e in starts] == ["/work/note.txt", "echo hi"]
    assert [e["call"] for e in starts] == [e["call"] for e in ends] and not any(e["err"] for e in ends)
    assert "".join(e["delta"] for e in shown if e["type"] == "message_update").strip() == "done"
    denied = [
        e for ev in events(version, "denied") for e in [normalize_event(ev)] if isinstance(e, dict) and e["type"] == "tool_execution_end"
    ]
    assert denied[0]["err"] and "Permission denied for command(ls)" in denied[0]["out"]


def test_max_turns_ends_a_launch_as_the_turn_past_it_begins_or_ends():
    fold = StreamReader()
    watch = LimitsWatch(Limits(max_turns=1), AgyBackend.watched_limits, fold)
    fold.feed(init())
    fold.feed(step(1, "agent_response", usage=usage(100, 5)))  # a response with no text arrives whole
    assert watch() is None and fold.turns == 1
    fold.feed(step(2, "tool", "ACTIVE", tool_name="run_command", tool_info={"name": "run_command", "parameters": {}}))
    assert watch() is None
    fold.feed(step(3, "agent_response", "ACTIVE", text_delta="so"))  # the second turn's text begins
    assert watch() is Stop.MAX_TURNS


def test_context_budget_ends_a_launch_on_one_call_s_whole_input():
    fold = StreamReader()
    watch = LimitsWatch(Limits(context_budget=1000), AgyBackend.watched_limits, fold)
    fold.feed(init())
    fold.feed(step(1, "agent_response", usage=usage(400, 5, cached=500)))
    assert watch() is None
    fold.feed(step(3, "agent_response", usage=usage(400, 5, cached=601)))  # the cached input counts
    assert watch() is Stop.CONTEXT


def test_thinking_tokens_are_added_when_the_total_counts_them_apart():
    # A response of Gemini 3.8 Flash (High), as agy 1.5.9 reported it: the output holds the thinking.
    measured = {"input_tokens": 9766, "output_tokens": 2275, "thinking_tokens": 2238, "cache_read_tokens": 0, "total_tokens": 12041}
    assert call_usage("m", measured).output == 2275
    assert call_usage("m", usage(100, 20, cached=30)).output == 20
    assert call_usage("m", usage(100, 20, thinking=7, total=127)).output == 27
    assert call_usage("m", usage(100, 20, thinking=7, total=120)).output == 20  # already in the output
    call = call_usage("m", usage(100, 20, cached=30))
    assert (call.input, call.cache_read, call.cache_creation, call.context) == (100, 30, 0, 130)


def test_the_answer_is_the_last_response_that_has_text():
    evs = [
        init(),
        step(1, "agent_response", "ACTIVE", text_delta="I will read "),
        step(1, "agent_response", text_delta="the file.\n", usage=usage(10, 5)),
        step(2, "tool", "ACTIVE", tool_name="read_file", tool_info={"name": "read_file", "parameters": {"Path": "a"}}),
        step(2, "tool", tool_name="read_file", tool_info={"name": "read_file", "parameters": {"Path": "a"}, "output": "1 lines"}),
        step(3, "agent_response", "ACTIVE", text_delta='{"title":'),
        step(3, "agent_response", text_delta=' "x"}\n', usage=usage(12, 6)),
        step(4, "agent_response", text_delta="\n", usage=usage(12, 1)),  # a last response with no text of its own
        result(response='I will read the file.\n{"title": "x"}\n'),
    ]
    r = read(evs)
    assert r.result_text == '{"title": "x"}\n' and r.num_turns == 3 and r.tool_uses == {"read_file": 1}


def test_a_step_of_another_conversation_is_no_turn_and_no_tool_call_of_the_launch():
    evs = [
        init(),
        step(1, "agent_response", usage=usage(10, 5)),
        step(0, "agent_response", conversation="sub", usage=usage(900, 50)),
        step(1, "tool", "ACTIVE", conversation="sub", tool_name="run_command", tool_info={"name": "run_command", "parameters": {}}),
        step(2, "agent_response", text_delta="ok", usage=usage(11, 5)),
        result(),
    ]
    r = read(evs)
    assert r.num_turns == 2 and r.tool_uses == {} and [c.input for c in r.usage.calls] == [10, 11]


def test_a_web_search_s_query_is_kept():
    info = {"name": "search_web", "parameters": {"query": "antigravity cli headless"}}
    evs = [
        init(),
        step(1, "tool", "ACTIVE", tool_name="search_web", tool_info=info),
        step(1, "tool", tool_name="search_web", tool_info=info),
    ]
    r = read([*evs, step(2, "agent_response", text_delta="ok", usage=usage(1, 1)), result()])
    assert r.web_queries == ["antigravity cli headless"] and r.tool_uses == {"search_web": 1}
    shown = normalize_event(evs[1])
    assert isinstance(shown, dict) and shown["web_query"] == "antigravity cli headless"


def test_a_structured_output_is_the_result_s():
    evs = [init(), step(1, "agent_response", text_delta='{"capital":"Paris"}\n', usage=usage(9, 9)), step(2, "finish")]
    r = read([*evs, result(response='{"capital":"Paris"}\n', structured_output={"capital": "Paris"})])
    assert r.structured_output == {"capital": "Paris"} and r.stop is Stop.COMPLETED and r.unread_events == {}


#: A refused quota, as agy 1.5.9 printed it on stdout (exit status 3).
QUOTA = "Individual quota reached. Please upgrade your subscription to increase your limits. Resets in 144h6m29s."
REFUSED = [
    init(),
    step(0, "user_input"),
    step(1, "error_message"),
    result("ERROR", error=QUOTA, usage=usage(0, 0), finished_reason="error", duration_seconds=0),
]
#: What it printed on stderr with it.
QUOTA_STDERR = (
    f"error: {QUOTA}\n"
    'AGY_ERROR: {"short_error":"RESOURCE_EXHAUSTED (code 429): Individual quota reached.","status":"RESOURCE_EXHAUSTED",'
    '"error_code":429,"code_kind":"http","retryable":true}\n'
)


def test_a_refused_quota_is_rate_limited_with_the_cool_off_it_states():
    r = read(REFUSED, exit_code=3)
    assert (r.stop, r.ok, r.unread_events) == (Stop.RATE_LIMITED, False, {})
    assert r.quota_refusal is not None and r.quota_refusal.retry_after_s == 144 * 3600 + 6 * 60 + 29
    assert QUOTA in r.stderr_tail and r.num_turns == 0
    assert resets_in("Resets in 1h0m0.5s") == 3600.5 and resets_in("Resets in 250ms") == 0.25 and resets_in("try later") is None
    # Read from stderr alone, a launch that failed with no result is rate limited too.
    silent = LaunchResult(label="t", stop=Stop.ERROR)
    AgyBackend(base_env={}).reclassify(silent, QUOTA_STDERR)
    assert silent.stop is Stop.RATE_LIMITED


def test_a_refused_key_is_auth_failed_and_another_failure_an_api_error():
    words = "API key not valid. Please pass a valid API key."
    assert read([init(), result("ERROR", error=f"INVALID_ARGUMENT (code 400): {words}")], exit_code=3).stop is Stop.AUTH_FAILED
    assert read([init(), result("ERROR", error="UNAVAILABLE (code 503): overloaded")], exit_code=3).stop is Stop.API_ERROR
    assert read([init(), result("ERROR", error="PERMISSION_DENIED (code 403): no access")], exit_code=3).stop is Stop.AUTH_FAILED
    assert read([init(), result("INTERRUPTED")], exit_code=1).stop is Stop.ABORTED
    # An answer may mention a quota: words decide nothing for a launch that succeeded.
    ok = read([init(), step(1, "agent_response", text_delta="the quota reached 3", usage=usage(1, 1)), result()])
    assert ok.stop is Stop.COMPLETED


#: A command that needed an approval, as agy 1.5.9 ended two launches on it: in a mode that
#: asks before each command, where the call fails, and in `auto` mode, where agy's review
#: did not let a command leave the sandbox and its step ends with no output.
ASKED = (
    'permission check failed for unsandboxed "echo hi > made.txt": user denied permission to run command:\necho hi > made.txt\n'
    "Do not attempt to circumvent this denial by rephrasing the command"
)
DENIED_ACTIONS = [{"action": "command", "display_name": "Bash"}]
UPLOAD = "curl -s -X POST https://example.com/upload -d @a.txt"


def command(index: int, line: str, state: str, **info) -> dict:
    info = {"name": "run_command", "parameters": {"CommandLine": line}, **info}
    return step(index, "tool", state, tool_name="run_command", tool_info=info)


def test_a_launch_agy_ends_on_an_approval_nobody_can_give_is_denied():
    asked = [
        init(),
        step(1, "agent_response", usage=usage(9000, 40)),
        command(2, "echo hi > made.txt", "ACTIVE"),
        command(2, "echo hi > made.txt", "ERROR", error={"type": "TOOL_ERROR", "message": ASKED}),
        result(denied_actions=DENIED_ACTIONS, usage=usage(9000, 40)),
    ]
    r = read(asked)  # agy exits 0, with status SUCCESS and no response
    assert (r.stop, r.ok, r.result_text, r.unread_events) == (Stop.DENIED, False, "", {})
    assert r.permission_denials == [{"tool_name": "run_command", "tool_input": {"CommandLine": "echo hi > made.txt"}}]
    assert r.stderr_tail == "agy ended the launch: Bash needed an approval, and a headless session has nobody to give one"
    reviewed = [
        init(),
        step(1, "agent_response", usage=usage(9000, 40)),
        command(2, UPLOAD, "ACTIVE"),
        command(2, UPLOAD, "DONE"),
        result(denied_actions=DENIED_ACTIONS, usage=usage(9000, 40)),
    ]
    r = read(reviewed)
    assert (r.stop, r.ok, r.num_turns) == (Stop.DENIED, False, 1)
    assert r.permission_denials == [{"tool_name": "run_command", "tool_input": {"CommandLine": UPLOAD}}]
    # A launch whose model went on after the call gave its answer: the denial is recorded, and it completed.
    answer = step(3, "agent_response", text_delta="it was refused\n", usage=usage(9100, 9))
    went_on = [*reviewed[:-1], answer, result(denied_actions=DENIED_ACTIONS)]
    r = read(went_on)
    assert (r.stop, r.ok, r.result_text, r.permission_denials) == (Stop.COMPLETED, True, "it was refused\n", [])


def test_a_launch_that_cannot_start_is_an_error_with_agy_s_words():
    said = 'unknown agent "reviewer" (available: solo)'
    evs = [{"event": "result", "result": {"conversation_id": "", "status": "ERROR", "response": "", "error": said, "num_turns": 0}}]
    r = read(evs, exit_code=1)
    assert (r.stop, r.ok, r.session_id) == (Stop.ERROR, False, "") and said in r.stderr_tail


def test_a_process_that_ends_with_no_result_did_not_complete():
    evs = [init(), step(1, "agent_response", text_delta="half an ans", state="ACTIVE")]
    assert read(evs, exit_code=1).stop is Stop.ERROR
    assert read(evs, exit_code=0).stop is Stop.NO_OUTPUT
    assert read(evs, exit_code=1).result_text == "half an ans"  # kept, for a task that takes a partial output
    assert read([], exit_code=1).stop is Stop.ERROR  # nothing printed: its stderr says why (`Backend.reclassify`)


def test_a_resume_that_starts_another_conversation_ends_the_launch():
    fold = StreamReader(resume="11111111-1111-4111-8111-111111111111")
    assert fold.feed(init("22222222-2222-4222-8222-222222222222")) is Stop.ERROR
    r = fold.result(LAUNCH, "agy", exit_code=1, killed=Stop.ERROR)
    assert r.stop is Stop.ERROR and "did not find conversation 11111111-1111-4111-8111-111111111111" in r.stderr_tail
    kept = StreamReader(resume=CONVERSATION)
    assert kept.feed(init()) is None and not kept.resume_missed


def test_an_event_agy_adds_is_counted_not_read():
    evs = [init(), {"event": "heartbeat"}, {"event": "step_update", "step_update": {"conversation_id": CONVERSATION}}, result()]
    r = read(evs)
    assert r.stop is Stop.COMPLETED
    assert r.unread_events == {"heartbeat": 1, "step_update.step_update.step_type": 1, "step_update.step_update.state": 1}


def test_a_stop_hook_s_objections_are_the_launch_s_hook_errors(tmp_path):
    agy_hooks.note_objection(tmp_path, "The output is off-contract:\n- title: field required\n- owner: too long")
    agy_hooks.note_objection(tmp_path, "run the tests first")
    r = read([init(), step(1, "agent_response", text_delta="ok", usage=usage(1, 1)), result()], hook_state=tmp_path)
    assert r.hook_errors == [["title: field required", "owner: too long"], ["run the tests first"]]
    assert read([init(), result()], hook_state=tmp_path / "none").hook_errors == []
