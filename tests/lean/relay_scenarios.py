"""Scenarios of the relay's shipping of a run, played on `Relay` with a `Hub` and on the Lean
specification.

    uv run python tests/lean/relay_scenarios.py     # rewrites tests/lean/relay_scenarios.jsonl

A scenario is one run's logs and a list of steps: lines added to a log, a pass of the relay at
a time, a hub that loses lines of a log or everything, and a hub whose retention removes the
run; `lean/Conformance/Relay.lean` has the fields. `play` plays one on a `Relay` over a run
directory and a `Hub` in memory, and returns the requests of each pass, the relay's progress
and the lines the hub holds (`lake exe contraagent-lean relay`).
`tests/lean/relay_scenarios.jsonl` holds scenarios (`scenarios`) with what the specification
answers for each; `tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import json
import random
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contraagent._internal.hub.client import DirectClient
from contraagent._internal.hub.core import Hub
from contraagent._internal.hub.protocol import Accepted, Heartbeat, HeartbeatAck, RecordBatch
from contraagent._internal.hub.relay import Relay
from contraagent._internal.hub.store import MemoryBlobs, MemoryHubStore
from contraagent._internal.hub.streams import MemoryStreamLogs, is_stream
from contraagent._internal.runs import layout
from contraagent._internal.runs.liveness import StaticLiveness
from contraagent.monitor import DirectorySource

FILE = Path(__file__).with_name("relay_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "relay"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 60

RUN = "r1"
#: The run's logs, in the order its source lists them.
LOGS = (layout.JOURNAL, layout.stream("a"), layout.stream("b"))


NAME = f"{RUN}@h1"


class Noting:
    """A `HubClient` that passes each request to a hub and notes its chunks."""

    def __init__(self, hub: Hub) -> None:
        self.inner = DirectClient(hub)
        self.requests: list[dict[str, Any]] = []

    def send_records(self, batch: RecordBatch) -> Accepted:
        chunks = [[chunk.log, chunk.offset, len(chunk.lines)] for chunk in batch.logs]
        self.requests.append({"documents": bool(batch.documents or batch.files), "chunks": chunks})
        return self.inner.send_records(batch)

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        return HeartbeatAck(ttl_s=heartbeat.ttl_s)  # none reaches the hub: no run is live there

    def has_blob(self, sha256: str) -> bool:
        return self.inner.has_blob(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        self.inner.put_blob(sha256, data)


def _held(hub: Hub, uid: str, log: str) -> list[str] | None:
    """The lines the hub holds of a log of the run `uid`, the list it keeps them in; None
    when it holds none of the log."""
    store, streams = hub.store, hub.streams
    assert isinstance(store, MemoryHubStore) and isinstance(streams, MemoryStreamLogs)
    if is_stream(log):
        return streams._logs.get((NAME, uid, log))
    run = store._runs.get(NAME)
    return run.logs.get(log) if run is not None and run.entry.run_uid == uid else None


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `Relay` and a `Hub`: the requests of each pass, then the relay's
    progress and how many lines of each log the hub holds."""
    assert scenario["logs"] == list(LOGS)
    clock = [0]
    hub = Hub(MemoryHubStore(), MemoryBlobs())
    client = Noting(hub)
    answers: list[Any] = []

    def hub_uid() -> str:
        """The uid of the run the hub holds under the name; '' when it holds none."""
        entry = hub.store.entry(NAME)
        return entry.run_uid if entry is not None else ""

    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        run = runs / RUN
        (run / layout.STREAMS).mkdir(parents=True)
        renewed = 0
        (run / layout.RUN_INFO).write_text(json.dumps({"run_id": RUN, "run_uid": "u0"}), encoding="utf-8")
        for log in LOGS:
            (run / log).write_bytes(b"")

        def start() -> Relay:
            return Relay(
                client,
                runs,
                Path(tmp) / "progress.json",
                host_id="h1",
                liveness=StaticLiveness(DirectorySource(runs)),
                clock=lambda: clock[0],
                resync_s=scenario["resyncS"],
                batch_lines=scenario["batchLines"],
            )

        relay = start()
        for step in scenario["steps"]:
            answer: Any = None
            if step["op"] == "grow":
                with open(run / step["log"], "ab") as f:
                    f.write("".join(line + "\n" for line in step["lines"]).encode())
            elif step["op"] == "lose":
                held = _held(hub, hub_uid(), step["log"])
                if held is not None:
                    del held[step["keep"] :]
            elif step["op"] == "forget":  # a hub that lost everything, its memory of the prunes too
                hub.store, hub.streams = MemoryHubStore(), MemoryStreamLogs()
            elif step["op"] == "prune":  # every run the hub holds is old enough
                hub.prune(older_than=timedelta(0), now=datetime.now(UTC) + timedelta(days=1))
            elif step["op"] == "reset":  # the relay starts again without its progress
                relay.progress_path.unlink(missing_ok=True)
                relay = start()
            elif step["op"] == "renew":  # the directory holds a new run: a new run uid over the same logs
                renewed += 1
                (run / layout.RUN_INFO).write_text(json.dumps({"run_id": RUN, "run_uid": f"u{renewed}"}), encoding="utf-8")
            else:
                clock[0] = step["now"]
                before = len(client.requests)
                assert relay.pass_once()
                answer = client.requests[before:]
            answers.append(answer)
        progress = relay.runs.get(RUN)
        known = {log: at[0] for log, at in progress.logs.items()} if progress is not None else {}
        held_now = {log: _held(hub, hub_uid(), log) for log in LOGS}
    return {
        "answers": answers,
        "progress": {log: known[log] for log in LOGS if log in known},
        "hub": {log: len(lines) for log, lines in held_now.items() if lines is not None},
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: three logs that grow, passes with small and large requests before
    and after the time to ask the hub what it holds, a hub that loses the last lines of a
    log, or everything, a hub whose retention removes the run, a relay that starts again
    without its progress, and a new run in the same directory."""
    now = 0
    grown = dict.fromkeys(LOGS, 0)
    steps = []
    for _ in range(rng.randint(4, 28)):
        op = rng.choices(["grow", "pass", "lose", "forget", "prune", "reset", "renew"], [38, 40, 7, 3, 7, 3, 2])[0]
        log = rng.choice(LOGS)
        lines: list[str] = []
        if op == "grow":
            lines = [json.dumps({"n": grown[log] + i}) for i in range(rng.randint(1, 6))]
            grown[log] += len(lines)
        elif op == "pass":
            now += rng.choice([0, 1, 5, 10, 60, 100])
        steps.append({"op": op, "now": now, "log": log, "lines": lines, "keep": rng.randint(0, max(grown[log], 1))})
    return {"logs": list(LOGS), "batchLines": rng.choice([2, 5, 50]), "resyncS": rng.choice([10, 60]), "steps": steps}


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
