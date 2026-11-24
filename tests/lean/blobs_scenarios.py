"""Scenarios of the hub's blobs while a prune runs beside the relays, played on `Hub` and
on the Lean specification.

    uv run python tests/lean/blobs_scenarios.py     # rewrites tests/lean/blobs_scenarios.jsonl

A scenario is a grace and a list of steps, each at a time: a relay asks whether the hub
holds a blob, stores one, or sends a file ref of one; the run's file refs go; and a prune,
with the steps of relays that come after it read the file refs and before it removes a
blob. `lean/Conformance/Core.lean` has the fields. `play` plays one on a `Hub` in memory,
and returns what each step answers, then the blobs held with their dates and the blobs
that file refs name (`lake exe contraagent-lean blobs`). `tests/lean/blobs_scenarios.jsonl`
holds scenarios (`scenarios`) with what the specification answers for each;
`tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import random
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.protocol import FileRef, RecordBatch, RunRef
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore

FILE = Path(__file__).with_name("blobs_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "blobs"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261124, 150

#: The time 0 of a scenario; its times are seconds from it.
START = datetime(2026, 1, 1, tzinfo=UTC)
BLOBS = ("b0", "b1", "b2", "b3")
SHA = {name: hashlib.sha256(name.encode()).hexdigest() for name in BLOBS}
NAME = {sha: name for name, sha in SHA.items()}


def moment(seconds: int) -> datetime:
    return START + timedelta(seconds=seconds)


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play the scenario's steps on a hub in memory: what each answers, the blobs held with
    their dates, and the blobs the file refs name."""
    clock = {"now": 0.0}
    store = MemoryHubStore()
    blobs = MemoryBlobs(clock=lambda: clock["now"])
    hub = Hub(store, blobs)
    answers: list[Any] = []
    uid, paths = [0], itertools.count()

    def run() -> RunRef:
        return RunRef(host_id="h", run_id="r", run_uid=f"u{uid[0]}")

    def relay(step: dict[str, Any]) -> None:
        clock["now"] = moment(step["now"]).timestamp()
        sha = SHA.get(step["blob"], "")
        if step["op"] == "has":
            answers.append(hub.has_blob(sha))
        elif step["op"] == "put":
            hub.put_blob(sha, step["blob"].encode())
            answers.append(None)
        elif step["op"] == "ref":
            hub.records(RecordBatch(run=run(), files=[FileRef(path=f"/w/{next(paths)}", sha256=sha, size=1, mtime="m")]))
            answers.append(None)
        else:  # the run's file refs go: another run uid under its name
            uid[0] += 1
            hub.records(RecordBatch(run=run()))
            answers.append(None)

    def prune(step: dict[str, Any]) -> None:
        read = store.referenced_blobs
        came = []

        def read_then_the_relays_come(excluding: Collection[str] = ()) -> set[str]:
            referenced = read(excluding)
            came.append(True)
            for inner in step["during"]:
                relay(inner)
            return referenced

        store.referenced_blobs = read_then_the_relays_come  # type: ignore[method-assign]
        try:
            report = hub.prune(older_than=timedelta(days=36500), blob_grace=timedelta(seconds=scenario["grace"]), now=moment(step["now"]))
        finally:
            store.referenced_blobs = read  # type: ignore[method-assign]
        if not came:  # no blob was old: the prune read no file ref, and removes nothing
            for inner in step["during"]:
                relay(inner)
        answers.append(sorted(NAME[sha] for sha in report.blobs))

    for step in scenario["steps"]:
        if step["op"] == "prune":
            prune(step)
        else:
            relay(step)
    held = sorted((NAME[item.sha256], round((item.modified - START).total_seconds())) for item in blobs.items())
    return {
        "answers": answers,
        "blobs": [list(pair) for pair in held],
        "refs": sorted(NAME[sha] for sha in store.referenced_blobs()),
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: relays that ask for a few blobs, store them and send file refs of
    them, at times that go on by a few steps of the grace, so that many blobs are dated at
    the edge of it; prunes, with relays that come while they run; and the run's file refs
    going. A relay sends a file ref of a blob it asked for and found, or stored, or of one it
    did neither for."""
    grace = rng.choice([10, 20])
    now = [0]

    def relay(ops: list[str]) -> dict[str, Any]:
        now[0] += rng.choice([0, 0, 1, grace // 2, grace - 1, grace, grace + 1])
        return {"op": rng.choice(ops), "now": now[0], "blob": rng.choice(BLOBS)}

    steps: list[dict[str, Any]] = []
    for _ in range(rng.randint(3, 14)):
        if rng.random() < 0.3:
            now[0] += rng.choice([0, 1, grace, grace + 1])
            at = now[0]
            during = [relay(["has", "put", "ref"]) for _ in range(rng.randint(0, 3))]
            steps.append({"op": "prune", "now": at, "blob": "", "during": during})
        else:
            steps.append({**relay(["has", "has", "put", "put", "ref", "ref", "reset"]), "during": []})
    return {"grace": grace, "steps": steps}


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
