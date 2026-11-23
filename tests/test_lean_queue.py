"""`WorkQueue` reports what its Lean specification does (`lean/Contraagent/Dispatch/Queue.lean`),
scenario by scenario: `tests/lean/queue_scenarios.py` has what a scenario is and plays one on
the code. The committed scenarios need no Lean; fresh ones are played on both under `-m lean`."""

from __future__ import annotations

import importlib.util
import json
import random
import shutil
from pathlib import Path
from types import ModuleType

import pytest

HERE = Path(__file__).parent / "lean"


def _scenarios_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lean_queue_scenarios", HERE / "queue_scenarios.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scenarios = _scenarios_module()
COMMITTED = [json.loads(line) for line in scenarios.FILE.read_text(encoding="utf-8").splitlines()]
REWRITE = "rewrite it: uv run python tests/lean/queue_scenarios.py"


def difference(code: list, specified: list) -> str:
    """Where two lists of events part, with the events around that place."""
    at = next((i for i, (a, b) in enumerate(zip(code, specified, strict=False)) if a != b), min(len(code), len(specified)))
    return f"event {at}: the code reports {code[max(0, at - 2) : at + 2]}, the specification {specified[max(0, at - 2) : at + 2]}"


def test_the_committed_scenarios_are_the_generator_s():
    made = json.loads(json.dumps(scenarios.scenarios(scenarios.SEED, scenarios.COUNT)))  # as JSON holds them
    assert [entry["scenario"] for entry in COMMITTED] == made, (
        f"tests/lean/queue_scenarios.jsonl does not hold the scenarios of its generator; {REWRITE}"
    )


@pytest.mark.parametrize("number", range(len(COMMITTED)))
def test_the_queue_reports_what_its_specification_does(number: int):
    entry = COMMITTED[number]
    code = scenarios.play(entry["scenario"])
    assert code == entry["events"], difference(code, entry["events"])


@pytest.mark.lean
def test_the_committed_events_are_what_the_specification_reports():
    assert shutil.which("lake"), "this test needs Lean (lake) on PATH"
    assert scenarios.specified([entry["scenario"] for entry in COMMITTED]) == [entry["events"] for entry in COMMITTED], (
        f"tests/lean/queue_scenarios.jsonl is not what the specification reports now; {REWRITE}"
    )


@pytest.mark.lean
def test_fresh_scenarios_are_reported_alike():
    """Scenarios nobody has seen, from a seed the failure names: 400 of them."""
    assert shutil.which("lake"), "this test needs Lean (lake) on PATH"
    seed = random.SystemRandom().randrange(10**9)
    given = scenarios.scenarios(seed, 400)
    for number, (scenario, specified) in enumerate(zip(given, scenarios.specified(given), strict=True)):
        code = scenarios.play(scenario)
        assert code == specified, f"scenario {number} of scenarios({seed}, 400): {difference(code, specified)}"
