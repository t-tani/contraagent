"""`FlowDriver`: generator flows over a `WorkQueue`, with the default (raw `Task`) callbacks
and with `result_or_raise`."""

import logging
import threading
import time
from types import SimpleNamespace

import pytest

from contraagent.dispatch import FlowDriver, Task, TaskDeferred, TaskFailed, TaskResult, WorkQueue, result_or_raise


class Runner:
    """Runs a task by sleeping `params["sleep"]` and ending with `params["stop"]`;
    records launches and how many ran at once."""

    def __init__(self) -> None:
        self.launched: list[str] = []
        self.peak = 0
        self._running = 0
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        with self._lock:
            self.launched.append(task.key)
            self._running += 1
            self.peak = max(self.peak, self._running)
        time.sleep(task.params.get("sleep", 0.0))
        with self._lock:
            self._running -= 1
        stop = task.params.get("stop", "completed")
        return TaskResult(task=task, ok=stop == "completed", stop=stop, reason="" if stop == "completed" else "scripted")


def t(key: str, **params) -> Task:
    return Task(key.split("-")[0], key=key, params=params)


def drive(*flows, driver: FlowDriver | None = None, **queue_options) -> tuple[FlowDriver, Runner, dict]:
    driver = driver or FlowDriver()
    runner = Runner()
    summary = driver.run(WorkQueue(runner, **queue_options), *flows)
    return driver, runner, summary


def test_a_single_yield_receives_the_task_result():
    def flow():
        res = yield t("a-1")
        return res.stop

    driver, runner, _ = drive(flow())
    top = driver.calls["0"]
    assert (top.state, top.value, runner.launched) == ("returned", "completed", ["a-1"])


def test_a_batch_waits_for_all_and_answers_in_yield_order():
    def flow():
        results = yield [t("a-slow", sleep=0.2), t("a-fast")]
        return [r.task.key for r in results]

    driver, runner, _ = drive(flow())
    assert driver.calls["0"].value == ["a-slow", "a-fast"]
    assert runner.peak == 2


def test_an_empty_batch_answers_at_once():
    def flow():
        return (yield [])

    driver, _, _ = drive(flow())
    assert driver.calls["0"].value == []


def test_child_generators_are_flow_calls_running_concurrently():
    def per_unit(u):
        a = yield t(f"a-{u}", sleep=0.2)
        b = yield t(f"b-{u}")
        return (a.stop, b.task.key)

    def flow():
        return (yield [per_unit(u) for u in ("x", "y")])

    started: list[tuple[str, str]] = []
    driver = FlowDriver(on_flow_call=lambda event, call: started.append((event, call.id)))
    driver, runner, _ = drive(flow(), driver=driver)
    assert driver.calls["0"].value == [("completed", "b-x"), ("completed", "b-y")]
    assert runner.peak == 2
    assert list(driver.calls) == ["0", "0.1", "0.2"]
    child = driver.calls["0.1"]
    assert child.parent is driver.calls["0"] and child.function.endswith("per_unit")
    assert child.site is not None and child.site[0] == __file__
    assert started[:3] == [("start", "0"), ("start", "0.1"), ("start", "0.2")] and ("end", "0") == started[-1]


def test_yield_from_stays_in_the_same_flow_call():
    def helper(u):
        r = yield t(f"a-{u}")
        return r.task.key

    def flow():
        first = yield from helper("1")
        second = yield from helper("2")
        return [first, second]

    driver, _, _ = drive(flow())
    assert list(driver.calls) == ["0"] and driver.calls["0"].value == ["a-1", "a-2"]


def test_a_child_flow_call_nested_through_yield_from_records_its_site():
    def child():
        return (yield t("a-1"))

    def helper():
        return (yield child())

    def flow():
        return (yield from helper())

    driver, _, _ = drive(flow())
    site = driver.calls["0.1"].site
    assert site is not None and site[1] == helper.__code__.co_firstlineno + 1


def test_an_error_from_on_flow_call_at_a_child_start_fails_the_child_before_it_runs():
    ran: list[str] = []

    def child(u):
        ran.append(u)
        return (yield t(f"a-{u}"))

    def flow():
        try:
            yield [child("1"), child("2")]
        except LookupError as exc:
            return f"caught {exc}"

    def on_flow_call(event, call):
        if event == "start" and call.id == "0.2":
            raise LookupError("refused")

    driver, runner, _ = drive(flow(), driver=FlowDriver(on_flow_call=on_flow_call))
    assert driver.calls["0"].value == "caught refused" and ran == ["1"] and runner.launched == ["a-1"]
    assert (driver.calls["0.2"].state, str(driver.calls["0.2"].error)) == ("raised", "refused")


def test_a_child_exception_raises_at_the_parent_yield():
    def child():
        yield t("a-1")
        raise ValueError("bad")

    def flow():
        try:
            yield [child()]
        except ValueError as exc:
            return f"caught {exc}"

    driver, _, _ = drive(flow())
    assert driver.calls["0.1"].state == "raised" and driver.calls["0"].value == "caught bad"


def test_an_uncaught_exception_ends_the_flow_call_raised():
    def flow():
        yield t("a-1")
        raise RuntimeError("boom")

    driver, _, _ = drive(flow())
    top = driver.calls["0"]
    assert top.state == "raised" and isinstance(top.error, RuntimeError)


def test_result_or_raise_throws_the_first_failure_by_position_after_the_batch_settles():
    def flow():
        try:
            yield [t("a-ok", sleep=0.1), t("a-late", stop="error", sleep=0.2), t("a-early", stop="timeout")]
        except TaskFailed as exc:
            return exc

    driver, runner, _ = drive(flow(), driver=FlowDriver(answer=result_or_raise))
    exc = driver.calls["0"].value
    assert isinstance(exc, TaskFailed) and not isinstance(exc, TaskDeferred)
    assert (exc.key, exc.stop, exc.result.reason) == ("a-late", "error", "scripted")
    assert exc.item is exc.result.task
    assert sorted(runner.launched) == ["a-early", "a-late", "a-ok"]


def test_a_deferred_task_raises_task_deferred_and_the_flow_may_yield_a_finishing_task():
    def flow():
        try:
            yield t("scan-1")
        except TaskDeferred as exc:
            report = yield t("report-1")
            return (exc.stop, report.stop)

    driver = FlowDriver(answer=result_or_raise)
    q = WorkQueue(Runner(), deadline_s=0.001, finishing_kinds=("report",))
    time.sleep(0.01)
    driver.run(q, flow())
    assert driver.calls["0"].value == ("deferred", "completed")


def test_past_the_grace_window_a_waiting_flow_call_and_its_parent_are_closed():
    closed: list[str] = []

    def child():
        try:
            yield t("scan-1")
        finally:
            closed.append("child")

    def flow():
        try:
            yield [child()]
        finally:
            closed.append("parent")

    driver = FlowDriver(answer=result_or_raise)
    q = WorkQueue(Runner(), deadline_s=0.001, grace_s=0.0)
    time.sleep(0.01)
    driver.run(q, flow())
    assert closed == ["child", "parent"]
    assert {c.id: c.state for c in driver.calls.values()} == {"0": "closed", "0.1": "closed"}


def test_ids_are_the_same_in_every_run():
    def leaf(i):
        return (yield t(f"a-{i}"))

    def mid(i):
        yield [leaf(i), leaf(i + 10)]
        return (yield leaf(i + 20))

    def flow():
        return (yield [mid(1), mid(2)])

    # The ids, not the order calls start in (that follows which task finishes first).
    runs = [{c.id: c.function.rsplit(".", 1)[-1] for c in drive(flow())[0].calls.values()} for _ in range(2)]
    assert runs[0] == runs[1]
    assert sorted(runs[0]) == ["0", "0.1", "0.1.1", "0.1.2", "0.1.3", "0.2", "0.2.1", "0.2.2", "0.2.3"]


def test_the_frontier_follows_what_each_flow_call_received():
    seen: dict[str, tuple[str, ...]] = {}
    driver = FlowDriver()

    def child(u):
        seen[f"child {u} start"] = driver.current.frontier if driver.current else ()
        yield t(f"b-{u}")
        seen[f"child {u} end"] = driver.current.frontier if driver.current else ()

    def flow():
        yield [t("a-1"), t("a-2")]
        seen["after batch"] = driver.current.frontier if driver.current else ()
        yield [child("x"), child("y")]
        seen["after children"] = driver.current.frontier if driver.current else ()

    drive(flow(), driver=driver)
    assert seen == {
        "after batch": ("a-1", "a-2"),
        "child x start": ("a-1", "a-2"),
        "child y start": ("a-1", "a-2"),
        "child x end": ("b-x",),
        "child y end": ("b-y",),
        "after children": ("b-x", "b-y"),
    }


def test_a_done_key_is_answered_at_once_and_a_shared_key_runs_once():
    def child():
        return (yield t("a-shared", sleep=0.1))

    def flow():
        first = yield [child(), child()]
        again = yield t("a-shared")
        return [r.task.key for r in [*first, again]]

    driver, runner, _ = drive(flow())
    assert runner.launched == ["a-shared"]
    assert driver.calls["0"].value == ["a-shared"] * 3 and "a-shared" in driver.done


def test_created_tasks_run_whether_or_not_they_are_yielded():
    made: list[Task] = []

    def created():
        out, made[:] = list(made), []
        return out

    def flow():
        made.append(t("side-1"))
        return (yield t("a-1"))

    driver, runner, _ = drive(flow(), driver=FlowDriver(created=created))
    assert sorted(runner.launched) == ["a-1", "side-1"] and driver.calls["0"].state == "returned"


def test_waits_for_errors_are_thrown_at_the_yield():
    def flow():
        try:
            yield 3
        except TypeError as exc:
            return str(exc)

    driver, _, _ = drive(flow())
    assert "not int" in driver.calls["0"].value


def test_a_typed_answer_and_item_come_from_the_callbacks():
    def waits_for(item):
        return t(item)

    def flow():
        return (yield ["a-1", "a-2"])

    driver = FlowDriver(waits_for=waits_for, answer=lambda item, result: f"{item}:{result.stop}")
    driver, _, _ = drive(flow(), driver=driver)
    assert driver.calls["0"].value == ["a-1:completed", "a-2:completed"]


def test_a_key_in_flight_outside_the_driver_raises_task_failed_duplicate_key():
    def flow():
        try:
            yield t("a-1")
        except TaskFailed as exc:
            return exc.stop

    driver = FlowDriver(answer=result_or_raise)
    q = WorkQueue(Runner())
    q.add(t("a-1", sleep=0.2))
    driver.run(q, flow())
    assert driver.calls["0"].value == "duplicate_key" and driver.done["a-1"].stop == "completed"


def test_a_thousand_children_and_a_deep_nesting_use_no_recursion():
    def leaf(i):
        return (yield t(f"a-{i}"))

    def flow():
        return len((yield [leaf(i) for i in range(1000)]))

    driver, runner, _ = drive(flow(), max_concurrent=32)
    assert driver.calls["0"].value == 1000 and len(runner.launched) == 1000

    def nest(n):
        if n == 0:
            return 0
        return (yield nest(n - 1)) + 1

    deep = FlowDriver()
    assert deep.start(nest(3000)) == []
    assert deep.calls["0"].value == 3000


def test_finish_closes_what_is_still_suspended():
    def flow():
        yield t("a-1")

    driver = FlowDriver()
    assert [task.key for task in driver.start(flow())] == ["a-1"]
    assert [c.id for c in driver.waiting] == ["0"]
    driver.finish()
    assert driver.calls["0"].state == "closed" and driver.waiting == []


def test_a_slow_step_is_logged(caplog):
    def flow():
        time.sleep(0.02)
        yield t("a-1")

    with caplog.at_level(logging.WARNING):
        drive(flow(), driver=FlowDriver(slow_step_s=0.01))
    assert "heavy work belongs in a Python task" in caplog.text


def test_a_flow_is_a_generator():
    with pytest.raises(TypeError):
        FlowDriver().start(lambda: None)  # type: ignore[arg-type]
