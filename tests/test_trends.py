"""Trends: what the runs of a period add up to (`Monitor.trends`, `/api/trends`)."""

import json
import time
from datetime import date
from pathlib import Path

import pytest

from contraagent.monitor import Monitor, Panel, api
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
    assert five["credential"] == "sub" and five["daily_peak"] == [None, 55, None] and len(five["points"]) == 2
    assert [r["credential"] for r in v["rests"]] == ["sub"] and v["rests"][0]["run"] == "r1"
    assert v["deferred_causes"] == {"rest": 1} and v["deferred"][0]["key"] == "write-c"
    # r1 started 09:00 UTC = 18:00 Thursday in Tokyo; r2 11:00 UTC = 20:00 Friday.
    assert v["starts"]["weekdays"][3] == "Thu" and v["starts"]["counts"][3][18] == 1 and v["starts"]["counts"][4][20] == 1


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
    m = Monitor(runs, panels={"quality": trend, "targets": lambda run: {"run": run}})
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
    assert [p["name"] for p in c.get("/api/info").json()["panels"]] == ["targets"]  # a trend panel is no run tab
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
