"""Scenarios of a resume, played on `resume_skip` and on the Lean specification.

    uv run python tests/lean/resume_scenarios.py     # rewrites tests/lean/resume_scenarios.jsonl

A scenario is each key's last journal row, the tasks a resume is asked about, in order, and
the keys whose output no longer reads; `lean/Conformance/Run.lean` has its fields. `play`
plays one on `resume_skip` and returns whether each task is skipped and why each task that an
earlier attempt finished runs again (`lake exe contraagent-lean resume`).
`tests/lean/resume_scenarios.jsonl` holds scenarios (`scenarios`) with what the specification
answers for each; `tests/test_lean_scenarios.py` plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path
from typing import Any

from contraagent import Task
from contraagent._internal.dispatch.task import Origin, fingerprint_of
from contraagent._internal.execution.run import resume_skip

FILE = Path(__file__).with_name("resume_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "resume"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 80


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on `resume_skip`: whether each task is skipped, and the reasons by key."""
    last = {
        row["key"]: {
            "key": row["key"],
            "ok": row["ok"],
            "stop": row["stop"],
            "fingerprint": row["fingerprint"],
            "fingerprint_parts": dict(row["fingerprintParts"]),
            "outside": row["outside"],
            "output_of_after": row["outputOfAfter"],
            "output_of_file": row["outputOfFile"],
        }
        for row in scenario["rows"]
    }
    unread = set(scenario["unread"])
    reruns: dict[str, str] = {}
    skip = resume_skip(last, reruns, reads=lambda task: task.key not in unread)
    skips = [
        skip(
            Task(
                t["kind"],
                unit=t["unit"],
                key=t["key"],
                fingerprint=t["fingerprint"],
                fingerprint_parts=dict(t["fingerprintParts"]),
                outside=t["outside"],
                rerun_on_resume=t["rerunOnResume"],
                fingerprint_at_start=t["fingerprintAtStart"],
                origin=Origin(given_from=tuple(t["givenFrom"]), created_from=tuple(t["createdFrom"])) if t["hasOrigin"] else None,
            )
        )
        for t in scenario["tasks"]
    ]
    return {"skips": skips, "reruns": [list(item) for item in sorted(reruns.items())]}


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: up to seven tasks, most with a row of an earlier attempt that
    differs in no part, in one, or in its kind; tasks that fill in one of two files, whose
    digests are few, so that the two files hold the same content at times; rows that are not
    ok or partial, outside states, tasks that rerun on resume, and outputs that no longer read."""
    digests = ["d0", "d1", "d2", "d3"]
    files = ["out/sheet/a.json", "out/sheet/b.json"]
    rows: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    keys: list[str] = []
    for i in range(rng.randint(1, 7)):
        key = f"k{i}"
        kind, unit = rng.choice(["write", "fill"]), rng.choice(["a", "b"])
        parts = {"definition": rng.choice(["def1", "def2"]), "params": rng.choice(["p1", "p2"])}
        if rng.random() < 0.3:
            parts["input_files"] = rng.choice(["i1", "i2"])
        outside = rng.choice(["o1", "o2"]) if rng.random() < 0.3 else ""
        if outside:
            parts["outside"] = outside
        fills = rng.random() < 0.45
        earlier, earlier_kind, earlier_outside = dict(parts), kind, outside
        for name in list(earlier):  # what the earlier attempt differed in
            if rng.random() < 0.15:
                earlier[name] = earlier[name] + "-before"
        if rng.random() < 0.08:
            earlier.pop(rng.choice(list(earlier)))
        if rng.random() < 0.08:
            earlier_kind = "other"
        if outside and "outside" in earlier:
            earlier_outside = earlier["outside"]
        elif rng.random() < 0.1:
            earlier_outside = "o-before"
        after, file = "", ""
        if fills:
            file = rng.choice(files)
            earlier["output_of"] = rng.choice(digests)  # the file as the earlier attempt found it
            after = rng.choice([*digests, ""])
            parts["output_of"] = after if after and rng.random() < 0.55 else rng.choice(digests)  # as it is now
        spliced = None
        if rng.random() < 0.88:
            named = rng.random() < 0.9
            rows.append(
                {
                    "key": key,
                    "ok": (ok := rng.random() < 0.85),
                    "stop": rng.choice(["completed"] * 6 + ["partial"]) if ok else rng.choice(["error", "cancelled"]),
                    "fingerprint": fingerprint_of(earlier_kind, unit, key, earlier) if rng.random() < 0.95 else "",
                    "fingerprintParts": sorted(earlier.items()) if named else [],
                    "outside": earlier_outside,
                    "outputOfAfter": after,
                    "outputOfFile": file,
                }
            )
            if "output_of" in parts and named and "output_of" in earlier:
                spliced = fingerprint_of(kind, unit, key, {**parts, "output_of": earlier["output_of"]})
        tasks.append(
            {
                "key": key,
                "kind": kind,
                "unit": unit,
                "fingerprint": fingerprint_of(kind, unit, key, parts),
                "fingerprintParts": sorted(parts.items()) if rng.random() < 0.93 else [],
                "outside": outside,
                "rerunOnResume": rng.random() < 0.08,
                "fingerprintAtStart": fills or bool(outside) or rng.random() < 0.1,
                "hasOrigin": (flowed := rng.random() < 0.8),
                "givenFrom": [k for k in keys if flowed and rng.random() < 0.3],
                "createdFrom": [k for k in keys if flowed and rng.random() < 0.3],
                "spliced": spliced,
            }
        )
        keys.append(key)
    return {"rows": rows, "tasks": tasks, "unread": [k for k in keys if rng.random() < 0.1]}


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
