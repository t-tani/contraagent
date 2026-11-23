"""Scenarios of the relay's shipping of a run, played on `Relay` and on the Lean specification.

    uv run python tests/lean/relay_scenarios.py     # rewrites tests/lean/relay_scenarios.jsonl

A scenario is one run's logs and a list of steps: lines added to a log, a pass of the relay at
a time, and a hub that loses lines of a log or the whole run; `lean/Conformance/Relay.lean` has
the fields. `play` plays one on a `Relay` over a run directory, with a hub that keeps every
line once, in order, and returns the requests of each pass, the relay's progress and the lines
the hub holds (`lake exe contraagent-lean relay`). `tests/lean/relay_scenarios.jsonl` holds
scenarios (`scenarios`) with what the specification answers for each;
`tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import json
import random
import tempfile
from pathlib import Path
from typing import Any

from contraagent._internal.hub.protocol import Accepted, Heartbeat, HeartbeatAck, RecordBatch
from contraagent._internal.hub.relay import Relay
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


class LineHub:
    """A hub that keeps every line of a log once, in order, and notes each request."""

    def __init__(self) -> None:
        self.held: dict[str, list[str]] = {}
        self.requests: list[dict[str, Any]] = []

    def send_records(self, batch: RecordBatch) -> Accepted:
        logs: dict[str, int] = {}
        for chunk in batch.logs:
            held = self.held.setdefault(chunk.log, [])
            if chunk.offset <= len(held):
                held.extend(chunk.lines[len(held) - chunk.offset :])
            logs[chunk.log] = len(held)
        chunks = [[chunk.log, chunk.offset, len(chunk.lines)] for chunk in batch.logs]
        self.requests.append({"documents": bool(batch.documents or batch.files), "chunks": chunks})
        return Accepted(logs=logs, durable=dict(logs))

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        return HeartbeatAck(ttl_s=heartbeat.ttl_s)

    def has_blob(self, sha256: str) -> bool:
        return True

    def put_blob(self, sha256: str, data: bytes) -> None:
        return None


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `Relay`: the requests of each pass, then the relay's progress and
    how many lines of each log the hub holds."""
    assert scenario["logs"] == list(LOGS)
    clock = [0]
    hub = LineHub()
    answers: list[Any] = []
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        run = runs / RUN
        (run / layout.STREAMS).mkdir(parents=True)
        (run / layout.RUN_INFO).write_text(json.dumps({"run_id": RUN, "run_uid": "u1"}), encoding="utf-8")
        for log in LOGS:
            (run / log).write_bytes(b"")
        relay = Relay(
            hub,
            runs,
            Path(tmp) / "progress.json",
            host_id="h1",
            liveness=StaticLiveness(DirectorySource(runs)),
            clock=lambda: clock[0],
            resync_s=scenario["resyncS"],
            batch_lines=scenario["batchLines"],
        )
        for step in scenario["steps"]:
            if step["op"] == "grow":
                with open(run / step["log"], "ab") as f:
                    f.write("".join(line + "\n" for line in step["lines"]).encode())
                answers.append(None)
            elif step["op"] == "lose":
                if step["log"] in hub.held:
                    del hub.held[step["log"]][step["keep"] :]
                answers.append(None)
            elif step["op"] == "forget":
                hub.held.clear()
                answers.append(None)
            else:
                clock[0] = step["now"]
                before = len(hub.requests)
                assert relay.pass_once()
                answers.append(hub.requests[before:])
        progress = relay.runs.get(RUN)
        known = {log: at[0] for log, at in progress.logs.items()} if progress is not None else {}
    return {
        "answers": answers,
        "progress": {log: known[log] for log in LOGS if log in known},
        "hub": {log: len(hub.held[log]) for log in LOGS if log in hub.held},
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: three logs that grow, passes with small and large requests before
    and after the time to ask the hub what it holds, and a hub that loses the last lines of
    a log, or everything."""
    now = 0
    grown = dict.fromkeys(LOGS, 0)
    steps = []
    for _ in range(rng.randint(4, 28)):
        op = rng.choices(["grow", "pass", "lose", "forget"], [42, 43, 11, 4])[0]
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
