"""Scenarios of a run's credential rests, played on `CredentialRests` and on the Lean
specification.

    uv run python tests/lean/rests_scenarios.py     # rewrites tests/lean/rests_scenarios.jsonl

A scenario is some credentials with their caps, a pool, the finishing kinds and the grace
window, and a list of steps, each at a time of day and a reading of the clock that only moves
forward: a reading observed, a launch refused, or a question (`rests`, `resting_members`)
with what the quota rule and the accounts answer then; `lean/Conformance/Quota.lean` has the
fields. A time is a number of seconds after `EPOCH`. `play` plays one on `CredentialRests`
and returns what each step answered and what `on_change` was told
(`lake exe contraagent-lean rests`). `tests/lean/rests_scenarios.jsonl` holds scenarios
(`scenarios`) with what the specification answers for each; `tests/test_lean_scenarios.py`
plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from contraagent._internal.backends.credentials import Credential, Pool, Subscription
from contraagent._internal.dispatch.records import WINDOWS, QuotaReading, QuotaWindow, Rest
from contraagent._internal.routing.quota import CredentialRests
from contraagent._internal.runs.times import parse_iso

FILE = Path(__file__).with_name("rests_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "rests"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 40

#: The time a scenario's times count from.
EPOCH = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
NAMES = ("c0", "c1", "c2")
POOL = "p"


def _iso(seconds: int | None) -> str | None:
    return None if seconds is None else (EPOCH + timedelta(seconds=seconds)).isoformat()


def _seconds(text: str) -> int | None:
    at = parse_iso(text)
    return None if at is None else round((at - EPOCH).total_seconds())


def _rest(rest: Rest) -> dict[str, Any]:
    """The fields of a rest that the specification decides."""
    return {
        "credential": rest.credential,
        "window": rest.window,
        "pct": None if rest.pct is None else round(rest.pct),
        "cap": None if rest.cap is None else round(rest.cap),
        "rule": rest.rule,
        "until": _seconds(rest.until),
        "account": rest.account,
        "stop": rest.stop,
        "agent": rest.agent,
        "model": rest.model,
    }


def _reading(given: dict[str, Any]) -> QuotaReading:
    return QuotaReading(
        observed_at=_iso(given["observedAt"]),
        credential=given["credential"],
        account=given["account"],
        five_hour_pct=given["fiveHourPct"],
        five_hour_resets_at=_iso(given["fiveHourResetsAt"]),
        seven_day_pct=given["sevenDayPct"],
        seven_day_resets_at=_iso(given["sevenDayResetsAt"]),
        windows={w["name"]: QuotaWindow(pct=w["pct"], resets_at=_iso(w["resetsAt"])) for w in given["windows"]},
    )


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `CredentialRests`: what each step answered, and what `on_change`
    was told."""
    assert [[name, round(spec.length.total_seconds())] for name, spec in WINDOWS.items()] == scenario["windows"]
    step: dict[str, Any] = {}
    caps: dict[str, dict[str, float]] = {}
    for cap in scenario["caps"]:
        caps.setdefault(cap["credential"], {})[f"max_{cap['window']}_pct"] = cap["cap"]
    credentials: dict[str, Credential] = {name: Subscription(name=name, **caps.get(name, {})) for name in NAMES}
    for name, members in scenario["pools"]:
        credentials[name] = Pool(name=name, members=tuple(members), **caps.get(name, {}))

    def rule(credential: str, reading: QuotaReading) -> str | tuple[str, datetime] | None:
        said = next((r for r in step["rule"] if r["credential"] == credential), None)
        if said is None:
            return None
        return said["said"] if said["end"] is None else (said["said"], EPOCH + timedelta(seconds=said["end"]))

    events: list[list[Any]] = []
    rests = CredentialRests(
        credentials,
        rule if scenario["hasRule"] else None,
        finishing_kinds=scenario["finishingKinds"],
        grace_s=scenario["graceS"],
        on_change=lambda event, rest: events.append([event, _rest(rest)]),
        now=lambda: EPOCH + timedelta(seconds=step["now"]),
        clock=lambda: step["clock"],
    )
    answers: list[Any] = []
    for step in scenario["steps"]:
        accounts = dict(step["accounts"])
        asked = (step["name"], step["kind"], lambda name: accounts.get(name, ""), step["agent"], step["model"])  # noqa: B023
        if step["op"] == "observe":
            rests.observe(_reading(step["reading"]))
            answers.append(None)
        elif step["op"] == "refuse":
            rests.refuse(step["name"], step["agent"], step["model"])
            answers.append(None)
        elif step["op"] == "resting_members":
            resting = rests.resting_members(*asked)
            answers.append([m for m in credentials[step["name"]].members if m in resting] if step["name"] == POOL else [])  # pyright: ignore[reportAttributeAccessIssue]
        else:
            answers.append([_rest(rest) for rest in rests.rests(*asked)])
    return {"answers": answers, "events": events}


#: The lengths of time a scenario steps by and counts resets, ends and the grace window in:
#: with few of them, a question often falls on the very time a reset or an end names.
SPANS = (0, 1, 300, 600, 6600, 7200, 18000)


def _observed(rng: random.Random, now: int) -> dict[str, Any]:
    """A reading that arrives at `now`."""
    return {
        "observedAt": None if rng.random() < 0.08 else now - rng.choice([0, 0, 600, 18000, 18001]),
        "credential": rng.choice([*NAMES, *NAMES, *NAMES, ""]),
        "account": rng.choice(["", "", "", "a1", "a2"]),
        "fiveHourPct": rng.choice([None, 20, 80, 85, 97]),
        "fiveHourResetsAt": rng.choice([None, now - 300, now + 600, now + 7200]),
        "sevenDayPct": rng.choice([None, 40, 95, 96]),
        "sevenDayResetsAt": rng.choice([None, now + 600, now + 200000]),
        "windows": [
            {
                "name": rng.choice(["seven_day_opus", "five_hour"]),
                "pct": rng.choice([None, 50]),
                "resetsAt": rng.choice([None, now + 300, now + 50000]),
            }
            for _ in range(rng.choice([0, 0, 0, 1]))
        ],
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: three credentials and a pool of some of them, with or without caps
    and a quota rule, and up to thirty steps: readings of two accounts, refused launches, and
    questions for tasks of a finishing kind and of another, at, before and after the resets,
    the rule's ends and the end of the grace window."""
    caps = [
        {"credential": name, "window": window, "cap": rng.choice([80, 95])}
        for name in (*NAMES, POOL)
        for window in ("five_hour", "seven_day")
        if rng.random() < 0.6
    ]
    members = [name for name in NAMES if rng.random() < 0.7] or [NAMES[0]]
    now = clock = 0
    steps = []
    for _ in range(rng.randint(4, 30)):
        passed = rng.choice(SPANS)
        now, clock = now + passed, clock + passed
        op = rng.choices(["observe", "refuse", "rests", "resting_members"], [30, 3, 57, 10])[0]
        steps.append(
            {
                "op": op,
                "now": now,
                "clock": clock,
                "name": POOL if op == "resting_members" else rng.choice([*NAMES, *NAMES, POOL]),
                "kind": rng.choice(["work", "work", "wrapup"]),
                "agent": rng.choice(["claude", "omp"]),
                "model": rng.choice(["m1", "m2"]),
                "reading": _observed(rng, now) if op == "observe" else None,
                "rule": [
                    {
                        "credential": name,
                        "said": rng.choice(["pace", "pace", ""]),
                        "end": rng.choice([None, now - 300, now, now + 600, now + 7200]),
                    }
                    for name in NAMES
                    if rng.random() < 0.5
                ],
                "accounts": [[name, rng.choice(["", "", "a1", "a2"])] for name in NAMES],
            }
        )
    return {
        "windows": [["five_hour", 18000], ["seven_day", 604800]],
        "caps": caps,
        "pools": [[POOL, members]],
        "finishingKinds": ["wrapup"],
        "graceS": rng.choice([0, 600, 7200]),
        "hasRule": rng.random() < 0.7,
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
