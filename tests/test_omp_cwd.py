"""The directory omp runs in decides what it reads at start: `<cwd>/.omp/config.yml` (its
model chains, `OmpBackend.model_chains`) and `<cwd>/.env` (the key it bills, whether a
credential stays isolated, the providers whose models it lists). A launch is asked about in its own working directory, the
preflight and the run's checks in the run's (`Pipeline(cwd=)`), a task call that names
its own directory (`.options(cwd=)`) in that one; never in this process's."""

import json
import logging
import os
import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, RoutingError, agent_task
from contraagent._internal.backends import opencode_key
from contraagent._internal.routing.preflight import catalogue_check
from contraagent.backends import LaunchResult, OmpBackend, Stop
from contraagent.config import KindConfig, Route, Subscription
from contraagent.engine import RoutingPlan
from fake_cli import write_fake_cli

#: A fake omp that answers `config get <key> --json` from `settings.json` of the directory
#: it runs in, and records each key it was asked there. For `models --json` it lists `p/m`
#: and `anthropic/claude-x`, and `openrouter/x` too when the `.env` file there holds an
#: OpenRouter key. It fails every other command.
ANSWERS = """
import json, os, sys
if sys.argv[1:3] == ["models", "--json"]:
    keys = open(".env").read() if os.path.exists(".env") else ""
    models = [{"selector": "p/m"}, {"selector": "anthropic/claude-x"}]
    models += [{"selector": "openrouter/x"}] if "OPENROUTER_API_KEY=" in keys else []
    print(json.dumps({"models": models}))
    sys.exit(0)
if sys.argv[1:3] != ["config", "get"]:
    sys.exit(1)
key = sys.argv[3]
settings = json.load(open("settings.json")) if os.path.exists("settings.json") else {}
if key not in settings:
    print(f"Unknown setting: {key}", file=sys.stderr)
    sys.exit(1)
open("asked-here", "a").write(key + "\\n")
print(json.dumps({"key": key, "value": settings[key], "type": "record"}))
"""

GO_MODEL = "opencode-go/glm-5.3"


class Note(BaseModel):
    text: str


needs_zdr = agent_task("private", instructions="n", output=Note, requires=["zdr"], max_turns=1, timeout_s=10)

CONFIG = """
[tasks.private]
agent = "omp"
model = "anthropic/claude-x"
credential = "team"

[credentials.team]
type = "subscription"
provider = "anthropic"
traits = ["zdr"]
"""


class Probed(OmpBackend):
    """omp whose launches answer at once, each recording the directory it ran in."""

    def __init__(self, base_env):
        super().__init__(base_env=base_env, trace=False)
        self.cwds: list[Path] = []

    def run(self, launch):
        self.cwds.append(Path(launch.cwd))
        return LaunchResult(label=launch.label, agent=self.name, stop=Stop.COMPLETED, ok=True, model=launch.model)


def environment(tmp_path) -> dict[str, str]:
    """A fake omp on PATH, and a home of its own (no `~/.env` of the user's)."""
    bindir = tmp_path / "bin"
    write_fake_cli(bindir, "omp", ANSWERS)
    home = tmp_path / "home"
    home.mkdir()
    return {"PATH": f"{bindir}{os.pathsep}/usr/bin:/bin", "HOME": str(home)}


def directory(path: Path, chain: list[str] | None = None, dotenv: str = "") -> Path:
    """A directory whose omp config chains `p/m` to `chain`, and whose `.env` holds `dotenv`."""
    path.mkdir(parents=True)
    if chain is not None:
        (path / "settings.json").write_text(json.dumps({"retry.modelFallback": True, "retry.fallbackChains": {"p/m": chain}}))
    if dotenv:
        (path / ".env").write_text(dotenv)
    return path


def test_omp_s_model_chains_are_those_of_the_directory_it_is_asked_in_once_each(tmp_path, monkeypatch):
    a, b = directory(tmp_path / "a", ["p/a"]), directory(tmp_path / "b", ["p/b"])
    monkeypatch.chdir(directory(tmp_path / "here", ["p/here"]))
    backend = OmpBackend(base_env=environment(tmp_path), trace=False)
    for _ in range(2):
        assert backend.model_chains(a).describe("p/m") == "omp's config -> p/a"
        assert backend.model_chains(b).describe("p/m") == "omp's config -> p/b"
    once = ["retry.modelFallback", "retry.fallbackChains"]
    assert (a / "asked-here").read_text().split() == (b / "asked-here").read_text().split() == once
    assert not (tmp_path / "here" / "asked-here").exists()


def test_the_preflight_probes_and_describes_omp_s_chain_in_the_run_s_directory(tmp_path, monkeypatch, caplog):
    run = directory(tmp_path / "run", ["p/run"])
    monkeypatch.chdir(directory(tmp_path / "here", ["p/here"]))
    backend = Probed(environment(tmp_path))
    configs = {"k": KindConfig(agent="omp", model="p/m", max_turns=1, timeout_s=10)}
    with caplog.at_level(logging.INFO, logger="contraagent"):
        plan = RoutingPlan(PipelineConfig(), {"omp": backend}, configs=configs)
        plan._cwd = run  # as `Pipeline(cwd=)` builds it
        plan.preflight("substitute")
    assert backend.cwds == [run]
    assert any("(own model chain: omp's config -> p/run)" in r.getMessage() for r in caplog.records)
    assert not (tmp_path / "here" / "asked-here").exists()


def test_the_key_omp_bills_is_the_one_of_the_env_file_of_the_directory_it_runs_in(tmp_path, monkeypatch):
    a = directory(tmp_path / "a", dotenv="OPENCODE_API_KEY=sk-test-a\n")
    b = directory(tmp_path / "b", dotenv="OPENCODE_API_KEY=sk-test-b\n")
    monkeypatch.chdir(directory(tmp_path / "here", dotenv="OPENCODE_API_KEY=sk-test-here\n"))
    backend = OmpBackend(base_env=environment(tmp_path))
    login = Subscription(name="oc", provider="opencode-go")
    assert backend._account_in(a, login, GO_MODEL) == opencode_key.account_of_key("sk-test-a")
    assert backend._account_in(b, login, GO_MODEL) == opencode_key.account_of_key("sk-test-b")
    assert backend.account(login, GO_MODEL) == opencode_key.account_of_key("sk-test-here")  # no directory: this process's


def test_a_key_in_the_env_file_of_a_call_s_own_directory_refuses_a_task_that_requires_isolation(tmp_path):
    repo = directory(tmp_path / "repo")
    leaky = directory(repo / "leaky", dotenv="ANTHROPIC_API_KEY=sk-ant-test\n")
    env = environment(tmp_path)

    def pipeline() -> Pipeline:
        backends = {"omp": OmpBackend(base_env=env, trace=False)}
        return Pipeline(
            PipelineConfig(tomllib.loads(CONFIG)),
            runs_dir=tmp_path / "runs",
            backends=backends,
            cwd=repo,
            preflight="off",
            log=lambda line: None,
        )

    assert pipeline().check(lambda: needs_zdr("a")).ok
    [error] = pipeline().check(lambda: needs_zdr.options(cwd="leaky")("a")).errors
    assert error.startswith(f"routing: private-a: cwd={leaky.as_posix()}: hop 1/1 omp/anthropic/claude-x@team: the task requires zdr")
    assert f"ANTHROPIC_API_KEY from {leaky / '.env'}" in error
    with pytest.raises(RoutingError, match=f"private-a: cwd={leaky.as_posix()}: "):
        pipeline().run(lambda: needs_zdr.options(cwd="leaky")("a"))


ROUTED = """
[tasks.private]
agent = "omp"
model = "openrouter/x"
"""


def test_omp_s_model_list_is_the_one_of_the_directory_its_launches_run_in(tmp_path, monkeypatch):
    run = directory(tmp_path / "run", dotenv="OPENROUTER_API_KEY=sk-or-test\n")
    here = directory(tmp_path / "here")
    monkeypatch.chdir(here)
    env = environment(tmp_path)
    backend = OmpBackend(base_env=env, trace=False)
    route = Route("omp", "openrouter/x")
    assert catalogue_check(backend, route, run) == (True, "in catalogue")
    assert catalogue_check(backend, route)[0] is False  # this process's directory holds no key
    assert backend.catalogue() == {"p/m", "anthropic/claude-x"}

    def pipeline(cwd: Path) -> Pipeline:
        backends = {"omp": OmpBackend(base_env=env, trace=False)}
        config = PipelineConfig(tomllib.loads(ROUTED))
        return Pipeline(config, runs_dir=tmp_path / "runs", backends=backends, cwd=cwd, preflight="off", log=lambda line: None)

    plain = agent_task("private", instructions="n", output=Note, max_turns=1, timeout_s=10)
    assert pipeline(run).check(lambda: plain("a")).ok
    [error] = pipeline(here).check(lambda: plain("a")).errors
    assert "model 'openrouter/x' is not in the omp model list" in error
