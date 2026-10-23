"""Credentials: which identity each task runs under, which agents can use which, and nothing leaking."""

import json
import os
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import ConfigError, Pipeline, PipelineConfig, RoutingError, agent_task
from contraagent._internal.platform import envvars
from contraagent.backends import Backend, CallFile, ClaudeBackend, Launch, LaunchResult, OmpBackend, Stop
from contraagent.config import AMBIENT, ApiKey, Limits, Subscription
from contraagent.engine import RoutingPlan
from contraagent.plugins import new_plugin
from fake_cli import write_fake_cli

CONFIG = """
[defaults]
agent = "claude"
credential = "personal"

[credentials.personal]
type = "subscription"

[credentials.zdr]
type = "api_key"
key = "env:ZDR_KEY"
traits = ["zdr"]

[tasks.analyze]
credential = "zdr"
max_turns = 3
timeout_s = 10

[tasks.research]
max_turns = 3
timeout_s = 10
"""


def config(tmp_path, text=CONFIG):
    f = tmp_path / "p.toml"
    f.write_text(text)
    return PipelineConfig.load(f)


BACKENDS = {"claude": ClaudeBackend(base_env={}), "omp": OmpBackend(base_env={})}


def test_each_kind_gets_its_credential_and_the_requirement_is_checked(tmp_path):
    plan = RoutingPlan.build(config(tmp_path), ["analyze", "research"], BACKENDS, requirements={"analyze": ["zdr"]})
    assert plan.configs["analyze"].credential == "zdr" and plan.configs["research"].credential == "personal"
    assert plan.credentials["zdr"].traits == {"zdr"} and plan.credentials["ambient"] is AMBIENT
    with pytest.raises(RoutingError, match="research hop 1/1 .*requires zdr; credential personal carries no traits"):
        RoutingPlan.build(config(tmp_path), ["analyze", "research"], BACKENDS, requirements={"research": ["zdr"]})


def test_a_failover_hop_cannot_move_a_task_onto_another_identity(tmp_path):
    text = CONFIG + '\n[[tasks.analyze.fallbacks]]\nagent = "claude"\nmodel = "m2"\ncredential = "personal"\n'
    with pytest.raises(RoutingError, match="analyze hop 2/2 claude/m2@personal: the task requires zdr"):
        RoutingPlan.build(config(tmp_path, text), ["analyze", "research"], BACKENDS, requirements={"analyze": ["zdr"]})
    # a hop that names no credential keeps the kind's own
    text = CONFIG + '\n[[tasks.analyze.fallbacks]]\nagent = "claude"\nmodel = "m2"\n'
    plan = RoutingPlan.build(config(tmp_path, text), ["analyze", "research"], BACKENDS, requirements={"analyze": ["zdr"]})
    assert [r.credential for r in plan.routers["analyze"].routes] == ["zdr", "zdr"]


def test_what_an_agent_cannot_do_is_a_config_error(tmp_path):
    on_omp = '[tasks.analyze]\ncredential = "zdr"\nagent = "omp"\nmodel = "opencode-go/glm"'
    omp_zdr = CONFIG.replace('[tasks.analyze]\ncredential = "zdr"', on_omp)
    with pytest.raises(RoutingError, match="opencode-go model; credential zdr is for anthropic"):
        RoutingPlan.build(config(tmp_path, omp_zdr), ["analyze", "research"], BACKENDS)
    og = CONFIG + '\n[credentials.og]\ntype = "api_key"\nprovider = "opencode-go"\nkey = "env:K"\ntraits = ["zdr"]\n'
    og = og.replace('[tasks.analyze]\ncredential = "zdr"', '[tasks.analyze]\ncredential = "og"\nagent = "omp"\nmodel = "opencode-go/glm"')
    with pytest.raises(RoutingError, match="omp cannot guarantee it uses only og"):  # isolation not verified
        RoutingPlan.build(config(tmp_path, og), ["analyze", "research"], BACKENDS, requirements={"analyze": ["zdr"]})
    plan = RoutingPlan.build(config(tmp_path, og), ["analyze", "research"], BACKENDS)  # fine without a requirement
    assert plan.configs["analyze"].credential == "og"
    vertex = CONFIG + '\n[credentials.v]\ntype = "vertex"\nproject = "p"\nregion = "us"\n'
    vertex = vertex.replace('[tasks.analyze]\ncredential = "zdr"', '[tasks.analyze]\ncredential = "v"\nagent = "omp"\nmodel = "x/y"')
    with pytest.raises(RoutingError, match="omp cannot use vertex"):
        RoutingPlan.build(config(tmp_path, vertex), ["analyze", "research"], BACKENDS)


def test_config_mistakes_are_named(tmp_path):
    with pytest.raises(ConfigError, match="credentials.bad"):
        config(tmp_path, '[credentials.bad]\ntype = "api_key"\nkey = "ZDR_KEY"\n').credentials()  # not env:/file:
    with pytest.raises(ConfigError, match="credentials.x"):
        config(tmp_path, '[credentials.x]\ntype = "smoke_signals"\n').credentials()
    with pytest.raises(RoutingError, match="no \\[credentials.nope\\]"):
        RoutingPlan.build(config(tmp_path, CONFIG.replace('credential = "zdr"', 'credential = "nope"')), ["analyze", "research"], BACKENDS)


FAKE_CLAUDE = r"""
import json, os, sys
if "--version" in sys.argv:
    print("2.1.296 (Claude Code)"); sys.exit(0)
dump = os.environ.get("FAKE_ENV_DUMP")
if dump:
    json.dump(dict(os.environ), open(dump, "w"))
src = os.environ.get("FAKE_SOURCE") or ("ANTHROPIC_API_KEY" if os.environ.get("ANTHROPIC_API_KEY") else "none")
print(json.dumps({"type": "system", "subtype": "init", "session_id": "s", "apiKeySource": src}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok", "session_id": "s",
                  "num_turns": 1, "usage": {"output_tokens": 1}}))
"""


@pytest.fixture
def fake_claude(tmp_path):
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "claude", FAKE_CLAUDE)
    return f"{bindir}{os.pathsep}/usr/bin:/bin"


def launch(tmp_path, credential, **env):
    return Launch(
        prompt="x",
        label="t",
        model="m",
        cwd=tmp_path,
        limits=Limits(timeout_s=30),
        credential=credential,
        env={"FAKE_ENV_DUMP": str(tmp_path / "env.json"), **env},
    )


def test_the_child_sees_only_the_chosen_credential(tmp_path, fake_claude):
    base = {
        "PATH": fake_claude,
        "ZDR_KEY": "sk-zdr",
        "ANTHROPIC_API_KEY": "sk-leftover",
        "SAKANA_API_KEY": "x",
        "CLAUDE_CONFIG_DIR": "/home/someone/.claude",
        "HOME": str(tmp_path),
    }
    out = ClaudeBackend(base_env=base).run(
        launch(tmp_path, ApiKey(name="zdr", key="env:ZDR_KEY"), EXA_API_KEY="tool-key", ANTHROPIC_API_KEY="sneaky")
    )
    assert out.ok, out.stderr_tail
    env = json.loads((tmp_path / "env.json").read_text())
    assert env["ANTHROPIC_API_KEY"] == "sk-zdr"  # neither the leftover nor launch.env wins
    assert "SAKANA_API_KEY" not in env and "ZDR_KEY" not in env  # any secret-looking variable is removed
    assert env["EXA_API_KEY"] == "tool-key"  # a tool's key comes back only when given
    assert env["CLAUDE_CONFIG_DIR"] != "/home/someone/.claude"  # isolated from the stored login


def test_a_secret_that_does_not_resolve_fails_the_launch(tmp_path, fake_claude):
    out = ClaudeBackend(base_env={"PATH": fake_claude}).run(launch(tmp_path, ApiKey(name="zdr", key="env:ZDR_KEY")))
    assert out.stop == Stop.LAUNCH_FAILED and "env:ZDR_KEY is not set" in out.stderr_tail
    assert not (tmp_path / "env.json").exists()  # nothing was launched


def test_an_agent_reporting_another_credential_fails_the_task(tmp_path, fake_claude):
    base = {"PATH": fake_claude, "ZDR_KEY": "sk-zdr"}
    out = ClaudeBackend(base_env=base).run(launch(tmp_path, ApiKey(name="zdr", key="env:ZDR_KEY"), FAKE_SOURCE="none"))
    assert out.stop == Stop.CREDENTIAL_MISMATCH and not out.ok and "apiKeySource='none'" in out.stderr_tail
    sub = ClaudeBackend(base_env={"PATH": fake_claude}).run(launch(tmp_path, Subscription(name="personal")))
    assert sub.ok and sub.api_key_source == "none"


class Out(BaseModel):
    ok: bool


class Recorder(Backend):
    name = binary = "claude"

    def __init__(self):
        super().__init__(base_env={"ZDR_KEY": "sk-very-secret"})
        self.launches = []
        self._lock = threading.Lock()

    def argv(self, launch):
        return ["x"]

    def env(self, launch):
        return {}

    def bind_credential(self, credential, model="", *, env=None, label="", cwd=None):
        return ClaudeBackend(base_env=self._base_env).bind_credential(credential, model, env=env, label=label)

    def run(self, launch):
        self.bind_credential(launch.credential, launch.model, env=self._base_env)  # resolves the secret
        with self._lock:
            self.launches.append(launch)
        call = CallFile.read(Path(launch.env[envvars.CALL]))
        Path(call.output.path).write_text('{"ok": true}')
        return LaunchResult(label=launch.label, agent="claude", stop=Stop.COMPLETED, ok=True, credential=launch.credential.label)


def test_a_pipeline_runs_each_task_under_its_credential_and_records_only_its_name(tmp_path):
    new_plugin(tmp_path / "plug")
    analyze = agent_task("analyze", plugin=tmp_path / "plug", output=Out, requires=["zdr"])
    research = agent_task("research", plugin=tmp_path / "plug", output=Out)
    agent = Recorder()
    rep = Pipeline(config(tmp_path), runs_dir=tmp_path / "runs", backends={"claude": agent}, cwd=tmp_path, log=lambda line: None).run(
        lambda: (analyze("u"), research("u")), run_id="c"
    )
    assert rep.ok
    assert {launch.label: launch.credential.label for launch in agent.launches} == {"analyze-u": "zdr", "research-u": "personal"}
    rows = {r["key"]: r for r in map(json.loads, (rep.run_dir / "journal.jsonl").read_text().splitlines())}
    assert rows["analyze-u"]["credential"] == "zdr"
    for f in rep.run_dir.rglob("*"):
        if f.is_file():
            assert "sk-very-secret" not in f.read_text(errors="replace"), f  # where it comes from, never the value


def test_ambient_is_the_host_default_and_a_chosen_credential_is_the_only_one(tmp_path, fake_claude):
    base = {"PATH": fake_claude, "ANTHROPIC_API_KEY": "sk-host", "OPENCODE_API_KEY": "oc-host", "CLAUDECODE": "1", "HOME": str(tmp_path)}
    assert ClaudeBackend(base_env=base).run(launch(tmp_path, AMBIENT)).ok
    env = json.loads((tmp_path / "env.json").read_text())
    assert env["ANTHROPIC_API_KEY"] == "sk-host" and env["OPENCODE_API_KEY"] == "oc-host"  # the host's, untouched
    assert "CLAUDECODE" not in env and "CLAUDE_CONFIG_DIR" not in env  # but never the parent session's
    assert ClaudeBackend(base_env=base).run(launch(tmp_path, Subscription(name="personal"))).ok
    env = json.loads((tmp_path / "env.json").read_text())
    assert "ANTHROPIC_API_KEY" not in env and "OPENCODE_API_KEY" not in env  # only the chosen one
