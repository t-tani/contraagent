"""`FlowDriver`'s laws on random flows: each flow call ends once, the run ends when every flow
call has ended, each task finishes once, a cancellable task that is cancelled has no flow call
waiting for it then, and a flow whose code does not depend on the order its tasks finish in
creates the same tasks, from the same results, whatever that order is.

A flow is made as data (`steps`) and run by `play`: waits for tasks, `gather`, Tasks awaited
or not, `TaskGroup`, and failures caught or not."""

from __future__ import annotations

import asyncio
import random
import time
from collections import Counter
from types import SimpleNamespace
from typing import Any

from contraagent import Task, TaskDeferred, TaskFailed, TaskResult
from contraagent._internal.dispatch import result_or_raise
from contraagent.engine import FlowDriver, WorkQueue


class Runner:
    """Ends a task with `params["stop"]` after `params["sleep"]` seconds."""

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        time.sleep(task.params["sleep"])
        stop = task.params["stop"]
        return TaskResult(task=task, ok=stop == "completed", stop=stop, reason="" if stop == "completed" else "scripted")


class Watched(WorkQueue):
    """A queue that notes each cancel, with whether a flow call waited for the key then."""

    def __init__(self, driver: FlowDriver, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.driver = driver
        self.cancels: list[tuple[str, bool]] = []

    def cancel(self, key: str) -> bool:
        waited = any(not future.done() for future in self.driver._waiters.get(key, ()))
        self.cancels.append((key, waited))
        return super().cancel(key)


def steps(rng: random.Random, names: Any, depth: int, failing: bool) -> list[Any]:
    """A random flow as data: a list of steps, each a tuple named by its first item."""
    made: list[Any] = []
    for _ in range(rng.randint(1, 4)):
        kind = rng.choice(["wait", "wait", "gather", "task", "group", "catch", "add"] if depth else ["wait", "wait", "add"])
        stop = "error" if failing and rng.random() < 0.2 else "completed"
        if kind == "wait":
            made.append(("wait", next(names), stop, failing and rng.random() < 0.6))
        elif kind == "add":
            made.append(("add", next(names), stop, failing and rng.random() < 0.6))
        elif kind == "gather":
            items = [
                steps(rng, names, depth - 1, failing) if rng.random() < 0.5 else ("wait", next(names), stop, failing)
                for _ in range(rng.randint(1, 3))
            ]
            made.append(("gather", items, failing and rng.random() < 0.3))
        elif kind == "task":
            made.append(("task", steps(rng, names, depth - 1, failing), rng.random() < 0.7))
        elif kind == "group":
            made.append(("group", [steps(rng, names, depth - 1, failing) for _ in range(rng.randint(1, 3))]))
        else:
            made.append(("catch", steps(rng, names, depth - 1, failing)))
    return made


def play(flow: list[Any], sleeps: random.Random, slots: int) -> SimpleNamespace:
    """Run `flow` on a driver and a queue: what the run showed."""
    events: list[tuple[str, str]] = []
    created: dict[str, tuple[str, tuple[str, ...]]] = {}  # key -> the flow call that created it, and its frontier then
    driver = FlowDriver(answer=result_or_raise, on_flow_call=lambda event, call: events.append((event, call.id)))
    finished: Counter[str] = Counter()

    def task(key: str, stop: str, cancellable: bool) -> Task:
        call = driver.current
        assert call is not None
        created[key] = (call.id, call.frontier)
        return Task("step", key=key, params={"stop": stop, "sleep": sleeps.choice([0.0, 0.001, 0.004, 0.02])}, cancellable=cancellable)

    async def run(todo: list[Any]) -> None:
        waiting: list[asyncio.Task[None]] = []
        for step in todo:
            name = step[0]
            if name == "wait":
                await driver.wait(task(step[1], step[2], step[3]))
            elif name == "add":
                driver.add(task(step[1], step[2], step[3]))
            elif name == "gather":
                items = [run(item) if isinstance(item, list) else driver.wait(task(item[1], item[2], item[3])) for item in step[1]]
                await asyncio.gather(*items, return_exceptions=step[2])
            elif name == "task":
                child = asyncio.create_task(run(step[1]))
                if step[2]:
                    waiting.append(child)
            elif name == "group":
                async with asyncio.TaskGroup() as group:
                    for item in step[1]:
                        group.create_task(run(item))
            else:
                try:
                    await run(step[1])
                except* (TaskFailed, TaskDeferred):
                    pass
        for child in waiting:
            await child

    queue = Watched(driver, Runner(), max_concurrent=slots, on_event=lambda e, t, **f: finished.update([t.key]) if e == "end" else None)
    driver.run(queue, run(flow))
    return SimpleNamespace(driver=driver, events=events, created=created, finished=finished, cancels=queue.cancels)


def test_every_flow_call_and_every_task_ends_once_and_none_is_cancelled_while_waited_for():
    rng = random.Random(41)
    closed = 0
    for case in range(100):
        names = (f"t{i}" for i in range(10_000))
        shown = play(steps(rng, names, 3, failing=True), random.Random(case), rng.randint(1, 4))
        per_call: dict[str, list[str]] = {}
        for event, call in shown.events:
            per_call.setdefault(call, []).append(event)
        for call, seen in per_call.items():
            assert seen in (["create", "end"], ["create", "start", "end"]), (case, call, seen)
        states = {call.id: call.state for call in shown.driver.calls.values()}
        assert set(states) == set(per_call) and "running" not in states.values(), (case, states)
        assert not shown.driver.alive()
        # Each task the flows created finished once: launched and ended, or cancelled before it launched.
        assert set(shown.driver.done) == set(shown.created), case
        assert all(count == 1 for count in shown.finished.values()) and set(shown.finished) == set(shown.created), case
        assert all(not waited for _, waited in shown.cancels), (case, shown.cancels)
        closed += sum(1 for state in states.values() if state == "closed")
    assert closed > 20, closed  # the cases close flow calls; which tasks are cancelled depends on which end first


def test_a_flow_that_does_not_depend_on_the_order_its_tasks_finish_in_creates_the_same_tasks():
    """With no failure and no order-dependent code, the flow calls, the tasks each creates
    and the results each task was created from are the same for every order of finishing."""
    rng = random.Random(43)
    for case in range(40):
        flow = steps(rng, (f"t{i}" for i in range(10_000)), 3, failing=False)
        first = play(flow, random.Random(1), 4)
        second = play(flow, random.Random(2), rng.randint(1, 3))
        assert first.created == second.created, case
        assert sorted(first.events) == sorted(second.events), case
        assert {c.id: c.state for c in first.driver.calls.values()} == {c.id: c.state for c in second.driver.calls.values()}, case
