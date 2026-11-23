"""Queues that run as they do in a run, with a thread pool and the real clock, report what
the Lean specification proves of the queue: no task starts before the tasks it comes after
finished, each task finishes once, every accepted task finishes, and the running tasks stay
within the queue's size, the capacity of each claim name and one task per key
(`tests/lean/trace.py`, `lean/Conformance/Trace.lean`). Needs Lean: `-m lean`."""

from __future__ import annotations

import copy
import importlib.util
import random
import shutil
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from contraagent import DeferralCause, Task, TaskResult
from contraagent.engine import Deferral, WorkQueue

pytestmark = pytest.mark.lean


def _trace():
    spec = importlib.util.spec_from_file_location("lean_trace", Path(__file__).parent / "lean" / "trace.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trace = _trace()


@pytest.fixture(autouse=True)
def lean():
    if shutil.which("lake") is None and not (Path.home() / ".elan" / "bin" / "lake").exists():
        pytest.skip("Lean is not installed (elan)")


class Sleeps:
    """A runner whose tasks take a few milliseconds on the queue's threads, some failing
    once, some resting."""

    def __init__(self, rng: random.Random, resting: set[str], failing: set[str]) -> None:
        self.rng, self.resting, self.failing = rng, resting, failing
        self.failed: set[str] = set()
        self._lock = threading.Lock()

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=2 if task.kind == "capped" else None)

    def deferral(self, task: Task) -> Deferral | None:
        return Deferral("its credential rests", DeferralCause(cause="rest")) if task.key in self.resting else None

    def run(self, task: Task) -> TaskResult:
        time.sleep(task.params["sleep"])
        with self._lock:
            first = task.key in self.failing and task.id not in self.failed
            self.failed.add(task.id)
        if first:
            return TaskResult(task=task, ok=False, stop="error")
        return TaskResult(task=task, ok=True, stop="completed")


def run_queue(seed: int) -> None:
    """One queue with random tasks, dependencies, claims, follow-ups, a resume's skips, rests,
    failures that are retried, and cancels while it runs."""
    rng = random.Random(seed)
    n = rng.randint(3, 14)

    def make(i: int, after: tuple[str, ...]) -> Task:
        return Task(
            rng.choice(["a", "b", "capped"]),
            key=f"t{i}" if rng.random() > 0.05 or i == 0 else f"t{rng.randrange(i)}",
            after=after,
            claims=tuple(rng.sample(["x", "y", "z"], rng.choice([0, 0, 1, 2]))),
            params={"sleep": rng.choice([0.0, 0.001, 0.003, 0.01])},
            cancellable=True,
        )

    tasks = [make(i, tuple(f"t{j}" for j in range(i) if rng.random() < 0.3)) for i in range(n)]
    later = {t.key: make(n + i, (t.key,) if rng.random() < 0.7 else ()) for i, t in enumerate(tasks) if rng.random() < 0.4}
    keys = sorted({t.key for t in tasks})
    runner = Sleeps(rng, {k for k in keys if rng.random() < 0.08}, {k for k in keys if rng.random() < 0.15})
    skipped = {k for k in keys if rng.random() < 0.1}
    cancels = [k for k in keys if rng.random() < 0.1]
    queue = WorkQueue(
        runner,
        follow_up=lambda res: [later.pop(res.task.key)] if res.task.key in later else [],
        skip=lambda task: task.key in skipped,
        max_concurrent=rng.randint(1, 4),
        claim_capacity={"x": rng.choice([1, 2]), "y": 1},
        retry_on=frozenset({"error"}),
        retry_wait_s=0.002,
    )

    async def between_passes() -> bool:
        while cancels and rng.random() < 0.5:
            queue.cancel(cancels.pop())
        return False

    queue.between_passes = between_passes
    for task in tasks:
        queue.add(task)
    queue.run()


def test_queues_that_run_on_threads_report_what_the_specification_proves():
    with trace.Recorder() as recorder:
        for seed in range(60):
            run_queue(seed)
    assert len(recorder.traces) == 60 and all(t["complete"] for t in recorder.traces)
    assert sum(1 for t in recorder.traces for e in t["events"] if e["event"] == "start") > 200
    broken = trace.breaks(recorder.traces)
    assert not broken, "\n".join(f"{test}: {line}" for test, lines in broken for line in lines)


def test_a_log_that_breaks_what_is_proved_is_found():
    """The check is of the log: one changed by hand breaks what it should."""
    with trace.Recorder() as recorder:
        queue = WorkQueue(Sleeps(random.Random(0), set(), set()), max_concurrent=2, claim_capacity={"x": 1})
        queue.add(Task("a", key="first", claims=("x",), params={"sleep": 0.0}))
        queue.add(Task("a", key="second", after=("first",), claims=("x",), params={"sleep": 0.0}))
        queue.run()
    (good,) = recorder.traces
    assert trace.breaks([good]) == []
    events = good["events"]

    def changed(edit) -> list[str]:
        other = copy.deepcopy(good)
        edit(other["events"])
        ((_, lines),) = trace.breaks([other])
        return lines

    def early(evs) -> None:  # the second task starts before the first one finished
        start = next(i for i, e in enumerate(evs) if e["event"] == "start" and e["key"] == "second")
        evs.insert(next(i for i, e in enumerate(evs) if e["event"] == "start"), evs.pop(start))

    def twice(evs) -> None:
        evs.append(next(e for e in evs if e["event"] == "finished"))

    def unfinished(evs) -> None:
        evs[:] = [e for e in evs if not (e["event"] == "finished" and e["key"] == "second")]

    assert any("before a task it comes after finished" in line for line in changed(early))
    assert any("holder 2 of x" in line for line in changed(early))
    assert any("finished 2 times" in line for line in changed(twice))
    assert any("was accepted and did not finish" in line for line in changed(unfinished))
    assert [e["event"] for e in events][:2] == ["queued", "queued"]
