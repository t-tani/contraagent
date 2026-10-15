"""The codex backend against a fake `codex`: argv, env, the event reader, the rollout file, the classifier.

The events and the rollout lines are the shapes codex-cli 0.162.1 printed and wrote in a live run.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from contraagent import ApiKey, CodexBackend, Gateway, Launch, Limits, Stop, Subscription
from contraagent.backends import CredentialError
from contraagent.backends.codex.wire import EventReader, normalize_event, read_rollout
from contraagent.backends.streams import normalize_stream_line

THREAD = "01a13afd-d786-78c2-9439-7b6c086efc20"

CODEX = r"""
import json, os, pathlib, sys
if "--version" in sys.argv:
    print("codex-cli 0.162.1"); sys.exit(0)
json.dump({"argv": sys.argv, "env": dict(os.environ), "stdin": sys.stdin.read() if "-" == sys.argv[-1] else None},
          open(os.environ["FAKE_DUMP"], "w"))
mode = os.environ.get("FAKE_MODE", "ok")
thread = "01a13afd-d786-78c2-9439-7b6c086efc20"
def out(o): print(json.dumps(o), flush=True)
out({"type": "thread.started", "thread_id": thread})
out({"type": "turn.started"})
if mode == "auth":
    for i in range(1, 6):
        out({"type": "error", "message": f"Reconnecting... {i}/5 (unexpected status 401 Unauthorized: bad key, url: http://gw/v1/responses)"})
    out({"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized: bad key"}})
    sys.exit(1)
if mode == "quota":
    out({"type": "turn.failed", "error": {"message": "You've hit your usage limit. Try again in 3 hours."}})
    sys.exit(1)
out({"type": "item.started", "item": {"id": "item_1", "type": "command_execution", "command": "bash -lc 'cat a.txt'",
     "aggregated_output": "", "exit_code": None, "status": "in_progress"}})
out({"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": "bash -lc 'cat a.txt'",
     "aggregated_output": "hi\n", "exit_code": 0, "status": "completed"}})
out({"type": "item.completed", "item": {"id": "item_2", "type": "web_search", "query": "python release"}})
out({"type": "item.completed", "item": {"id": "item_3", "type": "agent_message", "text": os.environ.get("FAKE_TEXT", "DONE")}})
out({"type": "turn.completed", "usage": {"input_tokens": 17240, "cached_input_tokens": 8509, "cache_write_input_tokens": 8727,
     "output_tokens": 197}})
home = pathlib.Path(os.environ.get("CODEX_HOME") or pathlib.Path.home() / ".codex")
d = home / "sessions" / "2026" / "10" / "15"
d.mkdir(parents=True, exist_ok=True)
def tc(i, c, w, o, limits=None):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {
        "input_tokens": i, "cached_input_tokens": c, "cache_write_input_tokens": w, "output_tokens": o},
        "model_context_window": 258400},
        "rate_limits": limits or {"primary": None, "secondary": None}}}
lines = [
    {"type": "session_meta", "payload": {"id": thread, "cli_version": "0.162.1"}},
    {"type": "turn_context", "payload": {"model": "gpt-5.6-luna"}},
    tc(8511, 0, 8509, 192),
    tc(8729, 8509, 218, 5, {"primary": {"used_percent": 42.0, "window_minutes": 300, "resets_at": 1791991076},
                            "secondary": {"used_percent": 7.5, "window_minutes": 10080, "resets_at": 1792500000}}),
]
with open(d / f"rollout-2026-10-15T00-17-56-{thread}.jsonl", "a") as f:
    for line in lines:
        f.write(json.dumps(line) + "\n")
"""


@pytest.fixture
def fake(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "codex"
    script.write_text(f"#!{sys.executable}\n{CODEX}")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    dump = tmp_path / "dump.json"
    base = {
        "PATH": f"{bindir}{os.pathsep}/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "OPENAI_API_KEY": "leftover",
        "CODEX_API_KEY": "leftover",
        "MY_KEY": "sk-test",
        "GW": "http://gw.example/v1",
        "CLAUDECODE": "1",
    }
    work = tmp_path / "work"
    work.mkdir()

    def run(mode="ok", **kw):
        launch = Launch(**{"prompt": "hello", "label": "t", "model": "gpt-5.6-luna", "cwd": work, "limits": Limits(timeout_s=30), **kw})
        launch = launch.__class__(**{**launch.__dict__, "env": {"FAKE_DUMP": str(dump), "FAKE_MODE": mode, **launch.env}})
        backend = CodexBackend(base_env=base)
        result = backend.run(launch)
        return backend, result, json.loads(dump.read_text())

    return run


def test_a_launch_reads_its_events_and_its_rollout(fake):
    _, r, seen = fake(credential=ApiKey(name="k", provider="openai", key="env:MY_KEY"), effort="low")
    assert r.stop is Stop.COMPLETED and r.ok, r.stderr_tail
    assert r.result_text == "DONE" and r.session_id == THREAD and r.agent == "codex" and r.credential == "k"
    assert r.tool_uses == {"command_execution": 1, "web_search": 1} and r.web_queries == ["python release"]
    # Per call, from the rollout: the cached and cache-written parts are not counted as input twice.
    assert [(c.input, c.cache_read, c.cache_creation, c.output) for c in r.usage.calls] == [(2, 0, 8509, 192), (2, 8509, 218, 5)]
    assert r.usage.resident == 8511 and r.usage.output_total == 197 and r.init_model == "gpt-5.6-luna"
    assert r.peak_context == 2 + 8509 + 218  # the second call's whole input
    assert (r.context_window, r.context_pct) == (258400, round(100 * (2 + 8509 + 218) / 258400, 1))  # as the rollout reports it
    assert [(q.five_hour_pct, q.seven_day_pct) for q in r.quota[-1:]] == [(42.0, 7.5)]
    env = seen["env"]
    assert env["CODEX_API_KEY"] == "sk-test" and "OPENAI_API_KEY" not in env and "CLAUDECODE" not in env
    assert "contraagent" in env["CODEX_HOME"] and "contraagent" in env["CODEX_SQLITE_HOME"]  # no stored login, no shared index
    argv = seen["argv"]
    assert argv[1:4] == ["exec", "--json", "--skip-git-repo-check"] and "--ignore-user-config" in argv
    assert {"project_doc_max_bytes=0", 'model_reasoning_effort="low"'} <= set(argv)
    assert argv[-1] == "hello"


def test_codex_sees_only_its_plugins_skills_and_its_commands_the_real_home(fake, tmp_path):
    task, shared = tmp_path / "task-plugin", tmp_path / "skill-plugin"
    for plug, names in ((task, ("write-output", "notes")), (shared, ("notes", "house-style"))):
        for name in names:
            (plug / "skills" / name).mkdir(parents=True)
            (plug / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n{plug.name}\n")
    (tmp_path / "home" / ".agents" / "skills" / "mine").mkdir(parents=True)  # the user's own skill
    _, r, seen = fake(plugin_dirs=(str(task), str(shared)))
    assert r.ok
    env = seen["env"]
    skills = os.path.join(env["HOME"], ".agents", "skills")
    assert sorted(os.listdir(skills)) == ["house-style", "notes", "write-output"]
    assert os.path.realpath(os.path.join(skills, "notes")) == str((task / "skills" / "notes").resolve())  # the task's own first
    assert env["HOME"] != str(tmp_path / "home") and env["CODEX_HOME"] == str(tmp_path / "home" / ".codex")
    assert f'shell_environment_policy.set.HOME="{tmp_path / "home"}"' in seen["argv"]
    assert (task / "skills" / "notes" / "SKILL.md").exists()  # a later launch's cleanup removes links only


def test_the_projects_own_skills_are_turned_off_by_path(fake, tmp_path):
    work = tmp_path / "work"
    (tmp_path / ".git").mkdir()  # the repository's root: codex looks from cwd up to here
    plugin = work / ".agents"  # a plugin whose skills are where codex looks for the project's
    for d, name in (
        (work / ".codex" / "skills", "mine"),
        (tmp_path / ".agents" / "skills", "above"),
        (plugin / "skills", "write-output"),
    ):
        (d / name).mkdir(parents=True)
        (d / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    _, r, seen = fake(plugin_dirs=(str(plugin),))
    assert r.ok
    table = next(a for a in seen["argv"] if a.startswith("skills.config="))
    assert str(work / ".codex" / "skills" / "mine" / "SKILL.md") in table
    assert str(tmp_path / ".agents" / "skills" / "above" / "SKILL.md") in table
    assert "write-output" not in table and table.count('"enabled"=false') == 2


def test_the_rollout_of_a_session_nobody_keeps_is_removed(fake, tmp_path):
    backend, r, seen = fake(credential=ApiKey(name="k", provider="openai", key="env:MY_KEY"))
    assert not list((tmp_path / "cache").rglob("rollout-*.jsonl"))
    backend, r, seen = fake(credential=ApiKey(name="k", provider="openai", key="env:MY_KEY"), persist_session=True)
    assert len(list((tmp_path / "cache").rglob("rollout-*.jsonl"))) == 1 and "CODEX_SQLITE_HOME" not in seen["env"]


def test_a_resumed_launch_counts_only_its_own_calls(fake, tmp_path):
    cred = ApiKey(name="k", provider="openai", key="env:MY_KEY")
    backend, first, _ = fake(credential=cred, persist_session=True)
    nxt = backend.resumed(backend.resumable(Launch(prompt="hello", label="t", credential=cred, cwd=tmp_path)), first, "again")
    assert nxt is not None and nxt.resume == THREAD
    _, second, seen = fake(credential=cred, persist_session=True, resume=THREAD, prompt="again")
    assert seen["argv"][1:4] == ["exec", "resume", THREAD] and seen["argv"][-1] == "again"
    assert len(second.usage.calls) == 2  # the rollout holds four calls by now


def test_a_gateway_is_a_model_provider_of_its_own(fake):
    _, r, seen = fake(credential=Gateway(name="gw", base_url="env:GW", token="env:MY_KEY"))
    assert r.ok
    argv = seen["argv"]
    assert 'model_provider="litellm"' in argv
    table = next(a for a in argv if a.startswith("model_providers.litellm="))
    assert '"base_url"="http://gw.example/v1"' in table and '"env_key"="LITELLM_API_KEY"' in table and "sk-test" not in table
    assert seen["env"]["LITELLM_API_KEY"] == "sk-test"


def test_a_long_prompt_and_its_attached_files_go_over_stdin(fake, tmp_path):
    role = tmp_path / "role.md"
    role.write_text("You review code.")
    long = "x" * 70_000
    _, r, seen = fake(prompt=long, preamble="PRE", context_files=(str(role),))
    assert r.ok and seen["argv"][-1] == "-"
    assert seen["stdin"].startswith("PRE") and "You review code." in seen["stdin"] and seen["stdin"].endswith(long)


def test_a_structured_answer_is_parsed(fake):
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False}
    _, r, seen = fake(json_schema=schema, env={"FAKE_TEXT": '{"n": 5}'})
    assert r.structured_output == {"n": 5}
    assert json.loads(Path(seen["argv"][seen["argv"].index("--output-schema") + 1]).read_text()) == schema


def test_a_refused_credential_ends_the_launch_on_its_second_retry(fake):
    _, r, _ = fake("auth")
    assert r.stop is Stop.AUTH_FAILED and not r.ok and r.retry_errors == {"http_401": 2}


def test_a_usage_limit_is_a_rate_limit(fake):
    _, r, _ = fake("quota")
    assert r.stop is Stop.RATE_LIMITED


def test_a_tool_call_past_max_turns_ends_the_launch(fake):
    _, r, _ = fake(limits=Limits(timeout_s=30, max_turns=1))
    assert r.stop is Stop.MAX_TURNS and not r.ok


def test_credentials_codex_cannot_use_are_refused():
    backend = CodexBackend(base_env={})
    with pytest.raises(CredentialError):
        backend.bind_credential(ApiKey(name="a", key="env:K"))  # an Anthropic key
    assert backend.bind_credential(Subscription(name="s", provider="openai", config_dir="/x")).env == {"CODEX_HOME": "/x"}


def test_a_missing_binary_is_a_launch_failure(tmp_path):
    r = CodexBackend(base_env={"PATH": str(tmp_path)}).run(Launch(prompt="hi", cwd=tmp_path))
    assert r.stop is Stop.LAUNCH_FAILED and "not on PATH" in r.stderr_tail


def test_the_monitor_renders_codex_events():
    def show(ev):
        found = normalize_stream_line("codex", json.dumps(ev))
        return found[0] if len(found) == 1 else found or None

    cmd = {"id": "item_1", "type": "command_execution", "command": "ls", "aggregated_output": "a\n", "exit_code": 2}
    assert show({"type": "item.started", "item": cmd}) == {
        "type": "tool_execution_start",
        "tool": "command_execution",
        "intent": "",
        "call": "item_1",
        "cmd": "ls",
    }
    assert show({"type": "item.completed", "item": cmd}) == {
        "type": "tool_execution_end",
        "tool": "",
        "out": "a\n",
        "err": True,
        "call": "item_1",
    }
    assert show({"type": "item.completed", "item": {"id": "i", "type": "agent_message", "text": "hi"}})["delta"] == "hi"
    start, end = show({"type": "item.completed", "item": {"id": "i", "type": "web_search", "query": "q"}})
    assert start["web_query"] == "q" and end["type"] == "tool_execution_end"
    retry = show({"type": "error", "message": "Reconnecting... 2/5 (unexpected status 502)"})
    assert retry == {"type": "auto_retry_start", "attempt": 2, "err": "unexpected status 502"}
    assert show({"type": "turn.started"}) is None


def test_an_unknown_event_is_counted():
    reader = EventReader()
    reader.feed({"type": "thread.started", "thread_id": "x"})
    reader.feed({"type": "item.delta"})
    assert reader.unread == {"item.delta": 1} and reader.stop(exit_code=0, killed=None) is Stop.NO_OUTPUT
    assert normalize_event({"type": "item.delta"}) == {"type": "skip"}


def test_a_rollout_without_windows_has_no_reading(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text(
        json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": None, "rate_limits": {"primary": None}}}) + "\n"
    )
    assert read_rollout(f).quota == [] and read_rollout(f).calls == [] and read_rollout(f).context_window is None


def test_a_web_search_names_its_query_and_pages_when_it_ends():
    """codex starts a search with no query and fills in the query and its results at the end."""
    started = {"id": "ws", "type": "web_search", "query": "", "action": {"type": "other"}}
    done = {
        "id": "ws",
        "type": "web_search",
        "query": "latest python",
        "action": {"type": "search", "query": "latest python"},
        "results": [{"type": "text_result", "title": "Python 3.14.6", "url": "https://www.python.org/x/"}],
    }
    assert normalize_event({"type": "item.started", "item": started})["cmd"] == ""
    start, end = normalize_event({"type": "item.completed", "item": done})
    assert start["type"] == "tool_execution_start" and start["web_query"] == start["cmd"] == "latest python"
    assert end["type"] == "tool_execution_end" and end["call"] == start["call"] == "ws"
    assert json.loads(end["out"]) == {"title": "Python 3.14.6", "url": "https://www.python.org/x/"}
    opened = {**done, "action": {"type": "open_page", "url": "https://a.example/"}}
    assert normalize_event({"type": "item.completed", "item": opened})[0]["web_fetch"] == "https://a.example/"
    reader = EventReader()
    reader.feed({"type": "item.completed", "item": done})
    reader.feed({"type": "item.completed", "item": opened})
    assert reader.web_queries == ["latest python"] and reader.tool_uses == {"web_search": 2}
