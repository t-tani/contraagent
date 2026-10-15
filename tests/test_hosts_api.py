"""The hosts behind the runs: `RunSummary.host_id` / `unresponsive`, `Monitor.hosts()` and
`/api/hosts`, on one host and on a hub."""

import json

from contraagent.hub.core import Hub
from contraagent.hub.protocol import DocumentPut, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent.hub.source import HeartbeatLiveness
from contraagent.hub.store import MemoryBlobs, MemoryHubStore
from contraagent.monitor import Monitor
from contraagent.runs import layout

T0 = 1_791_849_600.0  # 2026-10-13T00:00:00Z
AT = "2026-10-13T00:00:00+00:00"


def quota(at: str, pct: float) -> dict:
    return {"observed_at": at, "credential": "acct", "five_hour_pct": 1.0, "seven_day_pct": pct}


def ship(hub: Hub, host: str, run: str, *, finished: bool = False, reading: dict | None = None) -> RunRef:
    ref = RunRef(host_id=host, run_id=run, run_uid=f"{run}-{host}")
    info = {"run_id": run, "run_uid": ref.run_uid, "host_id": "pipeline-host", "started_at": AT}
    if finished:
        info["finished_at"] = AT
    row = {"key": "k", "kind": "k", "ok": True, "stop": "completed", "ts": AT, "quota": [reading] if reading else []}
    hub.records(
        RecordBatch(
            run=ref,
            documents=[DocumentPut(name=layout.RUN_INFO, text=json.dumps(info))],
            logs=[LogChunk(log=layout.JOURNAL, offset=0, lines=[json.dumps(row)])],
        )
    )
    return ref


def beat(hub: Hub, host: str, *runs: RunRef, at: str = AT) -> None:
    snap = {"launches": [], "tree": [], "python_tasks": []}
    hub.store.put_heartbeat(
        Heartbeat(host_id=host, sent_at=at, interval_s=3, runs=[RunLiveness(run=r, alive=True, snapshot=snap) for r in runs]), at
    )


def test_a_hub_names_each_runs_host_and_marks_runs_whose_host_went_quiet():
    hub = Hub(MemoryHubStore(), MemoryBlobs(), ttl_s=15)
    a = ship(hub, "h1", "r", reading=quota("2026-10-13T00:00:01+00:00", 40.0))
    b = ship(hub, "h2", "r", reading=quota("2026-10-13T00:00:05+00:00", 55.0))
    done = ship(hub, "h2", "old", finished=True)
    beat(hub, "h1", a)
    beat(hub, "h2", b, done)

    fresh = Monitor(source=hub.source(), liveness=HeartbeatLiveness(hub.store, 15, clock=lambda: T0 + 5), many_hosts=True)
    rows = {r["run"]: r for r in fresh.runs()}
    assert rows["r@h1"]["host_id"] == "h1" and rows["r@h1"]["run_uid"] == "r-h1"  # the hub's host, not run.json's
    assert rows["r@h1"]["running"] and not rows["r@h1"]["unresponsive"]

    quiet = Monitor(source=hub.source(), liveness=HeartbeatLiveness(hub.store, 15, clock=lambda: T0 + 60), many_hosts=True)
    rows = {r["run"]: r for r in quiet.runs()}
    assert not rows["r@h2"]["running"] and rows["r@h2"]["unresponsive"]
    assert not rows["old@h2"]["unresponsive"]  # finished: not waiting on its host
    hosts = quiet.hosts()
    assert [(h["host_id"], h["up"], h["runs"], h["unresponsive"]) for h in hosts["hosts"]] == [("h1", False, 1, 1), ("h2", False, 2, 1)]
    assert hosts["hosts"][0]["last_seen"] == AT and hosts["hosts"][0]["interval_s"] == 3
    (acct,) = hosts["quota"]
    assert acct["first"]["seven_day_pct"] == 40.0 and acct["last"]["seven_day_pct"] == 55.0


def test_one_host_is_its_own_single_host(tmp_path, monkeypatch):
    monkeypatch.setenv(layout.HOST_ID_ENV, "build-7")
    run = tmp_path / "r1"
    run.mkdir()
    (run / layout.RUN_INFO).write_text(json.dumps({"run_id": "r1", "run_uid": "u1", "host_id": "build-7", "started_at": AT}))
    (run / layout.JOURNAL).write_text(json.dumps({"key": "k", "kind": "k", "ok": True, "ts": AT}) + "\n")
    mon = Monitor(tmp_path)
    assert not mon.many_hosts
    (row,) = mon.runs()
    assert (row["host_id"], row["run_uid"], row["unresponsive"]) == ("build-7", "u1", False)
    assert mon.hosts()["hosts"] == [
        {"host_id": "build-7", "up": True, "last_seen": "", "interval_s": None, "runs": 1, "running": 0, "unresponsive": 0}
    ]
