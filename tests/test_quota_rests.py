"""Quota rests: a credential past its quota caps is not launched on; its tasks take the next
hop, or are deferred (`deferred.jsonl`) when none is left."""

import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from contraagent import (
    AgentRunner,
    Backend,
    KindConfig,
    LaunchResult,
    Pipeline,
    PipelineConfig,
    RateLimit,
    Route,
    Router,
    Stop,
    Task,
    TaskAdapter,
    TaskResult,
    agent_task,
)
from contraagent.dispatch import Deferral
from contraagent.dispatch.queue import WorkQueue
from contraagent.monitor import Monitor, api
from contraagent.routing.quota import QuotaRests
from contraagent.testing import StubAgent

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def iso(t: datetime) -> str:
    return t.isoformat()


def reading(credential="personal", five=None, week=None, *, resets=NOW + timedelta(hours=2), observed=NOW) -> RateLimit:
    return RateLimit(
        five_hour_pct=five,
        five_hour_resets_at=iso(resets) if resets else None,
        seven_day_pct=week,
        seven_day_resets_at=iso(NOW + timedelta(days=3)),
        observed_at=iso(observed),
        credential=credential,
    )


def config(tmp_path, extra="") -> PipelineConfig:
    f = tmp_path / "p.toml"
    f.write_text(
        """
[credentials.personal]
type = "subscription"
max_five_hour_pct = 90
max_seven_day_pct = 95

[credentials.sub-b]
type = "subscription"

[credentials.subs]
type = "pool"
members = ["personal", "sub-b"]
"""
        + extra
    )
    return PipelineConfig.load(f)


def rests(tmp_path, rule=None, **kw) -> QuotaRests:
    return QuotaRests(config(tmp_path).credentials(), rule, now=lambda: NOW, **kw)


# --- QuotaRests --------------------------------------------------------------


def test_a_credential_past_its_cap_rests_until_the_window_resets(tmp_path):
    r = rests(tmp_path)
    assert r.reason("personal") == ""  # no reading: no rest
    r.observe(reading(five=80))
    assert r.reason("personal") == ""
    r.observe(reading(five=92, observed=NOW + timedelta(minutes=1)))
    assert r.reason("personal") == "personal rests: 5-hour usage 92%, max 90%"
    r.observe(reading(five=10, observed=NOW - timedelta(hours=1)))  # older than the one held
    assert r.reason("personal") != ""
    r.observe(reading(week=96, observed=NOW + timedelta(minutes=2)))
    assert r.reason("personal") == "personal rests: weekly usage 96%, max 95%"
    # A reading whose window has reset says nothing about now.
    r.observe(reading(five=99, resets=NOW - timedelta(minutes=1), observed=NOW + timedelta(minutes=3)))
    assert r.reason("personal") == ""
    # Without a reset time, a reading stands for the window's length after it was taken.
    r.observe(reading(five=99, resets=None, observed=NOW - timedelta(hours=6)))
    assert r.reason("personal") == ""  # older than the reading held, and too old anyway


def test_a_credential_without_caps_or_reading_never_rests(tmp_path):
    r = rests(tmp_path)
    r.observe(reading("sub-b", five=100))
    assert r.reason("sub-b") == ""  # no cap
    assert r.reason("gateway") == ""  # unknown, no reading


def test_a_quota_rule_rests_a_credential_by_its_reading(tmp_path):
    r = rests(tmp_path, rule=lambda cred, rd: f"pace {rd.seven_day_pct:.0f}%" if (rd.seven_day_pct or 0) > 50 else None)
    r.observe(reading("sub-b", week=60))
    assert r.reason("sub-b") == "sub-b rests: pace 60%"


def test_a_pool_rests_when_every_member_does(tmp_path):
    r = rests(tmp_path, rule=None)
    r.observe(reading("personal", five=95))
    assert r.resting_members("subs") == {"personal"}
    assert r.reason("subs") == ""  # sub-b still launches
    r2 = QuotaRests(
        config(tmp_path, '\n[credentials.capped]\ntype = "pool"\nmembers = ["sub-b"]\nmax_five_hour_pct = 50\n').credentials(),
        now=lambda: NOW,
    )
    r2.observe(reading("sub-b", five=60))
    assert r2.reason("capped") == "sub-b rests: 5-hour usage 60%, max 50%"  # the pool's cap, for a member with none


def test_finishing_kinds_launch_for_the_grace_window(tmp_path):
    clock = [0.0]
    r = rests(tmp_path, finishing_kinds=("report",), grace_s=600, clock=lambda: clock[0])
    r.observe(reading(five=95))
    assert r.reason("personal", "write") != ""
    assert r.reason("personal", "report") == ""
    clock[0] = 601
    assert r.reason("personal", "report") != ""


# --- AgentRunner ---------------------------------------------------------------


class Agent(Backend):
    """Reports a 5-hour reading of `five` for every launch as `personal`."""

    name = binary = "claude"

    def __init__(self, five):
        super().__init__()
        self.five, self.seen, self._lock = five, [], threading.Lock()

    def argv(self, launch):
        return ["x"]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.seen.append(launch.credential.label)
        readings = [reading(launch.credential.label, five=self.five)] if launch.credential.label == "personal" else []
        return LaunchResult(
            label=launch.label,
            agent=self.name,
            credential=launch.credential.label,
            stop=Stop.COMPLETED,
            ok=True,
            model=launch.model,
            rate_limits=readings,
        )


def runner(tmp_path, agent, credential="personal", fallback=True):
    creds = config(tmp_path).credentials()
    cfg = {"k": KindConfig(agent="claude", model="m1", credential=credential, max_turns=1, timeout_s=10)}
    routers = {"k": Router(Route("claude", "m1", credential), (Route("claude", "m2", "sub-b"),) if fallback else ())}
    return AgentRunner(
        agent,
        cfg,
        run_dir=tmp_path,
        adapter=TaskAdapter(),
        credentials=creds,
        routers=routers,
        cwd=tmp_path,
        rests=QuotaRests(creds, now=lambda: NOW),
    )


def test_a_resting_hop_is_skipped_without_a_launch(tmp_path):
    agent = Agent(five=95)
    r = runner(tmp_path, agent)
    first = r.run(Task("k", key="t1"))
    assert first.ok and agent.seen == ["personal"]  # its own reading puts personal past the cap
    agent.seen.clear()
    second = r.run(Task("k", key="t2"))
    assert second.ok and agent.seen == ["sub-b"]
    assert [h["credential"] for h in second.hops] == ["sub-b"]  # a skipped hop is no hop
    assert second.reason == "personal rests: 5-hour usage 95%, max 90%; ran on hop 2/2 claude/m2@sub-b"
    [skipped] = second.skipped_hops
    assert (skipped["route"], skipped["model"], skipped["credential"], skipped["window"], skipped["pct"], skipped["cap"]) == (
        "hop 1/2 claude/m1@personal",
        "m1",
        "personal",
        "five_hour",
        95.0,
        90.0,
    )


def test_with_no_hop_left_the_task_is_deferred(tmp_path):
    agent = Agent(five=95)
    r = runner(tmp_path, agent, fallback=False)
    assert r.deferral(Task("k", key="t0")) is None
    assert r.run(Task("k", key="t1")).ok
    deferral = r.deferral(Task("k", key="t2"))
    assert deferral is not None and deferral.reason == "personal rests: 5-hour usage 95%, max 90%"
    assert deferral.cause["cause"] == "rest"
    [rest] = deferral.cause["rests"]
    assert rest | {"until": ""} == {
        "route": "hop 1/1 claude/m1@personal",
        "model": "m1",
        "credential": "personal",
        "window": "five_hour",
        "pct": 95.0,
        "cap": 90.0,
        "rule": "",
        "until": "",
        "account": "",
    }
    assert rest["until"] == iso(NOW + timedelta(hours=2))  # the window's reset
    res = r.run(Task("k", key="t2"))
    assert res.stop == "deferred" and not res.ok and res.reason.startswith("personal rests")
    assert res.cause is not None and res.cause["cause"] == "rest"
    assert agent.seen == ["personal"]


def test_a_pools_resting_member_is_passed_over(tmp_path):
    agent = Agent(five=95)
    r = runner(tmp_path, agent, credential="subs", fallback=False)
    assert r.run(Task("k", key="t1")).ok  # in order: personal first, which reports 95%
    agent.seen.clear()
    assert r.run(Task("k", key="t2")).ok and agent.seen == ["sub-b"]


# --- WorkQueue -------------------------------------------------------------------


class Deferring:
    """A runner that defers what `why` names, before the start or after it."""

    def __init__(self, before=(), after=()):
        self.before, self.after, self.ran = set(before), set(after), []

    def config(self, task):
        return KindConfig(agent="claude", max_turns=1, timeout_s=1)

    def deferral(self, task):
        return Deferral("rests", {"cause": "rest"}) if task.key in self.before else None

    def run(self, task):
        self.ran.append(task.key)
        if task.key in self.after:
            return TaskResult.deferred(task, Deferral("rests now", {"cause": "rest"}))
        return TaskResult(task=task, ok=True, stop="completed")


def test_the_queue_defers_what_its_runner_cannot_launch():
    events, results = [], []
    runner = Deferring(before={"a"}, after={"b"})
    q = WorkQueue(
        runner,
        on_event=lambda e, t, **f: events.append((e, t.key if t else None, f.get("reason"), f.get("cause"))),
        on_result=lambda r, n: results.append(r.task.key),
    )
    for key in ("a", "b", "c"):
        q.add(Task("k", key=key, unit=key))
    summary = q.run()
    assert runner.ran == ["b", "c"] or sorted(runner.ran) == ["b", "c"]  # a never started
    assert ("deferred", "a", "rests", {"cause": "rest"}) in events and ("deferred", "b", "rests now", {"cause": "rest"}) in events
    assert sorted(summary["deferred"]) == ["a", "b"] and results == ["c"]  # a deferral is no result


# --- Pipeline ----------------------------------------------------------------------


class Note(BaseModel):
    text: str


note = agent_task("note", instructions="n", output=Note, max_turns=1, timeout_s=10)


def flow(units):
    for u in units:
        note(u)


def seed(tmp_path, five):
    """A recent run's journal row with a reading of `personal`: the account's windows outlast a run."""
    old = tmp_path / "runs" / "earlier"
    old.mkdir(parents=True)
    row = {
        "ts": iso(NOW),
        "key": "x",
        "kind": "x",
        "stop": "completed",
        "ok": True,
        "quota": [reading(five=five).__dict__ | {"credential": "personal"}],
    }
    # A reading taken now, its window resetting in two hours from the real clock.
    row["quota"][0]["observed_at"] = datetime.now(UTC).isoformat()
    row["quota"][0]["five_hour_resets_at"] = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    (old / "journal.jsonl").write_text(json.dumps(row) + "\n")


def test_a_run_falls_over_to_the_next_hop_while_its_credential_rests(tmp_path):
    seed(tmp_path, five=93)
    cfg = config(
        tmp_path, '\n[defaults]\ncredential = "personal"\n\n[[defaults.fallbacks]]\nagent = "omp"\nmodel = "m2"\ncredential = "ambient"\n'
    )
    stub = StubAgent({"note": lambda launch: {"text": launch.unit}})
    report = Pipeline(cfg, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path).run(flow, units=["a"])
    assert report.ok
    row = json.loads((report.run_dir / "journal.jsonl").read_text().splitlines()[0])
    assert row["agent"] == "omp" and row["credential"] == "ambient" and len(row["hops"]) == 1
    assert row["reason"].startswith("personal rests: 5-hour usage 93%, max 90%; ran on hop 2/2 omp/m2")


def test_with_no_hop_left_the_run_defers_and_records_why(tmp_path):
    seed(tmp_path, five=93)
    cfg = config(tmp_path, '\n[defaults]\ncredential = "personal"\n')
    stub = StubAgent({"note": lambda launch: {"text": launch.unit}})
    report = Pipeline(cfg, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path).run(flow, units=["a", "b"])
    assert not report.ok and sorted(report.summary["deferred"]) == ["note-a", "note-b"]
    assert stub.launches == []
    assert not (report.run_dir / "journal.jsonl").exists() or (report.run_dir / "journal.jsonl").read_text() == ""
    rows = [json.loads(line) for line in (report.run_dir / "deferred.jsonl").read_text().splitlines()]
    assert {r["key"] for r in rows} == {"note-a", "note-b"}
    assert rows[0]["reason"] == "personal rests: 5-hour usage 93%, max 90%" and rows[0]["unit"] in ("a", "b")
    assert rows[0]["cause"]["cause"] == "rest" and rows[0]["cause"]["rests"][0]["pct"] == 93.0
    plan = Monitor(tmp_path / "runs").plan(report.run_id)
    nodes = {n["key"]: n for n in plan["nodes"]}
    assert nodes["note-a"]["state"] == "pending" and nodes["note-a"]["deferred"] == rows[0]["reason"]
    cause = nodes["note-a"]["deferred_cause"]
    assert cause["cause"] == "rest" and cause["rests"][0]["credential"] == "personal" and cause["rests"][0]["cap"] == 90.0
    # The run's caps, and the rest that began: what the monitor shows beside the readings.
    assert {"credential": "personal", "five_hour_pct": 90.0, "seven_day_pct": 95.0} in plan["quota_caps"]
    assert plan["quota_rule"] == ""
    [rest] = plan["rests"]
    assert rest["credential"] == "personal" and rest["window"] == "five_hour" and rest["since"] and rest["ended"] == ""
    api.Plan.model_validate(plan)


def test_the_run_records_its_rule_and_each_rest_as_it_begins_and_ends(tmp_path):
    seed(tmp_path, five=93)
    cfg = config(
        tmp_path, '\n[defaults]\ncredential = "sub-b"\n\n[[defaults.fallbacks]]\nagent = "omp"\nmodel = "m2"\ncredential = "ambient"\n'
    )
    calls = []

    def pace(credential, reading):
        """Rests sub-b for its first three checks: both tasks before they start (the queue asks), then the first to run."""
        calls.append(credential)
        return "over the pace" if credential == "sub-b" and len(calls) < 4 else None

    stub = StubAgent({"note": lambda launch: {"text": launch.unit}})
    # The stub agent reports no reading: the earlier run's is sub-b's.
    old = tmp_path / "runs" / "earlier" / "journal.jsonl"
    row = json.loads(old.read_text())
    row["quota"][0]["credential"] = "sub-b"
    old.write_text(json.dumps(row) + "\n")
    report = Pipeline(cfg, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, quota_rule=pace).run(flow, units=["a", "b"])
    assert report.ok
    info = json.loads((report.run_dir / "run.json").read_text())
    assert info["quota_rule"].endswith("pace") and info["quota_caps"]["personal"] == {"five_hour_pct": 90.0, "seven_day_pct": 95.0}
    events = [json.loads(line) for line in (report.run_dir / "rests.jsonl").read_text().splitlines()]
    assert [(e["event"], e["credential"], e["rule"]) for e in events] == [
        ("start", "sub-b", "over the pace"),
        ("end", "sub-b", "over the pace"),
    ]
    plan = Monitor(tmp_path / "runs").plan(report.run_id)
    assert plan["quota_rule"] == info["quota_rule"]
    [rest] = plan["rests"]
    assert rest["rule"] == "over the pace" and rest["since"] and rest["ended"]
    rows = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    skipped = [r for r in rows if r["skipped_hops"]]
    assert skipped and skipped[0]["skipped_hops"][0]["rule"] == "over the pace" and skipped[0]["agent"] == "omp"


def test_the_queue_records_its_own_causes(tmp_path):
    events = []

    class Never:
        def config(self, task):
            return KindConfig(agent="claude", max_turns=1, timeout_s=1)

        def run(self, task):
            return TaskResult(task=task, ok=True, stop="completed")

    q = WorkQueue(Never(), on_event=lambda e, t, **f: events.append((e, f.get("cause"))) if e == "deferred" else None)
    q.add(Task("k", key="x", after=("never-queued",)))
    q.run()
    assert events == [("deferred", {"cause": "dependency_not_queued"})]


@pytest.mark.parametrize("bad", ["0", "101", '"x"'])
def test_a_cap_is_a_percentage(tmp_path, bad):
    with pytest.raises(Exception, match="max_five_hour_pct"):
        config(tmp_path, f'\n[credentials.bad]\ntype = "subscription"\nmax_five_hour_pct = {bad}\n').credentials()
