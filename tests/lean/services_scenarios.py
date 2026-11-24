"""Scenarios of a run's services, played on `Services` and on the Lean specification.

    uv run python tests/lean/services_scenarios.py     # rewrites tests/lean/services_scenarios.jsonl

A scenario is the claim names that stand for a service, the address each gives, the
cool-off, and a list of steps: a task that runs holding the services it claims, or the run's
end. Each step gives what the code reads from outside then: the clock, whether a signal is
stopping the run, and the starts and the stops that raise; `lean/Conformance/Services.lean`
has the fields.
`play` plays one on `Services` and returns what each step answered and the lines of
`services.jsonl` (`lake exe contraagent-lean services`).
`tests/lean/services_scenarios.jsonl` holds scenarios (`scenarios`) with what the
specification answers for each; `tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import json
import random
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from contraagent import Task, TaskResult
from contraagent._internal.execution import services as services_module
from contraagent._internal.execution.services import Services
from contraagent._internal.platform import envvars
from contraagent._internal.runs import layout

FILE = Path(__file__).with_name("services_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "services"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 40

#: The claim names of the scenarios; two of them share one environment variable.
NAMES = ("db", "cache", "a-b", "a_b", "gpu")
_RAISED = "RuntimeError: "
_FAILURES = (
    (re.compile(r"services '(?P<first>.+)' and '(?P<second>.+)' share the variable \w+: claim one of them"), "clash"),
    (re.compile(r"service '(?P<name>.+)' did not start: the run is ending"), "ending"),
    (re.compile(r"service '(?P<name>.+)' did not start: (?P<error>.+)"), "not_started"),
)


def _failure(reason: str) -> dict[str, str]:
    """Why a task could not hold its services, from its result's reason."""
    for pattern, why in _FAILURES:
        match = pattern.fullmatch(reason)
        if match is not None:
            return {"why": why, **match.groupdict()}
    raise AssertionError(f"no failure of a service reads {reason!r}")


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `Services`: what each step answered, and the lines of
    `services.jsonl` without their times."""
    clock = [0]
    step: dict[str, Any] = {}
    addresses = dict(scenario["addresses"])

    class Scripted:
        """The service of one name: its start and its stop do what the step in play says."""

        def __init__(self, name: str) -> None:
            self.name = name

        def __enter__(self) -> str | None:
            script = next((s for s in step["starts"] if s["name"] == self.name), None)
            if script is not None:
                clock[0] += script["took"]
                raise RuntimeError(script["error"].removeprefix(_RAISED))
            return addresses.get(self.name)

        def __exit__(self, *exc: object) -> None:
            error = next((s["error"] for s in step["stops"] if s["name"] == self.name), None)
            if error is not None:
                raise RuntimeError(error.removeprefix(_RAISED))

    held: list[list[list[str | None]]] = []

    class Runner:
        """Notes the addresses of the services the task holds as it runs."""

        def config(self, task: Task) -> SimpleNamespace:
            return SimpleNamespace(max_concurrent=None)

        def run(self, task: Task) -> TaskResult:
            held.append([[name, address] for name, address in (services_module._addresses.get() or {}).items()])
            return TaskResult(task=task, ok=True, stop="completed")

    answers: list[Any] = []
    real_time, real_processes = services_module.time, services_module.live_processes
    services_module.time = SimpleNamespace(monotonic=lambda: clock[0])  # pyright: ignore[reportAttributeAccessIssue]
    services_module.live_processes = SimpleNamespace(launches_refused=lambda: step["refused"])  # pyright: ignore[reportAttributeAccessIssue]
    try:
        with tempfile.TemporaryDirectory() as run_dir:
            services = Services(
                {name: Scripted for name in scenario["services"]},
                Path(run_dir),
                plays=lambda task: task.params["plays"],
                cooloff_s=scenario["cooloffS"],
            )
            runner = services.wrap(Runner())
            for step in scenario["steps"]:
                clock[0] = step["now"]
                if step["op"] == "hold":
                    task = Task("step", key=step["key"], claims=tuple(step["claims"]), params={"plays": step["plays"]})
                    result = runner.run(task)
                    if result.ok:
                        answers.append({"held": held[-1]})
                    else:
                        assert result.stop == "launch_failed", result
                        answers.append({"failed": _failure(result.reason)})
                else:
                    services.close(step["cause"])
                    answers.append(None)
            file = Path(run_dir) / layout.SERVICES
            lines = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()] if file.exists() else []
    finally:
        services_module.time, services_module.live_processes = real_time, real_processes
    events = [
        {"event": "start", "name": e["name"], "key": e["key"], "address": e.get("address"), "error": e.get("error")}
        if e["event"] == "start"
        else {"event": "stop", "name": e["name"], "cause": e["cause"], "error": e.get("error")}
        for e in lines
    ]
    return {"answers": answers, "events": events}


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: one to five services, with or without a cool-off, and up to
    twenty-five tasks and ends of the run, with starts that raise, stops that raise, played
    tasks and a signal that stops the run."""
    standing = [name for name in NAMES if rng.random() < 0.7] or ["db"]
    now = 0
    steps = []
    count = rng.randint(3, 25)
    for number in range(count):
        ends = rng.random() < (0.7 if number == count - 1 else 0.04)  # the run's end is the last step of most
        starts = [
            {"name": name, "error": f"{_RAISED}start {number}", "took": rng.choice([0, 1, 3])} for name in standing if rng.random() < 0.3
        ]
        steps.append(
            {
                "op": "close" if ends else "hold",
                "now": now,
                "refused": rng.random() < 0.05,
                "key": f"t{number}",
                "claims": rng.choices(NAMES, k=rng.choice([0, 1, 1, 2, 2, 3])),
                "plays": rng.random() < 0.1,
                "starts": starts,
                "cause": rng.choice(["run_end", "interrupted"]),
                "stops": [{"name": name, "error": f"{_RAISED}stop {number}"} for name in standing if rng.random() < 0.2],
            }
        )
        now += max((s["took"] for s in starts), default=0) + rng.choice([0, 1, 5, 20, 200])
    return {
        "services": standing,
        "variables": [[name, envvars.service(name)] for name in NAMES],
        "addresses": [[name, f"{name}.sock"] for name in standing if rng.random() < 0.6],
        "cooloffS": rng.choice([None, 3, 10, 100]),
        "steps": steps,
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
