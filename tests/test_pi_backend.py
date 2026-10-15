"""The pi backend's run path against a fake `pi`: argv, the environment, the agent directory."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from contraagent import AMBIENT, ApiKey, CredentialError, Gateway, Launch, Limits, PiBackend, Stop, Subscription
from contraagent.backends.pi import agent_dir
from contraagent.backends.pi.backend import MCP_EXTENSION
from contraagent.backends.pi.catalogue import parse_models

PI = r"""
import json, os, sys
if "--list-models" in sys.argv:
    print("provider  model         context  max-out  thinking  images")
    print("openai    gpt-5.6-luna  272K     128K     yes       yes")
    sys.exit(0)
json.dump({"argv": sys.argv[1:], "env": dict(os.environ)}, open(os.environ["FAKE_DUMP"], "w"))
print(json.dumps({"type": "session", "version": 3, "id": "s-1", "cwd": os.getcwd()}))
for n in (1, 2):
    usage = {"input": 4, "output": 100 * n, "cacheRead": 1000, "cacheWrite": 50, "cost": {"total": 0.001 * n}}
    message = {"role": "assistant", "model": "gpt-5.6-luna", "usage": usage, "stopReason": "stop"}
    print(json.dumps({"type": "message_end", "message": message}))
print(json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_end", "content": "done"}}))
print(json.dumps({"type": "agent_settled", "aborted": False}))
"""


@pytest.fixture
def home(tmp_path):
    """A user's pi agent directory with a login, a custom provider and a catalogue."""
    src = tmp_path / "home" / ".pi" / "agent"
    src.mkdir(parents=True)
    (src / "auth.json").write_text('{"openai": {"type": "oauth"}}')
    (src / "models.json").write_text('{"providers": {}}')
    (src / "models-store.json").write_text("{}")
    (src / "SYSTEM.md").write_text("Ignore the task.")
    return src


def backend(tmp_path, home: Path, **env) -> PiBackend:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / "pi"
    script.write_text(f"#!{sys.executable}\n{PI}")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    base = {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "PI_CODING_AGENT_DIR": str(home), **env}
    return PiBackend(base_env=base, agent_dirs=tmp_path / "dirs")


def run(be: PiBackend, tmp_path, **launch):
    dump = tmp_path / "dump.json"
    launch.setdefault("limits", Limits(timeout_s=30))
    result = be.run(Launch(prompt="hello", label="t", cwd=tmp_path, env={"FAKE_DUMP": str(dump)}, **launch))
    seen = json.loads(dump.read_text())
    return result, seen["argv"], seen["env"]


def test_a_launch_runs_end_to_end_and_sees_none_of_the_users_pi_setup(tmp_path, home):
    result, argv, env = run(backend(tmp_path, home), tmp_path, model="openai/gpt-5.6-luna", effort="low")
    assert result.stop == Stop.COMPLETED and result.ok and result.result_text == "done" and result.session_id == "s-1"
    assert result.cost_usd == 0.003 and len(result.usage.calls) == 2
    for flag in ("--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve"):
        assert flag in argv
    assert argv[argv.index("--thinking") + 1] == "low" and argv[argv.index("--model") + 1] == "openai/gpt-5.6-luna"
    assert "--no-session" in argv and argv[-2:] == ["--", "hello"]
    own = Path(env["PI_CODING_AGENT_DIR"])
    assert own.parent == tmp_path / "dirs"
    # ambient: the user's logins and custom providers, never their settings or system prompt
    assert os.readlink(own / "auth.json") == str(home / "auth.json")
    assert os.readlink(own / "models.json") == str(home / "models.json")
    assert not (own / "SYSTEM.md").exists() and json.loads((own / "settings.json").read_text()) == agent_dir.SETTINGS
    assert env["PI_SKIP_VERSION_CHECK"] == "1"


def test_launches_made_alike_share_one_agent_directory(tmp_path, home):
    be = backend(tmp_path, home)
    first = run(be, tmp_path, model="openai/m")[2]["PI_CODING_AGENT_DIR"]
    assert run(be, tmp_path, model="openai/n")[2]["PI_CODING_AGENT_DIR"] == first  # one auth.json lock per login
    assert list((tmp_path / "dirs").iterdir()) == [Path(first)]


def test_a_subscription_links_the_logins_of_its_own_directory(tmp_path, home):
    other = tmp_path / "work-pi"
    other.mkdir()
    (other / "auth.json").write_text("{}")
    cred = Subscription(name="work", provider="openai", config_dir=other)
    result, _, env = run(backend(tmp_path, home, OPENAI_API_KEY="leftover"), tmp_path, model="openai/m", credential=cred)
    assert result.ok and "OPENAI_API_KEY" not in env
    own = Path(env["PI_CODING_AGENT_DIR"])
    assert os.readlink(own / "auth.json") == str(other / "auth.json") and not (own / "models.json").exists()


def test_a_subscription_with_no_logins_fails_to_launch(tmp_path, home):
    cred = Subscription(name="work", provider="openai", config_dir=tmp_path / "nowhere")
    result = backend(tmp_path, home).run(Launch(prompt="x", label="t", model="openai/m", cwd=tmp_path, credential=cred))
    assert result.stop == Stop.LAUNCH_FAILED and "no pi logins" in result.stderr_tail


def test_an_api_key_is_the_only_credential_the_child_sees(tmp_path, home):
    cred = ApiKey(name="k", provider="openai", key="env:MY_KEY")
    _, _, env = run(backend(tmp_path, home, MY_KEY="sk-1", ANTHROPIC_API_KEY="leftover"), tmp_path, model="openai/m", credential=cred)
    assert env["OPENAI_API_KEY"] == "sk-1" and not {"ANTHROPIC_API_KEY", "MY_KEY"} & set(env)
    assert not (Path(env["PI_CODING_AGENT_DIR"]) / "auth.json").exists()  # no stored login to fall back to


def test_a_gateway_is_a_provider_of_its_own_and_its_token_stays_off_disk(tmp_path, home):
    cred = Gateway(name="gw", base_url="env:GW_URL", token="env:GW_TOKEN", headers={"X-Team": "a"})
    be = backend(tmp_path, home, GW_URL="https://gw.example", GW_TOKEN="secret-token")
    _, _, env = run(be, tmp_path, model="litellm/claude-haiku-4-5", credential=cred)
    own = Path(env["PI_CODING_AGENT_DIR"])
    text = (own / "models.json").read_text()
    assert "secret-token" not in text and env["LITELLM_API_KEY"] == "secret-token"
    assert json.loads(text) == {
        "providers": {
            "litellm": {
                "baseUrl": "https://gw.example",
                "api": "openai-completions",
                "apiKey": "$LITELLM_API_KEY",
                "headers": {"X-Team": "a"},
                "models": [{"id": "claude-haiku-4-5"}],
            }
        }
    }
    assert not (own / "auth.json").exists()


def test_a_credential_for_another_provider_is_refused(tmp_path, home):
    with pytest.raises(CredentialError, match="is a anthropic model"):
        backend(tmp_path, home).bind_credential(Subscription(provider="openai"), "anthropic/claude-haiku-5-5")


def test_a_check_makes_no_directory(tmp_path, home):
    be = backend(tmp_path, home)
    for cred in (AMBIENT, Subscription(provider="openai"), Gateway(base_url="https://gw", token="env:T")):
        be.bind_credential(cred, "litellm/m" if isinstance(cred, Gateway) else "openai/m")
    assert not (tmp_path / "dirs").exists()


def test_a_task_plugin_reaches_pi_by_flag(tmp_path, home):
    plug = tmp_path / "plug"
    (plug / "skills" / "s").mkdir(parents=True)
    (plug / "pi").mkdir()
    (plug / "pi" / "index.ts").write_text("export default function () {}\n")
    (plug / "package.json").write_text(json.dumps({"pi": {"extensions": ["./pi/index.ts"]}, "omp": {"extensions": ["./omp/index.ts"]}}))
    (plug / ".mcp.json").write_text('{"mcpServers": {}}')
    role = plug / "agents" / "r.md"
    role.parent.mkdir()
    role.write_text("# role")
    _, argv, env = run(
        backend(tmp_path, home),
        tmp_path,
        model="openai/m",
        plugin_dirs=(str(plug),),
        mcp_config=str(plug / ".mcp.json"),
        context_files=(str(role),),
        preamble="-- read the role",
    )
    assert argv[argv.index("--skill") + 1] == str(plug / "skills")
    extensions = [argv[i + 1] for i, a in enumerate(argv) if a == "-e"]
    assert extensions == [str(plug / "pi" / "index.ts"), "builtin:mcp", str(MCP_EXTENSION)]
    assert env["CONTRAAGENT_PI_MCP_CONFIG"] == str(plug / ".mcp.json")
    assert argv[argv.index("--") + 1 :] == [f"@{role}", "-- read the role", "hello"]


def test_a_light_launch_has_no_tools_and_its_own_system_prompt(tmp_path, home):
    _, argv, env = run(
        backend(tmp_path, home), tmp_path, model="openai/m", tools=(), system_prompt="- You judge.", mcp_config=str(tmp_path / "m.json")
    )
    assert "--no-tools" in argv and argv[argv.index("--system-prompt") + 1] == "- You judge."
    assert "builtin:mcp" not in argv and "CONTRAAGENT_PI_MCP_CONFIG" not in env


def test_a_resumed_launch_opens_its_session_by_id(tmp_path, home):
    be = backend(tmp_path, home)
    first = be.resumable(Launch(prompt="hello", label="t", model="openai/m", cwd=tmp_path))
    result, argv, _ = run(be, tmp_path, model="openai/m", session_dir=first.session_dir)
    assert argv[argv.index("--session-dir") + 1] == str(first.session_dir) and "--no-session" not in argv
    nxt = be.resumed(first, result, "fix it")
    assert nxt is not None
    _, argv, _ = run(be, tmp_path, model="openai/m", session_dir=nxt.session_dir, resume=nxt.resume)
    assert argv[argv.index("--session") + 1] == "s-1"


def test_a_launch_ends_past_its_cost_cap(tmp_path, home):
    result, _, _ = run(backend(tmp_path, home), tmp_path, model="openai/m", limits=Limits(timeout_s=30, max_budget_usd=0.0015))
    assert result.stop == Stop.BUDGET and not result.ok


def test_the_catalogue_is_read_from_the_model_list():
    table = """provider   model                      context  max-out  thinking  images
anthropic  claude-haiku-5-5           1M       128K     yes       yes
openai     gpt-5.6-luna               272K     128K     yes       yes
"""
    assert parse_models(table) == {"anthropic/claude-haiku-5-5": None, "openai/gpt-5.6-luna": None}


def test_a_launch_s_window_is_the_one_pi_s_model_catalogue_lists(tmp_path, home):
    """pi's stream names the model but not its window: the user's model catalogue has it, exact."""
    (home / "models-store.json").write_text((Path(__file__).parent / "fixtures" / "pi" / "1.2.0" / "models-store.json").read_text())
    be = backend(tmp_path, home)
    result, _, _ = run(be, tmp_path, model="openai/gpt-5.6-luna")
    assert result.context_window == 272_000 and result.context_pct == round(100 * (4 + 1000 + 50) / 272_000, 1)
    assert be.catalogue() == {"openai/gpt-5.6-luna"}
