"""The flow loop (`FlowLoop`) and exact quiescence: one `settle` lets every flow call run
until it waits for a task, whatever asyncio does in between (nested `gather`,
`TaskGroup`, `create_task`); a clock, a thread or a future of another event loop fails
at the `await` that needs it; a flow call that waits for what nothing will answer is
closed once nothing is left to run.

Most tests drive the flows as a `WorkQueue` would, with a `Board` in its place: settle,
answer every task the flows queued since (in key order), settle again, until a pass
queues nothing. After each settle the main event loop turns 200 more times and the
flows settle again: a task queued then would have been missed by the first settle."""

import asyncio
import concurrent.futures
import random
import sys
import threading
import time
from typing import Any

import pytest

from contraagent import Task, TaskResult
from contraagent._internal.dispatch import result_or_raise
from contraagent._internal.dispatch.flowloop import FlowLoop
from contraagent.engine import FlowDriver, WorkQueue


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


def result(task: Task) -> TaskResult:
    if task.key.startswith("fail"):
        return TaskResult(task=task, ok=False, stop="error", reason="scripted")
    return TaskResult(task=task, ok=True, stop="completed")


def value(item: Any, res: TaskResult) -> str:
    result_or_raise(item, res)
    return f"v:{res.task.key}"


def make() -> FlowDriver:
    return FlowDriver(waits_for=lambda key: Task("t", key=key), answer=value)


async def drive(driver: FlowDriver, board: Board, *, answer: bool = True, between=None) -> list[list[str]]:
    """Settle and answer until a pass queues nothing; each pass's keys, sorted."""
    passes: list[list[str]] = []
    seen = 0
    n = 0
    while True:
        await driver.settle()
        before = len(board.tasks)
        for _ in range(200):
            await asyncio.sleep(0)
        await driver.settle()
        assert len(board.tasks) == before, f"pass {n}: the settle ended before every flow call waited"
        new = board.tasks[seen:]
        seen = len(board.tasks)
        if between is not None:
            between(n)
        n += 1
        if not new:
            break
        passes.append(sorted(t.key for t in new))
        if not answer:
            break
        for task in sorted(new, key=lambda t: t.key):
            driver.follow_up(result(task))
    return passes


def run(*flows, between=None, driver: FlowDriver | None = None, answer: bool = True) -> tuple[FlowDriver, list[list[str]]]:
    """Start `flows(driver)` (a function of the driver: the top coroutines) and drive them."""
    driver = driver or make()
    board = Board()

    async def main() -> list[list[str]]:
        with driver.driving():
            for flow in flows:
                driver.start(flow(driver))
            driver.attach(board)  # type: ignore[arg-type]
            try:
                return await drive(driver, board, answer=answer, between=between)
            finally:
                await driver.finish()

    return driver, asyncio.run(main())


def test_a_gather_nested_four_deep_reaches_the_next_wait_in_one_settle():
    async def top(d):
        t = d.wait
        r = await asyncio.gather(asyncio.gather(asyncio.gather(asyncio.gather(t("a"), t("b")), t("c")), t("e")), t("f"))
        assert r == [[[["v:a", "v:b"], "v:c"], "v:e"], "v:f"]
        return await t("next")

    driver, passes = run(top)
    assert passes == [["a", "b", "c", "e", "f"], ["next"]]
    assert (driver.calls["0"].state, driver.calls["0"].value) == ("returned", "v:next")
    # Every Task of a gather takes a number; those that only wait leave no record.
    assert len(driver.calls) == 6 and [c.id for c in driver.calls.values() if c.recorded] == ["0"]


@pytest.mark.parametrize("depth", range(1, 7))
def test_a_gather_of_waits_nested_any_depth_settles_exactly(depth):
    async def top(d):
        waiting: Any = d.wait("k0")
        for i in range(1, depth):
            waiting = asyncio.gather(waiting, d.wait(f"k{i}"))
        await waiting
        return await d.wait("next")

    driver, passes = run(top)
    assert passes == [sorted(f"k{i}" for i in range(depth)), ["next"]] and driver.calls["0"].value == "v:next"


def test_a_failure_in_a_task_group_cancels_its_siblings_and_the_parent_goes_on():
    rec: dict[str, Any] = {}

    async def top(d):
        async def bad():
            await d.wait("x")
            raise ValueError("bad")

        async def slow():
            try:
                await d.wait("y1")
                await d.wait("y2")
                rec["slow"] = "finished"
            except asyncio.CancelledError:
                rec["slow"] = "cancelled"
                raise

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(bad())
                tg.create_task(slow())
        except* ValueError as group:
            rec["group"] = [str(e) for e in group.exceptions]
        return await d.wait("after")

    driver, passes = run(top)
    # Results reach the flows one at a time: x fails bad, and its TaskGroup cancels slow
    # before y1 comes, so slow never waits for y2.
    assert passes == [["x", "y1"], ["after"]]
    assert rec == {"slow": "cancelled", "group": ["bad"]}
    assert {c.id: c.state for c in driver.calls.values()} == {"0": "returned", "0.1": "raised", "0.2": "closed"}


def test_children_of_create_task_wait_beside_their_parent():
    async def top(d):
        async def child(k):
            return await d.wait(k) + await d.wait(k + "2")

        t1 = asyncio.create_task(child("p"))
        t2 = asyncio.create_task(child("q"))
        await d.wait("own")
        assert [await t1, await t2] == ["v:pv:p2", "v:qv:q2"]
        return await d.wait("next")

    driver, passes = run(top)
    assert passes == [["own", "p", "q"], ["p2", "q2"], ["next"]] and list(driver.calls) == ["0", "0.1", "0.2"]


def test_the_end_of_a_child_flow_call_wakes_its_parent():
    async def top(d):
        async def leaf(k):
            return await d.wait(k)

        async def mid():
            return list(await asyncio.gather(leaf("l1"), leaf("l2")))

        assert await asyncio.create_task(mid()) == ["v:l1", "v:l2"]
        assert await leaf("l3") == "v:l3"  # the same flow call
        return await d.wait("next")

    driver, passes = run(top)
    assert passes == [["l1", "l2"], ["l3"], ["next"]]
    assert list(driver.calls) == ["0", "0.1", "0.1.1", "0.1.2"]


def test_cancelling_one_of_two_flow_calls_that_wait_for_a_key_leaves_the_other_its_value():
    rec: dict[str, Any] = {}

    async def a(d):
        try:
            return await d.wait("s")
        except asyncio.CancelledError:
            rec["a"] = "cancelled"
            await d.wait("cleanup")
            raise

    async def b(d):
        rec["b"] = await d.wait("s")
        return await d.wait("b_next")

    driver = make()

    def between(n: int) -> None:
        if n == 0:
            task = driver.calls["0"].task
            assert task is not None
            task.cancel()

    _, passes = run(a, b, driver=driver, between=between)
    assert passes == [["s"], ["b_next", "cleanup"]]
    assert rec == {"a": "cancelled", "b": "v:s"}
    assert (driver.calls["0"].state, driver.calls["1"].state, driver.calls["1"].value) == ("closed", "returned", "v:b_next")


def test_one_task_call_awaited_by_two_flow_calls_one_of_them_cancelled():
    rec: dict[str, Any] = {}
    driver = make()

    class Shared:  # awaited by both, as a task call is: each await waits on a future of its own
        def __await__(self):
            return driver.wait("s").__await__()

    shared = Shared()

    async def a(d):
        await shared

    async def b(d):
        try:
            rec["b"] = await shared
        except asyncio.CancelledError:
            rec["b"] = "cancelled"

    def between(n: int) -> None:
        if n == 0:
            task = driver.calls["0"].task
            assert task is not None
            task.cancel()

    run(a, b, driver=driver, between=between)
    assert rec == {"b": "v:s"}


def test_the_order_of_the_steps_is_the_same_whatever_runs_on_the_main_loop():
    def once(seed: int) -> list[str]:
        steps: list[str] = []
        rng = random.Random(seed)

        async def top(d):
            async def grand(k):
                v = await d.wait(k)
                steps.append(k)
                return v

            async def child(i):
                a, b = await asyncio.gather(d.wait(f"c{i:02}a"), d.wait(f"c{i:02}b"))
                steps.append(f"c{i:02} gathered")
                async with asyncio.TaskGroup() as tg:
                    g1 = tg.create_task(grand(f"c{i:02}g1"))
                    g2 = tg.create_task(grand(f"c{i:02}g2"))
                steps.append(f"c{i:02} grouped")
                return a + b + g1.result() + g2.result() + await d.wait(f"c{i:02}z")

            return list(await asyncio.gather(*[child(i) for i in range(20)]))

        driver = make()
        board = Board()

        async def main() -> None:
            loop = asyncio.get_running_loop()
            stop = False
            pool = concurrent.futures.ThreadPoolExecutor(4)

            async def noise() -> None:
                while not stop:
                    for _ in range(rng.randrange(1, 5)):
                        await asyncio.sleep(0)
                    loop.run_in_executor(pool, time.sleep, rng.random() / 1000)

            noisy = [asyncio.ensure_future(noise()) for _ in range(3)]
            with driver.driving():
                driver.start(top(driver))
                driver.attach(board)  # type: ignore[arg-type]
                await drive(driver, board)
                await driver.finish()
            stop = True
            await asyncio.gather(*noisy)
            pool.shutdown()

        asyncio.run(main())
        assert driver.calls["0"].state == "returned"
        return steps

    first = once(0)
    assert len(first) == 80
    assert all(once(seed) == first for seed in range(1, 5))


@pytest.mark.parametrize("n", [1000, 10000])
def test_many_child_flow_calls(n):
    async def top(d):
        async def child(i):
            await d.wait(f"k{i:05}")
            return await d.wait(f"k{i:05}b")

        assert len(await asyncio.gather(*[child(i) for i in range(n)])) == n
        return await d.wait("end")

    driver, passes = run(top)
    assert [len(p) for p in passes] == [n, n, 1] and len(driver.calls) == n + 1


def test_one_drain_with_no_event_loop_reaches_every_first_wait():
    async def top(d):
        t = d.wait

        async def leaf(k):
            return await t(k)

        async def nested():
            return await asyncio.gather(asyncio.gather(asyncio.gather(asyncio.gather(leaf("n1"), t("n2")), t("n3")), t("n4")))

        async def group():
            async with asyncio.TaskGroup() as tg:
                for i in range(3):
                    tg.create_task(leaf(f"g{i}"))

        async def spawner():
            await asyncio.gather(*[asyncio.create_task(leaf(f"s{i:02}")) for i in range(50)])

        async def chain():  # its first task comes after three child flow calls end
            async def nothing():
                return 1

            x = await asyncio.create_task(nothing())
            y = await asyncio.gather(nothing(), asyncio.create_task(nothing()))
            async with asyncio.TaskGroup() as tg:
                tg.create_task(nothing())
            await t(f"late{x + sum(y)}")

        async def deep():  # its first task comes after a 4-deep gather of flow calls
            async def one():
                return 1

            await asyncio.gather(asyncio.gather(asyncio.gather(asyncio.gather(one(), one()), one()), one()), one())
            await t("deep")

        await asyncio.gather(nested(), group(), spawner(), chain(), deep())

    driver = make()
    board = Board()
    with driver.driving():
        driver.start(top(driver))
        driver.attach(board)  # type: ignore[arg-type]
        assert driver.settle_here()
        keys = sorted(t.key for t in board.tasks)
        driver.finish_here()
    expected = sorted(["n1", "n2", "n3", "n4", "g0", "g1", "g2", *[f"s{i:02}" for i in range(50)], "late3", "deep"])
    assert keys == expected
    assert not driver.alive() and not asyncio.all_tasks(driver._loop)


def test_flow_code_runs_on_the_flow_loop_and_the_running_loop_comes_back():
    seen: list[Any] = []

    async def top(d):
        seen.append(asyncio.get_running_loop())
        await d.wait("x")
        seen.append(asyncio.get_running_loop())
        raise ValueError("after the wait")

    async def main() -> None:
        driver = make()
        board = Board()
        main_loop = asyncio.get_running_loop()
        with driver.driving():
            driver.start(top(driver))
            driver.attach(board)  # type: ignore[arg-type]
            await driver.settle()
            assert asyncio.get_running_loop() is main_loop
            driver.follow_up(result(board.tasks[0]))
            await driver.settle()
            assert asyncio.get_running_loop() is main_loop
            await driver.finish()
        assert seen == [driver._loop, driver._loop] and isinstance(driver._loop, FlowLoop)
        assert driver.calls["0"].state == "raised"

    asyncio.run(main())
    with pytest.raises(RuntimeError):  # no running loop is left behind
        asyncio.get_running_loop()


def test_a_drain_never_runs_inside_a_task_step():
    """`settle` drains from a plain callback of the main loop: on Python 3.14 a drain inside
    a Task step raises "Cannot enter into task"."""
    inside: list[Any] = []

    async def top(d):
        inside.append(asyncio.current_task())
        await d.wait("x")

    async def main() -> None:
        driver = make()
        with driver.driving():
            driver.start(top(driver))
            driver.attach(Board())  # type: ignore[arg-type]
            await driver.settle()
            await driver.finish()
        assert inside == [driver.calls["0"].task]

    asyncio.run(main())

    async def inside_a_step() -> str:
        loop = FlowLoop()
        errors: list[BaseException] = []
        loop.set_exception_handler(lambda _, context: errors.extend([context["exception"]] if "exception" in context else []))

        async def flow() -> None:
            pass

        task = loop.create_task(flow())
        loop.drain()
        if not task.done():  # its step never ran: no warning for its coroutine
            task.get_coro().close()  # type: ignore[union-attr]
        return "fails" if errors else "works"

    found = asyncio.run(inside_a_step())
    assert found == ("fails" if sys.version_info >= (3, 14) else "works")


def test_flow_code_may_set_an_event_of_the_main_loop():
    async def main() -> str:
        driver = make()
        event = asyncio.Event()

        async def waiter() -> str:
            await event.wait()
            return "woken"

        waiting = asyncio.ensure_future(waiter())
        await asyncio.sleep(0)

        async def top(d):
            event.set()  # what the queue's wake() does
            await d.wait("z")

        with driver.driving():
            driver.start(top(driver))
            driver.attach(Board())  # type: ignore[arg-type]
            await driver.settle()
            got = await asyncio.wait_for(waiting, 10)
            await driver.finish()
        return got

    assert asyncio.run(main()) == "woken"


@pytest.mark.parametrize(
    ("awaited", "error", "words"),
    [
        (lambda: asyncio.sleep(0.05), TypeError, "needs a clock"),
        (lambda: asyncio.wait_for(asyncio.get_running_loop().create_future(), timeout=1), TypeError, "needs a clock"),
        (lambda: asyncio.to_thread(time.sleep, 0), TypeError, "needs a thread"),
        (lambda: asyncio.open_connection("localhost", 9), TypeError, "needs I/O"),
        (lambda: asyncio.create_subprocess_exec("true"), TypeError, "needs I/O"),
    ],
    ids=["sleep", "wait_for", "to_thread", "open_connection", "subprocess"],
)
def test_a_clock_a_thread_or_io_raises_at_the_await(awaited, error, words):
    caught: list[BaseException] = []

    async def top(d):
        try:
            await awaited()
        except Exception as exc:
            caught.append(exc)
        return await d.wait("after")

    driver, passes = run(top)
    [exc] = caught
    assert isinstance(exc, error) and words in str(exc) and "Python task" in str(exc)
    assert passes == [["after"]] and driver.calls["0"].value == "v:after"


def test_an_asyncio_timeout_raises_at_the_async_with():
    caught: list[BaseException] = []

    async def top(d):
        try:
            async with asyncio.timeout(1):
                await d.wait("never")
        except TypeError as exc:
            caught.append(exc)
        async with asyncio.timeout(None):  # no clock needed
            await asyncio.sleep(0)
            return await d.wait("after")

    driver, passes = run(top)
    assert len(caught) == 1 and "needs a clock" in str(caught[0])
    assert passes == [["after"]] and driver.calls["0"].value == "v:after"


def test_a_future_of_another_event_loop_raises_at_the_await():
    other = asyncio.new_event_loop()
    caught: list[BaseException] = []

    async def top(d):
        try:
            await other.create_future()
        except RuntimeError as exc:
            caught.append(exc)
        return await d.wait("after")

    try:
        driver, passes = run(top)
    finally:
        other.close()
    assert len(caught) == 1 and "different loop" in str(caught[0])
    assert passes == [["after"]]


def test_a_flow_call_waiting_for_what_nothing_answers_is_closed_naming_where():
    never = asyncio.Event()

    async def child():
        await never.wait()

    async def top(d):
        await d.wait("a")
        await asyncio.gather(child())

    driver, passes = run(top)
    assert passes == [["a"]]
    calls = driver.calls
    assert {c.id: c.state for c in calls.values()} == {"0": "closed", "0.1": "closed"}
    error = calls["0.1"].error
    assert isinstance(error, RuntimeError)
    assert "flow call 0.1" in str(error) and "for what nothing will answer" in str(error)
    assert f"{__file__}:{child.__code__.co_firstlineno + 1}" in str(error)
    assert isinstance(calls["0"].error, RuntimeError) and "flow call 0 " in str(calls["0"].error)


def test_a_waiting_flow_call_is_not_closed_while_a_task_is_still_to_answer():
    never = asyncio.Event()
    rec: list[str] = []

    async def stuck():
        await never.wait()

    async def top(d):
        asyncio.create_task(stuck())
        rec.append(await d.wait("a"))

    driver = make()
    board = Board()

    async def main() -> None:
        with driver.driving():
            driver.start(top(driver))
            driver.attach(board)  # type: ignore[arg-type]
            assert await driver.settle()  # "a" is still to come: nothing is closed
            assert driver.calls["0.1"].state == "running"
            driver.follow_up(result(board.tasks[0]))
            assert not await driver.settle()  # now nothing is left: 0.1 is closed
            await driver.finish()

    asyncio.run(main())
    assert rec == ["v:a"] and driver.calls["0.1"].state == "closed" and driver.calls["0"].state == "returned"


def test_the_queue_ends_at_once_for_a_flow_that_waits_forever():
    driver = FlowDriver()
    never = asyncio.Event()

    async def flow():
        await driver.wait(Task("a", key="a-1"))
        await never.wait()

    class Runner:
        def config(self, task):
            return type("Config", (), {"max_concurrent": None})()

        def run(self, task):
            return TaskResult(task=task, ok=True, stop="completed")

    started = time.monotonic()
    driver.run(WorkQueue(Runner()), flow())  # no deadline: before, it waited forever
    assert time.monotonic() - started < 30
    top = driver.calls["0"]
    assert top.state == "closed" and "for what nothing will answer" in str(top.error)


def test_flow_code_closes_an_async_generator_it_left_open():
    closed: list[str] = []

    async def top(d):
        async def numbers():
            try:
                yield 1
                yield 2
            finally:
                closed.append("closed")

        gen = numbers()
        async for n in gen:
            assert n == 1
            break
        await d.wait("x")
        return gen

    driver, _ = run(top)
    assert driver.calls["0"].state == "returned" and closed == ["closed"]


def test_a_flow_loop_runs_on_a_thread_of_its_own_too():
    found: list[Any] = []

    def check() -> None:
        driver = make()
        board = Board()

        async def top(d):
            found.append(threading.current_thread().name)
            await d.wait("x")

        with driver.driving():
            driver.start(top(driver))
            driver.attach(board)  # type: ignore[arg-type]
            driver.settle_here()
            driver.finish_here()
        found.append([t.key for t in board.tasks])

    thread = threading.Thread(target=check, name="checker")
    thread.start()
    thread.join()
    assert found == ["checker", ["x"]]


def test_a_callback_carries_the_cause_of_what_scheduled_it():
    seen: list[tuple[str, tuple[str, ...]]] = []

    def on_run(context, cause):
        seen.append(("run", cause))
        return (*cause, "+") if cause else cause

    loop = FlowLoop(on_run=on_run)
    fut = loop.create_future()
    fut.add_done_callback(lambda f: loop.call_soon(lambda: None))
    with loop.caused_by(("k",)):
        fut.set_result(1)  # schedules its done callback, caused by k
    loop.call_soon(lambda: None)  # outside caused_by: no cause
    loop.drain()
    # the done callback ran with k; what it scheduled carries what on_run returned for it
    assert seen == [("run", ("k",)), ("run", ()), ("run", ("k", "+"))]
