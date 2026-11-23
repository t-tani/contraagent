"""Scenarios of the hub's logs, played on `SegmentedStreamLogs` and on the Lean specification.

    uv run python tests/lean/hub_scenarios.py     # rewrites tests/lean/hub_scenarios.jsonl

A scenario is when a segment is sealed and a list of steps on some logs of two runs:
appends, closes, ticks, reads, `sweep`, `drop`, and starts of the hub on what the last
process left; `lean/Conformance/Segments.lean` has the fields. A step may name a seal that
fails, or at which the process dies: the hub then starts again on the files, the objects
and the index as that seal left them. `play` plays one on `SegmentedStreamLogs` with an
objects store and an index in memory, and returns what each step answered and what
survives after the last (`lake exe contraagent-lean hub`). `tests/lean/hub_scenarios.jsonl`
holds scenarios (`scenarios`) with what the specification answers for each;
`tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import logging
import random
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from contraagent._internal.hub.segment_objects import MemorySegmentObjects
from contraagent._internal.hub.segments import MemorySegmentIndex, Segment, SegmentedStreamLogs, object_key, read_segment

FILE = Path(__file__).with_name("hub_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "hub"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 40

#: The logs of the scenarios: two of one run, one of another.
LOGS = (("job", "u1", "a"), ("job", "u1", "b"), ("job", "u2", "a"))
HOWS = ("failPut", "failAdd", "crashAfterPut", "crashAfterAdd")


class Died(BaseException):
    """The process dies at a step of a seal: nothing of the hub's own code catches it."""


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `SegmentedStreamLogs`: what each step answered, and the index
    rows, the objects and the files after the last."""
    clock = [0]
    armed: list[dict[str, Any] | None] = [None]  # the seal that goes wrong in the step in play

    def how(key: str) -> str | None:
        fault = armed[0]
        if fault is None:
            return None
        if fault["first"] is None:  # each segment of the log
            return fault["how"] if key.startswith(object_key(*fault["key"], 0).removesuffix("0.seg")) else None
        return fault["how"] if object_key(*fault["key"], fault["first"]) == key else None

    class Objects(MemorySegmentObjects):
        def put(self, key: str, data: bytes) -> None:
            if how(key) == "failPut":
                raise RuntimeError("the put failed")
            super().put(key, data)
            if how(key) == "crashAfterPut":
                raise Died

    class Index(MemorySegmentIndex):
        def add(self, segment: Segment, activity: str | None) -> None:
            if how(segment.key) == "failAdd":
                raise RuntimeError("the commit failed")
            super().add(segment, activity)
            if how(segment.key) == "crashAfterAdd":
                raise Died

    objects = Objects()
    held: dict[str, Any] = {"index": Index(), "logs": None}
    quiet = logging.getLogger("contraagent._internal.hub.segments")
    level = quiet.level
    quiet.setLevel(logging.CRITICAL)  # each failed seal is logged with its traceback
    answers: list[Any] = []
    try:
        with tempfile.TemporaryDirectory() as hot:

            def start() -> bool:
                """Start the hub on what the last process left; whether it died in the start."""
                held["logs"] = None
                try:
                    held["logs"] = SegmentedStreamLogs(
                        hot,
                        objects,
                        held["index"],
                        segment_bytes=scenario["segmentBytes"],
                        idle_s=scenario["idleS"],
                        age_s=scenario["ageS"],
                        clock=lambda: clock[0],
                        background=False,
                    )
                except (Died, RuntimeError):  # a start whose commit fails ends the process too
                    return True
                return False

            def files() -> list[tuple[str, int]]:
                found = []
                for path in Path(hot).glob("*/*/*/*.jsonl"):
                    name, uid, log = (unquote(part) for part in path.parts[-4:-1])
                    found.append((f"{name}/{uid}/{log}/{path.stem}", path.read_bytes().count(b"\n")))
                return found

            start()
            for step in scenario["steps"]:
                clock[0], armed[0] = step["now"], step["fault"]
                logs, key = held["logs"], step["key"]
                answer: Any = None
                died = False
                try:
                    if step["op"] == "append":
                        answer = {"held": list(logs.append(*key, step["offset"], step["lines"], "t")), "crashed": False}
                    elif step["op"] == "close":
                        logs.close(*key)
                        answer = {"crashed": False}
                    elif step["op"] == "tick":
                        logs.tick()
                        answer = {"crashed": False}
                    elif step["op"] == "restart":
                        if step["loseIndex"]:
                            held["index"] = Index()
                        for path in sorted(Path(hot).glob("*/*/*/*.jsonl"), key=lambda p: int(p.stem))[-1:]:
                            with open(path, "ab") as torn:  # a torn last line: the start cuts it
                                torn.write(b'{"torn')
                        died = start()
                        answer = {"crashed": died}
                    elif step["op"] == "read":
                        lines, total = logs.read(*key, step["since"], limit=step["limit"])
                        answer = {"lines": lines, "total": total}
                    elif step["op"] == "held":
                        answer = list(logs.held(*key))
                    elif step["op"] == "sweep":
                        answer = sorted(logs.sweep())
                    else:
                        answer = sorted(logs.drop(key[0], key[1]))
                except Died:
                    died = True
                    answer = {"crashed": True}
                    if step["op"] == "append":  # the lines were written; what it would have answered died with it
                        answer["held"] = None
                armed[0] = None
                if died:
                    assert not start(), "a start with no fault died"
                answers.append(answer)
            index = held["index"]
            kept = {
                "rows": sorted(f"{s.key.removesuffix('.seg')}:{s.line_count}" for rows in index._rows.values() for s in rows.values()),
                "objects": sorted(f"{key.removesuffix('.seg')}:{_lines(objects, key)}" for key in objects.keys()),
                "files": sorted(f"{name}:{count}" for name, count in files()),
            }
    finally:
        quiet.setLevel(level)
    return {"answers": answers, "kept": kept}


def _lines(objects: MemorySegmentObjects, key: str) -> int:
    segment = read_segment(objects, key)
    assert segment is not None, key
    return segment.line_count


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: segments of a few lines, and up to thirty-five steps on three logs
    of two runs, with chunks that overlap what the hub holds, continue it or leave a gap,
    seals that fail, processes that die at a step of a seal, starts, an index that lost its
    rows, sweeps and drops."""
    true: dict[tuple[str, str, str], list[str]] = {key: [] for key in LOGS}  # each log, as its relay holds it
    sent = dict.fromkeys(LOGS, 0)  # how far each log was sent
    segment = rng.choice([12, 30, 80])
    now = 0
    steps = []
    for number in range(rng.randint(5, 35)):
        now += rng.choice([0, 1, 5, 40, 200])
        key = rng.choice(LOGS)
        op = rng.choices(["append", "close", "tick", "restart", "read", "held", "sweep", "drop"], [40, 8, 9, 9, 20, 6, 5, 3])[0]
        offset, lines = 0, []
        if op == "append":
            offset = max(0, sent[key] + rng.choice([0, 0, 0, 0, -1, -3, 2]))
            log = true[key]
            while len(log) < offset + 6:
                log.append(f"{key[2]}{len(log)}:" + "x" * rng.choice([0, 1, 3, 9, 20]))
            lines = log[offset : offset + rng.randint(1, 6)]
            if offset <= sent[key]:
                sent[key] = max(sent[key], offset + len(lines))
        fault = None
        if op in ("append", "close", "tick", "restart") and rng.random() < 0.3:
            fault = {"key": list(rng.choice(LOGS)), "first": rng.choice([None, None, None, 0, 1, 2, 3, 5]), "how": rng.choice(HOWS)}
        lost = op == "restart" and fault is None and rng.random() < 0.15
        if op == "drop" or lost:  # its relay sends the log again from what the hub says it holds
            for other in LOGS:
                if lost or other[:2] == key[:2]:
                    sent[other] = 0
        steps.append(
            {
                "op": op,
                "now": now,
                "key": list(key),
                "offset": offset,
                "lines": lines,
                "since": rng.choice([0, 0, 0, 1, 4, 9]),
                "limit": rng.choice([None, None, None, 0, 2, 5]),
                "loseIndex": lost,
                "fault": fault,
            }
        )
        _ = number
    # The times a step moves the clock by are among these: a tick often falls on the very time a segment is due.
    return {"segmentBytes": segment, "idleS": rng.choice([40, 200]), "ageS": rng.choice([40, 200, 1000]), "steps": steps}


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
