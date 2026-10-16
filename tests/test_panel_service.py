"""How panels are served: a trends panel made once per period over the same runs, the runs
it reads through, checked as a run panel is, and a slow panel holding no other endpoint back."""

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from contraagent._internal.runs import layout
from contraagent.monitor import Monitor, Panel, Period, PeriodRuns, RunRecords

PERIOD = Period.parse("2026-10-13", "2026-10-15", "UTC")


def write_run(runs: Path, run: str, rows: list[dict], **logs: list[dict]) -> None:
    (runs / run).mkdir(parents=True, exist_ok=True)
    (runs / run / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (runs / run / "run.json").write_text(json.dumps({"run_id": run, "started_at": rows[0]["ts"], "finished_at": rows[-1]["ts"]}))
    for log, items in logs.items():
        (runs / run / log).write_text("".join(json.dumps(x) + "\n" for x in items))


def row(ts: str, key: str = "write-a", cost: float = 0.5) -> dict:
    return {"ts": ts, "key": key, "kind": "write", "stop": "completed", "ok": True, "cost_usd": cost, "wall_s": 3}


def test_a_trends_panel_reads_its_runs_through_period_runs(tmp_path):
    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")], **{"deferred.jsonl": [{"ts": "2026-10-14T01:00:00Z", "key": "x"}]})
    seen: dict = {}

    def view(runs: PeriodRuns, period: Period) -> dict:
        seen["runs"] = list(runs)
        seen["journal"] = runs.journal("r1")
        seen["deferred"] = runs.records("r1", layout.DEFERRED)
        seen["info"] = runs.info("r1")
        seen["dir"] = runs.dir("r1")
        return {"type": "tiles", "tiles": [{"id": "n", "label": "Runs", "value": len(runs)}]}

    mon = Monitor(tmp_path, panels={"n": Panel(view, scope="trends")})
    assert mon.trends_panel("n", PERIOD) == {"type": "tiles", "tiles": [{"id": "n", "label": "Runs", "value": 1}]}
    assert seen["runs"] == ["r1"] and seen["journal"][0]["key"] == "write-a" and seen["deferred"][0]["key"] == "x"
    assert seen["info"]["run_id"] == "r1" and seen["dir"] == (tmp_path / "r1").resolve()


def test_a_trends_panel_is_made_once_for_the_same_runs_and_again_when_they_change(tmp_path):
    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])
    calls: list[int] = []

    def view(runs: PeriodRuns, period: Period) -> dict:
        calls.append(len(runs))
        return {"calls": len(calls)}

    mon = Monitor(tmp_path, panels={"v": Panel(view, scope="trends")})
    assert mon.trends_panel("v", PERIOD) == {"calls": 1}
    assert mon.trends_panel("v", PERIOD) == {"calls": 1}  # a page asking again gets it back
    write_run(tmp_path, "r2", [row("2026-10-14T05:00:00Z", "write-b")])
    assert mon.trends_panel("v", PERIOD) == {"calls": 2}  # a new run: made again
    assert mon.trends_panel("v", Period.parse("2026-10-14", "2026-10-14", "UTC")) == {"calls": 3}  # another period


def test_requests_for_a_trends_panel_being_made_wait_for_that_one(tmp_path):
    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])
    started, release, calls = threading.Event(), threading.Event(), []

    def view(runs: PeriodRuns, period: Period) -> dict:
        calls.append(1)
        started.set()
        release.wait(5)
        return {"ok": True}

    mon = Monitor(tmp_path, panels={"v": Panel(view, scope="trends")})
    got: list[dict] = []
    threads = [threading.Thread(target=lambda: got.append(mon.trends_panel("v", PERIOD))) for _ in range(8)]
    for t in threads:
        t.start()
    assert started.wait(5)
    release.set()
    for t in threads:
        t.join(5)
    assert got == [{"ok": True}] * 8 and len(calls) == 1


def test_a_trends_panel_that_raises_is_made_again_next_time(tmp_path):
    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])
    fails = [True]

    def view(runs: PeriodRuns, period: Period) -> dict:
        if fails.pop():
            raise RuntimeError("not yet")
        return {"ok": True}

    fails.insert(0, False)
    mon = Monitor(tmp_path, panels={"v": Panel(view, scope="trends")})
    with pytest.raises(RuntimeError):
        mon.trends_panel("v", PERIOD)
    assert mon.trends_panel("v", PERIOD) == {"ok": True}


def test_panels_keep_the_order_they_are_given_in(tmp_path):
    mon = Monitor(
        tmp_path, panels={"zeta": Panel(lambda r: {}), "alpha": Panel(lambda rs, p: {}, scope="trends"), "mid": Panel(lambda r: {})}
    )
    assert [p["name"] for p in mon.panel_info()] == ["zeta", "alpha", "mid"]
    assert mon.run_panels() == ["zeta", "mid"]


def test_a_trends_panel_is_checked_as_a_run_panel_is(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.exceptions import ResponseValidationError
    from fastapi.testclient import TestClient

    from contraagent._internal.monitor import server

    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])
    panels = {
        "ok": Panel(lambda runs, period: {"type": "tiles", "tiles": [{"id": "n", "label": "N", "value": 2}]}, scope="trends"),
        "bad": Panel(lambda runs, period: {"type": "hbars", "bars": [{"label": "x"}]}, scope="trends"),
    }
    c = TestClient(server.create_app(Monitor(tmp_path, panels=panels)), base_url="http://127.0.0.1")
    q = "?from=2026-10-13&to=2026-10-15"
    assert c.get(f"/api/trends/panels/ok{q}").json() == {"type": "tiles", "tiles": [{"id": "n", "label": "N", "value": 2}]}
    assert c.get(f"/api/trends/panels/nope{q}").status_code == 404
    with pytest.raises(ResponseValidationError):  # a typed body that does not validate is never sent as a JSON tree
        c.get(f"/api/trends/panels/bad{q}")


def test_a_slow_panel_holds_no_other_route_back(tmp_path):
    """Many requests for a panel that takes seconds (a page refreshing, many trends panels)
    used to take every thread the server answers routes with: the run list waited for them."""
    pytest.importorskip("fastapi")
    import httpx2

    from contraagent._internal.monitor import server

    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])

    def slow(runs: PeriodRuns, period: Period) -> dict:
        time.sleep(2.0)
        return {"done": True}

    def slow_run(run: RunRecords) -> dict:
        time.sleep(2.0)
        return {"done": True}

    panels = {"slow0": Panel(slow, scope="trends"), "slow1": Panel(slow, scope="trends"), "slowrun": Panel(slow_run)}
    app = server.create_app(Monitor(tmp_path, panels=panels))

    async def scenario() -> tuple[float, list[int]]:
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://127.0.0.1", timeout=60) as c:
            q = "?from=2026-10-13&to=2026-10-15"
            # More requests than the threads that answer the other endpoints (40).
            heavy = [asyncio.create_task(c.get(f"/api/trends/panels/slow{i % 2}{q}")) for i in range(80)]
            heavy += [asyncio.create_task(c.get("/api/runs/r1/panels/slowrun")) for _ in range(2)]
            await asyncio.sleep(0.5)  # every slow request is in
            t0 = time.monotonic()
            runs = await c.get("/api/runs")
            took = time.monotonic() - t0
            assert runs.status_code == 200 and runs.json()[0]["run"] == "r1"
            codes = [r.status_code for r in await asyncio.gather(*heavy)]
            return took, codes

    took, codes = asyncio.run(scenario())
    assert took < 1.0, f"/api/runs took {took:.2f}s while slow panels were being made"
    assert codes == [200] * 82


def test_a_slow_run_panel_does_not_stop_the_event_loop(tmp_path):
    """The run feed reads its views off the event loop: while a run panel takes its time,
    the loop goes on serving."""
    pytest.importorskip("fastapi")
    from contraagent._internal.monitor import server

    write_run(tmp_path, "r1", [row("2026-10-14T01:00:00Z")])

    def slow_run(run: RunRecords) -> dict:
        time.sleep(1.0)
        return {"done": True}

    mon = Monitor(tmp_path, panels={"slowrun": Panel(slow_run)})

    async def scenario() -> int:
        ticks = 0
        stop = asyncio.Event()

        async def ticker() -> None:
            nonlocal ticks
            while not stop.is_set():
                ticks += 1
                await asyncio.sleep(0.05)

        async def connected() -> bool:
            return False

        t = asyncio.create_task(ticker())
        async for msg in server.run_feed(mon, "r1", connected):
            if msg["event"] == "panel:slowrun":
                break
        stop.set()
        await t
        return ticks

    assert asyncio.run(scenario()) >= 10  # about 20 in the second the panel took
