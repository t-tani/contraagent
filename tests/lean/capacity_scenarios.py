"""Scenarios of the host's room, played on `HostCapacity` and on the Lean specification.

    uv run python tests/lean/capacity_scenarios.py     # rewrites tests/lean/capacity_scenarios.jsonl

A scenario is a host's cores, some `PerTask` needs and a list of calls of a `HostCapacity` or
of one of its capacities, each with what the host reads then; `lean/Conformance/Capacity.lean`
has its fields. `play` plays one on `HostCapacity` and returns, after each call, what it
answered, the baseline and the running tasks (`lake exe contraagent-lean capacity`).
`tests/lean/capacity_scenarios.jsonl` holds scenarios (`scenarios`) with what the
specification answers for each; `tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path
from typing import Any

from contraagent import PerTask
from contraagent._internal.routing.capacity import HostCapacity

FILE = Path(__file__).with_name("capacity_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "capacity"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 80


def play(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Play `scenario` on a `HostCapacity`: after each step, the answer, the baseline and the tasks."""
    host: dict[str, Any] = {"free": None, "usage": {}}
    room = HostCapacity(
        mem_available_mb=lambda: host["free"],
        usage_mb=lambda keys: {key: host["usage"][key] for key in keys if key in host["usage"]},
        cores=scenario["cores"],
    )
    capacities = [room.capacity(PerTask(memory_mb=need["memoryMb"], cores=need["cores"])) for need in scenario["needs"]]
    answers: list[dict[str, Any]] = []
    for step in scenario["steps"]:
        host["free"], host["usage"] = step["freeMb"], dict(step["usageMb"])
        capacity = capacities[step["need"]]
        answer: int | None = None
        if step["op"] == "refresh":
            room.refresh()
        elif step["op"] == "allowed":
            allowed = capacity.allowed(step["held"])
            answer = None if allowed == sys.maxsize else allowed
        elif step["op"] == "started":
            capacity.started(step["key"])
        else:
            capacity.ended(step["key"])
        tasks = [[key, declared, names] for key, (declared, names) in room.tasks.items()]
        answers.append({"answer": answer, "baseline": room.baseline_mb, "tasks": tasks})
    return answers


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: one to three needs, of memory, of cores or of both, and up to
    twenty-five calls, with tasks that start and end under one or two names, a host whose
    free memory moves or is not reported, and tasks that take less or more than they
    declared."""
    needs = []
    for _ in range(rng.randint(1, 3)):
        memory = rng.choice([None, 500, 1000, 4000])
        needs.append({"memoryMb": memory, "cores": rng.choice([1, 2, 4] if memory is None else [None, None, 1, 2, 4])})
    running: list[tuple[str, int]] = []
    steps = []
    for _ in range(rng.randint(3, 25)):
        op = rng.choices(["refresh", "allowed", "started", "ended"], [15, 45, 25, 15])[0]
        need, key = rng.randrange(len(needs)), rng.choice(["a", "b", "c", "d"])
        if op == "started":
            running.append((key, need))
        elif op == "ended":
            if running and rng.random() < 0.9:
                key, need = running.pop(rng.randrange(len(running)))
            else:
                op = "refresh"  # nothing runs: read the host again
        steps.append(
            {
                "op": op,
                "need": need,
                "held": rng.choice([0, 0, 1, 2, 5]),
                "key": key,
                "freeMb": rng.choice([None, 0, 300, 1000, 3000, 8000, 8000]),
                "usageMb": sorted({k: rng.choice([0, 200, 1500, 5000]) for k, _ in running if rng.random() < 0.6}.items()),
            }
        )
    return {"cores": rng.choice([1, 2, 8]), "needs": needs, "steps": steps}


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
