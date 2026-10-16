"""The real backends' run paths, against fake CLIs: argv, env, the stream reader, the classifier.

The stub backends elsewhere replace `Backend.run`, so they never execute this code. A small
script on PATH standing in for `claude` / `omp` does, without spending a token.
"""

import json
import os
from pathlib import Path

from contraagent._internal.backends.base import temp_root
from contraagent.backends import ClaudeBackend, Launch, LaunchResult, OmpBackend, OmpRpcBackend, Stop
from contraagent.config import ApiKey, Limits
from fake_cli import write_fake_cli

CLAUDE = r"""
import json, os, sys
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)"); sys.exit(0)
json.dump(dict(os.environ), open(os.environ["FAKE_ENV_DUMP"], "w"))
source = os.environ.get("FAKE_SOURCE") or ("ANTHROPIC_API_KEY" if os.environ.get("ANTHROPIC_API_KEY") else "none")
print(json.dumps({"type": "system", "subtype": "init", "model": "fake-model", "tools": ["Read"], "session_id": "s-1",
                  "apiKeySource": source}))
print(json.dumps({"type": "assistant", "message": {"id": "m1", "model": "fake-model", "content": [{"type": "text", "text": "hi"}],
                  "usage": {"input_tokens": 10, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 2}}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok", "session_id": "s-1",
                  "num_turns": 1, "total_cost_usd": 0.001, "usage": {"output_tokens": 2},
                  "modelUsage": {"fake-model": {"inputTokens": 10, "outputTokens": 2, "cacheReadInputTokens": 0,
                                                "cacheCreationInputTokens": 0, "webSearchRequests": 0, "costUSD": 0.001,
                                                "contextWindow": 1000000, "maxOutputTokens": 64000}}}))
"""

OMP = r"""
import json, os, sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.8.6"); sys.exit(0)
json.dump(dict(os.environ), open(os.environ["FAKE_ENV_DUMP"], "w"))
print("Done: wrote the file.")
"""


def fake_cli(tmp_path, name, body):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, name, body)
    return bindir


def test_claude_backend_runs_a_launch_end_to_end(tmp_path):
    bindir = fake_cli(tmp_path, "claude", CLAUDE)
    dump = tmp_path / "env.json"
    base = {
        "PATH": f"{bindir}{os.pathsep}/usr/bin:/bin",
        "ANTHROPIC_API_KEY": "leftover",
        "MY_KEY": "sk-test",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_MESSAGING_SOCKET": "/run/parent.sock",
        "CLAUDE_CODE_MESSAGING_TOKEN": "parent-token",
    }
    backend = ClaudeBackend(base_env=base)
    launch_result = backend.run(
        Launch(
            prompt="hello",
            label="t",
            model="fake-model",
            cwd=tmp_path,
            limits=Limits(timeout_s=30, max_turns=1),
            env={"FAKE_ENV_DUMP": str(dump)},
            credential=ApiKey(name="k", key="env:MY_KEY"),
        )
    )
    assert launch_result.stop == Stop.COMPLETED and launch_result.ok, launch_result.stderr_tail
    assert launch_result.result_text == "ok" and launch_result.session_id == "s-1" and len(launch_result.usage.calls) == 1
    assert launch_result.credential == "k" and launch_result.api_key_source == "ANTHROPIC_API_KEY"
    assert (launch_result.context_window, launch_result.as_dict()["context_window"]) == (1_000_000, 1_000_000)  # as reported
    env = json.loads(dump.read_text())
    assert env["ANTHROPIC_API_KEY"] == "sk-test"  # the credential named, not the leftover
    assert not {"CLAUDECODE", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN"} & set(env)  # nor the parent session
    assert env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    argv = launch_result.argv
    assert argv[argv.index("--setting-sources") + 1] == ""  # no user, project or local settings files
    # isolated: no stored login to fall back to
    assert Path(env["CLAUDE_CONFIG_DIR"]).is_relative_to(temp_root()) and "/claude-" in env["CLAUDE_CONFIG_DIR"]


def test_omp_backend_runs_a_launch_end_to_end(tmp_path):
    bindir = fake_cli(tmp_path, "omp", OMP)
    dump = tmp_path / "env.json"
    backend = OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"}, trace=False)
    launch_result = backend.run(
        Launch(prompt="hello", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30), env={"FAKE_ENV_DUMP": str(dump)})
    )
    assert launch_result.stop == Stop.COMPLETED and launch_result.ok, launch_result.stderr_tail
    assert "wrote the file" in launch_result.result_text


def test_a_missing_binary_is_a_launch_failure_not_a_crash(tmp_path):
    for backend in (ClaudeBackend(base_env={"PATH": str(tmp_path)}), OmpBackend(base_env={"PATH": str(tmp_path)})):
        launch_result = backend.run(Launch(prompt="x", label="t", cwd=tmp_path))
        assert launch_result.stop == Stop.LAUNCH_FAILED


def test_an_unstartable_launch_is_a_launch_failure_for_every_backend(tmp_path):
    """The binary is on PATH but the process cannot start (its cwd is gone): a LaunchResult, not an exception."""
    bindir = fake_cli(tmp_path, "claude", CLAUDE)
    fake_cli(tmp_path, "omp", OMP)
    env = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"}
    for backend in (ClaudeBackend(base_env=env), OmpBackend(base_env=env, trace=False), OmpRpcBackend(base_env=env, trace=False)):
        launch_result = backend.run(Launch(prompt="x", label="t", cwd=tmp_path / "gone"))
        assert launch_result.stop == Stop.LAUNCH_FAILED and not launch_result.ok, backend.name
        assert "gone" in launch_result.stderr_tail, launch_result.stderr_tail


def test_a_missing_rpc_binary_is_a_launch_failure(tmp_path):
    launch_result = OmpRpcBackend(base_env={"PATH": str(tmp_path)}).run(Launch(prompt="x", label="t", cwd=tmp_path))
    assert launch_result.stop == Stop.LAUNCH_FAILED


def test_every_utilization_reading_of_a_session_is_kept():
    """Claude Code reports the subscription's utilization when a session starts and again when it is
    resumed (shapes from real transcripts); each reading is kept, with when it arrived."""
    from contraagent._internal.backends.claude.wire import StreamReader

    def event(five, week):
        windows = {"five_hour": {"utilization": five, "resetsAt": 1791347400}, "seven_day": {"utilization": week, "resetsAt": 1791800000}}
        return json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": windows}})

    reader = StreamReader(Limits())
    reader.feed_line(event(0.1, 0.55))
    reader.feed_line(event(0.15, 0.56))
    assert [(r.five_hour_pct, r.seven_day_pct) for r in reader.quota] == [(10.0, 55.0), (15.0, 56.0)]
    assert all(r.observed_at for r in reader.quota)


OMP_ACCOUNTED = r"""
import json, sys
if "usage" in sys.argv:
    limit = lambda w, used, resets: {"scope": {"provider": "anthropic", "windowId": w, "shared": True}, "status": "ok",
                                     "window": {"id": w, "resetsAt": resets}, "amount": {"usedFraction": used, "unit": "percent"}}
    report = {"provider": "anthropic", "fetchedAt": 1791776226254,
              "limits": [limit("5h", 0.05, 1791784800000), limit("7d", 0.79, 1791979200000),
                         {**limit("7d", 0.0, 1791979200000), "scope": {"windowId": "7d", "tier": "fable"}}]}
    print(json.dumps({"reports": [report]})); sys.exit(0)
print(json.dumps({"type": "session", "id": "s-1"}))
for n in (1, 2):
    usage = {"input": 4, "output": 100 * n, "cacheRead": 1000, "cacheWrite": 50, "cost": {"total": 0.001 * n}}
    print(json.dumps({"type": "message_end", "message": {"role": "assistant", "model": "claude-haiku-5-5", "usage": usage}}))
print(json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "Done: wrote the file."}}))
"""


def test_omp_reports_tokens_cost_and_the_accounts_usage(tmp_path):
    bindir = fake_cli(tmp_path, "omp", OMP_ACCOUNTED)
    backend = OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"})
    launch = Launch(prompt="hello", label="t", model="anthropic/claude-haiku-5-5", cwd=tmp_path, limits=Limits(timeout_s=30))
    result = backend.run(launch)
    assert result.stop == Stop.COMPLETED and result.cost_usd == 0.003
    t = result.usage.totals()
    assert t is not None and (t.calls, t.output, t.cache_read, t.cache_creation) == (2, 300, 2000, 100)
    [reading] = result.quota
    assert (reading.five_hour_pct, reading.seven_day_pct, reading.status) == (5.0, 79.0, "allowed")
    assert reading.seven_day_resets_at == "2026-10-14T12:00:00+00:00" and reading.observed_at
    assert backend.run(launch).quota[0] == reading  # read again at each launch: the latest request's


def test_omp_ends_a_launch_past_its_cost_cap(tmp_path):
    bindir = fake_cli(tmp_path, "omp", OMP_ACCOUNTED)
    backend = OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"})
    launch = Launch(prompt="hello", label="t", model="anthropic/x", cwd=tmp_path, limits=Limits(timeout_s=30, max_budget_usd=0.0015))
    result = backend.run(launch)
    assert result.stop == Stop.BUDGET and not result.ok


def test_claude_reports_its_peak_context_and_stops_past_its_context_budget():
    """Claude Code sends one API call's usage on each of its `assistant` lines (several lines
    per call share the message id): the peak context is the largest call's whole input."""
    from contraagent._internal.backends.claude.wire import StreamReader
    from contraagent.backends import LimitsWatch

    def call(mid: str, fresh: int, read: int, written: int) -> str:
        usage = {"input_tokens": fresh, "cache_read_input_tokens": read, "cache_creation_input_tokens": written, "output_tokens": 5}
        return json.dumps({"type": "assistant", "message": {"id": mid, "model": "claude-haiku-5-5", "content": [], "usage": usage}})

    lines = [call("m1", 3, 0, 9000), call("m1", 3, 0, 9000), call("m2", 2, 9000, 2500), call("m3", 1, 11500, 40)]
    reader = StreamReader(Limits())
    assert [reader.feed_line(line) for line in lines] == [None] * 4
    result = LaunchResult(label="t", usage=reader.usage())
    assert (len(result.usage.calls), result.usage.resident, result.peak_context) == (3, 9003, 11541)
    capped = StreamReader(Limits(context_budget=11000))
    watch = LimitsWatch(Limits(context_budget=11000), ClaudeBackend.watched_limits, capped)
    assert [capped.feed_line(line) or watch() for line in lines][-2:] == [Stop.CONTEXT, Stop.CONTEXT]
    assert LaunchResult(label="t").peak_context is None  # no API call read


def test_claude_records_what_its_stop_hook_sent_back():
    from contraagent._internal.backends.claude.wire import StreamReader, normalize_event

    text = "Stop hook feedback:\n[validate]: fix them.\n\n## out.json\nErrors:\n- out.json: [lines] line 99 is past the end\n"
    feedback = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    reader = StreamReader(Limits())
    reader.feed(feedback)
    assert reader.hook_errors == [["out.json: [lines] line 99 is past the end"]]
    assert normalize_event(feedback)["type"] == "notice"


def test_omp_launches_see_only_their_plugin():
    """omp discovers instructions, skills, hooks and MCP servers in the project and the home
    directory; every launch turns that off but for the plugin it is given."""
    from contraagent._internal.backends.omp.backend import ISOLATION

    backend = OmpBackend(base_env={"PATH": "/usr/bin", "CLAUDE_CONFIG_DIR": "/home/me/.claude", "CLAUDE_CODE_MESSAGING_TOKEN": "t"})
    launch = Launch(prompt="hi", label="t", model="anthropic/x", plugin_dirs=("/p",))
    argv = backend.argv(launch)
    assert argv[argv.index("--config") + 1] == str(ISOLATION / "config.yml")
    assert backend.env(launch)["CLAUDE_CONFIG_DIR"] == str(ISOLATION)  # the user's installed Claude plugins: none
    assert "CLAUDE_CODE_MESSAGING_TOKEN" not in backend.env(launch)  # nor the session that started the run
    assert not (ISOLATION / "plugins").exists()
    disabled = [line.split("#")[0].strip(" -") for line in (ISOLATION / "config.yml").read_text().splitlines() if line.startswith("  - ")]
    assert "claude-plugins" not in disabled and {"native", "agents-md", "claude-md", "claude", "mcp-json"} <= set(disabled)
    rpc = OmpRpcBackend(base_env={"PATH": "/usr/bin"}).argv(launch)
    assert rpc[rpc.index("--config") + 1] == str(ISOLATION / "config.yml")


OMP_SEARCHING = r"""
import json, sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.8.6"); sys.exit(0)
for q in ("contraagent  docs", ""):
    call = {"type": "toolcall_end", "toolCall": {"name": "web_search", "arguments": {"query": q}}}
    print(json.dumps({"type": "message_update", "assistantMessageEvent": call}))
    print(json.dumps({"type": "tool_execution_end", "toolName": "web_search"}))
print(json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "Done."}}))
"""


def test_omp_records_its_web_searches_and_counts_each_call_once(tmp_path):
    from contraagent._internal.backends.omp.rpc import RpcReader

    bindir = fake_cli(tmp_path, "omp", OMP_SEARCHING)
    backend = OmpBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"})
    result = backend.run(Launch(prompt="hello", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30)))
    assert result.ok and result.web_queries == ["contraagent docs"]
    assert result.tool_uses == {"web_search": 2}  # each call once, not again at its execution
    acc = RpcReader("p1")
    call = {"type": "toolcall_end", "toolCall": {"name": "web_search", "arguments": {"query": "omp rpc"}}}
    acc.feed({"type": "message_update", "assistantMessageEvent": call})
    acc.feed({"type": "tool_execution_end", "toolName": "web_search"})
    rpc = acc.result(Launch(prompt="x", label="t"), "omp-rpc", exit_code=None, killed=None)
    assert rpc.web_queries == ["omp rpc"] and rpc.tool_uses == {"web_search": 1}


def test_claude_shows_a_web_search_by_its_query_and_a_web_page_by_its_url():
    from contraagent._internal.backends.claude.wire import normalize_event

    call = {"type": "tool_use", "id": "c1", "name": "WebSearch", "input": {"query": "omp rpc"}}
    shown = normalize_event({"type": "assistant", "message": {"content": [call]}})
    assert (shown["cmd"], shown["web_query"]) == ("omp rpc", "omp rpc")
    read = {"type": "tool_use", "id": "c2", "name": "Read", "input": {"file_path": "a.md"}}
    assert "web_query" not in normalize_event({"type": "assistant", "message": {"content": [read]}})
    fetch = {"type": "tool_use", "id": "c3", "name": "WebFetch", "input": {"url": "https://omp.sh/", "prompt": "what is it"}}
    shown = normalize_event({"type": "assistant", "message": {"content": [fetch]}})
    assert (shown["cmd"], shown["web_fetch"], shown["intent"]) == ("https://omp.sh/", "https://omp.sh/", "what is it")


def test_omp_shows_a_read_of_a_url_as_a_web_page():
    from contraagent._internal.backends.omp.wire import normalize_event

    def start(path):
        return normalize_event({"type": "tool_execution_start", "toolName": "read", "args": {"path": path}, "toolCallId": "c"})

    assert start("https://omp.sh/docs")["web_fetch"] == "https://omp.sh/docs"
    assert "web_fetch" not in start("notes/a.md")


OMP_RPC = r"""
import json, sys
if sys.argv[1:2] == ["--version"]:
    print("omp/18.9.1"); sys.exit(0)
def send(o):
    print(json.dumps(o), flush=True)
send({"type": "ready", "supportedProtocolVersions": [1]})
for line in sys.stdin:
    req = json.loads(line)
    if req["type"] == "prompt":
        send({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "done"}})
        send({"type": "agent_end", "isTerminal": True})
    elif req["type"] == "get_state":
        send({"type": "extension_ui_request", "id": "w1", "method": "setWidget"})  # before the response
        send({"type": "response", "id": req["id"], "command": "get_state", "success": True, "data": {"sessionId": "s-42",
             "model": {"id": "m", "provider": "p", "contextWindow": 400000, "maxTokens": 128000}}})
"""


def test_omp_rpc_reads_its_session_id_and_context_window_past_frames_that_come_first(tmp_path):
    bindir = fake_cli(tmp_path, "omp", OMP_RPC)
    backend = OmpRpcBackend(base_env={"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin"})
    result = backend.run(Launch(prompt="hello", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30)))
    assert result.ok and result.result_text == "done" and result.session_id == "s-42"
    assert result.context_window == 400_000  # the model's, from get_state


def test_a_chatgpt_login_is_one_credential_for_omp_and_codex():
    """`provider = "openai"` names whose login it is; omp runs that login's models as `openai-codex/`."""
    import pytest

    from contraagent import CredentialError
    from contraagent.backends import CodexBackend
    from contraagent.config import Subscription

    sub = Subscription(name="chatgpt", provider="openai")
    binding = OmpBackend(base_env={}).bind_credential(sub, "openai-codex/gpt-5.6-luna")
    assert binding.isolated and "openai-codex login" in binding.isolation
    with pytest.raises(CredentialError, match="openai-codex \\(its openai login\\)"):
        OmpBackend(base_env={}).bind_credential(sub, "openai/gpt-5.6-luna")  # omp's openai is the API platform
    assert CodexBackend(base_env={}).bind_credential(sub, "gpt-5.6-luna").isolated
