"""`FlowDriver`: async flows over a `WorkQueue`, with the default (raw `Task`) callbacks
and with `result_or_raise`."""

import asyncio
import logging
import threading
import time
from types import SimpleNamespace

import pytest

from contraagent import Task, TaskDeferred, TaskFailed, TaskResult
from contraagent._internal.dispatch import result_or_raise, time_box
from contraagent.engine import FlowDriver, WorkQueue


class Runner:
    """Runs a task by waiting until `params["meet"]` tasks ran at once (10 s at most), or
    until every key of `params["after_ended"]` ended, and until its gate (`gates[key]`) is
    open, then sleeping `params["sleep"]` and
    ending with `params["stop"]`; records launches, ends and how many ran at once."""

    def __init__(self) -> None:
        self.launched: list[str] = []
        self.ended: list[str] = []
        self.peak = 0
        self.gates: dict[str, threading.Event] = {}
        self._running = 0
        self._lock = threading.Condition()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        with self._lock:
            self.launched.append(task.key)
            self._running += 1
            self.peak = max(self.peak, self._running)
            self._lock.notify_all()
            self._lock.wait_for(lambda: self.peak >= task.params.get("meet", 0), timeout=10)
            after = str(task.params.get("after_ended", ""))
            self._lock.wait_for(lambda: all(k in self.ended for k in after.split(",") if k), timeout=10)
        if task.key in self.gates:
            self.gates[task.key].wait(timeout=10)
        time.sleep(task.params.get("sleep", 0.0))
        with self._lock:
            self._running -= 1
            self.ended.append(task.key)
            self._lock.notify_all()
        stop = task.params.get("stop", "completed")
        return TaskResult(task=task, ok=stop == "completed", stop=stop, reason="" if stop == "completed" else "scripted")


def t(key: str, **params) -> Task:
    return Task(key.split("-")[0], key=key, params=params)


def drive(*flows, driver: FlowDriver, runner: Runner | None = None, **queue_options) -> tuple[FlowDriver, Runner, dict]:
    runner = runner or Runner()
    summary = driver.run(WorkQueue(runner, **queue_options), *flows)
    return driver, runner, summary


def test_an_await_receives_the_task_result():
    driver = FlowDriver()

    async def flow():
        res = await driver.wait(t("a-1"))
        return res.stop

    _, runner, _ = drive(flow(), driver=driver)
    top = driver.calls["0"]
    assert (top.state, top.value, runner.launched) == ("returned", "completed", ["a-1"])


def test_gather_waits_for_all_and_answers_in_order():
    driver = FlowDriver()

    async def flow():
        results = await asyncio.gather(driver.wait(t("a-slow", sleep=0.2, meet=2)), driver.wait(t("a-fast", meet=2)))
        return [r.task.key for r in results]

    _, runner, _ = drive(flow(), driver=driver)
    assert driver.calls["0"].value == ["a-slow", "a-fast"]
    assert runner.peak == 2


def test_every_task_takes_a_number_and_one_that_only_waits_is_not_on_record():
    events: list[tuple[str, str]] = []
    driver = FlowDriver(on_flow_call=lambda event, call: events.append((event, call.id)))

    async def child():
        return (await driver.wait(t("b-1"))).task.key

    async def adder():
        driver.add(t("c-1"))

    async def flow():
        await asyncio.gather(driver.wait(t("a-1")), driver.wait(t("a-2")))
        await asyncio.create_task(adder())
        return await asyncio.gather(child(), driver.wait(t("a-3")))

    drive(flow(), driver=driver)
    assert list(driver.calls) == ["0", "0.1", "0.2", "0.3", "0.4", "0.5"] and driver.calls["0"].value[0] == "b-1"
    assert [c.id for c in driver.calls.values() if c.recorded] == ["0", "0.3"]
    assert [e for e in events if e[0] == "start"] == [("start", "0"), ("start", "0.3")]
    assert ("end", "0.1") in events and driver.calls["0"].frontier == ("b-1", "a-3")


def test_child_coroutines_in_tasks_are_flow_calls_running_concurrently():
    started: list[tuple[str, str]] = []
    driver = FlowDriver(on_flow_call=lambda event, call: started.append((event, call.id)))

    async def per_unit(u):
        a = await driver.wait(t(f"a-{u}", meet=2))
        b = await driver.wait(t(f"b-{u}"))
        return (a.stop, b.task.key)

    async def flow():
        return await asyncio.gather(*[per_unit(u) for u in ("x", "y")])

    _, runner, _ = drive(flow(), driver=driver)
    assert driver.calls["0"].value == [("completed", "b-x"), ("completed", "b-y")]
    assert runner.peak == 2
    assert list(driver.calls) == ["0", "0.1", "0.2"]
    child = driver.calls["0.1"]
    assert child.parent is driver.calls["0"] and child.function.endswith("per_unit")
    assert child.site is not None and child.site[0] == __file__
    assert [e for e in started if e[0] == "create"] == [("create", "0"), ("create", "0.1"), ("create", "0.2")]
    assert ("start", "0") in started and ("start", "0.1") not in started and ("end", "0") == started[-1]


def test_create_task_and_task_group_make_flow_calls_too():
    driver = FlowDriver()

    async def child(u):
        return (await driver.wait(t(f"a-{u}"))).task.key

    async def flow():
        first = asyncio.create_task(child("1"))
        async with asyncio.TaskGroup() as group:
            second = group.create_task(child("2"))
        return [await first, second.result()]

    drive(flow(), driver=driver)
    assert driver.calls["0"].value == ["a-1", "a-2"] and list(driver.calls) == ["0", "0.1", "0.2"]


def test_an_awaited_coroutine_stays_in_the_same_flow_call():
    driver = FlowDriver()

    async def helper(u):
        r = await driver.wait(t(f"a-{u}"))
        return r.task.key

    async def flow():
        first = await helper("1")
        second = await helper("2")
        return [first, second]

    drive(flow(), driver=driver)
    assert list(driver.calls) == ["0"] and driver.calls["0"].value == ["a-1", "a-2"]


def test_a_child_flow_call_created_in_an_awaited_helper_records_its_site():
    driver = FlowDriver()

    async def child():
        return await driver.wait(t("a-1"))

    async def helper():
        return await asyncio.create_task(child())

    async def flow():
        return await helper()

    drive(flow(), driver=driver)
    site = driver.calls["0.1"].site
    assert site is not None and site[1] == helper.__code__.co_firstlineno + 1


def test_an_error_from_on_flow_call_at_a_child_start_fails_the_child_before_it_runs():
    ran: list[str] = []

    def on_flow_call(event, call):
        if event == "create" and call.id == "0.2":
            raise LookupError("refused")

    driver = FlowDriver(on_flow_call=on_flow_call)

    async def child(u):
        ran.append(u)
        return await driver.wait(t(f"a-{u}"))

    async def flow():
        try:
            await asyncio.gather(child("1"), child("2"))
        except LookupError as exc:
            return f"caught {exc}"

    _, runner, _ = drive(flow(), driver=driver)
    assert driver.calls["0"].value == "caught refused"
    assert (driver.calls["0.2"].state, str(driver.calls["0.2"].error)) == ("raised", "refused")
    assert "2" not in ran and "a-2" not in runner.launched


def test_a_child_exception_raises_at_the_parent_await():
    driver = FlowDriver()

    async def child():
        await driver.wait(t("a-1"))
        raise ValueError("bad")

    async def flow():
        try:
            await asyncio.gather(child())
        except ValueError as exc:
            return f"caught {exc}"

    drive(flow(), driver=driver)
    assert driver.calls["0.1"].state == "raised" and driver.calls["0"].value == "caught bad"


def test_an_uncaught_exception_ends_the_flow_call_raised():
    driver = FlowDriver()

    async def flow():
        await driver.wait(t("a-1"))
        raise RuntimeError("boom")

    drive(flow(), driver=driver)
    top = driver.calls["0"]
    assert top.state == "raised" and isinstance(top.error, RuntimeError)


def test_gather_with_return_exceptions_gives_each_failure_by_position():
    driver = FlowDriver(answer=result_or_raise)

    async def flow():
        return await asyncio.gather(
            driver.wait(t("a-ok", sleep=0.1)),
            driver.wait(t("a-late", stop="error", after_ended="a-early")),
            driver.wait(t("a-early", stop="timeout")),
            return_exceptions=True,
        )

    _, runner, _ = drive(flow(), driver=driver)
    ok, late, early = driver.calls["0"].value
    assert isinstance(ok, TaskResult) and ok.ok
    assert isinstance(late, TaskFailed) and not isinstance(late, TaskDeferred)
    assert (late.key, late.stop, late.result.reason) == ("a-late", "error", "scripted")
    assert late.item is late.result.task
    assert isinstance(early, TaskFailed) and early.stop == "timeout"
    assert sorted(runner.launched) == ["a-early", "a-late", "a-ok"]


def test_a_deferred_task_raises_task_deferred_and_the_flow_may_await_a_finishing_task():
    driver = FlowDriver(answer=result_or_raise)

    async def flow():
        try:
            await driver.wait(t("scan-1"))
        except TaskDeferred as exc:
            report = await driver.wait(t("report-1"))
            return (exc.stop, report.stop)

    q = WorkQueue(Runner(), deadline_s=0.001, finishing_kinds=("report",))
    while not q.past_deadline():
        pass
    driver.run(q, flow())
    assert driver.calls["0"].value == ("deferred", "completed")


def test_past_the_grace_window_a_waiting_flow_call_and_its_parent_are_closed():
    closed: list[str] = []
    driver = FlowDriver(answer=result_or_raise)

    async def child():
        try:
            await driver.wait(t("scan-1"))
        finally:
            closed.append("child")

    async def flow():
        try:
            await asyncio.gather(child())
        finally:
            closed.append("parent")

    q = WorkQueue(Runner(), deadline_s=0.001, grace_s=0.0)
    while not q.past_hard_stop():
        pass
    driver.run(q, flow())
    assert closed == ["child", "parent"]
    assert {c.id: c.state for c in driver.calls.values()} == {"0": "closed", "0.1": "closed"}


def test_ids_are_the_same_in_every_run_whatever_order_the_tasks_finish_in():
    def run(reverse: bool) -> dict[str, str]:
        driver = FlowDriver()

        async def leaf(i):
            # In the reversed run, each leaf's task ends only after the next leaf's.
            after = f"a-{i + 1}" if reverse and i < 3 else ""
            return await driver.wait(t(f"a-{i}", after_ended=after))

        async def mid(i):
            await asyncio.gather(leaf(i), leaf(i + 1))
            return await asyncio.create_task(leaf(i + 10))

        async def flow():
            return await asyncio.gather(mid(1), mid(2))

        drive(flow(), driver=driver, max_concurrent=8)
        return {c.id: c.function.rsplit(".", 1)[-1] for c in driver.calls.values()}

    forward, backward = run(False), run(True)
    assert forward == backward
    assert sorted(forward) == ["0", "0.1", "0.1.1", "0.1.2", "0.1.3", "0.2", "0.2.1", "0.2.2", "0.2.3"]


def test_the_frontier_follows_what_each_flow_call_received():
    seen: dict[str, tuple[str, ...]] = {}
    driver = FlowDriver()

    def frontier() -> tuple[str, ...]:
        return driver.current.frontier if driver.current else ()

    async def child(u):
        seen[f"child {u} start"] = frontier()
        await driver.wait(t(f"b-{u}"))
        seen[f"child {u} end"] = frontier()

    async def flow():
        await asyncio.gather(driver.wait(t("a-1")), driver.wait(t("a-2")))
        seen["after gather"] = frontier()
        await asyncio.gather(child("x"), child("y"))
        seen["after children"] = frontier()
        await driver.wait(t("c-1"))
        await driver.wait(t("c-2"))
        seen["after two awaits"] = frontier()

    drive(flow(), driver=driver)
    # As a generator flow's: a batch gives the union, a child its last frontier, an await its key.
    assert seen == {
        "after gather": ("a-1", "a-2"),
        "child x start": ("a-1", "a-2"),
        "child y start": ("a-1", "a-2"),
        "child x end": ("b-x",),
        "child y end": ("b-y",),
        "after children": ("b-x", "b-y"),
        "after two awaits": ("c-2",),
    }


def test_a_done_key_is_answered_at_once_and_a_shared_key_runs_once():
    driver = FlowDriver()

    async def child():
        return await driver.wait(t("a-shared", sleep=0.1))

    async def flow():
        first = await asyncio.gather(child(), child())
        again = await driver.wait(t("a-shared"))
        return [r.task.key for r in [*first, again]]

    _, runner, _ = drive(flow(), driver=driver)
    assert runner.launched == ["a-shared"]
    assert driver.calls["0"].value == ["a-shared"] * 3 and "a-shared" in driver.done


def test_added_tasks_run_whether_or_not_they_are_awaited():
    driver = FlowDriver()

    async def flow():
        driver.add(t("side-1"))
        return await driver.wait(t("a-1"))

    _, runner, _ = drive(flow(), driver=driver)
    assert sorted(runner.launched) == ["a-1", "side-1"] and driver.calls["0"].state == "returned"


def test_waits_for_errors_are_raised_at_the_await():
    driver = FlowDriver()

    async def flow():
        try:
            await driver.wait(3)
        except TypeError as exc:
            return str(exc)

    drive(flow(), driver=driver)
    assert "not int" in driver.calls["0"].value


def test_a_typed_answer_and_item_come_from_the_callbacks():
    driver = FlowDriver(waits_for=lambda item: t(item), answer=lambda item, result: f"{item}:{result.stop}")

    async def flow():
        return await asyncio.gather(driver.wait("a-1"), driver.wait("a-2"))

    drive(flow(), driver=driver)
    assert driver.calls["0"].value == ["a-1:completed", "a-2:completed"]


def test_a_key_in_flight_outside_the_driver_raises_task_failed_duplicate_key():
    driver = FlowDriver(answer=result_or_raise)

    async def flow():
        try:
            await driver.wait(t("a-1"))
        except TaskFailed as exc:
            return exc.stop

    q = WorkQueue(Runner())
    q.add(t("a-1", sleep=0.2))
    driver.run(q, flow())
    assert driver.calls["0"].value == "duplicate_key" and driver.done["a-1"].stop == "completed"


def test_a_thousand_children_and_a_deep_nesting_use_no_recursion():
    driver = FlowDriver()

    async def leaf(i):
        return await driver.wait(t(f"a-{i}"))

    async def flow():
        return len(await asyncio.gather(*[leaf(i) for i in range(1000)]))

    _, runner, _ = drive(flow(), driver=driver, max_concurrent=32)
    assert driver.calls["0"].value == 1000 and len(runner.launched) == 1000
    assert len(driver.calls) == 1001

    async def nest(n):
        if n == 0:
            return 0
        return await asyncio.create_task(nest(n - 1)) + 1

    deep = FlowDriver()
    drive(nest(3000), driver=deep)
    assert deep.calls["0"].value == 3000


def test_a_flow_that_awaits_a_clock_raises_type_error_there():
    driver = FlowDriver()

    async def flow():
        try:
            await asyncio.sleep(0.05)
        except TypeError as exc:
            return str(exc), (await driver.wait(t("a-1"))).stop

    _, runner, _ = drive(flow(), driver=driver)
    message, stop = driver.calls["0"].value
    assert "needs a clock" in message and "time_box()" in message and "Python task" in message
    assert stop == "completed" and runner.launched == ["a-1"]


def test_a_flow_call_that_waits_for_what_nothing_answers_is_closed_at_once():
    driver = FlowDriver()
    never = asyncio.Event()

    async def flow():
        await never.wait()

    q = WorkQueue(Runner())  # no deadline: nothing else would end the run
    driver.run(q, flow())
    top = driver.calls["0"]
    assert top.state == "closed" and isinstance(top.error, RuntimeError)
    assert f"waits at {__file__}:{flow.__code__.co_firstlineno + 1}" in str(top.error)


def test_cancelling_a_flow_call_leaves_its_tasks_running():
    runner = Runner()
    runner.gates["a-slow"] = threading.Event()  # opened once flow call 0.1 is closed

    def on_flow_call(event, call):
        if event == "end" and call.id == "0.1":
            runner.gates["a-slow"].set()

    driver = FlowDriver(answer=result_or_raise, on_flow_call=on_flow_call)

    async def slow():
        await driver.wait(t("a-slow"))

    async def bad():
        await driver.wait(t("a-bad", stop="error"))

    async def flow():
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(slow())
                group.create_task(bad())
        except ExceptionGroup as group:
            return [type(e).__name__ for e in group.exceptions]

    drive(flow(), driver=driver, runner=runner)
    assert driver.calls["0"].value == ["TaskFailed"]
    assert (driver.calls["0.1"].state, driver.calls["0.2"].state) == ("closed", "raised")
    assert sorted(runner.ended) == ["a-bad", "a-slow"]


def test_a_time_box_is_a_flow_call_with_its_own_deadline():
    driver = FlowDriver(answer=result_or_raise)

    async def child():
        return (await driver.wait(t("a-1"))).task.time_boxes

    async def flow():
        return await time_box(child(), deadline_s=600)

    drive(flow(), driver=driver)
    [box] = driver.calls["0"].value
    assert box.flow_call == "0.1" and box.deadline_s == 600 and driver.calls["0.1"].time_box is box


def test_finish_closes_what_is_still_running():
    driver = FlowDriver()

    async def flow():
        await driver.wait(t("a-1"))

    async def main():
        with driver.driving():
            driver.start(flow())
            assert await driver.settle()
            assert [task.key for task in driver._outbox] == ["a-1"]
            await driver.finish()

    asyncio.run(main())
    assert driver.calls["0"].state == "closed" and not driver.alive()


def test_one_driver_per_event_loop():
    async def main():
        with FlowDriver().driving():
            with pytest.raises(RuntimeError, match="one event loop runs one run at a time"):
                with FlowDriver().driving():
                    pass

    asyncio.run(main())


def test_a_slow_step_is_logged(caplog):
    driver = FlowDriver(slow_step_s=0.01)

    async def flow():
        time.sleep(0.02)
        await driver.wait(t("a-1"))

    with caplog.at_level(logging.WARNING):
        drive(flow(), driver=driver)
    assert "heavy work belongs in a Python task" in caplog.text


def test_a_flow_is_a_coroutine():
    def generator():
        yield t("a-1")

    async def main():
        with FlowDriver().driving() as driver:
            with pytest.raises(TypeError, match="not function"):
                driver.start(lambda: None)  # type: ignore[arg-type]
            with pytest.raises(TypeError, match=r"`yield x` -> `await x`"):
                driver.start(generator())  # type: ignore[arg-type]

    asyncio.run(main())
