"""Refused credentials: a launch refused for its credential (`auth_failed`) rests that
credential on its coding agent and model for the rest of the run, so later tasks pass the
hop over without a launch."""

import json
import threading

from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, Task, agent_task
from contraagent._internal.monitor import api
from contraagent.backends import Backend, LaunchResult, Stop
from contraagent.config import KindConfig, Route
from contraagent.engine import AgentRunner, CredentialRests, Router, TaskAdapter
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent, fails


def config(tmp_path, extra="") -> PipelineConfig:
    f = tmp_path / "p.toml"
    f.write_text(
        """
[credentials.personal]
type = "subscription"

[credentials.sub-b]
type = "subscription"

[credentials.subs]
type = "pool"
members = ["personal", "sub-b"]
"""
        + extra
    )
    return PipelineConfig.load(f)


class Agent(Backend):
    """Answers each launch by its (credential, model) from `script`, `completed` for any
    other, and records every launch."""

    name = binary = "claude"

    def __init__(self, script):
        super().__init__()
        self.script, self.seen, self._lock = script, [], threading.Lock()

    def argv(self, launch):
        return ["x"]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.seen.append((launch.credential.label, launch.model))
        stop = self.script.get((launch.credential.label, launch.model), Stop.COMPLETED)
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            credential=launch.credential.label,
            stop=stop,
            ok=stop == Stop.COMPLETED,
            model=launch.model,
            wall_s=0.1,
            cost_usd=0.01,
        )


def runner(tmp_path, agent, chain, credential="personal", events=None):
    creds = config(tmp_path).credentials()
    cfg = {"k": KindConfig(agent="claude", model=chain[0][0], credential=credential, max_turns=1, timeout_s=10)}
    routes = [Route("claude", m, c) for m, c in chain]
    routers = {"k": Router(routes[0], tuple(routes[1:]))} if len(routes) > 1 else {}
    on_change = (lambda e, rest: events.append((e, rest))) if events is not None else None
    return AgentRunner(
        agent,
        cfg,
        run_dir=tmp_path,
        adapter=TaskAdapter(),
        credentials=creds,
        routers=routers,
        cwd=tmp_path,
        rests=CredentialRests(creds, on_change=on_change),
    )


def test_a_refused_credential_rests_on_its_route_for_the_run(tmp_path):
    agent = Agent({("personal", "m1"): Stop.AUTH_FAILED})
    events = []
    r = runner(tmp_path, agent, [("m1", "personal"), ("m2", "sub-b")], events=events)
    first = r.run(Task("k", key="t1"))
    assert first.ok and agent.seen == [("personal", "m1"), ("sub-b", "m2")]
    assert [h.stop for h in first.hops] == ["auth_failed", "completed"]
    [(event, rest)] = events
    assert event == "start" and rest.to_dict() == {
        "credential": "personal",
        "stop": "auth_failed",
        "agent": "claude",
        "model": "m1",
        "window": "",
        "pct": None,
        "cap": None,
        "rule": "",
        "until": "",
        "account": "",
    }
    agent.seen.clear()
    second = r.run(Task("k", key="t2"))
    assert second.ok and agent.seen == [("sub-b", "m2")]  # the refused hop is not launched again
    assert [h.route for h in second.hops] == ["hop 2/2 claude/m2@sub-b"]
    assert second.reason == "personal rests on claude/m1: authentication failed (auth_failed); ran on hop 2/2 claude/m2@sub-b"
    [skipped] = second.skipped_hops
    assert (skipped.route, skipped.model, skipped.credential, skipped.stop, skipped.agent) == (
        "hop 1/2 claude/m1@personal",
        "m1",
        "personal",
        "auth_failed",
        "claude",
    )
    assert len(events) == 1  # it began resting once


def test_another_model_of_a_refused_credential_still_launches(tmp_path):
    """A key may be refused one model only: its other models are other routes."""
    agent = Agent({("personal", "m1"): Stop.AUTH_FAILED})
    r = runner(tmp_path, agent, [("m1", "personal"), ("m2", "personal")])
    assert r.run(Task("k", key="t1")).ok
    agent.seen.clear()
    assert r.run(Task("k", key="t2")).ok and agent.seen == [("personal", "m2")]


def test_with_every_hop_refused_the_task_fails_without_a_launch(tmp_path):
    """Nothing in the run changes a refused credential: the task fails, it is not deferred."""
    agent = Agent({("personal", "m1"): Stop.AUTH_FAILED})
    r = runner(tmp_path, agent, [("m1", "personal")])
    first = r.run(Task("k", key="t1"))
    assert first.stop == "auth_failed" and agent.seen == [("personal", "m1")]
    assert r.deferral(Task("k", key="t2")) is None
    second = r.run(Task("k", key="t2"))
    assert not second.ok and second.stop == "auth_failed" and agent.seen == [("personal", "m1")]
    assert second.reason == "personal rests on claude/m1: authentication failed (auth_failed)"
    assert [h.stop for h in second.skipped_hops] == ["auth_failed"] and second.hops == ()


def test_the_attempt_ends_on_the_stop_of_the_hop_that_ran(tmp_path):
    """A refused hop after one that ran does not stand for the attempt: the stop that ran does."""
    agent = Agent({("personal", "m1"): Stop.TIMEOUT, ("sub-b", "m2"): Stop.AUTH_FAILED})
    r = runner(tmp_path, agent, [("m1", "personal"), ("m2", "sub-b")])
    first = r.run(Task("k", key="t1"))
    assert first.stop == "timeout" and first.route == "hop 1/2 claude/m1@personal"
    assert [h.stop for h in first.hops] == ["timeout", "auth_failed"]
    assert first.reason.endswith("; auth_failed on hop 2/2 claude/m2@sub-b")
    assert first.launch_result is not None and round(first.launch_result.cost_usd or 0, 2) == 0.02  # both hops spent
    agent.seen.clear()
    second = r.run(Task("k", key="t2"))
    assert second.stop == "timeout" and agent.seen == [("personal", "m1")]
    assert [h.stop for h in second.hops] == ["timeout"] and [h.stop for h in second.skipped_hops] == ["auth_failed"]


def test_a_refused_pool_member_rests_and_the_next_member_launches_at_once(tmp_path):
    agent = Agent({("personal", "m1"): Stop.AUTH_FAILED})
    r = runner(tmp_path, agent, [("m1", "subs")], credential="subs")
    first = r.run(Task("k", key="t1"))
    assert first.ok and agent.seen == [("personal", "m1"), ("sub-b", "m1")]
    assert first.reason.startswith("pool subs: personal refused, ran on sub-b")
    agent.seen.clear()
    assert r.run(Task("k", key="t2")).ok and agent.seen == [("sub-b", "m1")]


# --- Pipeline ----------------------------------------------------------------------


class Note(BaseModel):
    text: str


note = agent_task("note", instructions="n", output=Note, max_turns=1, timeout_s=10)


def flow(units):
    for u in units:
        note(u)


def test_a_run_records_the_refused_credential_and_the_hops_passed_over(tmp_path):
    chain = '\n[[defaults.fallbacks]]\nagent = "omp"\nmodel = "m2"\ncredential = "ambient"\n'
    cfg = config(tmp_path, '\n[defaults]\nmodel = "m1"\ncredential = "personal"\n' + chain)
    stub = StubAgent({"note": lambda launch: fails(Stop.AUTH_FAILED) if launch.model == "m1" else {"text": launch.unit}})
    pipeline = Pipeline(cfg, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, preflight="off", max_concurrent=1)
    report = pipeline.run(flow, units=["a", "b"])
    assert report.ok
    assert [launch.model for launch in stub.launches] == ["m1", "m2", "m2"]  # m1 refused once, then passed over
    events = [json.loads(line) for line in (report.run_dir / "rests.jsonl").read_text().splitlines()]
    assert [(e["event"], e["credential"], e["stop"], e["model"]) for e in events] == [("start", "personal", "auth_failed", "m1")]
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    skipped = [r["skipped_hops"] for r in rows if r["skipped_hops"]]
    assert len(skipped) == 1 and skipped[0][0]["stop"] == "auth_failed" and skipped[0][0]["route"].startswith("hop 1/2")
    plan = Monitor(tmp_path / "runs").plan(report.run_id)
    [rest] = plan["rests"]
    assert rest["stop"] == "auth_failed" and rest["agent"] == "claude" and rest["model"] == "m1" and rest["ended"] == ""
    api.Plan.model_validate(plan)


def test_a_refused_task_is_not_retried(tmp_path):
    cfg = config(tmp_path, '\n[defaults]\nmodel = "m1"\ncredential = "personal"\n\n[tasks.note]\nretries = 2\n')
    stub = StubAgent({"note": lambda launch: fails(Stop.AUTH_FAILED)})
    pipeline = Pipeline(cfg, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, preflight="off", max_concurrent=1)
    report = pipeline.run(flow, units=["a", "b"])
    assert sorted(r.task.key for r in report.failed) == ["note-a", "note-b"] and not report.deferred
    assert len(stub.launches) == 1  # note-b never launched: its one route rests
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    assert sorted((r["key"], r["stop"]) for r in rows) == [("note-a", "auth_failed"), ("note-b", "auth_failed")]
