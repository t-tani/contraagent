"""The preflight and its policy: substitute, stop, off; what run.json and the monitor record."""

import json
import sys

import pytest
from pydantic import BaseModel

from contraagent import (
    Backend,
    KindConfig,
    LaunchResult,
    Pipeline,
    PipelineConfig,
    PreflightStopped,
    RateLimit,
    Route,
    Router,
    RoutingError,
    RoutingPlan,
    Stop,
    agent_task,
)
from contraagent.cli import main
from contraagent.monitor.api import Plan
from contraagent.monitor.core import Monitor
from contraagent.routing.preflight import DroppedRoute, KeptKind, Substitution
from contraagent.testing import StubAgent


class Agent(Backend):
    """A coding agent whose launches end by model, from a script; it records every model launched."""

    drivable_model_chain = False

    def __init__(self, name, script):
        super().__init__()
        self.name, self.binary, self.script = name, name, script
        self.seen: list[str] = []

    def argv(self, launch):
        return [self.name]

    def env(self, launch):
        return {}

    def run(self, launch):
        self.seen.append(launch.model)
        stop = self.script(launch.model)
        rl = RateLimit(retry_after_s=300) if stop == Stop.RATE_LIMITED else None
        return LaunchResult(label=launch.label, agent=self.name, stop=stop, ok=stop == Stop.COMPLETED, model=launch.model, rate_limit=rl)


def kind(agent, model, credential="ambient"):
    return KindConfig(agent=agent, model=model, credential=credential, max_turns=3, timeout_s=10)


def dead_on(*models):
    return lambda m: Stop.RATE_LIMITED if m in models else Stop.COMPLETED


def test_a_kind_without_a_chain_stays_on_its_route_when_it_answered():
    backends = {"claude": Agent("claude", dead_on()), "omp": Agent("omp", dead_on())}
    configs = {"a": kind("omp", "first"), "b": kind("claude", "own")}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs)
    record = plan.preflight("substitute")
    assert (plan.configs["b"].agent, plan.configs["b"].model) == ("claude", "own")
    assert record.substituted == [] and record.dropped == [] and record.kept == []


def test_substitute_runs_a_kind_with_no_route_left_on_the_first_route_that_answered():
    backends = {"claude": Agent("claude", dead_on("dead", "dead-hop")), "omp": Agent("omp", dead_on())}
    configs = {"a": kind("omp", "alive"), "b": kind("claude", "dead")}
    routers = {"b": Router(Route("claude", "dead", "ambient"), (Route("claude", "dead-hop", "ambient"),))}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs, routers=routers)
    record = plan.preflight("substitute")
    assert (plan.configs["b"].agent, plan.configs["b"].model) == ("omp", "alive")
    assert "b" not in plan.routers
    assert record.policy == "substitute"
    assert record.substituted == [Substitution(kind="b", from_agent="claude", from_model="dead", to_agent="omp", to_model="alive")]
    assert record.dropped == [
        DroppedRoute(agent="claude", model="dead", credential="ambient", reason="rate limited", kinds=("b",)),
        DroppedRoute(agent="claude", model="dead-hop", credential="ambient", reason="rate limited", kinds=("b",)),
    ]
    assert json.loads(json.dumps(record.model_dump(mode="json")))["substituted"][0]["to_model"] == "alive"


def test_substitute_keeps_a_kind_when_the_route_that_answered_runs_as_another_credential():
    backends = {"claude": Agent("claude", dead_on("dead"))}
    configs = {"a": kind("claude", "alive", "team"), "b": kind("claude", "dead", "personal")}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs)
    record = plan.preflight("substitute")
    assert plan.configs["b"].model == "dead"  # left as configured
    [kept] = record.kept
    assert kept == KeptKind(kind="b", agent="claude", model="dead", reason=kept.reason)
    assert "runs as team, not personal" in kept.reason


def test_stop_names_each_kind_with_no_route_and_why_each_route_was_dropped():
    backends = {"claude": Agent("claude", dead_on("dead", "dead-hop")), "omp": Agent("omp", dead_on())}
    configs = {"a": kind("omp", "alive"), "b": kind("claude", "dead")}
    routers = {"b": Router(Route("claude", "dead", "ambient"), (Route("claude", "dead-hop", "ambient"),))}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs, routers=routers)
    with pytest.raises(PreflightStopped) as raised:
        plan.preflight("stop")
    message = str(raised.value)
    assert "1 kind(s) have no route that answered" in message
    assert "  b: claude/dead (rate limited); claude/dead-hop (rate limited)" in message
    assert raised.value.record.stopped == ["b"]
    assert plan.configs["b"].model == "dead"


def test_stop_with_every_kind_answering_trims_the_chains_and_goes_on():
    backends = {"claude": Agent("claude", dead_on("dead-hop"))}
    configs = {"b": kind("claude", "alive")}
    routers = {"b": Router(Route("claude", "alive", "ambient"), (Route("claude", "dead-hop", "ambient"),))}
    plan = RoutingPlan(PipelineConfig(), backends, configs=configs, routers=routers)
    record = plan.preflight("stop")
    assert [str(r) for r in plan.routers["b"].routes] == ["claude/alive"]
    assert record.stopped == [] and [d.model for d in record.dropped] == ["dead-hop"]


def test_off_probes_nothing():
    claude = Agent("claude", dead_on("dead"))
    plan = RoutingPlan(PipelineConfig(), {"claude": claude}, configs={"b": kind("claude", "dead")})
    record = plan.preflight("off")
    assert claude.seen == [] and record.policy == "off" and record.dropped == []


# --- in a run -----------------------------------------------------------------


class Note(BaseModel):
    text: str


write = agent_task("write", instructions="Write a note.", output=Note, max_turns=3, timeout_s=60)
check = agent_task("check", instructions="Check the note.", output=Note, max_turns=3, timeout_s=60)


def flow():
    check(note=write(unit="a"), unit="a")


class Listed(StubAgent):
    """The stub, with a model list: a model not in it is dropped by the preflight."""

    def catalogue(self):
        return {"listed"}


CONFIG = {"defaults": {"agent": "claude", "model": "listed"}, "tasks": {"check": {"model": "unlisted"}}}


def test_a_stopped_run_launches_nothing_and_records_why(tmp_path):
    stub = Listed({"write": {"text": "n"}, "check": {"text": "ok"}})
    p = Pipeline(PipelineConfig(CONFIG), runs_dir=tmp_path, stub=stub, preflight="stop", log=lambda line: None)
    with pytest.raises(PreflightStopped, match=r"check: claude/unlisted \(not in the claude model list\)"):
        p.run(flow, run_id="r")
    assert stub.launches == []
    info = json.loads((tmp_path / "r" / "run.json").read_text())
    assert info["preflight"]["policy"] == "stop" and info["preflight"]["stopped"] == ["check"]
    plan = Plan.model_validate(Monitor(tmp_path).plan("r"))
    assert plan.preflight is not None and plan.preflight.dropped[0].kinds == ("check",)


def test_a_substituted_run_records_where_each_kind_ran(tmp_path):
    stub = Listed({"write": {"text": "n"}, "check": {"text": "ok"}})
    config = PipelineConfig({**CONFIG, "defaults": {**CONFIG["defaults"], "preflight": "substitute"}})
    report = Pipeline(config, runs_dir=tmp_path, stub=stub, log=lambda line: None).run(flow, run_id="r")
    assert report.ok
    assert {launch.kind: launch.model for launch in stub.launches} == {"write": "listed", "check": "listed"}
    plan = Plan.model_validate(Monitor(tmp_path).plan("r"))
    assert plan.preflight is not None and plan.preflight.policy == "substitute"
    [moved] = plan.preflight.substituted
    assert (moved.kind, moved.from_model, moved.to_agent, moved.to_model) == ("check", "unlisted", "claude", "listed")


def test_a_run_with_the_preflight_off_records_its_policy(tmp_path):
    stub = StubAgent({"write": {"text": "n"}, "check": {"text": "ok"}})
    assert Pipeline(None, runs_dir=tmp_path, stub=stub, log=lambda line: None).run(flow, run_id="r").ok
    assert json.loads((tmp_path / "r" / "run.json").read_text())["preflight"]["policy"] == "off"


def test_a_policy_that_is_not_one_is_refused_where_it_is_written():
    with pytest.raises(ValueError, match="Pipeline: preflight = True is not one of substitute, stop, off"):
        Pipeline(None, stub=StubAgent(), preflight=True)  # type: ignore[arg-type]
    config = PipelineConfig({"defaults": {"preflight": "skip"}})
    with pytest.raises(RoutingError, match=r"\[defaults\]\.preflight = 'skip' is not one of substitute, stop, off"):
        RoutingPlan.build(config, ["write"], StubAgent().backends())


def test_the_cli_stops_a_run_and_exits_non_zero(tmp_path, capsys, monkeypatch):
    (tmp_path / "pipeline.toml").write_text('[defaults]\nmodel = "listed"\n[tasks.check]\nmodel = "unlisted"\n')
    monkeypatch.setattr(StubAgent, "catalogue", lambda self: {"listed"})
    monkeypatch.setattr(sys, "path", list(sys.path))
    args = ["run", f"{__file__}:flow", "--stub", "--config", str(tmp_path / "pipeline.toml"), "--runs-dir", str(tmp_path)]
    assert main([*args, "--preflight", "stop"]) == 1
    out = capsys.readouterr().out
    assert "no route that answered" in out and "check: claude/unlisted" in out
