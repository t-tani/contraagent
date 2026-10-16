"""A task call's `credential`: every route of its kind runs that task as it, failover hops
included; it outranks the kind's table and declaration, a run-wide override outranks it;
a credential that does not exist or lacks a required trait is refused before a launch;
a resting one defers the task; it is outside the fingerprint and recorded in the plan."""

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from contraagent import Overrides, Pipeline, PipelineConfig, RoutingError, agent_task
from contraagent.backends import Stop
from contraagent.config import Route
from contraagent.engine import Router
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent, fails, rate_limited


class Note(BaseModel):
    text: str


note = agent_task("note", instructions="n", output=Note, max_turns=1, timeout_s=10)
needs_zdr = agent_task("private", instructions="n", output=Note, requires=["zdr"], max_turns=1, timeout_s=10)

CONFIG = """
[tasks.note]
agent = "claude"
model = "m1"
credential = "team"

[[tasks.note.fallbacks]]
agent = "omp"
model = "m2"
credential = "other"

[tasks.private]
credential = "team"

[credentials.team]
type = "subscription"
traits = ["zdr"]

[credentials.company]
type = "subscription"
traits = ["zdr"]
max_five_hour_pct = 90

[credentials.other]
type = "subscription"
traits = ["zdr"]

[credentials.personal]
type = "subscription"
"""


def config(tmp_path, text=CONFIG) -> PipelineConfig:
    f = tmp_path / "p.toml"
    f.write_text(text)
    return PipelineConfig.load(f)


def written(launch):
    return {"text": launch.unit}


def pipeline(tmp_path, agent, **options) -> Pipeline:
    return Pipeline(config(tmp_path), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **options)


def lines(report, name: str) -> list[dict]:
    path = report.run_dir / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def journal(report) -> dict[str, dict]:
    return {row["key"]: row for row in lines(report, "journal.jsonl")}


def test_every_route_of_the_kind_runs_the_task_as_its_call_s_credential(tmp_path):
    """The primary and the failover hop: a fallback never moves the task to another identity."""
    agent = StubAgent(
        {"note-b": lambda launch: fails(Stop.REFUSED, "declined") if launch.model == "m1" else written(launch), "note": written}
    )

    def flow():
        note("a")
        note("b", credential="company")

    report = pipeline(tmp_path, agent).run(flow)
    assert report.ok, report.failed
    rows = journal(report)
    assert [(h["model"], h["credential"]) for h in rows["note-b"]["hops"]] == [("m1", "company"), ("m2", "company")]
    assert rows["note-b"]["credential"] == "company"
    assert rows["note-a"]["credential"] == "team"
    assert [launch.launch.credential.label for launch in agent.launches_of("note-b")] == ["company", "company"]


def test_a_429_on_the_call_s_credential_moves_its_own_breaker_not_the_kind_s(tmp_path):
    """One identity's 429 says nothing of another's: the kind's tasks still start on the
    primary, the next task of the same call credential starts on the hop."""
    agent = StubAgent({"note-b": lambda launch: rate_limited() if launch.model == "m1" else written(launch), "note": written})

    def flow():
        note("b", credential="company", priority=3)
        note("c", credential="company", priority=2)
        note("a", priority=1)

    report = pipeline(tmp_path, agent, max_concurrent=1).run(flow)
    assert report.ok, report.failed
    assert [launch.model for launch in agent.launches_of("note-b")] == ["m1", "m2"]
    assert [launch.model for launch in agent.launches_of("note-c")] == ["m2"]
    assert [(launch.model, launch.launch.credential.label) for launch in agent.launches_of("note-a")] == [("m1", "team")]


def test_the_call_outranks_the_kind_s_table_and_declaration(tmp_path):
    declared = agent_task("declared", instructions="n", output=Note, credential="other", max_turns=1, timeout_s=10)
    text = CONFIG + '\n[tasks.declared]\ncredential = "team"\n'
    agent = StubAgent({"declared": written})

    def flow():
        declared("a")
        declared("b", credential="company")

    report = Pipeline(config(tmp_path, text), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(flow)
    assert report.ok, report.failed
    assert {k: r["credential"] for k, r in journal(report).items()} == {"declared-a": "team", "declared-b": "company"}


def test_a_run_wide_override_outranks_the_call_and_says_so(tmp_path, caplog):
    agent = StubAgent({"note": written})
    with caplog.at_level(logging.WARNING, logger="contraagent"):
        report = pipeline(tmp_path, agent, overrides=Overrides(credential="other")).run(lambda: note("b", credential="company"))
    assert report.ok, report.failed
    assert journal(report)["note-b"]["credential"] == "other"
    assert "credential" not in lines(report, "plan.jsonl")[0]  # the call's choice was not in effect
    assert any("note-b: runs as other, the override's credential, not company, its task call's" in r.getMessage() for r in caplog.records)


def test_an_unknown_credential_is_refused_before_anything_launches(tmp_path):
    agent = StubAgent({"note": written})

    def flow():
        note("a")
        note("b", credential="compnay")

    with pytest.raises(RoutingError, match=r"note-b: credential='compnay': no \[credentials.compnay\] \(did you mean company\?\)"):
        pipeline(tmp_path, agent).run(flow)
    assert agent.launches == []
    report = pipeline(tmp_path, agent).check(flow)
    assert not report.ok and "routing" in report.topics
    assert any(e.startswith("routing: note-b: credential='compnay': no [credentials.compnay]") for e in report.errors)


def test_a_credential_without_a_trait_the_task_requires_is_refused(tmp_path):
    agent = StubAgent({"private": written})

    def flow():
        needs_zdr("a", credential="personal")

    with pytest.raises(RoutingError, match="the task requires zdr; credential personal carries no traits"):
        pipeline(tmp_path, agent).run(flow)
    assert agent.launches == []
    [error] = pipeline(tmp_path, agent).check(flow).errors
    assert error.startswith("routing: private-a: credential='personal': hop 1/1 claude@personal: the task requires zdr")
    assert pipeline(tmp_path, agent).check(lambda: needs_zdr("a", credential="company")).ok


def test_a_hop_whose_coding_agent_cannot_use_the_call_s_credential_is_refused(tmp_path):
    """Checked on the real coding agents: Codex takes no OAuth token."""
    text = """
[tasks.note]
agent = "codex"
model = "gpt-6.1-sol"
credential = "openai-key"

[credentials.openai-key]
type = "api_key"
provider = "openai"
key = "env:OPENAI_API_KEY"

[credentials.token]
type = "oauth_token"
token = "env:CLAUDE_CODE_OAUTH_TOKEN"
"""
    report = Pipeline(config(tmp_path, text), runs_dir=tmp_path / "runs", cwd=tmp_path).check(lambda: note("a", credential="token"))
    assert [e for e in report.errors if "credential='token'" in e][0].startswith(
        "routing: note-a: credential='token': hop 1/1 codex/gpt-6.1-sol@token: "
    )


def test_a_task_call_later_in_a_generator_flow_is_refused_at_the_call(tmp_path):
    agent = StubAgent({"note": written})

    def flow():
        yield note("a")
        note("b", credential="nobody")

    report = pipeline(tmp_path, agent).run(flow)
    assert set(journal(report)) == {"note-a"}
    [error] = report.flow_errors
    assert "note-b: credential='nobody': no [credentials.nobody]" in str(error.error)


def seed(tmp_path, credential: str, five: float) -> None:
    """A recent run's journal row with a reading of `credential`: the account's windows outlast a run."""
    old = tmp_path / "runs" / "earlier"
    old.mkdir(parents=True)
    now = datetime.now(UTC)
    reading = {
        "credential": credential,
        "five_hour_pct": five,
        "five_hour_resets_at": (now + timedelta(hours=2)).isoformat(),
        "observed_at": now.isoformat(),
    }
    row = {"ts": now.isoformat(), "key": "x", "kind": "x", "stop": "completed", "ok": True, "quota": [reading]}
    (old / "journal.jsonl").write_text(json.dumps(row) + "\n")


def test_a_resting_call_credential_defers_the_task_and_the_kind_s_still_run(tmp_path):
    seed(tmp_path, "company", 93)
    agent = StubAgent({"note": written})

    def flow():
        note("a")
        note("b", credential="company")

    report = pipeline(tmp_path, agent).run(flow)
    assert report.ok and not report.failed  # deferred: not a failure
    assert [r.task.key for r in report.deferred] == ["note-b"]
    assert set(journal(report)) == {"note-a"} and not agent.launches_of("note-b")
    [deferred] = lines(report, "deferred.jsonl")
    assert deferred["key"] == "note-b" and deferred["reason"].startswith("company rests: 5-hour usage 93%, max 90%")


def test_the_call_s_credential_is_outside_the_fingerprint(tmp_path):
    """A credential is who the work is billed to, not what the work is: a resumed run that
    names another one for a call skips the task it already finished."""
    agent = StubAgent({"note": written})
    first = pipeline(tmp_path, agent).run(lambda: note("b", credential="company"), run_id="r")
    assert first.ok and len(agent.launches) == 1
    again = pipeline(tmp_path, agent).run(lambda: note("b"), run_id="r", resume=True)
    assert again.ok and len(agent.launches) == 1
    assert journal(first)["note-b"]["credential"] == "company"


def test_the_plan_and_the_monitor_record_the_call_s_credential(tmp_path):
    agent = StubAgent({"note": written})

    def flow():
        note("a")
        note("b", credential="company")

    report = pipeline(tmp_path, agent).run(flow)
    plan = {row["key"]: row for row in lines(report, "plan.jsonl")}
    assert plan["note-b"]["credential"] == "company" and "credential" not in plan["note-a"]
    nodes = {n["key"]: n for n in Monitor(tmp_path / "runs").plan(report.run_id)["nodes"]}
    assert nodes["note-b"]["credential"] == "company" and nodes["note-a"].get("credential", "") == ""


def test_the_check_s_routes_and_the_run_s_progress_name_the_call_s_credential(tmp_path):
    def flow():
        note("a")
        note("b", credential="company")
        note("c", credential="company")

    agent = StubAgent({"note": written})
    report = pipeline(tmp_path, agent).check(flow)
    assert report.ok, report
    assert report.routes["note"].endswith("; credential=company for note-b, note-c, by their task calls")
    assert "credential=company for note-b, note-c" in str(report)
    overridden = pipeline(tmp_path, agent, overrides=Overrides(credential="other")).check(flow)
    assert "by their task calls" not in overridden.routes["note"]  # the override outranks them

    progress: list[str] = []
    p = Pipeline(config(tmp_path), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=progress.append)
    assert p.run(flow).ok
    assert {"[start] note-a", "[start] note-b credential=company", "[start] note-c credential=company"} <= set(progress)


def test_a_credential_that_is_not_a_name_is_refused_at_the_task_call(tmp_path):
    agent = StubAgent({"note": written})
    for i, bad in enumerate((3, "", " team")):
        (tmp_path / str(i)).mkdir()
        with pytest.raises(TypeError, match="credential must name a"):
            pipeline(tmp_path / str(i), agent).run(lambda bad=bad: note("a", credential=bad))


def test_a_params_field_named_credential_is_refused_at_declaration():
    class Params(BaseModel):
        credential: str

    with pytest.raises(TypeError, match="params Params has a field named credential"):
        agent_task("summarize", instructions="x", params=Params, max_turns=1, timeout_s=1)


def test_a_router_on_a_credential_is_its_chain_each_route_on_it_and_no_hop_twice():
    router = Router(Route("claude", "m1", "team"), (Route("claude", "m1", "other"), Route("omp", "m2", "")))
    router.rate_limited(router.routes[0])
    own = router.on_credential("company")
    assert own.routes == (Route("claude", "m1", "company"), Route("omp", "m2", "company"))
    assert own.pick() == own.routes[0]  # a breaker of its own: closed
