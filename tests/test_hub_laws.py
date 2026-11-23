"""The laws of the hub's logs on random scenarios, those of `tests/lean/hub_scenarios.py`:
appends that overlap what the hub holds, continue it or leave a gap, seals that fail,
processes that die at a step of a seal, starts on what they left, an index that lost its rows,
sweeps and drops.

After every step, each log reads as the first lines of what its relay holds, the durable
lines are among the lines held, and they are no fewer than before unless the run was dropped
or the index lost its rows. After the last step, every index row has its object."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent / "lean"


def _scenarios() -> Any:
    spec = importlib.util.spec_from_file_location("lean_hub_scenarios", HERE / "hub_scenarios.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hub = _scenarios()


def relay_copy(scenario: dict[str, Any]) -> dict[tuple[str, ...], dict[int, str]]:
    """Each log as its relay holds it: every line the scenario sends, by its number."""
    logs: dict[tuple[str, ...], dict[int, str]] = {}
    for step in scenario["steps"]:
        if step["op"] == "append":
            log = logs.setdefault(tuple(step["key"]), {})
            for i, line in enumerate(step["lines"]):
                assert log.setdefault(step["offset"] + i, line) == line, "the scenario sends two lines under one number"
    return logs


def test_a_log_reads_as_its_relay_sent_it_whatever_fails_or_dies():
    for number, scenario in enumerate(hub.scenarios(20261124, 150)):
        sent = relay_copy(scenario)
        steps: list[dict[str, Any]] = []
        for step in scenario["steps"]:  # after each step, ask of every log
            steps.append(step)
            for key in hub.LOGS:
                asked = {**step, "key": list(key), "fault": None, "loseIndex": False}
                steps += [{**asked, "op": "held"}, {**asked, "op": "read", "since": 0, "limit": None}]
        shown = hub.play({**scenario, "steps": steps})
        answers = iter(shown["answers"])
        durable = dict.fromkeys(hub.LOGS, 0)
        for at, step in enumerate(scenario["steps"]):
            next(answers)
            for key in hub.LOGS:
                (held, safe), read = next(answers), next(answers)
                where = (number, at, step["op"], key)
                assert read["lines"] == [sent.get(key, {}).get(i) for i in range(read["total"])], where
                assert safe <= held == read["total"], where
                forgotten = step["loseIndex"] or (step["op"] == "drop" and tuple(step["key"][:2]) == key[:2])
                assert safe >= durable[key] or forgotten, (where, durable[key], safe)
                durable[key] = safe
        assert set(shown["kept"]["rows"]) <= set(shown["kept"]["objects"]), number
