"""A task's created from (its flow call's frontier), as properties: over a fixed flow, the
tasks finish in 100 random orders, their results reach the flow code in batches of random
size, and every task gets the same created from, which holds only keys given before it was
created. Driven where no event loop runs (`settle_here`), with a `Board` in the queue's place."""

import asyncio
import random
from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from contraagent import Task, TaskFailed, TaskResult
from contraagent._internal.dispatch import result_or_raise
from contraagent.engine import FlowDriver


class Board:
    """In the place of the `WorkQueue`: records the tasks the flows queue."""

    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.between_passes: Any = None

    def extend(self, tasks) -> None:
        self.tasks += list(tasks)

    def wake(self) -> None:
        pass

    def past_hard_stop(self) -> bool:
        return False


class Flows:
    """A driver whose flow code waits for keys (`wait`) and creates tasks (`create`); what
    each created task's created from was, and the keys given when it was created."""

    def __init__(self) -> None:
        self.driver = FlowDriver(waits_for=lambda key: Task("t", key=key), answer=lambda item, res: result_or_raise(item, res).task.key)
        self.created: dict[str, tuple[str, ...]] = {}
        self.given: dict[str, set[str]] = {}

    def wait(self, key: str) -> Coroutine[Any, Any, str]:
        return self.driver.wait(key)

    def create(self, key: str) -> None:
        call = self.driver.current
        assert call is not None
        self.created[key] = call.frontier
        self.given[key] = set(self.driver.done)
        self.driver.add(Task("t", key=key))


Flow = Callable[[Flows], Coroutine[Any, Any, Any]]


def run(flow: Flow, rng: random.Random, fails: frozenset[str] = frozenset()) -> Flows:
    """Run `flow`, finishing its tasks in an order `rng` picks, a random number at a time."""
    flows = Flows()
    board = Board()
    driver = flows.driver
    with driver.driving():
        driver.start(flow(flows))
        driver.attach(board)
        answered: set[str] = set()
        while True:
            driver.settle_here()
            open_ = [task for task in board.tasks if task.key not in answered]
            if not open_:
                break
            rng.shuffle(open_)
            for task in open_[: rng.randint(1, len(open_))]:
                answered.add(task.key)
                ok = task.key not in fails
                driver.follow_up(TaskResult(task=task, ok=ok, stop="completed" if ok else "error"))
        driver.finish_here()
    for key, frontier in flows.created.items():
        assert set(frontier) <= flows.given[key], f"{key} created from {frontier}, before all of them were given"
    return flows


async def sequence(f: Flows) -> None:
    await f.wait("a")
    f.create("t1")
    await f.wait("b")
    f.create("t2")


async def gather(f: Flows) -> None:
    await asyncio.gather(f.wait("a"), f.wait("b"), f.wait("c"))
    f.create("t")


async def nested_gather(f: Flows) -> None:
    await asyncio.gather(asyncio.gather(f.wait("a"), asyncio.gather(f.wait("b"), f.wait("c"))), f.wait("e"))
    f.create("t")


async def child_flow_call(f: Flows) -> None:
    async def child() -> None:
        await asyncio.gather(f.wait("a"), f.wait("b"))
        f.create("in-child")
        await f.wait("c")

    await asyncio.create_task(child())
    f.create("t")


async def gather_of_children(f: Flows) -> None:
    async def child(u: str) -> None:
        await f.wait(f"{u}1")
        await f.wait(f"{u}2")

    await asyncio.gather(child("x"), child("y"), f.wait("z"))
    f.create("t")


async def through_wrappers(f: Flows) -> None:
    # Coroutines that only await a task call: Tasks of their own, which are not on record.
    async def one(key: str) -> str:
        return await f.wait(key)

    await asyncio.gather(one("a"), asyncio.ensure_future(f.wait("b")))
    f.create("t")


async def unawaited_child(f: Flows) -> None:
    async def side() -> None:
        await f.wait("e")
        f.create("in-side")

    side_task = asyncio.create_task(side())
    await f.wait("a")
    f.create("t1")
    await f.wait("b")
    f.create("t2")
    del side_task


async def unawaited_task(f: Flows) -> None:
    f.create("z")
    await f.wait("a")
    f.create("t")


async def task_group(f: Flows) -> None:
    async def child(u: str) -> None:
        await f.wait(u)

    async def both() -> None:
        await asyncio.gather(f.wait("c"), f.wait("e"))

    async with asyncio.TaskGroup() as tg:
        tg.create_task(child("a"))
        tg.create_task(child("b"))
        tg.create_task(both())
    f.create("t")


async def helper(f: Flows) -> None:
    async def gathered() -> None:
        await asyncio.gather(f.wait("a"), f.wait("b"))

    await gathered()
    f.create("t")


async def created_first(f: Flows) -> None:
    f.create("a")
    f.create("b")
    await f.wait("a")
    f.create("t1")
    await f.wait("b")  # given already or not: a resume by b
    f.create("t2")


async def child_starts_from_parent(f: Flows) -> None:
    async def child() -> None:
        f.create("first")
        await f.wait("c")
        f.create("second")

    await f.wait("a")
    await asyncio.create_task(child())


async def event(f: Flows) -> None:
    ready = asyncio.Event()

    async def setter() -> None:
        await f.wait("a")
        ready.set()

    async def waiter() -> None:
        await ready.wait()
        f.create("t")

    await asyncio.gather(setter(), waiter())


async def failure_through_a_child(f: Flows) -> None:
    async def child() -> None:
        await f.wait("a")
        await f.wait("fail")

    try:
        await child()
    except TaskFailed:
        f.create("t-except")
    await f.wait("b")
    f.create("t")


async def failure_in_gather_with_exceptions(f: Flows) -> None:
    async def child(u: str) -> None:
        await f.wait(u)

    await asyncio.gather(child("fail"), child("a"), f.wait("g"), return_exceptions=True)
    f.create("t")


async def failure_in_a_task_group(f: Flows) -> None:
    async def child(u: str) -> None:
        await f.wait(u)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(child("fail"))
    except* TaskFailed:
        f.create("t")


CASES: list[tuple[Flow, dict[str, tuple[str, ...]]]] = [
    (sequence, {"t1": ("a",), "t2": ("b",)}),
    (gather, {"t": ("a", "b", "c")}),
    (nested_gather, {"t": ("b", "c", "a", "e")}),  # by the flow calls that queued them
    (child_flow_call, {"in-child": ("a", "b"), "t": ("c",)}),
    (gather_of_children, {"t": ("x2", "y2", "z")}),
    (through_wrappers, {"t": ("b", "a")}),  # ensure_future queues b first
    (unawaited_child, {"in-side": ("e",), "t1": ("a",), "t2": ("b",)}),
    (unawaited_task, {"z": (), "t": ("a",)}),
    (task_group, {"t": ("a", "b", "c", "e")}),
    (helper, {"t": ("a", "b")}),
    (created_first, {"a": (), "b": (), "t1": ("a",), "t2": ("b",)}),
    (child_starts_from_parent, {"first": ("a",), "second": ("c",)}),
    (event, {"t": ("a",)}),
    (failure_through_a_child, {"t-except": ("fail",), "t": ("b",)}),
    (failure_in_gather_with_exceptions, {"t": ("fail", "a", "g")}),
    (failure_in_a_task_group, {"t": ("fail",)}),
]


@pytest.mark.parametrize(("flow", "expected"), CASES, ids=[flow.__name__ for flow, _ in CASES])
def test_every_order_the_tasks_finish_in_gives_the_same_created_from(flow, expected):
    fails = frozenset({"fail"})
    for seed in range(100):
        assert run(flow, random.Random(seed), fails).created == expected, f"seed {seed}"


async def failure_first_in_gather(f: Flows) -> None:
    try:
        await asyncio.gather(f.wait("fail"), f.wait("a"))
    except TaskFailed:
        f.create("t-except")
    await f.wait("b")
    f.create("t")


async def task_group_body_waits(f: Flows) -> None:
    async def child() -> None:
        await f.wait("c")

    async with asyncio.TaskGroup() as tg:
        tg.create_task(child())
        await f.wait("a")
        f.create("t-body")
    f.create("t")


@pytest.mark.parametrize("flow", [failure_first_in_gather, task_group_body_waits])
def test_where_the_flow_code_runs_on_the_order_the_same_order_gives_the_same_created_from(flow):
    # These flows resume on whichever result comes first: what reached them depends on the
    # order, and the same order always gives the same created from.
    outcomes = set()
    for seed in range(100):
        first, again = run(flow, random.Random(seed), frozenset({"fail"})), run(flow, random.Random(seed), frozenset({"fail"}))
        assert first.created == again.created
        outcomes.add(tuple(sorted(first.created.items())))
    assert len(outcomes) > 1
