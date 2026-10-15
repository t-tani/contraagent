"""Trends: what the runs of a period add up to (`Monitor.trends`, `/api/trends`)."""

import json
import time
from datetime import date
from pathlib import Path

import pytest

from contraagent.monitor import Monitor, Panel, api, trends
from contraagent.monitor.source import DirectorySource, StaticLiveness
from contraagent.monitor.trends import Period, PeriodError

TOKYO = "Asia/Tokyo"


def row(ts, key, kind, *, ok=True, stop="completed", wall=10.0, cost=0.1, hops=None, quota=(), executor="agent", tokens=100):
    usage = {"input": tokens, "output": tokens // 10, "cache_read": 0, "cache_creation": 0, "calls": 1}
    return {
        "ts": ts,
        "key": key,
        "kind": kind,
        "executor": executor,
        "agent": "claude" if executor == "agent" else "",
        "ok": ok,
        "stop": stop,
        "wall_s": wall,
        "cost_usd": cost if executor == "agent" else None,
        "usage": usage if executor == "agent" else None,
        "hops": hops
        if hops is not None
        else ([{"agent": "claude", "model": "m-a", "cost_usd": cost, "wall_s": wall, "usage": usage}] if executor == "agent" else []),
        "quota": list(quota),
    }


def write_run(
    root: Path,
    run: str,
    rows,
    *,
    started="2026-10-01T00:00:00+00:00",
    finished="2026-10-03T00:00:00+00:00",
    group="",
    stub=False,
    launches=(),
    rests=(),
    deferred=(),
):
    d = root / run
    d.mkdir(parents=True)
    info = {"run_id": run, "run_group": group or run, "host_id": "h1", "started_at": started, "stub": stub}
    if finished:
        info["finished_at"] = finished
    (d / "run.json").write_text(json.dumps(info))
    (d / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    for name, items in (("launches.jsonl", launches), ("rests.jsonl", rests), ("deferred.jsonl", deferred)):
        if items:
            (d / name).write_text("".join(json.dumps(x) + "\n" for x in items))
    return d


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "runs"
    # 15:30 UTC on Oct 1 is 00:30 on Oct 2 in Tokyo: the day a row counts on follows the time zone.
    write_run(
        root,
        "r1",
        [
            row("2026-10-01T10:00:00+00:00", "write-a", "write", cost=0.5, wall=30),
            row("2026-10-01T15:30:00+00:00", "write-b", "write", ok=False, stop="timeout", cost=0.2, wall=60),
            row("2026-10-01T16:00:00+00:00", "write-b", "write", cost=0.3, wall=20),  # the task's second attempt
            row(
                "2026-10-02T03:00:00+00:00",
                "classify-a",
                "classify",
                cost=0.01,
                wall=2,
                quota=[{"observed_at": "2026-10-02T03:00:00+00:00", "credential": "sub", "five_hour_pct": 40, "seven_day_pct": 70}],
            ),
            row(
                "2026-10-02T04:00:00+00:00",
                "verify-a",
                "verify",
                cost=0.02,
                wall=3,
                hops=[
                    {"agent": "claude", "model": "m-a", "cost_usd": 0.005, "wall_s": 1, "usage": {"input": 10, "calls": 1}},
                    {"agent": "omp", "model": "m-b", "cost_usd": 0.015, "wall_s": 2, "usage": {"input": 30, "calls": 2}},
                ],
                quota=[{"observed_at": "2026-10-02T04:00:00+00:00", "credential": "sub", "five_hour_pct": 55, "seven_day_pct": 71}],
            ),
            row("2026-10-02T05:00:00+00:00", "python:report", "report", executor="python", wall=1),
        ],
        started="2026-10-01T09:00:00+00:00",
        launches=[
            {
                "ts": "2026-10-01T09:59:00+00:00",
                "label": "write-a",
                "denied": [{"tool": "WebFetch", "input": "{}"}, {"tool": "Bash", "input": "{}"}],
            }
        ],
        rests=[
            {
                "ts": "2026-10-02T04:00:01+00:00",
                "event": "start",
                "credential": "sub",
                "window": "five_hour",
                "pct": 55,
                "cap": 50,
                "until": "2026-10-02T09:00:00+00:00",
            }
        ],
        deferred=[
            {"ts": "2026-10-02T04:00:02+00:00", "key": "write-c", "kind": "write", "reason": "sub rests", "cause": {"cause": "rest"}}
        ],
    )
    write_run(
        root, "r2", [row("2026-10-02T12:00:00+00:00", "write-a", "write", cost=1.0)], started="2026-10-02T11:00:00+00:00", group="nightly"
    )
    write_run(root, "stubbed", [row("2026-10-02T12:00:00+00:00", "write-a", "write", cost=9.0)], stub=True)
    write_run(root, "later", [row("2026-11-20T12:00:00+00:00", "write-a", "write")], started="2026-11-20T11:00:00+00:00", finished="")
    return root


def utc(start="2026-10-01", end="2026-10-03"):
    return Period.parse(start, end, "UTC")


def test_a_period_reads_its_days_and_refuses_what_it_cannot_read():
    p = Period.parse(tz=TOKYO, today=date(2026, 10, 14))
    assert (p.start, p.end, len(p.days)) == (date(2026, 10, 1), date(2026, 10, 14), 14)
    for args, says in (
        (("2026-10-05", "2026-10-01", ""), "is after"),
        (("2025-01-01", "2026-10-01", ""), "at most 366"),
        (("2026-10-01", "2026-10-02", "Mars/Olympus"), "unknown time zone"),
        (("10/01/2026", "", ""), "not a date"),
    ):
        with pytest.raises(PeriodError, match=says):
            Period.parse(*args)


def test_attempts_count_on_their_day_in_the_period_s_time_zone(runs):
    by_utc = {d["day"]: d for d in Monitor(runs).trends(utc())["daily"]}
    by_tokyo = {d["day"]: d for d in Monitor(runs).trends(Period.parse("2026-10-01", "2026-10-03", TOKYO))["daily"]}
    assert (by_utc["2026-10-01"]["attempts"], by_utc["2026-10-02"]["attempts"]) == (3, 4)
    # 15:30 and 16:00 UTC on Oct 1 are Oct 2 in Tokyo.
    assert (by_tokyo["2026-10-01"]["attempts"], by_tokyo["2026-10-02"]["attempts"]) == (1, 6)
    assert by_utc["2026-10-01"]["cost_usd"] == {"write": 1.0}


def test_kinds_count_tasks_by_their_last_attempt_and_groups_join_kinds(runs):
    groups = [{"id": "judge", "label": "Judging", "kinds": ["classify", "verify"]}]
    v = Monitor(runs, groups=groups).trends(utc())
    kinds = {k["kind"]: k for k in v["kinds"]}
    w = kinds["write"]
    assert (w["tasks"], w["tasks_ok"], w["attempts"], w["ok"]) == (3, 3, 4, 3)  # write-b failed, then passed; r2 is another run
    assert w["wall_s"] == 120 and w["wall_s_median"] == 25 and w["cost_usd"] == 2.0
    assert kinds["classify"]["group"] == kinds["verify"]["group"] == "Judging"
    assert v["daily"][1]["cost_usd"] == {"Judging": 0.03, "write": 1.0}
    assert kinds["report"]["executor"] == "python" and kinds["report"]["cost_usd"] is None
    assert v["totals"]["runs"] == 2 and v["totals"]["attempts"] == 7 and v["totals"]["cost_usd"] == 2.03


def test_a_partial_result_is_counted_apart_from_passed_and_failed(tmp_path):
    root = tmp_path / "runs"
    write_run(
        root,
        "r1",
        [
            row("2026-10-01T10:00:00+00:00", "python:lookup-a", "lookup", executor="python", stop="partial"),
            row("2026-10-01T10:01:00+00:00", "python:lookup-b", "lookup", executor="python"),
            row("2026-10-01T10:02:00+00:00", "python:lookup-c", "lookup", executor="python", ok=False, stop="error"),
        ],
    )
    v = Monitor(root).trends(utc())
    [k] = v["kinds"]
    assert (k["tasks"], k["tasks_ok"], k["tasks_partial"], k["attempts"], k["ok"], k["partial"]) == (3, 1, 1, 3, 1, 1)
    assert (v["totals"]["ok"], v["totals"]["partial"]) == (1, 1) and (v["daily"][0]["ok"], v["daily"][0]["partial"]) == (1, 1)
    assert (v["runs"][0]["ok"], v["runs"][0]["partial"]) == (1, 1)
    api.Trends.model_validate(v)
    body = trends.bodies(v)
    [failures] = [b for b in body["failures"]["blocks"] if b["type"] == "table"]
    assert [r["stop"] for r in failures["rows"]] == ["error"]  # a partial result is not a failure
    [kinds] = body["kinds"]["blocks"]
    assert kinds["rows"][0]["partial"] == 1 and kinds["rows"][0]["_tone"] == "failed"


def test_each_hop_counts_on_its_own_model(runs):
    models = {(m["agent"], m["model"]): m for m in Monitor(runs).trends(utc())["models"]}
    assert models[("omp", "m-b")]["cost_usd"] == 0.015 and models[("omp", "m-b")]["input"] == 30
    assert models[("claude", "m-a")]["sessions"] == 6  # r1's 4 writes and classify, verify's first hop, r2's write: python not counted
    assert round(sum(m["cost_usd"] for m in models.values()), 6) == 2.03


def test_failures_refusals_utilization_rests_deferrals_and_starts(runs):
    v = Monitor(runs).trends(Period.parse("2026-10-01", "2026-10-03", TOKYO))
    assert [(s["stop"], s["attempts"]) for s in v["stops"]] == [("completed", 6), ("timeout", 1)]
    assert {d["tool"]: d["kinds"] for d in v["denials"]} == {"Bash": {"write": 1}, "WebFetch": {"write": 1}}
    five = next(q for q in v["quota"] if q["window"] == "five_hour")
    assert five["credential"] == "sub" and five["daily_peak"] == [None, 55, None]
    # Hours from Oct 1 00:00 in Tokyo (Sep 30 15:00 UTC): 03:00 and 04:00 UTC on Oct 2 are hours 36 and 37.
    hourly = five["hourly_peak"]
    assert len(hourly) == 72 and (hourly[36], hourly[37]) == (40, 55) and sum(p is not None for p in hourly) == 2
    assert [r["credential"] for r in v["rests"]] == ["sub"] and v["rests"][0]["run"] == "r1"
    assert v["deferred_causes"] == {"rest": 1} and v["deferred"][0]["key"] == "write-c"
    # r1 started 09:00 UTC = 18:00 Thursday in Tokyo; r2 11:00 UTC = 20:00 Friday.
    assert v["starts"]["weekdays"][3] == "Thu" and v["starts"]["counts"][3][18] == 1 and v["starts"]["counts"][4][20] == 1


def test_utilization_is_per_account_and_window_and_a_rest_keeps_its_reading(tmp_path):
    """A token replaced on one credential is two accounts, two lines; a model's own window
    (`seven_day_opus`) is counted beside the account's; a rest keeps the account and the
    reading a rule judged."""
    reading = {"observed_at": "2026-10-02T03:00:00+00:00", "windows": {"seven_day": {"pct": 70, "resets_at": "2026-10-07T00:00:00+00:00"}}}
    write_run(
        tmp_path,
        "r1",
        [
            row(
                "2026-10-02T03:10:00+00:00",
                "a-1",
                "a",
                quota=[
                    {"observed_at": "2026-10-02T03:00:00+00:00", "credential": "sub", "account": "old", "seven_day_pct": 70},
                    {
                        "observed_at": "2026-10-02T05:00:00+00:00",
                        "credential": "sub",
                        "account": "new",
                        "seven_day_pct": 5,
                        "windows": {"seven_day": {"pct": 5}, "seven_day_opus": {"pct": 12}},
                    },
                ],
            )
        ],
        rests=[
            {
                "ts": "2026-10-02T03:20:00+00:00",
                "event": "start",
                "credential": "sub",
                "rule": "weekly",
                "account": "old",
                "reading": reading,
            }
        ],
    )
    v = Monitor(tmp_path).trends(utc())
    lines = {(q["credential"], q["account"], q["window"]): q["daily_peak"][1] for q in v["quota"]}
    assert lines == {("sub", "old", "seven_day"): 70, ("sub", "new", "seven_day"): 5, ("sub", "new", "seven_day_opus"): 12}
    [rest] = v["rests"]
    assert rest["account"] == "old" and rest["reading"] == reading
    names = sorted(s["name"] for s in trends.bodies(v)["quota"]["blocks"][0]["series"])
    assert names == ["sub (new) seven_day_opus", "sub (new) weekly", "sub (old) weekly"]  # two accounts of one credential: named
    assert api.Trends.model_validate(v)


def test_stub_runs_count_only_when_asked_and_a_run_group_keeps_its_own(runs):
    m = Monitor(runs)
    assert {r["run"] for r in m.trends(utc())["runs"]} == {"r1", "r2"}
    assert {r["run"] for r in m.trends(utc(), stub=True)["runs"]} == {"r1", "r2", "stubbed"}
    assert [r["run"] for r in m.trends(utc(), run_group="nightly")["runs"]] == ["r2"]


def test_a_run_outside_the_period_is_not_read(runs):
    m = Monitor(runs)
    m.trends(utc())
    assert "later" not in m._digests  # started after the period: its logs were not read


def test_a_finished_run_keeps_its_digest_and_reads_it_back_while_its_logs_are_the_same(runs):
    cold = Monitor(runs).trends(utc())
    assert (runs / "r1" / "trends.json").is_file() and (runs / "r2" / "trends.json").is_file()
    again = Monitor(runs)
    assert again.trends(utc()) == cold
    # A row more: the kept digest is out of date, and made again.
    with open(runs / "r2" / "journal.jsonl", "a") as f:
        f.write(json.dumps(row("2026-10-02T13:00:00+00:00", "write-b", "write", cost=1.0)) + "\n")
    assert again.trends(utc())["totals"]["cost_usd"] == 3.03
    assert Monitor(runs, keep_digests=False).trends(utc()) == again.trends(utc())


def test_a_live_or_unfinished_run_is_not_kept_on_disk(tmp_path):
    root = tmp_path / "runs"
    write_run(root, "live", [row("2026-10-01T10:00:00+00:00", "write-a", "write")])
    write_run(root, "crashed", [row("2026-10-01T10:00:00+00:00", "write-a", "write")], finished="")
    m = Monitor(root, liveness=StaticLiveness(DirectorySource(root), live=["live"]))
    assert m.trends(utc())["totals"]["runs"] == 2
    assert not (root / "live" / "trends.json").exists() and not (root / "crashed" / "trends.json").exists()


def test_a_digest_of_another_version_is_made_again(runs):
    Monitor(runs).trends(utc())
    kept = json.loads((runs / "r2" / "trends.json").read_text())
    kept["digest"]["version"] = -1
    kept["digest"]["rows"] = []
    (runs / "r2" / "trends.json").write_text(json.dumps(kept))
    assert Monitor(runs).trends(utc())["totals"]["attempts"] == 7


def test_the_api_serves_trends_and_trend_panels(runs):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from contraagent.monitor import server

    seen = {}

    def quality(run_ids, period):
        seen["args"] = (sorted(run_ids), period.tz)
        return {"type": "tiles", "tiles": [{"id": "q", "label": "Runs", "value": str(len(run_ids))}]}

    trend = Panel(quality, title="Quality", scope="trends")
    m = Monitor(runs, panels={"quality": trend, "targets": lambda run: {"run": run.id}})
    c = TestClient(server.create_app(m), base_url="http://127.0.0.1")
    got = c.get("/api/trends", params={"from": "2026-10-01", "to": "2026-10-03", "tz": TOKYO})
    assert got.status_code == 200, got.text
    body = api.Trends.model_validate(got.json())
    assert body.period.from_ == "2026-10-01" and body.totals.attempts == 7
    assert [p.name for p in body.panels] == ["quality"]
    assert {k: [b["type"] for b in v["blocks"]] for k, v in body.bodies.items()}["overview"] == ["tiles", "columns"]
    assert c.get("/api/trends", params={"tz": "Mars/Olympus"}).status_code == 400
    assert c.get("/api/trends/panels/quality", params={"from": "2026-10-01", "to": "2026-10-03"}).json()["tiles"][0]["value"] == "2"
    assert seen["args"] == (["r1", "r2"], "UTC")
    assert c.get("/api/trends/panels/targets").status_code == 404  # a run panel
    assert [(p["name"], p["scope"]) for p in c.get("/api/info").json()["panels"]] == [("quality", "trends"), ("targets", "run")]
    assert c.get("/api/runs/r1/panels/quality").status_code == 404


def test_hundreds_of_runs_are_summed_quickly_and_read_back_without_their_logs(tmp_path, monkeypatch):
    from contraagent.monitor import trends

    root = tmp_path / "runs"
    for i in range(300):
        day = 1 + i % 14
        rows = [row(f"2026-10-{day:02d}T{h:02d}:00:00+00:00", f"k{j}-u{h}", f"k{j}", cost=0.01) for h in range(4) for j in range(5)]
        write_run(root, f"run{i:03d}", rows, started=f"2026-10-{day:02d}T00:00:00+00:00", finished=f"2026-10-{day:02d}T05:00:00+00:00")
    period = Period.parse("2026-10-01", "2026-10-14", "UTC")
    t0 = time.perf_counter()
    v = Monitor(root).trends(period)
    assert time.perf_counter() - t0 < 10
    assert v["totals"]["attempts"] == 6000 and len(v["runs"]) == 300

    def no_logs(source, run):
        raise AssertionError(f"read the logs of {run}")

    monkeypatch.setattr(trends, "digest", no_logs)
    assert Monitor(root).trends(period) == v  # a new monitor: every digest from trends.json


def same(a, b, where="") -> None:
    """`a` equals `b`, numbers to 1e-6 (sums made in another order round apart in the last digit)."""
    if isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-6), where
    elif isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), (where, a.keys(), b.keys() if isinstance(b, dict) else b)
        for k in a:
            same(a[k], b[k], f"{where}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), (where, len(a), len(b) if isinstance(b, list) else b)
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            same(x, y, f"{where}[{i}]")
    else:
        assert a == b, (where, a, b)


def many_runs(root: Path, seed: int = 7) -> None:
    """Runs over Oct 30 .. Nov 2, 2026 (New York leaves daylight saving time on Nov 1), with
    retries across slots, two models, reports with no cost, readings and refused calls."""
    import random

    rnd = random.Random(seed)
    for i in range(8):
        start = 1793318400 + i * 9 * 3600 + rnd.randrange(3600)  # 2026-10-30T00:00Z + i * 9 h
        rows, launches, t = [], [], start
        for _ in range(30):
            t += rnd.randrange(60, 2400)
            ts = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))
            kind = rnd.choice(["write", "research", "classify", "report"])
            key = f"{kind}-u{rnd.randrange(8)}"
            stop = rnd.choice(["completed"] * 5 + ["timeout", "invalid_output", "partial"])
            hops = [
                {
                    "agent": a,
                    "model": m,
                    "cost_usd": round(rnd.random() / 10, 6),
                    "wall_s": round(rnd.random() * 90, 1),
                    "usage": {"input": rnd.randrange(900), "output": rnd.randrange(90), "calls": 1},
                }
                for a, m in rnd.sample([("claude", "sonnet"), ("omp", "glm"), ("claude", "haiku")], rnd.choice([1, 1, 2]))
            ]
            quota = (
                [
                    {
                        "observed_at": ts,
                        "credential": rnd.choice(["sub", "team"]),
                        "account": rnd.choice(["", "acct-a", "acct-b"]),  # a token replaced mid-period
                        "five_hour_pct": rnd.randrange(100),
                        "seven_day_pct": rnd.randrange(100),
                        "windows": {"seven_day_opus": {"pct": rnd.randrange(100)}} if rnd.random() < 0.5 else {},
                    }
                ]
                if rnd.random() < 0.4
                else []
            )
            executor = "python" if kind == "report" else "agent"
            rows.append(
                {
                    **row(
                        ts,
                        key,
                        kind,
                        ok=stop in ("completed", "partial"),
                        stop=stop,
                        wall=round(rnd.random() * 120, 1),
                        cost=round(rnd.random() / 5, 6),
                        hops=hops,
                        quota=quota,
                        executor=executor,
                        tokens=rnd.randrange(5000),
                    )
                }
            )
            if rnd.random() < 0.2:
                launches.append({"ts": ts, "label": key, "denied": [{"tool": rnd.choice(["Bash", "WebFetch"]), "input": "{}"}]})
        fmt = "%Y-%m-%dT%H:%M:%S+00:00"
        write_run(
            root,
            f"run{i}",
            rows,
            started=time.strftime(fmt, time.gmtime(start)),
            finished=time.strftime(fmt, time.gmtime(t + 60)),
            launches=launches,
        )


@pytest.mark.parametrize(
    "start,end,tz",
    [
        ("2026-10-30", "2026-11-03", "UTC"),
        ("2026-10-30", "2026-11-03", "Asia/Kolkata"),  # +05:30
        ("2026-10-31", "2026-11-01", "Asia/Kathmandu"),  # +05:45; cuts runs at both ends
        ("2026-10-30", "2026-11-03", "America/New_York"),  # Nov 1 has 25 hours
        ("2026-11-01", "2026-11-01", "America/New_York"),
    ],
)
def test_slot_digests_sum_to_what_the_attempts_sum_to(tmp_path, start, end, tz):
    import trends_reference as reference
    from contraagent.monitor import trends

    many_runs(tmp_path)
    source = DirectorySource(tmp_path)
    groups = {"classify": "Judging", "research": "Judging"}
    got = trends.aggregate([trends.digest(source, r) for r in source.runs()], Period.parse(start, end, tz), groups)
    want = reference.aggregate([reference.digest(source, r) for r in source.runs()], reference.Period.parse(start, end, tz), groups)
    assert got["totals"]["attempts"] > 0 and any(q["hourly_peak"] for q in got["quota"])
    same(got, want)


def test_a_source_other_than_a_directory_is_summed_the_same_and_keeps_nothing_on_disk(runs, tmp_path):
    from contraagent.monitor.source import MemorySource

    records: dict[str, dict] = {}
    for run in ("r1", "r2"):
        d = runs / run
        records[run] = {"run.json": (d / "run.json").read_text()}
        for log in ("journal.jsonl", "launches.jsonl", "rests.jsonl", "deferred.jsonl"):
            if (d / log).is_file():
                records[run][log] = (d / log).read_text().splitlines()
    hub_like = Monitor(tmp_path / "nowhere", source=MemorySource(records))
    assert hub_like.trends(utc()) == Monitor(runs).trends(utc())
    assert not (tmp_path / "nowhere").exists()


@pytest.mark.perf
def test_thirty_days_of_hourly_runs_sum_within_their_budgets(tmp_path):
    """720 runs (one an hour for 30 days) of 421 attempts each, one journal hard-linked into
    every run: a cold call once, then within budget: again over the same runs (reused), over
    another period and time zone (summed again), and from the digests a new monitor reads back."""
    import os
    import random

    rnd = random.Random(3)
    base = 1789862400  # 2026-09-20T00:00Z
    journal = tmp_path / "journal.jsonl"
    rows = []
    for j in range(421):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(base + 30 * j))
        kind = rnd.choice(["writer", "researcher", "triage", "lint_fixer", "jp_reviewer", "classify"])
        reading = {"observed_at": ts, "credential": "sub", "five_hour_pct": rnd.randrange(100), "seven_day_pct": 98}
        wall, cost = round(rnd.random() * 90, 1), round(rnd.random() / 10, 6)
        rows.append(row(ts, f"{kind}-u{j}", kind, wall=wall, cost=cost, tokens=rnd.randrange(9000), quota=[reading]))
    journal.write_text("".join(json.dumps(r) + "\n" for r in rows))
    root = tmp_path / "runs"
    for i in range(720):
        d = root / f"cycle-{i:04d}"
        d.mkdir(parents=True)
        os.link(journal, d / "journal.jsonl")
        started = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(base - 30 * 86400 + 3600 * i))
        (d / "run.json").write_text(json.dumps({"run_id": d.name, "started_at": started, "finished_at": started}))
    p30 = Period.parse("2026-08-21", "2026-09-20", "Asia/Tokyo")
    p29 = Period.parse("2026-08-22", "2026-09-20", "Asia/Kolkata")

    def timed(fn):
        t0 = time.perf_counter()
        v = fn()
        return v, time.perf_counter() - t0

    m = Monitor(root)
    view, cold = timed(lambda: m.trends(p30))
    _, again = timed(lambda: m.trends(p30))
    _, other = timed(lambda: m.trends(p29))
    _, disk = timed(lambda: Monitor(root).trends(p30))
    size = len(json.dumps(view))
    print(
        f"\n  720 runs, {view['totals']['attempts']} attempts: cold {cold:.1f} s | same period {again * 1000:.0f} ms"
        f" | another period {other * 1000:.0f} ms | a new monitor from disk {disk * 1000:.0f} ms | response {size // 1024} KiB"
    )
    assert view["totals"]["attempts"] == 720 * 421 and len(view["runs"]) == 720
    assert again < 0.3 and other < 0.3 and disk < 1.5 and size < 300_000
