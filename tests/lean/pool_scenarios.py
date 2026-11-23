"""Scenarios of a credential pool, played on `CredentialPool` and on the Lean specification.

    uv run python tests/lean/pool_scenarios.py     # rewrites tests/lean/pool_scenarios.jsonl

A scenario is a pool's members, its strategy and its cool-down, and a list of calls of a
`CredentialPool`, each at a time the scenario gives; `lean/Conformance/Pool.lean` has its
fields. `play` plays one on `CredentialPool` and returns what each call answered
(`lake exe contraagent-lean pool`). `tests/lean/pool_scenarios.jsonl` holds scenarios
(`scenarios`) with what the specification answers for each; `tests/test_lean_scenarios.py`
plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path
from typing import Any

from contraagent._internal.backends.credentials import Pool, Subscription
from contraagent._internal.routing.pool import CredentialPool

FILE = Path(__file__).with_name("pool_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "pool"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 100


def play(scenario: dict[str, Any]) -> list[str | None]:
    """Play `scenario` on a `CredentialPool`: what each call answered."""
    clock = [0.0]
    members = {name: Subscription(name=name) for name in scenario["members"]}
    strategy = "round_robin" if scenario["roundRobin"] else "in_order"
    pool = CredentialPool(
        Pool(name="pool", members=tuple(members), strategy=strategy, cooldown_s=scenario["cooldownS"]),
        list(members.values()),
        clock=lambda: clock[0],
    )
    answers: list[str | None] = []
    for step in scenario["steps"]:
        clock[0] = step["now"]
        if step["op"] == "pick":
            picked = pool.pick(step["model"], step["exclude"])
            answers.append(None if picked is None else picked.label)
        else:
            pool.rate_limited(members[step["member"]], step["model"], step["retryAfterS"])
            answers.append(None)
    return answers


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: one to four members, in order or in a round robin, and up to thirty
    picks and 429s on two models, at times within and past the cool-downs."""
    members = [f"m{i}" for i in range(rng.randint(1, 4))]
    cooldown = rng.choice([10, 900])
    now = 0
    steps = []
    for _ in range(rng.randint(3, 30)):
        now += rng.choice([0, 1, 5, 20, 1000])
        steps.append(
            {
                "now": now,
                "op": rng.choices(["pick", "rate_limited"], [65, 35])[0],
                "model": rng.choice(["", "", "opus"]),
                "exclude": [m for m in members if rng.random() < 0.15],
                "member": rng.choice(members),
                "retryAfterS": rng.choice([None, None, 0, 3, 5000]),
            }
        )
    return {"members": members, "roundRobin": rng.random() < 0.5, "cooldownS": cooldown, "steps": steps}


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
