"""Scenarios of the work queue, played on `WorkQueue` and on the Lean specification.

    uv run python tests/lean/queue_scenarios.py     # rewrites tests/lean/queue_scenarios.jsonl

A scenario is a queue's configuration, its tasks, and a script for everything the queue does
not decide; `lean/Conformance/Queue.lean` has its fields and the rules of its virtual time.
`play` plays one on `WorkQueue` and returns what the queue reported, as the specification
writes it (`lake exe contraagent-lean queue`). `tests/lean/queue_scenarios.jsonl` holds
scenarios (`scenarios`) with what the specification reports for each;
`tests/test_lean_queue.py` plays them on the code.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import contraagent._internal.dispatch.queue as queue_module
from contraagent import DeferralCause, Task, TaskResult
from contraagent._internal.dispatch.task import TimeBox
from contraagent.engine import Deferral, WorkQueue

ROOT = Path(__file__).resolve().parents[2]
FILE = Path(__file__).with_name("queue_scenarios.jsonl")

#: Where elan keeps the Lean it installed: the home of the user running this, read before a
#: test is given an empty home of its own, where elan would install Lean again.
ELAN_HOME = os.environ.get("ELAN_HOME") or str(Path.home() / ".elan")
#: Where the clock starts (`Conformance.startAt`).
START_AT = 1000
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261123, 150


class Clock:
    """The queue's clock: it moves only when the play moves it."""

    def __init__(self) -> None:
        self.now = float(START_AT)

    def monotonic(self) -> float:
        return self.now


def play(scenario: dict[str, Any]) -> list[list[Any]]:
    """Play `scenario` on a `WorkQueue`: the events it reported, the earliest first."""
    clock = Clock()
    saved = queue_module.time, queue_module.random
    queue_module.time = clock  # type: ignore[assignment]
    queue_module.random = SimpleNamespace(uniform=lambda low, high: high)  # type: ignore[assignment]  # the retry wait in full
    try:
        return _play(scenario, clock)
    finally:
        queue_module.time, queue_module.random = saved


def _task(spec: dict[str, Any]) -> Task:
    return Task(
        spec["kind"],
        id=spec["id"],
        key=spec["key"],
        after=tuple(spec["after"]),
        claims=tuple(spec["claims"]),
        estimate_s=spec["estimateS"],
        tail_s=spec["tailS"],
        priority=spec["priority"],
        fingerprint_at_start=spec["fingerprintAtStart"],
        time_boxes=tuple(
            TimeBox(b["deadlineAt"], b["deadlineS"], b["graceS"], b["slackS"], frozenset(b["finishingKinds"]), b["flowCall"])
            for b in spec["timeBoxes"]
        ),
    )


def _play(sc: dict[str, Any], clock: Clock) -> list[list[Any]]:
    tasks = {spec["id"]: _task(spec) for spec in sc["tasks"]}
    kind_caps, estimates = dict(sc["kindCaps"]), dict(sc["estimates"])
    follow_ups, outcomes, durations, cancels = dict(sc["followUps"]), dict(sc["outcomes"]), dict(sc["durations"]), dict(sc["cancels"])
    skip, rests = set(sc["skip"]), set(sc["rests"])
    events: list[list[Any]] = []
    finished: list[str] = []
    ends_at: list[tuple[str, float]] = []  # the running tasks, in the order they started
    retry_at: dict[str, float] = {}
    gates: dict[str, threading.Event] = {}
    attempts: dict[str, int] = {}
    state = {"cancels_seen": 0, "callback": False, "ending": None}

    class Runner:
        def config(self, task: Task) -> SimpleNamespace:
            return SimpleNamespace(max_concurrent=kind_caps.get(task.kind))

        def deferral(self, task: Task) -> Deferral | None:
            return Deferral("its credential rests", DeferralCause(cause="rest")) if task.key in rests else None

        def run(self, task: Task) -> TaskResult:
            if not gates[task.id].wait(timeout=60):
                raise RuntimeError(f"the play never ended {task.id}")
            given = outcomes.get(task.id, [])
            attempt = attempts[task.id]
            if attempt > len(given):
                return TaskResult(task=task, ok=True, stop="completed")
            o = given[attempt - 1]
            cause = DeferralCause(cause=o["cause"]) if o["cause"] is not None else None
            return TaskResult(task=task, ok=o["ok"], stop=o["stop"], retryable=o["retryable"], cause=cause)

    def number(value: float | None) -> int | None:
        return None if value is None else int(value)

    def on_event(event: str, task: Task | None, **fields: Any) -> None:
        assert task is not None
        if event == "start":
            events.append(["start", task.id, fields["attempt"], fields["running"], fields["slots"]])
            gates[task.id] = threading.Event()
            attempts[task.id] = fields["attempt"]
            ends_at.append((task.id, clock.now + durations.get(task.id, 1)))
            retry_at.pop(task.id, None)
        elif event == "retry":
            events.append(["retry", task.id, fields["stop"], number(fields["wait_s"])])
            retry_at[task.id] = clock.now + fields["wait_s"]
        elif event == "throttle":
            events.append(["throttle", task.id, fields["slots"]])
        elif event == "deferred":
            cause = fields["cause"]
            if state["ending"] == task.id:
                state["ending"] = None
            retry_at.pop(task.id, None)
            if cause is None:
                events.append(["deferred", task.id, None, None, None, None])
            else:
                events.append(["deferred", task.id, cause.cause, number(cause.need_s), number(cause.left_s), cause.flow_call])
        elif event == "end":
            events.append(["end", task.id, fields["attempt"], fields["stop"], fields["ok"]])
            retry_at.pop(task.id, None)
        elif event in ("queued", "duplicate_key_refused"):
            events.append([event, task.id])
        else:  # a note: a callback raised
            events.append([event, task.id, sorted(fields)])

    def on_result(result: TaskResult, attempt: int) -> None:
        if state["ending"] == result.task.id:
            state["ending"] = None
        events.append(["result", result.task.id, result.stop, attempt])

    def follow_up(result: TaskResult) -> list[Task]:
        events.append(["finished", result.task.id, result.stop])
        finished.append(result.task.id)
        return [tasks[i] for i in follow_ups.get(result.task.id, []) if i in tasks]

    def when_the_queue_waits() -> None:
        """Move the play on: end the running task that ends first, or end the retry wait."""
        state["callback"] = False
        if state["ending"] is not None:
            return  # the task ended last is still on its way to the queue
        if ends_at:
            first = min(ends_at, key=lambda item: item[1])  # of those that end together, the first started
            ends_at.remove(first)
            clock.now = max(clock.now, first[1])
            state["ending"] = first[0]
            gates[first[0]].set()
        else:
            waits = [t for t in retry_at.values() if t > clock.now]
            if waits:
                clock.now = min(waits)
                q.wake()

    async def between_passes() -> bool:
        seen = len(finished)
        due = [key for i in finished[state["cancels_seen"] :] for key in cancels.get(i, [])]
        state["cancels_seen"] = seen
        for key in due:
            q.cancel(key)
        if not state["callback"]:
            state["callback"] = True
            asyncio.get_running_loop().call_soon(when_the_queue_waits)
        return False

    q = WorkQueue(
        Runner(),
        follow_up=follow_up,
        between_passes=between_passes,
        on_event=on_event,
        on_result=on_result,
        max_concurrent=sc["maxConcurrent"],
        deadline_s=sc["deadlineS"],
        grace_s=sc["graceS"],
        slack_s=sc["slackS"],
        finishing_kinds=tuple(sc["finishingKinds"]),
        retry_on=frozenset(sc["retryOn"]),
        throttle_on=frozenset(sc["throttleOn"]),
        throttle_s=sc["throttleS"],
        overdue_s=sc["overdueS"],
        retry_wait_s=sc["retryWaitS"],
        claim_capacity=dict(sc["claimCapacity"]),
        estimate=lambda task: estimates.get(task.kind),
        skip=lambda task: task.key in skip,
    )
    for i in sc["initial"]:
        q.add(tasks[i])
    q.run()
    return events


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: up to eight tasks at the start and the follow-ups of some, with
    dependencies, claims, a kind under a cap, keys in flight twice, a resume's skips, rests,
    failed and throttled attempts, cancels, and deadlines."""
    n = rng.randint(1, 8)
    total = n + rng.randint(0, 4)
    box = rng.random() < 0.5
    deadline = rng.choice([3, 10, 40, 200]) if box else None
    specs: list[dict[str, Any]] = []
    for i in range(total):
        twin = rng.random() < 0.08 and i > 0  # the key of an earlier task: in flight twice, or queued again
        earlier = [s["key"] for s in specs]
        key = rng.choice(earlier) if twin else f"k{i}"
        # A task comes after keys older than its own only, so that no tasks wait for each other:
        # the specification's bottom level is the code's where `after` has no cycle.
        older = list(dict.fromkeys(earlier))
        older = older[: older.index(key)] if key in older else older
        after = [k for k in older if rng.random() < 0.3]
        if rng.random() < 0.04:
            after.append("never-queued")
        boxes = []
        if rng.random() < 0.12:
            length = rng.choice([2, 8, 30])
            boxes.append(
                {
                    "deadlineAt": START_AT + length,
                    "deadlineS": length,
                    "graceS": rng.choice([0, 5]),
                    "slackS": rng.choice([0, 2, 30]),
                    "finishingKinds": rng.choice([[], ["report"]]),
                    "flowCall": "0.1",
                }
            )
        specs.append(
            {
                "id": f"t{i}",
                "key": key,
                "kind": rng.choice(["a", "b", "capped", "report"]),
                "after": after,
                "claims": rng.sample(["x", "y"], rng.choice([0, 0, 1, 2])),
                "estimateS": rng.choice([None, 1, 20, 150]),
                "tailS": rng.choice([None, 0, 90]),
                "priority": rng.choice([0, 0, 0, 1, -1]),
                "fingerprintAtStart": rng.random() < 0.3,
                "timeBoxes": boxes,
            }
        )
    initial = [s["id"] for s in specs[:n]]
    rng.shuffle(initial)
    follow_ups: dict[str, list[str]] = {}
    for s in specs[n:]:  # each later task follows the result of an earlier one
        follow_ups.setdefault(rng.choice(specs[: int(s["id"][1:])])["id"], []).append(s["id"])
    keys = sorted({s["key"] for s in specs})
    outcomes: dict[str, list[dict[str, Any]]] = {}
    for s in specs:
        roll = rng.random()
        if roll < 0.12:
            outcomes[s["id"]] = [{"stop": "error", "ok": False, "retryable": rng.random() < 0.8, "cause": None}] * rng.choice([1, 2])
        elif roll < 0.22:
            outcomes[s["id"]] = [{"stop": "rate_limited", "ok": False, "retryable": True, "cause": None}]
        elif roll < 0.27:
            outcomes[s["id"]] = [{"stop": "deferred", "ok": False, "retryable": True, "cause": "rest"}]
        elif roll < 0.32:
            outcomes[s["id"]] = [{"stop": "invalid_output", "ok": False, "retryable": True, "cause": None}]
    cancels: dict[str, list[str]] = {}
    for s in specs:
        if rng.random() < 0.08:
            cancels[s["id"]] = [rng.choice(keys)]
    return {
        "maxConcurrent": rng.randint(1, 4),
        "deadlineS": deadline,
        "graceS": rng.choice([0, 5, 50]),
        "slackS": rng.choice([0, 3, 200]),
        "finishingKinds": ["report"],
        "retryOn": rng.choice([[], ["error"], ["error", "rate_limited"]]),
        "throttleOn": ["rate_limited"],
        "throttleS": rng.choice([5, 300]),
        "overdueS": rng.choice([2, 600]),
        "retryWaitS": rng.choice([0, 3]),
        "claimCapacity": sorted({"x": rng.choice([1, 2]), "y": 1}.items()) if rng.random() < 0.5 else [],
        "kindCaps": [["capped", rng.choice([1, 2])]],
        "estimates": [["a", 5]] if rng.random() < 0.3 else [],
        "skip": [key for key in keys if rng.random() < 0.15],
        "rests": [key for key in keys if rng.random() < 0.15],
        "tasks": specs,
        "initial": initial,
        "followUps": sorted(follow_ups.items()),
        "outcomes": sorted(outcomes.items()),
        "durations": [[s["id"], rng.choice([0, 1, 3, 10])] for s in specs],
        "cancels": sorted(cancels.items()),
    }


def scenarios(seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [scenario(rng) for _ in range(count)]


def specified(given: list[dict[str, Any]]) -> list[Any]:
    """What the Lean specification reports for each of `given` (`lake exe contraagent-lean queue`)."""
    text = "".join(json.dumps(sc, separators=(",", ":")) + "\n" for sc in given)
    done = subprocess.run(
        ["lake", "exe", "contraagent-lean", "queue"],
        cwd=ROOT / "lean",
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "ELAN_HOME": ELAN_HOME},
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr)
    return [json.loads(line) for line in done.stdout.splitlines()]


def main() -> None:
    given = scenarios(SEED, COUNT)
    played = zip(given, specified(given), strict=True)
    lines = [json.dumps({"scenario": sc, "events": events}, separators=(",", ":")) for sc, events in played]
    FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
