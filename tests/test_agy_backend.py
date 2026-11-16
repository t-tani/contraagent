"""The agy backend: its command line, what it gives a launch in a directory of the launch's
own, its credentials and its deny rules. A fake `agy` stands in for the real one; the shapes
it prints are agy 1.5.9's (`tests/fixtures/agy/`)."""

import json
import os
from pathlib import Path

import pytest

from contraagent import CredentialError
from contraagent._internal.backends.agy import catalogue
from contraagent._internal.backends.agy.backend import LIGHT_AGENT, agent_file, deny_rule, mcp_config
from contraagent._internal.backends.agy.hooks import STATE_ENV, command_line
from contraagent._internal.plugins import hooks
from contraagent.backends import AgyBackend, Launch, Stop, create_backend
from contraagent.config import AMBIENT, ApiKey, Limits, OAuthToken, Secret, Subscription
from contraagent.plugins import Plugin, new_plugin
from fake_cli import write_fake_cli

GOOGLE = Subscription(name="google", provider="google")
#: The settings of a launch that names no mode, and nothing else.
AUTO = {"agentMode": "auto", "permissions": {"allow": ["read_url(*)"]}}
KEY = ApiKey(name="gemini-key", provider="google", key=Secret("env:MY_GEMINI_KEY"))


def flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def flags(argv: list[str], name: str) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == name]


@pytest.fixture
def backend(tmp_path) -> AgyBackend:
    """A backend with no agy on its PATH: it builds a launch, and asks agy nothing."""
    empty = tmp_path / "no-agy"
    empty.mkdir()
    return AgyBackend(base_env={"PATH": str(empty), "HOME": str(Path.home())})


@pytest.fixture
def plugin(tmp_path):
    root = tmp_path / "plugins" / "noter"
    new_plugin(root)
    (root / "hooks" / "guard.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
    (root / "hooks.toml").write_text(
        (root / "hooks.toml").read_text(encoding="utf-8") + '\n[[hooks]]\non = "pre_tool"\ntool = "bash"\nscript = "hooks/guard.sh"\n',
        encoding="utf-8",
        newline="\n",
    )
    hooks.write(Plugin.load(root))
    return root


def test_agy_is_a_registered_coding_agent():
    assert isinstance(create_backend("agy"), AgyBackend)
    assert (AgyBackend.name, AgyBackend.binary, AgyBackend.stop_hooks_file) == ("agy", "agy", "agy/hooks.json")
    assert AgyBackend.light_launch and AgyBackend.needs_inline_role_file and not AgyBackend.cost_is_session_total
    assert AgyBackend.watched_limits == {"max_turns", "context_budget"}


def test_a_plain_launch_names_the_prompt_the_model_and_nothing_else(backend, tmp_path):
    argv = backend.argv(Launch(prompt="summarize it", label="t", model="gemini-3.8-flash", effort="high", cwd=tmp_path))
    assert argv[:-2] == ["agy", "-p", "summarize it", "--output-format", "stream-json", "--model", "gemini-3.8-flash", "--effort", "high"]
    # Its mode is the launch's own setting: in agy's other modes a headless session runs no command.
    # The sandbox of that mode gets the network, which agy gives it for the domains a rule lets it read.
    assert argv[-2] == "--settings" and json.loads(Path(argv[-1]).read_text(encoding="utf-8")) == AUTO


def test_a_long_prompt_goes_over_stdin_as_one_json_message(backend, tmp_path):
    argv = backend.argv(Launch(prompt="x" * 70_000, label="t", model="m", cwd=tmp_path))
    assert argv[:5] == ["agy", "--input-format", "stream-json", "--output-format", "stream-json"] and "-p" not in argv
    assert not any(len(a) > 1000 for a in argv)


def test_a_resume_names_the_conversation(backend, tmp_path):
    launch = backend.resumable(Launch(prompt="x", label="t", model="m", cwd=tmp_path))
    assert launch.persist_session
    prior = backend.launch_failed(launch, "")
    prior.session_id = "7db11684-2a25-4839-96bb-e8dc7dbcef6d"
    again = backend.resumed(launch, prior, "fix it")
    assert again is not None and flag(backend.argv(again), "--conversation") == prior.session_id
    assert backend.resumed(Launch(prompt="x", label="t", cwd=tmp_path), prior, "fix it") is None  # its session was not kept


@pytest.mark.parametrize(
    ("mode", "expected", "settings"),
    [
        (None, [], AUTO),
        ("default", [], {"agentMode": ""}),  # agy's own default mode: no sandbox, so no network rule
        ("plan", ["--mode", "plan"], None),
        ("acceptEdits", ["--mode", "accept-edits"], None),
        ("bypassPermissions", ["--dangerously-skip-permissions"], None),
    ],
)
def test_a_permission_mode_is_agy_s_own_flag_or_setting(backend, tmp_path, mode, expected, settings):
    argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, permission_mode=mode))
    rest = argv[argv.index("m") + 1 :]
    if settings is None:
        assert rest == expected
    else:
        assert rest[:-2] == expected and json.loads(Path(flag(argv, "--settings")).read_text(encoding="utf-8")) == settings


def test_the_run_s_out_and_the_input_roots_join_the_workspace(backend, tmp_path):
    cwd, out, root = tmp_path / "cwd", tmp_path / "run" / "out", tmp_path / "inputs"
    for d in (cwd, out, root, cwd / "inside"):
        d.mkdir(parents=True)
    argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=cwd, out_dir=out, input_roots=(root, cwd / "inside")))
    assert flags(argv, "--add-dir") == [str(out.resolve()), str(root.resolve())]


def test_the_role_s_file_the_preamble_and_added_instructions_go_into_the_prompt(backend, tmp_path):
    role = tmp_path / "worker.md"
    role.write_text("You are the worker.", encoding="utf-8")
    launch = Launch(
        prompt="do it", label="t", model="m", cwd=tmp_path, preamble="PREAMBLE", context_files=(str(role),), append_system_prompt="APPENDED"
    )
    prompt = flag(backend.argv(launch), "-p")
    assert prompt == f'APPENDED\n\nPREAMBLE\n\n<file path="{role}">\nYou are the worker.\n</file>\n\ndo it'
    resumed = flag(
        backend.argv(Launch(prompt="again", label="t", model="m", cwd=tmp_path, append_system_prompt="APPENDED", resume="abc")), "-p"
    )
    assert resumed == "again"  # the session holds the instructions already
    # A system prompt replaces agy's own only with every tool off: here it goes with the prompt.
    kept = backend.argv(Launch(prompt="do it", label="t", model="m", cwd=tmp_path, system_prompt="SYSTEM"))
    assert flag(kept, "-p") == "SYSTEM\n\ndo it" and "--agent" not in kept
    missing = backend.run(Launch(prompt="x", label="t", model="m", cwd=tmp_path, context_files=(str(tmp_path / "none.md"),)))
    assert missing.stop is Stop.LAUNCH_FAILED and "attached file" in missing.stderr_tail


def test_a_light_launch_runs_as_an_agent_whose_file_is_its_system_prompt(backend, tmp_path, plugin):
    launch = Launch(
        prompt="judge it",
        label="light",
        model="m",
        cwd=tmp_path,
        tools=(),
        system_prompt="You are a judge.",
        append_system_prompt="One line.",
        plugin_dirs=(str(plugin),),
        mcp_config=str(plugin / ".mcp.json"),
    )
    argv = backend.argv(launch)
    assert flag(argv, "--agent") == LIGHT_AGENT and flag(argv, "-p") == "judge it"
    [root] = flags(argv, "--add-dir")
    files = sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file())
    assert files == [f".agents/agents/{LIGHT_AGENT}.md"]  # no skill, no hook, no MCP server
    text = (Path(root) / ".agents" / "agents" / f"{LIGHT_AGENT}.md").read_text(encoding="utf-8")
    assert text == agent_file("You are a judge.", "One line.")
    head, body = text.split("---\n")[1:]
    assert "tools: []" in head and "inheritCustomizations: false" in head and "inheritMcp: false" in head
    assert body == "You are a judge.\n\nOne line.\n"
    assert "--settings" not in argv
    # With a schema it has the one tool that hands in the structured answer.
    assert "tools: [finish]" in agent_file("x", None, structured=True)
    schema = backend.argv(
        Launch(prompt="x", label="light", model="m", cwd=tmp_path, tools=(), system_prompt="s", json_schema={"type": "object"})
    )
    assert json.loads(Path(flag(schema, "--json-schema")).read_text(encoding="utf-8")) == {"type": "object"}
    assert "tools: [finish]" in (Path(flag(schema, "--add-dir")) / ".agents" / "agents" / f"{LIGHT_AGENT}.md").read_text(encoding="utf-8")


def test_a_plugin_reaches_a_launch_in_a_directory_of_its_own(backend, tmp_path, plugin):
    shared = tmp_path / "plugins" / "shared"
    for name in ("write-output", "glossary"):
        (shared / "skills" / name).mkdir(parents=True)
        (shared / "skills" / name / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: shared\n---\nshared {name}\n", encoding="utf-8"
        )
    (plugin / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "notes": {"command": "notes-mcp", "args": ["--db", "x"], "env": {"A": "1"}},
                    "docs": {"url": "https://example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    launch = Launch(
        prompt="x",
        label="t",
        model="m",
        cwd=tmp_path,
        plugin_dirs=(str(plugin), str(shared)),
        mcp_config=str(plugin / ".mcp.json"),
        env={"CONTRAAGENT_PYTHON": "/venv/bin/python"},
    )
    argv = backend.argv(launch)
    [root] = flags(argv, "--add-dir")
    agents = Path(root) / ".agents"
    # A copy of each skill, the task's own plugin first: agy follows no link to a skill.
    own = agents / "skills" / "write-output" / "SKILL.md"
    assert own.read_text(encoding="utf-8") == (plugin / "skills" / "write-output" / "SKILL.md").read_text(encoding="utf-8")
    assert not own.is_symlink() and not own.parent.is_symlink()
    assert (agents / "skills" / "glossary" / "SKILL.md").read_text(encoding="utf-8").endswith("shared glossary\n")
    # The plugin's hooks, each handler the bridge on the plugin's own directory.
    [(name, hook)] = json.loads((agents / "hooks.json").read_text(encoding="utf-8")).items()
    assert name == "contraagent-0-noter" and sorted(hook) == ["PreToolUse", "Stop"]
    command = command_line(["/venv/bin/python", "-m", "contraagent", "plugin", "hook", "--agent", "agy", "--root", str(plugin.resolve())])
    assert hook["Stop"] == [{"type": "command", "command": command, "timeout": 600}]
    assert hook["PreToolUse"] == [{"matcher": "*", "hooks": [{"type": "command", "command": command, "timeout": 600}]}]
    # The launch's MCP servers, each allowed: nobody answers a prompt.
    servers = json.loads((agents / "mcp_config.json").read_text(encoding="utf-8"))["mcpServers"]
    assert servers == {
        "notes": {"command": "notes-mcp", "args": ["--db", "x"], "env": {"A": "1"}},
        "docs": {"url": "https://example.com/mcp"},
    }
    assert servers == mcp_config(str(plugin / ".mcp.json"))
    assert json.loads(Path(flag(argv, "--settings")).read_text(encoding="utf-8")) == {
        "agentMode": "auto",
        "permissions": {"allow": ["read_url(*)", "mcp(notes/*)", "mcp(docs/*)"]},
    }
    # Made afresh: what an earlier launch of the label left is gone.
    (plugin / ".mcp.json").unlink()
    again = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, plugin_dirs=(str(plugin),)))
    assert not (agents / "mcp_config.json").exists() and not (agents / "skills" / "glossary").exists()
    assert json.loads(Path(flag(again, "--settings")).read_text(encoding="utf-8")) == AUTO
    # A launch with nothing to give adds no directory.
    assert "--add-dir" not in backend.argv(Launch(prompt="x", label="bare", model="m", cwd=tmp_path))


def test_a_post_tool_hook_adds_the_handler_that_hands_its_words_to_the_model(backend, tmp_path, plugin):
    (plugin / "hooks.toml").write_text(
        (plugin / "hooks.toml").read_text(encoding="utf-8") + '\n[[hooks]]\non = "post_tool"\ntool = "write"\nscript = "hooks/guard.sh"\n',
        encoding="utf-8",
        newline="\n",
    )
    hooks.write(Plugin.load(plugin))
    argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, plugin_dirs=(str(plugin),)))
    [hook] = json.loads((Path(flag(argv, "--add-dir")) / ".agents" / "hooks.json").read_text(encoding="utf-8")).values()
    assert sorted(hook) == ["PostToolUse", "PreInvocation", "PreToolUse", "Stop"]
    assert hook["PreInvocation"] == hook["Stop"]


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ("Bash", "command(*)"),
        ("Bash(git push:*)", "command(git push)"),
        ("Bash(rm -rf *)", "command(rm -rf)"),
        ("Bash(ls)", "command(ls)"),
        ("Bash(git * --force)", None),
        ("Read", "read_file(*)"),
        ("Read(secrets/**)", "read_file(secrets)"),
        ("Read(./notes/a.md)", "read_file(notes/a.md)"),
        ("Read(//etc/passwd)", "read_file(/etc/passwd)"),
        ("Read(**/*.env)", None),
        ("Write", "write_file(*)"),
        ("Edit(src/*)", "write_file(src)"),
        ("MultiEdit", "write_file(*)"),
        ("NotebookEdit(nb/**)", "write_file(nb)"),
        ("WebFetch", "read_url(*)"),
        ("WebFetch(domain:example.com)", "read_url(example.com)"),
        ("WebFetch(https://example.com/*)", None),
        ("mcp__notes__delete", "mcp(notes/delete)"),
        ("mcp__notes", "mcp(notes/*)"),
        ("WebSearch", None),
        ("Grep", None),
        ("Skill(deploy)", None),
    ],
)
def test_a_denied_tool_is_a_deny_rule_of_agy_s_permissions(rule, expected):
    assert deny_rule(rule) == expected
    problem = AgyBackend.tool_deny_problem((rule,))
    assert (problem is None) == (expected is not None)
    if problem is not None:
        assert problem.startswith(f"agy cannot hold {rule}: ") and "(contraagent docs agents, What each one does)" in problem


def test_the_task_s_denied_tools_are_the_launch_s_settings(backend, tmp_path):
    assert deny_rule("Read(~/keys)") == f"read_file({Path('~/keys').expanduser()})"
    limits = Limits(disallowed_tools=("WebFetch", "Bash(git push:*)", "Edit", "Write"))
    argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, limits=limits))
    settings = Path(flag(argv, "--settings"))
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "agentMode": "auto",  # a task that denies WebFetch gets no network in the sandbox
        "permissions": {"deny": ["read_url(*)", "command(git push)", "write_file(*)"]},
    }
    one = Limits(disallowed_tools=("WebFetch(domain:example.com)", "Bash(rm:*)"))
    argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, limits=one))
    assert json.loads(Path(flag(argv, "--settings")).read_text(encoding="utf-8"))["permissions"] == {
        "allow": ["read_url(*)"],  # every other domain: agy's deny rule holds over its allow rule
        "deny": ["read_url(example.com)", "command(rm)"],
    }
    assert AgyBackend.tool_deny_problem(limits.disallowed_tools) is None and AgyBackend.tool_deny_problem(()) is None


def test_the_credentials_agy_takes(backend, tmp_path):
    assert backend.bind_credential(AMBIENT).env == {} and not backend.bind_credential(AMBIENT).isolated
    login = backend.bind_credential(GOOGLE)
    assert login.env == {} and login.isolated
    key = backend.bind_credential(KEY)  # a check: the secret is not read
    assert list(key.env) == ["GEMINI_API_KEY"] and "secret" not in key.env["GEMINI_API_KEY"] and key.isolated
    for refused, why in [
        (Subscription(name="s", provider="google", config_dir=tmp_path), "names no config_dir or profile"),
        (Subscription(name="s"), "provider must be google"),
        (ApiKey(name="k", provider="openai", key=Secret("env:K")), "provider must be google"),
        (OAuthToken(name="o", token=Secret("env:T")), "agy cannot use oauth_token credentials"),
    ]:
        with pytest.raises(CredentialError, match=why):
            backend.bind_credential(refused)


def test_a_launch_s_environment_holds_its_credential_alone(tmp_path):
    base = {"PATH": "/bin", "HOME": str(tmp_path), "MY_GEMINI_KEY": "secret-1", "GEMINI_API_KEY": "the-host-s", "AGY_ADC_AUTH": "true"}
    base |= {"GOOGLE_GEMINI_BASE_URL": "https://elsewhere", "CLAUDECODE": "1", "KEPT": "yes"}
    backend = AgyBackend(base_env=base)
    ambient = backend.env(Launch(prompt="x", label="t", cwd=tmp_path, env={"CONTRAAGENT_CALL": "/call.json"}))
    assert ambient["GEMINI_API_KEY"] == "the-host-s" and ambient["AGY_ADC_AUTH"] == "true" and "CLAUDECODE" not in ambient
    assert ambient["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true" and ambient["CONTRAAGENT_CALL"] == "/call.json"
    assert Path(ambient[STATE_ENV]).is_dir()
    keyed = backend.env(Launch(prompt="x", label="t", cwd=tmp_path, credential=KEY))
    assert keyed["GEMINI_API_KEY"] == "secret-1" and keyed["KEPT"] == "yes"
    assert not {"MY_GEMINI_KEY", "AGY_ADC_AUTH", "GOOGLE_GEMINI_BASE_URL"} & set(keyed)
    login = backend.env(Launch(prompt="x", label="t", cwd=tmp_path, credential=GOOGLE))
    assert not {"GEMINI_API_KEY", "AGY_ADC_AUTH", "GOOGLE_GEMINI_BASE_URL"} & set(login)
    # The model provider is the launch's own setting: a key is used only with `gemini`.
    for credential, provider in ((KEY, "gemini"), (GOOGLE, "")):
        argv = backend.argv(Launch(prompt="x", label="t", model="m", cwd=tmp_path, credential=credential))
        assert json.loads(Path(flag(argv, "--settings")).read_text(encoding="utf-8")) == {**AUTO, "modelProvider": provider}
    unset = AgyBackend(base_env={"PATH": "/bin"}).run(Launch(prompt="x", label="t", cwd=tmp_path, credential=KEY))
    assert unset.stop is Stop.LAUNCH_FAILED and "secret env:MY_GEMINI_KEY is not set" in unset.stderr_tail


MODELS = (
    "Fetching available models...\n"
    "gemini-3.8-flash-high\tGemini 3.8 Flash (High)\n"
    "claude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)\n"
    "gemini-4-argon-low\tGemini 4 Argon (Low)\n"
    "gemini-pro-orchestrator-g1-pro\tOrchestrator (Argon)\n"
)
#: `agy -p /usage --output-format json`, as agy 1.5.9 printed it for two plans: a group lists
#: its models in its description, or is named after its one model (descriptions cut).
USAGE = {
    "conversation_id": "",
    "status": "SUCCESS",
    "command": {
        "name": "usage",
        "data": {
            "groups": [
                {
                    "name": "Gemini Models",
                    "description": "Models within this group: Gemini 3.8 Flash",
                    "buckets": [
                        {
                            "id": "gemini-weekly",
                            "name": "Weekly Limit Remaining",
                            "window": "weekly",
                            "remaining_fraction": 0,
                            "reset_time": "2026-11-21T13:00:22Z",
                        },
                        {
                            "id": "gemini-5h",
                            "name": "Five Hour Limit Remaining",
                            "window": "5h",
                            "remaining_fraction": 0.25,
                            "reset_time": "2026-11-15T18:00:00Z",
                        },
                    ],
                },
                {
                    "name": "Claude and GPT models",
                    "description": "Models within this group: Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B",
                    "buckets": [
                        {
                            "id": "3p-weekly",
                            "window": "weekly",
                            "remaining_fraction": 0.9756199717521667,
                            "reset_time": "2026-11-22T12:54:10Z",
                        }
                    ],
                },
                {
                    "name": "Gemini 4 Argon",
                    "description": "For paid Pro plans, Argon quota is separate.",
                    "buckets": [
                        {
                            "id": "gemini-argon-wtu-weekly",
                            "window": "weekly",
                            "remaining_fraction": 0.5,
                            "reset_time": "2026-11-23T02:36:55Z",
                        }
                    ],
                },
            ]
        },
    },
}


def test_the_catalogue_is_what_agy_models_lists_with_and_without_the_level():
    labels = catalogue.parse_models(MODELS)
    assert labels == {
        "gemini-3.8-flash-high": "Gemini 3.8 Flash (High)",
        "claude-opus-4-6-thinking": "Claude Opus 4.6 (Thinking)",
        "gemini-4-argon-low": "Gemini 4 Argon (Low)",
        "gemini-pro-orchestrator-g1-pro": "Orchestrator (Argon)",
    }
    assert catalogue.model_ids(labels) == [*labels, "gemini-3.8-flash", "gemini-4-argon"]
    assert catalogue.family("Gemini 3.8 Flash (High)") == "Gemini 3.8 Flash" and catalogue.family("GPT-OSS 120B") == "GPT-OSS 120B"
    assert catalogue.parse_models("error: authentication required\n") == {}


def test_a_usage_report_is_a_reading_of_the_model_s_group():
    report = json.dumps(USAGE)
    gemini = catalogue.usage_reading(report, "Gemini 3.8 Flash (High)", observed_at="2026-11-15T13:00:00+00:00")
    assert gemini is not None and gemini.status == "rejected" and gemini.observed_at == "2026-11-15T13:00:00+00:00"
    assert (gemini.seven_day_pct, gemini.seven_day_resets_at) == (100.0, "2026-11-21T13:00:22+00:00")
    assert (gemini.five_hour_pct, gemini.five_hour_resets_at) == (75.0, "2026-11-15T18:00:00+00:00")
    claude = catalogue.usage_reading(report, "Claude Opus 4.6 (Thinking)")
    assert claude is not None and (claude.status, claude.seven_day_pct, claude.five_hour_pct) == ("allowed", 2.4, None)
    argon = catalogue.usage_reading(report, "Gemini 4 Argon (Low)")  # a group of one model, named after it
    assert argon is not None and (argon.status, argon.seven_day_pct, argon.five_hour_pct) == ("allowed", 50.0, None)
    assert catalogue.usage_reading(report, "Orchestrator (Argon)") is None  # in no group the report names
    assert catalogue.usage_reading(report, "Gemini 9 Ultra") is None
    assert catalogue.usage_reading("not json", "Gemini 3.8 Flash") is None and catalogue.usage_reading("{}", "Gemini 3.8 Flash") is None


#: A fake agy: `models` and `/usage` as the real one prints them, and a launch that keeps
#: what it was given and plays a recorded conversation.
AGY = r"""
import json, os, sys
args = sys.argv[1:]
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.jsonl"), "a") as log:
    log.write(json.dumps(args) + "\n")
if args == ["--version"]:
    print("1.5.9"); sys.exit(0)
if args == ["models"]:
    sys.stdout.write(MODELS); sys.exit(0)
if "/usage" in args:
    print(json.dumps(USAGE)); sys.exit(0)
stdin = sys.stdin.read() if "--input-format" in args else ""
with open(os.path.join(here, "launch.json"), "w") as f:
    json.dump({"args": args, "stdin": stdin, "state": os.environ.get("STATE_ENV_NAME", "")}, f)
cid = "0d695f8b-aaed-4ace-8ef6-e9111123b53f"
if "--conversation" in args and "--lose" not in os.environ.get("FAKE", ""):
    cid = args[args.index("--conversation") + 1]
home = os.path.join(os.environ["HOME"], ".gemini", "antigravity-cli")
os.makedirs(os.path.join(home, "conversations"), exist_ok=True)
os.makedirs(os.path.join(home, "brain", cid, "logs"), exist_ok=True)
os.makedirs(os.path.join(home, "presence"), exist_ok=True)
open(os.path.join(home, "conversations", cid + ".db"), "w").close()
open(os.path.join(home, "presence", cid + ".lock"), "w").close()
def say(event, **fields): print(json.dumps({"event": event, **fields}), flush=True)
say("init", conversation_id=cid, init={"model": "gemini-3.8-flash-high", "cwd": os.getcwd(), "tools": ["run_command"]})
usage = {"input_tokens": 100, "output_tokens": 7, "thinking_tokens": 0, "cache_read_tokens": 50, "total_tokens": 107}
step = {"conversation_id": cid, "step_index": 1, "state": "DONE", "step_type": "agent_response", "text_delta": "done\n", "usage": usage}
say("step_update", step_update=step)
say("result", result={"conversation_id": cid, "status": "SUCCESS", "response": "done\n", "num_turns": 1, "usage": usage})
"""


@pytest.fixture
def fake(tmp_path):
    bindir = tmp_path / "bin"
    body = AGY.replace("MODELS", repr(MODELS)).replace("json.dumps(USAGE)", f"json.dumps({USAGE!r})").replace("STATE_ENV_NAME", STATE_ENV)
    write_fake_cli(bindir, "agy", body)
    home = tmp_path / "home"
    home.mkdir()
    backend = AgyBackend(base_env={"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(home)})
    return backend, bindir, home


def calls(bindir: Path) -> list[list[str]]:
    return [json.loads(line) for line in (bindir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_launch_is_run_read_and_leaves_no_conversation(fake, tmp_path):
    backend, bindir, home = fake
    launch = Launch(prompt="do it", label="t", model="gemini-3.8-flash-high", cwd=tmp_path, credential=GOOGLE)
    r = backend.run(launch)
    assert (r.stop, r.ok, r.result_text, r.num_turns, r.cli_version) == (Stop.COMPLETED, True, "done\n", 1, "1.5.9")
    assert r.session_id == "0d695f8b-aaed-4ace-8ef6-e9111123b53f" and r.usage.peak_context == 150 and r.credential == "google"
    # The plan's usage for the model's group is read before the launch, once for the launches of a minute.
    [reading] = r.quota
    assert (reading.status, reading.seven_day_pct, reading.five_hour_pct) == ("rejected", 100.0, 75.0)
    again = backend.run(launch)
    assert [q.seven_day_pct for q in again.quota] == [100.0]
    assert sum("/usage" in c for c in calls(bindir)) == 1 and calls(bindir).count(["models"]) == 1
    assert backend.catalogue() == {*catalogue.parse_models(MODELS), "gemini-3.8-flash", "gemini-4-argon"}
    # A session nobody resumes is removed from agy's own directory.
    data = home / ".gemini" / "antigravity-cli"
    assert [list((data / d).iterdir()) for d in ("conversations", "brain", "presence")] == [[], [], []]
    kept = backend.run(backend.resumable(launch))
    assert (data / "conversations" / f"{kept.session_id}.db").is_file() and (data / "brain" / kept.session_id).is_dir()
    backend.discard_session(launch, kept.session_id)
    assert list((data / "conversations").iterdir()) == []
    backend.discard_session(launch, "../../etc")  # not an id: nothing is joined into a path


def test_a_long_prompt_reaches_agy_as_one_json_message_on_stdin(fake, tmp_path):
    backend, bindir, _ = fake
    prompt = "p" * 70_000 + "\n日本語"
    r = backend.run(Launch(prompt=prompt, label="t", model="claude-opus-4-6-thinking", cwd=tmp_path, stream_path=tmp_path / "s.jsonl"))
    assert r.stop is Stop.COMPLETED and "-p" not in r.argv
    given = json.loads((bindir / "launch.json").read_text(encoding="utf-8"))
    assert json.loads(given["stdin"]) == {"event": "user", "message": {"content": prompt}} and given["stdin"].endswith("\n")
    assert Path(given["state"]).is_dir()
    marker = json.loads((tmp_path / "s.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert marker["type"] == "launch" and marker["prompt"] == prompt  # the transcript shows the prompt, not the message
    [reading] = r.quota  # the group of a model named without its level's label
    assert reading.seven_day_pct == 2.4


def test_an_effort_is_passed_only_with_a_model_id_that_names_no_level(fake, tmp_path):
    backend, _, _ = fake  # it lists gemini-3.8-flash-high, claude-opus-4-6-thinking, gemini-4-argon-low and the orchestrator

    def effort(model: str, level: str | None = "medium") -> list[str]:
        return flags(backend.argv(Launch(prompt="x", label="t", model=model, effort=level, cwd=tmp_path)), "--effort")

    assert effort("gemini-3.8-flash") == ["medium"] and effort("gemini-3.8-flash", "high") == ["high"]
    assert effort("gemini-3.8-flash-high") == []  # the id names its level: agy refuses another beside it
    assert effort("gemini-4-argon-xhigh") == [] and effort("gemini-3.8-flash", None) == []
    assert effort("gemini-pro-orchestrator-g1-pro") == []  # listed as it is: agy takes no effort for it
    assert effort("claude-opus-4-6-thinking") == []
    assert effort("gemini-9-ultra") == ["medium"]  # not listed: its id names no level
    assert effort("") == []  # the user's saved model decides


def test_no_usage_is_read_for_an_api_key_or_an_unlisted_model(fake, tmp_path):
    backend, bindir, _ = fake
    assert backend.usage_reading(Launch(prompt="x", label="t", model="gemini-9-ultra", cwd=tmp_path)) is None
    assert backend.usage_reading(Launch(prompt="x", label="t", model="", cwd=tmp_path)) is None
    keyed = AgyBackend(base_env={**backend._base_env, "MY_GEMINI_KEY": "k"})
    assert keyed.usage_reading(Launch(prompt="x", label="t", model="gemini-3.8-flash-high", cwd=tmp_path, credential=KEY)) is None
    assert not any("/usage" in c for c in calls(bindir))
    base = backend.usage_reading(Launch(prompt="x", label="t", model="gemini-3.8-flash", cwd=tmp_path))
    assert base is not None and base.seven_day_pct == 100.0


def test_a_resume_agy_does_not_find_ends_the_launch_and_removes_what_it_started(fake, tmp_path, monkeypatch):
    backend, _, home = fake
    backend._base_env["FAKE"] = "--lose"
    launch = backend.resumable(Launch(prompt="x", label="t", model="gemini-3.8-flash-high", cwd=tmp_path))
    r = backend.run(Launch(**{**launch.__dict__, "resume": "11111111-1111-4111-8111-111111111111"}))
    assert r.stop is Stop.ERROR and not r.ok and "did not find conversation 11111111-1111-4111-8111-111111111111" in r.stderr_tail
    assert list((home / ".gemini" / "antigravity-cli" / "conversations").iterdir()) == []
