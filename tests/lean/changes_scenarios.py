"""Scenarios of the changes patterns, played on `may_overlap` and `overlap` and on the Lean
specification.

    uv run python tests/lean/changes_scenarios.py     # rewrites tests/lean/changes_scenarios.jsonl

A scenario is two tasks' `changes` patterns and the real path of each task's working
directory; `lean/Conformance/Changes.lean` has its fields. `play` returns the pair of
patterns that may cover one file when both are read from one directory (`may_overlap`), and
when each is read from its own (`overlap`), as the specification writes them (`lake exe
contraagent-lean changes`). `tests/lean/changes_scenarios.jsonl` holds scenarios
(`scenarios`) with what the specification answers for each; `tests/test_lean_scenarios.py`
plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path
from typing import Any

from contraagent._internal.execution.changes import may_overlap, overlap

FILE = Path(__file__).with_name("changes_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "changes"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261126, 300

#: The segments patterns are made of: names, wildcards, sets (one with no closing bracket,
#: which is a character), `**`, `.` and letters in either case.
SEGMENTS = ["a", "b", "A", "ab", "ba", "a*", "*b", "*", "?", "a?", "[ab]", "[!a]x", "x[", "**", ".", "a.md", "*.md", "B*"]
#: The working directories: one, one under it, one under that, the first in other case, and one apart.
DIRS = ["/w", "/w/a", "/w/a/b", "/W/A", "/x"]


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """What `may_overlap` and `overlap` answer for `scenario`."""
    a, b = scenario["a"], scenario["b"]
    pair = may_overlap(a, b)
    found = overlap(Path(scenario["dirA"]), a, Path(scenario["dirB"]), b)
    return {"mayOverlap": list(pair) if pair else None, "overlap": list(found) if found else None}


def pattern(rng: random.Random) -> str:
    segs = [rng.choice(SEGMENTS) for _ in range(rng.randint(1, 3))]
    text = ("\\" if rng.random() < 0.1 else "/").join(segs)
    return ("!" if rng.random() < 0.1 else "") + text


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: up to three patterns a task, from `SEGMENTS`, some separated by
    `\\`, some leaving paths out (`!`), in two of `DIRS`."""
    return {
        "a": [pattern(rng) for _ in range(rng.randint(0, 3))],
        "b": [pattern(rng) for _ in range(rng.randint(0, 3))],
        "dirA": rng.choice(DIRS),
        "dirB": rng.choice(DIRS),
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
