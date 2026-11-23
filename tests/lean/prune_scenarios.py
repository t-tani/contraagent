"""Scenarios of the hub's retention, played on `Hub.prune` and on the Lean specification.

    uv run python tests/lean/prune_scenarios.py     # rewrites tests/lean/prune_scenarios.jsonl

A scenario is what a hub holds (runs with their activity and file refs, transcripts of the
runs and of run uids the hub no longer holds, heartbeats, blobs, and the runs it remembers
it pruned), a time, how old a run and a blob must be, and whether the prune is a dry run;
`lean/Conformance/Core.lean` has the fields. `play` fills a `Hub` in memory with the same,
calls `Hub.prune`, and returns its report and what the hub holds after (`lake exe
contraagent-lean prune`). `tests/lean/prune_scenarios.jsonl` holds scenarios (`scenarios`)
with what the specification answers for each; `tests/test_lean_scenarios.py` plays them on
the code.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.protocol import DocumentPut, FileRef, Heartbeat, LogChunk, RecordBatch, RunLiveness, RunRef
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore
from contraagent._internal.hub.streams import MemoryStreamLogs
from contraagent._internal.runs import layout

FILE = Path(__file__).with_name("prune_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "prune"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261124, 70

#: The time 0 of a scenario; its times are seconds from it.
START = datetime(2026, 1, 1, tzinfo=UTC)
RECORDS = (layout.JOURNAL, layout.PLAN)
TRANSCRIPTS = (layout.stream("a"), layout.stream("b"))


def moment(seconds: int) -> datetime:
    return START + timedelta(seconds=seconds)


def iso(seconds: int | None) -> str:
    """The time as the hub's stores hold it; empty for no time."""
    return "" if seconds is None else moment(seconds).isoformat(timespec="milliseconds")


def ref(name: str, uid: str) -> RunRef:
    run_id, _, host = name.partition("@")
    return RunRef(host_id=host, run_id=run_id, run_uid=uid)


def content(sha: str, blobs: list[dict[str, Any]]) -> bytes:
    return next(b["content"].encode() for b in blobs if b["sha"] == sha)


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Fill a hub in memory with what the scenario's hub holds, prune it, and return the
    report and what it holds after."""
    clock = {"now": 0.0}
    store, streams = MemoryHubStore(), MemoryStreamLogs()
    blobs = MemoryBlobs(clock=lambda: clock["now"])
    hub = Hub(store, blobs, streams=streams)
    for blob in scenario["blobs"]:
        clock["now"] = moment(blob["modified"]).timestamp()
        blobs.put(blob["sha"], blob["content"].encode())
    for name, was in scenario["pruned"]:  # a run the hub pruned before: stored, then pruned
        store.put_batch(RecordBatch(run=ref(name, was["runUid"])), iso(0))
        assert store.prune_run(name, was["runUid"], dict(was["logs"]), iso(0), iso(0))
    for run in scenario["runs"]:
        info = {"run_id": run["name"].partition("@")[0], **({"finished_at": iso(0)} if run["finished"] else {})}
        store.put_batch(
            RecordBatch(
                run=ref(run["name"], run["runUid"]),
                logs=[LogChunk(log=log, offset=0, lines=[f"line {i}" for i in range(n)]) for log, n in run["logs"]],
                documents=[DocumentPut(name=layout.RUN_INFO, text=json.dumps(info))],
                files=[FileRef(path=f"/w/{i}", sha256=sha, size=1, mtime="m") for i, sha in enumerate(run["files"])],
            ),
            iso(run["recordsAt"]),
        )
    for held in scenario["transcripts"]:
        for log, n in held["logs"]:
            streams.append(held["name"], held["runUid"], log, 0, [f"line {i}" for i in range(n)], iso(held["activity"]))
    for heartbeat in scenario["heartbeats"]:
        alive = [RunLiveness(run=ref(name, "uid"), alive=True, snapshot={}) for name in heartbeat["alive"]]
        at = iso(heartbeat["receivedAt"])
        store.put_heartbeat(Heartbeat(host_id=heartbeat["host"], sent_at=at, interval_s=3, ttl_s=heartbeat["ttl"], runs=alive), at)
    report = hub.prune(
        older_than=timedelta(seconds=scenario["olderThan"]),
        blob_grace=timedelta(seconds=scenario["blobGrace"]),
        dry_run=scenario["dryRun"],
        now=moment(scenario["now"]),
    )
    names = sorted({run["name"] for run in scenario["runs"]} | {name for name, _ in scenario["pruned"]})
    remembered = [(name, store.pruned(name)) for name in names]
    return {
        "runs": report.runs,
        "transcripts": [list(pair) for pair in report.transcripts],
        "blobs": report.blobs,
        "blobBytes": report.blob_bytes,
        "heartbeats": report.heartbeats,
        "keptRuns": [list(item) for item in report.kept_runs.items()],
        "keptHeartbeats": [list(item) for item in report.kept_heartbeats.items()],
        "heldRuns": [[entry.name, entry.run_uid] for entry in store.runs()],
        "heldTranscripts": [list(pair) for pair in sorted(streams.runs())],
        "heldHeartbeats": sorted(store.heartbeats()),
        "heldBlobs": sorted(blob.sha256 for blob in blobs.items()),
        "pruned": [[name, was.run_uid, [list(item) for item in sorted(was.logs.items())]] for name, was in remembered if was is not None],
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: a few runs on a few hosts, old, recent or with no activity time,
    finished or not, with file refs to shared blobs; transcripts of those runs and of run
    uids the hub does not hold; heartbeats, up or not, old or not, that report runs alive;
    blobs, old or young, some that no file ref names; and runs pruned before. The times fall
    on a few values around the cutoff and the blobs' grace, so that many are equal to one."""
    now = rng.choice([1000, 5000])
    older_than = rng.choice([100, 400])
    grace = rng.choice([50, 100, 400])
    cutoff, old_blobs = now - older_than, now - grace
    times = [cutoff - 300, cutoff - 1, cutoff, cutoff + 1, now - 5, now]
    made = [
        {"content": f"blob {i}", "modified": rng.choice([old_blobs - 200, old_blobs - 1, old_blobs, old_blobs + 1, now])} for i in range(6)
    ]
    blobs = [{"sha": hashlib.sha256(b["content"].encode()).hexdigest(), "size": len(b["content"]), **b} for b in made]
    names = sorted({f"r{rng.randint(1, 5)}@h{rng.randint(1, 2)}" for _ in range(rng.randint(0, 5))})
    runs = []
    for name in names:
        runs.append(
            {
                "name": name,
                "runUid": rng.choice(["u1", "u2"]),
                "recordsAt": rng.choice([None, *times, *times]),
                "finished": rng.random() < 0.3,
                "files": [rng.choice(blobs)["sha"] for _ in range(rng.randint(0, 3))],
                "logs": [[log, rng.randint(0, 3)] for log in RECORDS if rng.random() < 0.7],
            }
        )
    transcripts = []
    others = sorted({*names, *(f"r{rng.randint(1, 6)}@h{rng.randint(1, 2)}" for _ in range(rng.randint(0, 3)))})
    for name in others:
        for uid in ("u1", "u2"):
            logs = [[log, rng.randint(1, 3)] for log in TRANSCRIPTS if rng.random() < 0.6]
            if logs and rng.random() < 0.6:
                transcripts.append({"name": name, "runUid": uid, "activity": rng.choice([None, *times, *times]), "logs": logs})
    heartbeats = []
    for host in ("h1", "h2", "h3"):
        if rng.random() < 0.7:
            received = rng.choice([cutoff - 300, cutoff - 1, cutoff, now - 20, now - 5])
            alive = [name for name in [*names, "gone@h9"] if rng.random() < 0.3]
            heartbeats.append({"host": host, "receivedAt": received, "ttl": rng.choice([12, 12, 30, 5000]), "alive": alive})
    # A name holds a run or the memory of one it pruned, not both.
    gone = [name for name in others if name not in names]
    pruned = [[name, {"runUid": rng.choice(["u1", "u0"]), "logs": [[layout.JOURNAL, 2]]}] for name in gone if rng.random() < 0.3]
    return {
        "now": now,
        "olderThan": older_than,
        "blobGrace": grace,
        "dryRun": rng.random() < 0.2,
        "runs": runs,
        "transcripts": transcripts,
        "heartbeats": heartbeats,
        "blobs": sorted(blobs, key=lambda b: b["sha"]),
        "pruned": pruned,
    }


def scenarios(seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [scenario(rng) for _ in range(count)]


def _exe() -> Any:
    spec = importlib.util.spec_from_file_location("lean_exe", Path(__file__).with_name("exe.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    _exe().rewrite(FILE, WHAT, scenarios(SEED, COUNT))
