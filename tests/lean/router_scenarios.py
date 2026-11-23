"""Scenarios of the failover breaker, played on `Router` and on the Lean specification.

    uv run python tests/lean/router_scenarios.py     # rewrites tests/lean/router_scenarios.jsonl

A scenario is a chain of routes and a list of calls of a `Router`, each at a time the scenario
gives; `lean/Conformance/Router.lean` has its fields. `play` plays one on `Router` and returns
what each call answered and the switches recorded, as the specification writes them
(`lake exe contraagent-lean router`). `tests/lean/router_scenarios.jsonl` holds scenarios
(`scenarios`) with what the specification answers for each; `tests/test_lean_scenarios.py`
plays them on the code.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path
from typing import Any

from contraagent.config import Route
from contraagent.engine import Router

FILE = Path(__file__).with_name("router_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "router"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 100


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Play `scenario` on a `Router`: what each call answered, and the switches recorded."""
    clock = [0.0]
    routes = [Route(r["agent"], r["model"], r["credential"], tuple(r["stops"])) for r in scenario["routes"]]
    router = Router(
        routes[scenario["primary"]],
        tuple(routes[i] for i in scenario["fallbacks"]),
        probe_interval_s=scenario["probeIntervalS"],
        max_probe_interval_s=scenario["maxProbeIntervalS"],
        clock=lambda: clock[0],
    )

    def named(route: Route | None) -> str | None:
        return None if route is None else str(route)

    answers: list[str | None] = []
    for step in scenario["steps"]:
        clock[0] = step["now"]
        route = None if step["route"] is None else routes[step["route"]]
        op = step["op"]
        if op == "pick":
            answers.append(named(router.pick()))
        elif op == "look":
            answers.append(named(router.pick(probe=False)))
        elif op == "active":
            answers.append(named(router.active()))
        elif op == "rate_limited":
            answers.append(router.rate_limited(route, step["retryAfterS"], started=step["started"]))
        elif op == "succeeded":
            router.succeeded(route, started=step["started"])
            answers.append(None)
        else:
            answers.append(None if route is None else named(router.next_route_after(route, step["stop"])))
    return {"answers": answers, "switches": [list(pair) for pair in router.history()]}


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: a chain of one to four hops, some for some stops only, a fallback
    that is the primary again, a route of no chain, and up to thirty calls at times that
    pass the cool-off or do not, with launches begun before or after the breaker moved."""
    n = rng.randint(1, 4)
    routes = [
        {
            "agent": rng.choice(["claude", "omp"]),
            "model": f"m{i}",
            "credential": rng.choice(["", "", "ambient", "team"]),
            "stops": rng.choice([[], [], [], ["rate_limited"], ["api_error"], ["rate_limited", "timeout"]]),
        }
        for i in range(n)
    ]
    fallbacks = list(range(1, n))
    if rng.random() < 0.2:  # the primary again, as a fallback: no hop of its own
        routes.append({**routes[0], "stops": []})
        fallbacks.insert(rng.randint(0, len(fallbacks)), len(routes) - 1)
    routes.append({"agent": "pi", "model": "elsewhere", "credential": "", "stops": []})  # of no chain
    probe = rng.choice([10, 900])
    now = 0
    steps = []
    for _ in range(rng.randint(3, 30)):
        now += rng.choice([0, 1, 5, 20, 1000, 8000])
        op = rng.choices(["pick", "look", "active", "rate_limited", "succeeded", "next_route_after"], [30, 8, 5, 32, 20, 5])[0]
        steps.append(
            {
                "now": now,
                "op": op,
                "route": None if rng.random() < 0.08 else rng.randrange(len(routes)),
                "retryAfterS": rng.choice([None, None, 0, 5, 100, 100000]),
                "started": rng.choice([None, now, now - 1, now - 10, now - 2000]),
                "stop": rng.choice(["", "rate_limited", "api_error", "timeout"]),
            }
        )
    return {
        "routes": routes,
        "primary": 0,
        "fallbacks": fallbacks,
        "probeIntervalS": probe,
        "maxProbeIntervalS": probe * rng.choice([1, 4, 8]),
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
