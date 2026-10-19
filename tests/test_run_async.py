"""`run_async` of `WorkQueue` and `Pipeline` on a running event loop, their synchronous
`run` entries, the queue's wake, and Ctrl-C while the queue's loop waits."""

import asyncio
import os
import signal
import threading
from types import SimpleNamespace

import pytest

from contraagent import Pipeline, Task, TaskResult, python_task
from contraagent._internal.dispatch import queue as queue_module
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


class Gated:
    """Runs a task by waiting up to 30 seconds for its gate (`gates[task.key]`), if it has one."""

    def __init__(self, *gated: str) -> None:
        self.gates = {key: threading.Event() for key in gated}
        self.started: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def started_event(self, key: str) -> threading.Event:
        with self._lock:
            return self.started.setdefault(key, threading.Event())

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        self.started_event(task.key).set()
        gate = self.gates.get(task.key)
        if gate is not None:
            gate.wait(timeout=30)
        return TaskResult(task=task, ok=True, stop="completed")


async def until(condition, timeout_s: float = 30.0) -> None:
    """Yield to the event loop until `condition()` holds."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    while not condition():
        assert asyncio.get_running_loop().time() < deadline, "the condition never held"
        await asyncio.sleep(0.01)


def test_run_async_runs_the_queue_on_a_running_loop_and_leaves_it_free():
    runner = Gated("a")
    q = WorkQueue(runner)
    q.add(Task("step", key="a"))

    async def main():
        queue = asyncio.ensure_future(q.run_async())
        # The runner blocks on a thread of the queue's pool; this coroutine still runs.
        await until(runner.started_event("a").is_set)
        runner.gates["a"].set()
        return await queue

    summary = asyncio.run(main())
    assert summary["finished"] == 1 and summary["ok"] == 1


def test_run_from_a_running_loop_raises_and_names_run_async():
    q = WorkQueue(Gated())
    q.add(Task("step", key="a"))

    async def main():
        with pytest.raises(RuntimeError, match=r"await queue\.run_async\(\)"):
            q.run()

    asyncio.run(main())
    assert q.run()["finished"] == 1  # nothing ran, and nothing was lost


def test_a_task_added_while_the_queue_waits_wakes_it(monkeypatch):
    # Only a finished task or the wake can end the wait: a poll of an hour never does.
    monkeypatch.setattr(queue_module, "POLL_S", 3600.0)
    runner = Gated("a")
    finished: list[str] = []

    def follow_up(result: TaskResult) -> list[Task]:
        finished.append(result.task.key)
        runner.gates["a"].set()
        return []

    q = WorkQueue(runner, follow_up=follow_up)
    q.add(Task("step", key="a"))

    async def main():
        queue = asyncio.ensure_future(q.run_async())
        await until(runner.started_event("a").is_set)
        q.add(Task("step", key="b"))  # from outside the queue's pass, while it waits
        return await queue

    summary = asyncio.run(main())
    assert finished == ["b", "a"] and summary["finished"] == 2


@python_task
def double(n: int) -> int:
    return 2 * n


def flow(n: int):
    doubled = yield double(n=n)
    return doubled


def pipeline(tmp_path) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=StubAgent().backends(), cwd=tmp_path, log=lambda line: None)


def test_pipeline_run_async_awaited_from_a_running_loop(tmp_path):
    async def main():
        return await pipeline(tmp_path).run_async(flow, 3, run_id="r")

    report = asyncio.run(main())
    assert report.ok and report.value == 6 and report.run_id == "r"


def test_pipeline_run_from_a_running_loop_raises_and_writes_nothing(tmp_path):
    async def main():
        with pytest.raises(RuntimeError, match=r"await pipeline\.run_async\(\.\.\.\)"):
            pipeline(tmp_path).run(flow, 3, run_id="r")

    asyncio.run(main())
    assert not (tmp_path / "runs" / "r").exists()


@pytest.mark.skipif(os.name == "nt", reason="a signal to the process itself")
def test_ctrl_c_while_the_queue_waits_ends_the_run_and_puts_its_handlers_back(tmp_path, monkeypatch):
    if threading.current_thread() is not threading.main_thread():  # pragma: no cover
        pytest.skip("signal handlers live on the main thread")
    monkeypatch.setattr(queue_module, "POLL_S", 3600.0)  # the main thread waits in the event loop
    release = threading.Event()

    @python_task
    def hold(unit: str) -> str:
        os.kill(os.getpid(), signal.SIGINT)
        release.wait(timeout=30)  # until the signal reached the main thread
        return unit

    def host(signum, frame):  # the program's own handler, called after the run's teardown
        release.set()
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGINT, host)
    try:
        with pytest.raises(KeyboardInterrupt):
            pipeline(tmp_path).run(lambda: hold(unit="a"), run_id="r")
        # The run's own `finally` ran: the handler is back and the run's lock is free.
        assert signal.getsignal(signal.SIGINT) is host
    finally:
        release.set()
        signal.signal(signal.SIGINT, previous)
    assert pipeline(tmp_path).run(lambda: double(n=1), run_id="r", resume=True).ok


@pytest.mark.skipif(os.name == "nt", reason="a signal to the process itself")
def test_ctrl_c_in_the_flow_code_stops_it_at_once(tmp_path):
    if threading.current_thread() is not threading.main_thread():  # pragma: no cover
        pytest.skip("signal handlers live on the main thread")
    went_on: list[bool] = []

    def interrupted():
        os.kill(os.getpid(), signal.SIGINT)
        went_on.append(True)  # never reached: Ctrl-C does not wait for an `await`
        return double(n=1)

    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        with pytest.raises(KeyboardInterrupt):
            pipeline(tmp_path).run(interrupted, run_id="r")
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, previous)
    assert went_on == []
