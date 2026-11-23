"""The code answers what its Lean specification does, scenario by scenario, for each part
of `PARTS`. A module of `tests/lean/` says what a scenario of one part is, makes scenarios
and plays one on the code. The committed scenarios need no Lean; fresh ones are played on
both sides under `-m lean`."""

from __future__ import annotations

import importlib.util
import json
import random
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

HERE = Path(__file__).parent / "lean"


def _module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"lean_{name}", HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exe = _module("exe")
#: What is specified, with the module of its scenarios.
NAMES = ("queue", "router", "resume", "graph", "capacity", "pool", "services", "attempt", "rests", "hub")
PARTS = {name: _module(f"{name}_scenarios") for name in NAMES}
COMMITTED = {name: [json.loads(line) for line in part.FILE.read_text(encoding="utf-8").splitlines()] for name, part in PARTS.items()}
CASES = [(name, number) for name, entries in COMMITTED.items() for number in range(len(entries))]


def difference(code: Any, specified: Any) -> str:
    """Where what the code and the specification answer part, with what is around that place."""
    if isinstance(code, dict) and isinstance(specified, dict):
        key = next((k for k in specified if code.get(k) != specified[k]), None)
        return f"{key}: " + difference(code.get(key), specified.get(key)) if key is not None else f"{code} and {specified}"
    if not isinstance(code, list) or not isinstance(specified, list):
        return f"the code answers {code}, the specification {specified}"
    at = next((i for i, (a, b) in enumerate(zip(code, specified, strict=False)) if a != b), min(len(code), len(specified)))
    return f"place {at}: the code answers {code[max(0, at - 2) : at + 2]}, the specification {specified[max(0, at - 2) : at + 2]}"


def rewrite(name: str) -> str:
    return f"rewrite it: uv run python tests/lean/{name}_scenarios.py"


@pytest.mark.parametrize("name", PARTS)
def test_the_committed_scenarios_are_the_generator_s(name: str):
    part = PARTS[name]
    assert COMMITTED[name], f"{part.FILE.name} holds no scenario"
    made = json.loads(json.dumps(part.scenarios(part.SEED, part.COUNT)))  # as JSON holds them
    assert [entry["scenario"] for entry in COMMITTED[name]] == made, (
        f"{part.FILE.name} does not hold the scenarios of its generator; {rewrite(name)}"
    )


@pytest.mark.parametrize(("name", "number"), CASES)
def test_the_code_answers_what_its_specification_does(name: str, number: int):
    entry = COMMITTED[name][number]
    code = json.loads(json.dumps(PARTS[name].play(entry["scenario"])))
    assert code == entry["specified"], difference(code, entry["specified"])


@pytest.mark.lean
@pytest.mark.parametrize("name", PARTS)
def test_the_committed_answers_are_what_the_specification_gives(name: str):
    assert shutil.which("lake"), "this test needs Lean (lake) on PATH"
    given = [entry["scenario"] for entry in COMMITTED[name]]
    assert exe.specified(PARTS[name].WHAT, given) == [entry["specified"] for entry in COMMITTED[name]], (
        f"{PARTS[name].FILE.name} is not what the specification gives now; {rewrite(name)}"
    )


@pytest.mark.lean
@pytest.mark.parametrize("name", PARTS)
def test_fresh_scenarios_are_answered_alike(name: str):
    """Scenarios nobody has seen, from a seed the failure names: 400 of them."""
    assert shutil.which("lake"), "this test needs Lean (lake) on PATH"
    part = PARTS[name]
    seed = random.SystemRandom().randrange(10**9)
    given = part.scenarios(seed, 400)
    for number, (scenario, specified) in enumerate(zip(given, exe.specified(part.WHAT, given), strict=True)):
        code = json.loads(json.dumps(part.play(scenario)))
        assert code == specified, f"scenario {number} of {name}_scenarios.scenarios({seed}, 400): {difference(code, specified)}"
