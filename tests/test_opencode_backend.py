"""The opencode backend's run path against a fake `opencode` on PATH: argv, env, the config it
writes, the readers of stdout and stderr. No token is spent; `tests/live/` runs the real one."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from contraagent import CredentialError
from contraagent._internal.backends.opencode.backend import LIGHT_AGENT
from contraagent.backends import Launch, OpencodeBackend, Stop
from contraagent.config import ApiKey, Gateway, Limits, Subscription
from test_backends_offline import fake_cli

OPENCODE = r"""
import json, os, sys, time
json.dump({"env": dict(os.environ), "argv": sys.argv, "cwd": os.getcwd()}, open(os.environ["FAKE_DUMP"], "w"))
if os.environ.get("FAKE_QUOTA"):
    print('level=ERROR message="stream error" providerID=opencode-go small=false error.error="AI_APICallError: Go usage limit exceeded"',
          file=sys.stderr, flush=True)
    time.sleep(60)  # opencode waits as long as the provider asks
def send(typ, **part):
    print(json.dumps({"type": typ, "sessionID": "ses_1", "part": {"messageID": part.pop("message", "m1"), **part}}), flush=True)
if os.environ.get("FAKE_OUT"):  # writes its output file, then ends the turn on an empty message
    send("step_start", type="step-start")
    open(os.environ["FAKE_OUT"], "w").write('{"word": "pelican"}')
    send("tool_use", type="tool", tool="apply_patch", callID="c1", state={"status": "completed", "input": {}, "output": "Success."})
    send("step_finish", type="step-finish", reason="tool-calls", tokens={"input": 10, "output": 5})
    send("step_start", type="step-start", message="m2")
    send("text", type="text", text="", message="m2")
    send("step_finish", type="step-finish", reason=os.environ.get("FAKE_REASON", "stop"), message="m2", tokens={"input": 20, "output": 1})
    sys.exit(0)
for n in (1, 2):
    send("step_start", type="step-start")
    if n == 1:
        send("text", type="text", text="I will run it.")
        send("tool_use", type="tool", tool="bash", callID="c1",
             state={"status": "completed", "input": {"command": "echo hi"}, "output": "hi\n"})
    else:
        send("text", type="text", text="done", message="m2")
    send("step_finish", type="step-finish", message="m%d" % n, cost=0.002,
         tokens={"input": 10 * n, "output": 5, "reasoning": 1, "cache": {"read": 100, "write": 7}})
"""


@pytest.fixture
def opencode(tmp_path):
    bindir = fake_cli(tmp_path, "opencode", OPENCODE)
    dump = tmp_path / "dump.json"

    def run(launch: Launch, **base) -> tuple:
        # A home of its own: a login the host stores for opencode-go would send a request to opencode.ai.
        env = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(tmp_path / "home"), **base}
        result = OpencodeBackend(base_env=env).run(launch.__class__(**{**launch.__dict__, "env": {"FAKE_DUMP": str(dump), **launch.env}}))
        seen = json.loads(dump.read_text()) if dump.exists() else {}
        return result, seen

    return run


def config(seen: dict) -> dict:
    return json.loads(seen["env"]["OPENCODE_CONFIG_CONTENT"])


def test_a_launch_runs_with_its_key_alone(opencode, tmp_path):
    launch = Launch(prompt="-hello", label="t", model="anthropic/m", cwd=tmp_path, credential=ApiKey(name="k", key="env:MY_KEY"))
    result, seen = opencode(launch, MY_KEY="sk-test", OPENCODE_API_KEY="leftover", ANTHROPIC_API_KEY="leftover", PWD="/elsewhere")
    assert result.stop == Stop.COMPLETED and result.ok, result.stderr_tail
    assert result.result_text == "done" and result.session_id == "ses_1" and result.tool_uses == {"bash": 1}
    t = result.usage.totals()
    assert t is not None and (t.calls, t.output, t.cache_read, result.cost_usd) == (2, 12, 200, 0.004)
    env = seen["env"]
    assert config(seen)["provider"] == {"anthropic": {"options": {"apiKey": "sk-test"}}}  # over any key in the user's config
    assert env["OPENCODE_AUTH_CONTENT"] == "{}"  # and no stored login
    assert not {"MY_KEY", "OPENCODE_API_KEY", "ANTHROPIC_API_KEY"} & set(env)
    assert env["OPENCODE_DISABLE_PROJECT_CONFIG"] == env["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"
    assert env["OPENCODE_DB"] == ":memory:"  # the session stays out of the user's database
    assert env["PWD"] == str(tmp_path.resolve())  # opencode's directory is PWD, not the process's
    assert seen["argv"][-2:] == ["--", "-hello"] and "--title=t" in seen["argv"]


def test_a_turn_that_ends_on_an_empty_message_after_writing_its_output_completes(opencode, tmp_path):
    """A model may end its turn with no text once its output file is written: the turn's end
    (`step_finish` with reason `stop`) completes the launch, and the contract check reads the
    file. A turn cut short (`length`) with no text has no result."""
    out = tmp_path / "a.json"
    result, _ = opencode(Launch(prompt="x", label="t", model="openai/m", cwd=tmp_path, env={"FAKE_OUT": str(out)}))
    assert result.stop == Stop.COMPLETED and result.ok, result.stderr_tail
    assert result.result_text == "" and json.loads(out.read_text()) == {"word": "pelican"}
    env = {"FAKE_OUT": str(out), "FAKE_REASON": "length"}
    cut, _ = opencode(Launch(prompt="x", label="t", model="openai/m", cwd=tmp_path, env=env))
    assert cut.stop == Stop.NO_OUTPUT and not cut.ok


def test_a_quota_refusal_in_the_log_ends_the_launch(opencode, tmp_path):
    launch = Launch(prompt="x", label="t", model="opencode-go/m", cwd=tmp_path, env={"FAKE_QUOTA": "1"}, limits=Limits(timeout_s=30))
    t0 = time.monotonic()
    result, _ = opencode(launch)
    assert result.stop == Stop.RATE_LIMITED and result.quota_refusal is not None
    assert result.result_text == "AI_APICallError: Go usage limit exceeded"
    assert time.monotonic() - t0 < 25  # ended by the refusal, before the 30 s timeout would end it


def test_a_launch_ends_past_its_cost_cap(opencode, tmp_path):
    result, _ = opencode(Launch(prompt="x", label="t", model="p/m", cwd=tmp_path, limits=Limits(timeout_s=30, max_budget_usd=0.003)))
    assert result.stop == Stop.BUDGET and not result.ok


def test_a_plugin_reaches_opencode_as_config(tmp_path):
    plug = tmp_path / "plug"
    (plug / "agents").mkdir(parents=True)
    (plug / "skills" / "s").mkdir(parents=True)
    (plug / "opencode").mkdir()
    (plug / "agents" / "worker.md").write_text("---\nname: worker\ntools: Read, Bash, Skill\n---\nYou work.\n")
    (plug / "opencode" / "index.js").write_text("export const X = async () => ({});\n")
    (plug / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"db": {"command": "db-mcp", "args": ["--ro"]}, "web": {"url": "https://m"}}})
    )
    launch = Launch(
        prompt="x",
        label="t",
        role="worker",
        plugin_dirs=(str(plug),),
        mcp_config=str(plug / ".mcp.json"),
        limits=Limits(max_turns=7, disallowed_tools=("Bash(git push:*)",)),
    )
    cfg = OpencodeBackend(base_env={}).config(launch)
    assert cfg["instructions"] == [str(plug / "agents" / "worker.md")]  # added to opencode's own prompt
    assert cfg["skills"] == {"paths": [str(plug / "skills")]}
    assert cfg["plugin"] == [(plug.resolve() / "opencode" / "index.js").as_uri()]
    assert cfg["mcp"] == {"db": {"type": "local", "command": ["db-mcp", "--ro"]}, "web": {"type": "remote", "url": "https://m"}}
    # opencode takes the last rule that matches: bash stays allowed but for the pattern.
    assert cfg["permission"] == {"*": "deny", "read": "allow", "bash": {"*": "allow", "git push*": "deny"}, "skill": "allow"}
    assert cfg["agent"] == {"build": {"steps": 7}}


def test_a_light_launch_runs_as_its_own_agent_with_no_tool(tmp_path):
    launch = Launch(prompt="x", label="t", tools=(), system_prompt="Answer in digits.", cwd=tmp_path)
    backend = OpencodeBackend(base_env={"XDG_CONFIG_HOME": "/home/u/.config"})
    assert f"--agent={LIGHT_AGENT}" in backend.argv(launch)
    env = backend.env(launch)
    agent = json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"][LIGHT_AGENT]
    assert agent["mode"] == "primary" and agent["permission"] == {"*": "deny"}
    # The prompt is opencode's reference to a file, which it replaces with the file's text.
    assert agent["prompt"].startswith("{file:") and agent["prompt"].endswith("}")
    prompt_file = Path(agent["prompt"][len("{file:") : -1])
    assert prompt_file.is_absolute()  # `/tmp/...` on POSIX, `C:/...` on Windows
    assert prompt_file.read_text(encoding="utf-8") == "Answer in digits."
    assert env["XDG_CONFIG_HOME"] != "/home/u/.config"  # no user config: with no tool, nothing else reads it


def test_a_resumable_launch_keeps_its_session_in_its_own_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # the session directory: under tmp_path
    backend = OpencodeBackend(base_env={})
    launch = backend.resumable(Launch(prompt="x", label="t", cwd=tmp_path))
    assert backend.env(launch)["OPENCODE_DB"] == str(launch.session_dir.resolve() / "opencode.db")
    from contraagent.backends import LaunchResult

    nxt = backend.resumed(launch, LaunchResult(label="t", session_id="ses_9"), "fix it")
    assert nxt is not None and "--session=ses_9" in backend.argv(nxt) and backend.argv(nxt)[-1] == "fix it"


def test_a_stored_login_is_the_only_one_a_launch_sees(tmp_path):
    data = tmp_path / "data"
    (data / "opencode").mkdir(parents=True)
    logins = {
        "opencode-go": {"type": "api", "key": "sk-go"},
        "github-copilot": {"type": "oauth", "refresh": "r", "access": "a", "expires": 0},
    }
    (data / "opencode" / "auth.json").write_text(json.dumps(logins))
    backend = OpencodeBackend(base_env={"XDG_DATA_HOME": str(data)})
    env = {"XDG_DATA_HOME": str(data)}
    go = backend.bind_credential(Subscription(name="go", provider="opencode-go"), "opencode-go/m", env=env)
    assert go.isolated and json.loads(go.env["OPENCODE_CONFIG_CONTENT"])["provider"]["opencode-go"]["options"]["apiKey"] == "sk-go"
    oauth = backend.bind_credential(Subscription(name="c", provider="github-copilot"), "github-copilot/m", env=env)
    assert not oauth.isolated and "OAuth" in oauth.isolation  # opencode writes a refreshed token over the whole store
    with pytest.raises(CredentialError):
        backend.bind_credential(Subscription(name="x", provider="openai"), "openai/m", env=env)
    with pytest.raises(CredentialError):
        backend.bind_credential(ApiKey(name="k", provider="anthropic", key="env:K"), "openai/m")


def test_a_gateway_is_a_provider_opencode_knows_or_an_openai_compatible_one():
    backend = OpencodeBackend(base_env={})
    env = {"T": "tok"}
    anthropic = backend.bind_credential(Gateway(base_url="https://gw/v1", token="env:T", provider="anthropic"), "anthropic/m", env=env)
    assert json.loads(anthropic.env["OPENCODE_CONFIG_CONTENT"])["provider"] == {
        "anthropic": {"options": {"baseURL": "https://gw/v1", "apiKey": "tok"}}
    }
    litellm = backend.bind_credential(Gateway(base_url="https://gw/v1", token="env:T"), "litellm/gpt-x", env=env)
    entry = json.loads(litellm.env["OPENCODE_CONFIG_CONTENT"])["provider"]["litellm"]
    assert entry["npm"] == "@ai-sdk/openai-compatible" and entry["models"] == {"gpt-x": {}} and litellm.isolated
