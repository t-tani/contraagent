"""Quota rests: a credential past its quota caps is not launched on; its tasks take the next
hop, or are deferred (`deferred.jsonl`) when none is left."""

import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, Task, TaskResult, agent_task
from contraagent._internal.monitor import api
from contraagent.backends import Backend, LaunchResult, Stop
from contraagent.config import KindConfig, QuotaReading, Route
from contraagent.engine import AgentRunner, CredentialRests, Deferral, Router, TaskAdapter, WorkQueue
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def iso(t: datetime) -> str:
    return t.isoformat()


def reading(credential="personal", five=None, week=None, *, resets=NOW + timedelta(hours=2), observed=NOW) -> QuotaReading:
    return QuotaReading(
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


def rests(tmp_path, rule=None, **kw) -> CredentialRests:
    return CredentialRests(config(tmp_path).credentials(), rule, now=lambda: NOW, **kw)


# --- CredentialRests --------------------------------------------------------------


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


def test_a_rule_s_rest_records_its_reading_and_ends_when_that_reading_is_out_of_date(tmp_path):
    """Nothing launches on a resting credential, so no new reading comes: the rule's rest
    lasts until the reading it judged is out of date (its earliest reset), then the stale
    reading counts no more, and the next launch brings a fresh one."""
    clock = [NOW]
    events: list[tuple[str, dict]] = []
    r = CredentialRests(
        config(tmp_path).credentials(),
        lambda cred, rd: "pace" if (rd.seven_day_pct or 0) > 50 else None,
        now=lambda: clock[0],
        on_change=lambda event, rest: events.append((event, rest.to_dict())),
    )
    r.observe(reading("sub-b", five=10, week=60))  # 5-hour resets at NOW + 2h, weekly in 3 days
    [rest] = r.rests("sub-b")
    assert rest.rule == "pace" and rest.until == iso(NOW + timedelta(hours=2))
    assert rest.reading == {
        "observed_at": iso(NOW),
        "windows": {
            "five_hour": {"pct": 10, "resets_at": iso(NOW + timedelta(hours=2))},
            "seven_day": {"pct": 60, "resets_at": iso(NOW + timedelta(days=3))},
        },
    }
    assert events == [("start", rest.to_dict())] and events[0][1]["reading"] == rest.reading
    clock[0] = NOW + timedelta(hours=1, minutes=59)
    assert r.reason("sub-b") == "sub-b rests: pace"  # the reading still stands
    clock[0] = NOW + timedelta(hours=2, seconds=1)
    assert r.reason("sub-b") == ""  # out of date: no rest on it
    assert [e for e, _ in events] == ["start", "end"]
    r.observe(reading("sub-b", five=20, week=40, observed=clock[0], resets=clock[0] + timedelta(hours=5)))
    assert r.reason("sub-b") == ""  # the fresh reading, judged anew


def test_a_rule_s_rest_on_a_reading_with_no_reset_lasts_its_window_s_length(tmp_path):
    clock = [NOW]
    r = CredentialRests(config(tmp_path).credentials(), lambda cred, rd: "pace", now=lambda: clock[0])
    r.observe(reading("sub-b", five=10, resets=None))
    # five_hour names no reset: it stands 5 hours after it was observed; seven_day resets in 3 days.
    assert r.rests("sub-b")[0].until == iso(NOW + timedelta(hours=5))
    clock[0] = NOW + timedelta(hours=5, seconds=1)
    assert r.rests("sub-b") == []


def test_a_rule_that_gives_an_end_rests_the_credential_to_then_and_is_not_asked_before(tmp_path):
    """A daily budget rests to the next day's start, past the 5-hour window's reset: one rest,
    opened once, its end recorded, the rule not asked again while it lasts."""
    clock = [NOW]
    asked: list[datetime] = []
    events: list[tuple[str, str]] = []
    tomorrow = datetime(2026, 10, 15, 8, 0)  # no zone: UTC

    def rule(cred, rd):
        asked.append(clock[0])
        return ("over the daily pace", tomorrow) if clock[0] < tomorrow.replace(tzinfo=UTC) else None

    r = CredentialRests(
        config(tmp_path).credentials(), rule, now=lambda: clock[0], on_change=lambda e, rest: events.append((e, rest.until))
    )
    r.observe(reading("sub-b", five=10, week=20))  # the 5-hour window resets at NOW + 2h
    [rest] = r.rests("sub-b")
    assert rest.rule == "over the daily pace" and rest.until == iso(tomorrow.replace(tzinfo=UTC))
    for hours in (1, 3, 10, 19):  # past the 5-hour reset, the reading stale: still resting
        clock[0] = NOW + timedelta(hours=hours)
        assert r.reason("sub-b") == "sub-b rests: over the daily pace"
    assert asked == [NOW]  # judged once
    assert events == [("start", iso(tomorrow.replace(tzinfo=UTC)))]  # no reopening
    clock[0] = tomorrow.replace(tzinfo=UTC) + timedelta(seconds=1)
    assert r.reason("sub-b") == ""  # the end passed; the old reading is stale too
    assert [e for e, _ in events] == ["start", "end"]


def test_a_rule_that_gives_no_end_keeps_the_reading_s_end(tmp_path):
    r = CredentialRests(config(tmp_path).credentials(), lambda cred, rd: ("pace", None), now=lambda: NOW)
    r.observe(reading("sub-b", five=10))
    assert r.rests("sub-b")[0].until == iso(NOW + timedelta(hours=2))


def test_a_quota_rule_rests_a_credential_by_its_reading(tmp_path):
    r = rests(tmp_path, rule=lambda cred, rd: f"pace {rd.seven_day_pct:.0f}%" if (rd.seven_day_pct or 0) > 50 else None)
    r.observe(reading("sub-b", week=60))
    assert r.reason("sub-b") == "sub-b rests: pace 60%"


def test_two_threads_that_judge_one_account_at_once_record_its_rests_in_the_order_judged(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def rule(cred, rd):
        if (rd.seven_day_pct or 0) > 50:
            entered.set()
            assert release.wait(10)
            return "pace"
        return None

    events = []
    r = rests(tmp_path, rule=rule, on_change=lambda event, rest: events.append((event, rest.rule)))
    r.observe(reading("sub-b", week=60))
    first = threading.Thread(target=r.rests, args=("sub-b",))
    first.start()
    assert entered.wait(10)  # the first judgement is inside the rule, on the reading of 60%
    r.observe(reading("sub-b", week=10, observed=NOW + timedelta(minutes=1)))
    second = threading.Thread(target=r.rests, args=("sub-b",))
    second.start()
    second.join(0.2)  # unserialized, the second would judge 10% and finish here, before the first records its rest
    release.set()
    first.join(10)
    second.join(10)
    # The rest the first judgement found began, and the second, on the newer reading, ended it.
    assert events == [("start", "pace"), ("end", "pace")]


def test_a_pool_rests_when_every_member_does(tmp_path):
    r = rests(tmp_path, rule=None)
    r.observe(reading("personal", five=95))
    assert r.resting_members("subs") == {"personal"}
    assert r.reason("subs") == ""  # sub-b still launches
    r2 = CredentialRests(
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
            quota=readings,
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
        rests=CredentialRests(creds, now=lambda: NOW),
    )


def test_a_resting_hop_is_skipped_without_a_launch(tmp_path):
    agent = Agent(five=95)
    r = runner(tmp_path, agent)
    first = r.run(Task("k", key="t1"))
    assert first.ok and agent.seen == ["personal"]  # its own reading puts personal past the cap
    agent.seen.clear()
    second = r.run(Task("k", key="t2"))
    assert second.ok and agent.seen == ["sub-b"]
    assert [h.credential for h in second.hops] == ["sub-b"]  # a skipped hop is no hop
    assert second.reason == "personal rests: 5-hour usage 95%, max 90%; ran on hop 2/2 claude/m2@sub-b"
    [skipped] = second.skipped_hops
    assert (skipped.route, skipped.model, skipped.credential, skipped.window, skipped.pct, skipped.cap) == (
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
    assert deferral.cause.cause == "rest"
    [rest] = deferral.cause.to_dict()["rests"]
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
    assert res.cause is not None and res.cause.cause == "rest"
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
        "quota": [reading(five=five).model_dump() | {"credential": "personal"}],
    }
    # A reading taken now, its windows resetting in two hours and three days from the real clock.
    row["quota"][0]["observed_at"] = datetime.now(UTC).isoformat()
    row["quota"][0]["five_hour_resets_at"] = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    row["quota"][0]["seven_day_resets_at"] = (datetime.now(UTC) + timedelta(days=3)).isoformat()
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
    assert report.ok and not report.failed and sorted(report.summary["deferred"]) == ["note-a", "note-b"]  # deferred: no failure
    assert sorted(r.task.key for r in report.deferred) == ["note-a", "note-b"]
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
    # The run list counts them as not run: they were deferred, nothing waits for them.
    [summary] = [s for s in Monitor(tmp_path / "runs").runs() if s["run"] == report.run_id]
    assert summary["tasks"]["not_run"] == 2 and summary["tasks"]["waiting"] == 0


def test_a_queued_task_waits_only_in_a_live_run(tmp_path):
    from contraagent._internal.runs.liveness import StaticLiveness
    from contraagent.monitor import DirectorySource

    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"run_id": "r", "started_at": iso(NOW)}))
    (run / "plan.jsonl").write_text(json.dumps({"key": "note-a", "kind": "note", "unit": "a", "after": []}) + "\n")
    source = DirectorySource(tmp_path / "runs")
    live = Monitor(source=source, liveness=StaticLiveness(source, live=["r"])).runs()[0]["tasks"]
    over = Monitor(source=source, liveness=StaticLiveness(source)).runs()[0]["tasks"]
    assert (live["waiting"], live["not_run"]) == (1, 0)
    assert (over["waiting"], over["not_run"]) == (0, 1)


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

    q = WorkQueue(Never(), on_event=lambda e, t, **f: events.append((e, f["cause"].to_dict())) if e == "deferred" else None)
    q.add(Task("k", key="x", after=("never-queued",)))
    q.run()
    assert events == [("deferred", {"cause": "dependency_not_queued"})]


@pytest.mark.parametrize("bad", ["0", "101", '"x"'])
def test_a_cap_is_a_percentage(tmp_path, bad):
    with pytest.raises(Exception, match="max_five_hour_pct"):
        config(tmp_path, f'\n[credentials.bad]\ntype = "subscription"\nmax_five_hour_pct = {bad}\n').credentials()


def test_the_hosts_view_names_each_account_s_rests_in_force(tmp_path):
    from contraagent._internal.runs.liveness import StaticLiveness
    from contraagent.monitor import DirectorySource

    def run(name: str, rests: list[dict]) -> None:
        d = tmp_path / "runs" / name
        d.mkdir(parents=True)
        (d / "run.json").write_text(json.dumps({"run_id": name, "host_id": "h1", "started_at": iso(NOW)}))
        reading_row = {"observed_at": iso(NOW), "credential": "personal", "five_hour_pct": 93.0, "seven_day_pct": 40.0}
        row = {"ts": iso(NOW), "key": "k", "kind": "k", "stop": "completed", "ok": True, "quota": [reading_row]}
        (d / "journal.jsonl").write_text(json.dumps(row) + "\n")
        (d / "rests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rests))

    later = iso(datetime.now(UTC) + timedelta(hours=2))
    start = {"ts": iso(NOW), "event": "start", "credential": "personal", "window": "five_hour", "pct": 93.0, "cap": 90.0, "until": later}
    run("live", [start])
    run("ended", [start, {**start, "event": "end"}])
    run("over", [start])  # not live: its rest says nothing of now
    source = DirectorySource(tmp_path / "runs")
    hosts = Monitor(source=source, liveness=StaticLiveness(source, live=["live", "ended"])).hosts()
    api.Hosts.model_validate(hosts)
    [account] = hosts["quota"]
    assert [(r["credential"], r["window"], r["until"]) for r in account["rests"]] == [("personal", "five_hour", later)]
