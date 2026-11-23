"""Scenarios of the attempts of agent tasks, played on `RetryingRunner` and `AgentRunner` and
on the Lean specification.

    uv run python tests/lean/attempt_scenarios.py     # rewrites tests/lean/attempt_scenarios.jsonl

A scenario is a failover chain, what a kind gives its attempts, and some tasks that run one
after the other on the chain's breaker. Each task scripts its attempts, and each attempt its
rounds: how long the launch takes, which routes rest, what a launch on each route gives,
whether the task is cancelled during the launch, and what other tasks do to the breaker
meanwhile; `lean/Conformance/Runner.lean` has the fields. `play` plays one on the code with
coding agents and credential rests that answer from the script, and returns, for each task,
the results the journal gets, the task's result and the breaker's switches
(`lake exe contraagent-lean attempt`). `tests/lean/attempt_scenarios.jsonl` holds scenarios
(`scenarios`) with what the specification answers for each; `tests/test_lean_scenarios.py`
plays them on the code.
"""

from __future__ import annotations

import importlib.util
import logging
import random
import tempfile
from pathlib import Path
from typing import Any

from contraagent import Task, TaskResult
from contraagent._internal.dispatch.records import Rest, SafetyStop
from contraagent.backends import Backend, LaunchResult, QuotaRefusal, Stop
from contraagent.config import KindConfig, Route
from contraagent.engine import AgentRunner, RetryingRunner, Router, TaskAdapter

FILE = Path(__file__).with_name("attempt_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "attempt"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 30

#: The stops a failover hop is for; none: every stop.
FOR_STOPS: tuple[list[str], ...] = ([], [], [], ["rate_limited"], ["error"], ["refused", "auth_failed"], ["rate_limited", "timeout"])
#: The stops a scripted launch ends on, the likelier first.
STOPS = ("completed", "completed", "completed", "rate_limited", "rate_limited", "error", "auth_failed", "refused", "timeout", "max_turns")


def _result(result: TaskResult) -> dict[str, Any]:
    """The fields of a result that the specification decides."""
    rests = result.cause.rests if result.cause is not None else result.skipped_hops
    return {
        "ok": result.ok,
        "stop": result.stop,
        "route": result.route,
        "hops": [[hop.route, hop.stop] for hop in result.hops],
        "skipped": [[rest.route, "refused" if rest.stop else "quota"] for rest in rests],
    }


def play(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Play `scenario` on a `RetryingRunner` over an `AgentRunner`: for each task, the results
    the journal got, the task's result, and the breaker's switches after it."""
    clock = [0]
    routes = [Route(r["agent"], r["model"], stops=tuple(r["stops"])) for r in scenario["routes"]]
    place = {r.model: i for i, r in enumerate(routes)}  # a route by its model, which no two share
    router = Router(routes[0], tuple(routes[1:]), probe_interval_s=scenario["probeIntervalS"], clock=lambda: clock[0])
    walk: dict[str, Any] = {"attempts": iter(()), "rounds": [], "launched": 0, "task": None}  # the task and the attempt in play

    def script() -> dict[str, Any] | None:
        rounds = walk["rounds"]
        return rounds[walk["launched"]] if walk["launched"] < len(rounds) else None

    class Agent(Backend):
        """A coding agent whose launches end as the round in play says."""

        drivable_model_chain = False

        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = self.binary = name

        def argv(self, launch: Any) -> list[str]:
            return [self.name]

        def env(self, launch: Any) -> dict[str, str]:
            return {}

        def run(self, launch: Any) -> LaunchResult:
            round_ = script()
            walk["launched"] += 1
            if round_ is None:
                return LaunchResult(label=launch.label, agent=self.name, stop=Stop.ERROR, ok=False, model=launch.model)
            given = round_["launch"][place[launch.model]]
            clock[0] += round_["took"]
            for call in round_["meanwhile"]:  # other tasks, on the same breaker
                if call["op"] == "rate_limited":
                    router.rate_limited(routes[call["route"]], call["retryAfterS"], started=clock[0] - call["startedAgo"])
                elif call["op"] == "succeeded":
                    router.succeeded(routes[call["route"]], started=clock[0] - call["startedAgo"])
                else:
                    router.pick()
            if round_["cancel"]:
                runner.cancel(walk["task"])
            stop = Stop(given["stop"])
            return LaunchResult(
                label=launch.label,
                agent=self.name,
                stop=stop,
                ok=stop == Stop.COMPLETED,
                model=launch.model,
                exit_code=-15 if given["signalled"] else None,
                quota_refusal=QuotaRefusal(retry_after_s=given["retryAfterS"]) if stop == Stop.RATE_LIMITED else None,
                safety_stops=[SafetyStop(part="response")] if given["safetyStop"] else [],
            )

    class Rests:
        """Credential rests that answer as the round in play says, by the route's model."""

        def rests(self, name: str, kind: str = "", account: Any = None, agent: str = "", model: str = "") -> list[Rest]:
            round_ = script()
            why = round_["rests"][place[model]] if round_ is not None else None
            if why is None:
                return []
            if why == "refused":
                return [Rest(credential=name, stop="auth_failed", agent=agent, model=model)]
            return [Rest(credential=name, rule="scripted")]

        def resting_members(self, *args: Any, **kwargs: Any) -> set[str]:
            return set()

        def observe(self, reading: Any) -> None:
            return None

        def refuse(self, name: str, agent: str, model: str) -> None:
            return None

    class Begun:
        """The runner, each of whose attempts begins after its script's wait and reads its
        script's rounds."""

        def config(self, task: Task) -> KindConfig:
            return runner.config(task)

        def run(self, task: Task) -> TaskResult:
            attempt = next(walk["attempts"], {"wait": 0, "rounds": []})
            clock[0] += attempt["wait"]
            walk.update(rounds=attempt["rounds"], launched=0, task=task)
            return runner.run(task)

    class Unhurried(RetryingRunner):
        """A fresh attempt follows at once."""

        backoff = staticmethod(lambda base, attempt: 0.0)

    kind = KindConfig(
        agent=routes[0].agent,
        model=routes[0].model,
        max_turns=3,
        timeout_s=10,
        retries=scenario["retries"],
        max_turns_growth=1.0 if scenario["sameTurnCap"] else 2.0,
        safety_stop_failover=("response",),
    )
    answers = []
    quiet = logging.getLogger("contraagent")
    level = quiet.level
    quiet.setLevel(logging.CRITICAL)  # each failover is a warning
    try:
        with tempfile.TemporaryDirectory() as run_dir:
            runner = AgentRunner(
                {name: Agent(name) for name in dict.fromkeys(r.agent for r in routes)},
                {"k": kind},
                run_dir=run_dir,
                adapter=TaskAdapter(),
                routers={"k": router},
                cwd=run_dir,
                rests=Rests(),  # pyright: ignore[reportArgumentType]
            )
            journal: list[dict[str, Any]] = []
            retrying = Unhurried(Begun(), on_attempt=lambda result: journal.append(_result(result)))  # pyright: ignore[reportArgumentType]
            for number, task_script in enumerate(scenario["tasks"]):
                journal.clear()
                walk["attempts"] = iter(task_script["attempts"])
                result = retrying.run(Task("k", key=f"t{number}"))
                answers.append(
                    {"journaled": list(journal), "result": _result(result), "switches": [list(pair) for pair in router.history()]}
                )
    finally:
        quiet.setLevel(level)
    return answers


def _round(rng: random.Random, n: int, calm: bool) -> dict[str, Any]:
    """One round of an attempt on a chain of `n` routes."""
    return {
        "took": rng.choice([0, 1, 5, 60]),
        "rests": [None if calm or rng.random() < 0.8 else rng.choice(["quota", "refused"]) for _ in range(n)],
        "launch": [
            {
                "stop": (stop := rng.choice(STOPS)),
                "signalled": stop != "completed" and rng.random() < 0.08,
                "safetyStop": rng.random() < 0.1,
                "retryAfterS": rng.choice([None, None, 0, 30, 5000]),
            }
            for _ in range(n)
        ],
        "cancel": rng.random() < 0.04,
        "meanwhile": [
            {
                "op": rng.choice(["rate_limited", "rate_limited", "succeeded", "pick"]),
                "route": rng.randrange(n),
                "retryAfterS": rng.choice([None, 0, 30]),
                "startedAgo": rng.choice([0, 1, 30, 2000]),
            }
            for _ in range(rng.choice([0, 0, 0, 1, 2]))
        ],
    }


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: a chain of one to four routes, some of them for some stops only,
    and one to six tasks of up to three attempts, with rate limits, failures, refused
    credentials, safety stops, resting credentials, cancels, and other tasks' 429s. An
    attempt scripts its first rounds; in a round after them no route rests and every launch
    ends `error`."""
    n = rng.randint(1, 4)
    routes = [
        {
            "agent": rng.choice(["claude", "omp"]),
            "model": f"m{i}",
            "stops": [] if i == 0 else rng.choice(FOR_STOPS),
        }
        for i in range(n)
    ]
    retries = rng.choice([0, 1, 2])
    calm = rng.random() < 0.4  # no credential rests in the whole scenario
    tasks = [
        {
            "attempts": [
                {"wait": rng.choice([0, 1, 20, 1000, 8000]), "rounds": [_round(rng, n, calm) for _ in range(rng.randint(1, 4))]}
                for _ in range(retries + 1)
            ]
        }
        for _ in range(rng.randint(1, 6))
    ]
    probe = rng.choice([10, 900])
    return {"routes": routes, "probeIntervalS": probe, "retries": retries, "sameTurnCap": rng.random() < 0.7, "tasks": tasks}


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
