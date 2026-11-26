"""Scenarios of the flow driver, played on `FlowDriver` and on the Lean specification.

    uv run python tests/lean/flow_scenarios.py     # rewrites tests/lean/flow_scenarios.jsonl

A scenario is a flow made as data (waits, tasks, `gather`, Tasks awaited or not, Tasks that
are cancelled when one of them fails, failures caught or not), how its tasks end, the order
in which their results come, and the calls that the run of that flow makes on its driver (`ops`), which `scenarios` records by
running it. `lean/Conformance/Flow.lean` has the fields of a call. The specification is
played on the calls. `play` runs the flow again on `FlowDriver`, where no event loop runs and
with a board in the queue's place, checks that it makes the same calls, and returns what the
driver answered each, the tasks it gave the queue, the keys it cancelled and how each flow
call ended (`lake exe contraagent-lean flow`). `tests/lean/flow_scenarios.jsonl` holds
scenarios with what the specification answers for each; `tests/test_lean_scenarios.py` plays
them on the code.
"""

from __future__ import annotations

import asyncio
import importlib.util
import random
from pathlib import Path
from typing import Any

from contraagent import Task, TaskDeferred, TaskFailed, TaskResult
from contraagent._internal.dispatch import flow as flow_module
from contraagent._internal.dispatch import result_or_raise
from contraagent._internal.dispatch.flowloop import FlowTask
from contraagent.engine import FlowDriver

FILE = Path(__file__).with_name("flow_scenarios.jsonl")
#: What `lake exe contraagent-lean` is asked to play.
WHAT = "flow"
#: The scenarios of the committed file: `scenarios(SEED, COUNT)`.
SEED, COUNT = 20261124, 30


class Board:
    """In the place of the `WorkQueue`: holds the tasks in flight, those of its own from the
    start and those the driver gives it, and the keys the driver cancels. As the queue, it
    refuses a task whose key is in flight, and finishes it as a duplicate key at once."""

    def __init__(self, own: list[str], follow_up: Any) -> None:
        self.flying: dict[str, Task] = {key: Task("step", key=key) for key in own}
        self.sent: list[str] = []
        self.cancels: list[str] = []
        self.cancelled: set[str] = set()
        self.between_passes: Any = None
        self._follow_up = follow_up

    def extend(self, tasks: Any) -> None:
        for task in tasks:
            self.sent.append(task.key)
            if task.key in self.flying:
                self._follow_up(TaskResult.duplicate_key(task))
            else:
                self.flying[task.key] = task

    def cancel(self, key: str) -> bool:
        self.cancels.append(key)
        if key in self.flying:
            self.cancelled.add(key)
        return key in self.flying

    def wake(self) -> None:
        return None

    def past_hard_stop(self) -> bool:
        return False


class Noted(FlowDriver):
    """A driver that notes each call made on it (`ops`) and what it answered (`answers`)."""

    def __init__(self, past: bool, replay: dict[str, int]) -> None:
        self.ops: list[dict[str, Any]] = []
        self.answers: list[Any] = []
        self.past = past
        self.quiet = False  # inside `_cancel_rest`: its cancels are its own
        super().__init__(answer=self._answered, past_grace=self._past, replay=replay, on_give=self._given)

    def note(self, op: str, answer: Any = None, **fields: Any) -> int:
        call = self.current
        blank = {"parent": None, "call": call.id if call is not None else None, "key": "", "cancellable": False}
        self.ops.append({"op": op, **blank, "stop": "", "how": "", "flag": False, **fields})
        self.answers.append(answer)
        return len(self.answers) - 1

    def _past(self) -> bool:
        return self.past

    def _answered(self, item: Any, result: TaskResult) -> Any:
        self.note("waited", False, stop=result.stop, flag=self.past)
        return result_or_raise(item, result)

    def _cancel(self, call: Any, own: bool) -> Any:
        self.note("waited", True, stop="deferred", flag=self.past)
        return super()._cancel(call, own)

    def _given(self, result: TaskResult) -> None:
        self.note("give", result.task.key, call=None)

    def _make_task(self, coro: Any, *, name: str | None = None, context: Any = None) -> Any:
        task = super()._make_task(coro, name=name, context=context)
        made = self._made
        assert made is not None
        self.note("create", made.id, call=None, parent=made.parent.id if made.parent is not None else None)
        return task

    def add(self, task: Task) -> None:
        self.note("add", key=task.key, cancellable=task.cancellable)
        super().add(task)

    def _waiting(self, item: Any) -> Any:
        task = self._waits_for(item)
        self.note("wait", task.key in self.done, key=task.key)
        return (yield from super()._waiting(item))

    def follow_up(self, result: TaskResult) -> list[Task]:
        self.note("result", call=None, key=result.task.key, stop=result.stop)
        return super().follow_up(result)

    def _task_done(self, call: Any, task: Any) -> None:
        if call.state != "running":
            return super()._task_done(call, task)
        how = "cancelled" if task.cancelled() else "raised" if task.exception() is not None else "returned"
        at = self.note("ended", call=call.id, how=how)
        super()._task_done(call, task)
        self.answers[at] = call.state
        return None

    def _close_stuck(self) -> bool:
        at = self.note("closeStuck", call=None, flag=bool(self._loop.ready()))
        closed = super()._close_stuck()
        self.answers[at] = closed
        return closed

    def _end_stuck(self) -> None:
        self.note("endStuck", call=None, flag=bool(self._loop.ready()))
        super()._end_stuck()

    def _cancel_rest(self) -> None:
        self.note("cancelRest", call=None)
        self.quiet = True
        try:
            super()._cancel_rest()
        finally:
            self.quiet = False

    def _close_rest(self) -> None:
        self.note("closeRest", call=None)
        super()._close_rest()

    def attach(self, queue: Any) -> None:
        self.note("attach", call=None)
        super().attach(queue)


def _run(scenario: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the scenario's flow on a driver: the calls made on it, and what it showed."""
    driver = Noted(scenario["pastGrace"], dict(scenario["replay"]))
    board = Board([key for key, _ in scenario["own"]], driver.follow_up)
    stops: dict[str, str] = dict(scenario["own"])  # a key of the queue's own ends as the queue says

    class Told(FlowTask):  # pyright: ignore[reportMissingTypeArgument]
        """A flow call's Task that tells when it is cancelled."""

        def cancel(self, msg: Any = None) -> bool:
            if not self.done() and not driver.quiet:
                call = next((c for c in driver.calls.values() if c.task is self), None)
                if call is not None:
                    driver.note("cancelled", call=call.id)
            return super().cancel(msg)

    def task(key: str, stop: str, cancellable: bool) -> Task:
        stops.setdefault(key, stop)  # a key that two steps name ends as the first says
        return Task("step", key=key, cancellable=cancellable)

    async def run(todo: list[Any]) -> None:
        waiting: list[asyncio.Task[None]] = []
        for step in todo:
            name = step[0]
            if name == "wait":
                await driver.wait(task(step[1], step[2], step[3]))
            elif name == "add":
                driver.add(task(step[1], step[2], step[3]))
            elif name == "gather":
                # An item is one wait, or a flow of its own (also one of no step).
                items = [driver.wait(task(item[1], item[2], item[3])) if item and item[0] == "wait" else run(item) for item in step[1]]
                await asyncio.gather(*items, return_exceptions=step[2])
            elif name == "task":
                child = asyncio.create_task(run(step[1]))
                if step[2]:
                    waiting.append(child)
            elif name == "group":
                # As a `TaskGroup`: when one fails, the others are cancelled. A `TaskGroup` cancels
                # them in the order of a set, which changes from run to run; here, of their creation.
                group = [asyncio.create_task(run(item)) for item in step[1]]
                try:
                    await asyncio.gather(*group)
                except (Exception, asyncio.CancelledError):  # not GeneratorExit: a coroutine closed waits no more
                    for other in group:
                        other.cancel()
                    await asyncio.gather(*group, return_exceptions=True)
                    raise
            elif name == "catch":
                try:
                    await run(step[1])
                except* (TaskFailed, TaskDeferred):
                    pass
            elif name == "keep":  # flow code that goes on when it is cancelled
                try:
                    await run(step[1])
                except asyncio.CancelledError:
                    pass
            elif name == "fail":  # flow code that fails by itself
                raise RuntimeError("the flow code failed")
            else:  # a wait that nothing answers
                await asyncio.Event().wait()
        for child in waiting:
            await child

    rng = random.Random(scenario["order"])
    real = flow_module.FlowTask
    flow_module.FlowTask = Told  # pyright: ignore[reportAttributeAccessIssue]
    try:
        with driver.driving():
            driver.start(run(scenario["flow"]))
            if scenario["lateAttach"]:
                driver.settle_here()
            driver.attach(board)
            while True:
                driver.settle_here()
                waits = list(board.flying)
                if not waits:
                    break
                rng.shuffle(waits)
                for key in waits[: rng.randint(1, len(waits))]:
                    flown = board.flying.pop(key)
                    stop = "skipped" if key in driver._replay else stops[key]
                    if key in board.cancelled:
                        board.cancelled.discard(key)
                        stop = "cancelled"
                    driver.follow_up(TaskResult(task=flown, ok=stop in ("completed", "skipped"), stop=stop))
            driver.finish_here()
    finally:
        flow_module.FlowTask = real  # pyright: ignore[reportAttributeAccessIssue]
    # Copies: flow code that outlives the run (a Task that went on after every cancellation)
    # is closed when the collector frees it, whenever that is, and must not change the record.
    shown = {
        "answers": list(driver.answers),
        "sent": list(board.sent),
        "cancels": list(board.cancels),
        "states": [[call.id, call.state] for call in driver.calls.values()],
        "running": driver._running,
    }
    return list(driver.ops), shown


def play(scenario: dict[str, Any]) -> dict[str, Any]:
    """Run the scenario's flow on a `FlowDriver`: what the driver answered each call, the
    tasks it gave the queue, the keys it cancelled, and how each flow call ended. The calls
    are those of the scenario: the same flow makes the same calls in every run."""
    ops, shown = _run(scenario)
    assert ops == scenario["ops"], "the flow made other calls on its driver than the scenario's"
    return shown


def _steps(rng: random.Random, names: Any, used: list[str], depth: int, busy: bool) -> list[Any]:
    """A random flow as data: a list of steps, each a list named by its first item. A step
    names a new task, or one that an earlier step named. `busy`: more of its tasks are
    cancellable, fail and are named again, and more of its steps create tasks and Tasks."""

    def name() -> str:
        if used and rng.random() < (0.5 if busy else 0.25):
            return rng.choice(used)
        used.append(next(names))
        return used[-1]

    def below() -> list[Any]:
        return _steps(rng, names, used, depth - 1, busy)

    made: list[Any] = []
    kinds = ["wait", "wait", "add"]
    if depth:
        kinds = ["wait", "wait", "wait", "gather", "task", "group", "catch", "add", "keep", "never", "fail"]
        if busy:
            kinds += ["add", "add", "group", "task", "keep"]
    for _ in range(rng.randint(1, 4)):
        kind = rng.choice(kinds)
        stop = rng.choices(["completed", "error", "deferred"], [55, 25, 20] if busy else [75, 15, 10])[0]
        cancellable = rng.random() < (0.9 if busy else 0.5)
        if kind in ("wait", "add"):
            made.append([kind, name(), stop, cancellable])
        elif kind == "gather":
            items = [below() if rng.random() < 0.5 else ["wait", name(), stop, cancellable] for _ in range(rng.randint(1, 3))]
            made.append(["gather", items, rng.random() < 0.3])
        elif kind == "task":
            made.append(["task", below(), rng.random() < 0.7])
        elif kind == "group":
            made.append(["group", [below() for _ in range(rng.randint(1, 3))]])
        elif kind in ("never", "fail"):
            if rng.random() < 0.3:  # rare: it stops the flow call, until the driver closes it or at once
                made.append([kind])
        else:
            made.append([kind, below()])
    return made


def scenario(rng: random.Random) -> dict[str, Any]:
    """A random scenario: a flow of a few levels whose tasks end well, fail or are deferred,
    some of them cancellable, some named by more than one step, some skipped on a resume,
    some the queue's own from the start, with waits that nothing answers, flow code that
    fails by itself and flow code that goes on when it is cancelled, to wait again or to
    create a task; with the calls its run makes."""
    count = [0]

    def names() -> Any:
        while True:
            count[0] += 1
            yield f"t{count[0] - 1}"

    source = names()
    flow = _steps(rng, source, [], 3, rng.random() < 0.4)
    # What random steps seldom reach, begun by a Task of its own that the flow does not await.
    opening = rng.random()
    if opening < 0.1:
        # A cancellable task whose creator is cancelled at once: before the queue is attached,
        # when it is attached late.
        early = [["add", next(source), "completed", True], ["never"]]
        flow = [["task", [["group", [early, [["fail"]]]]], False], *flow]
    elif opening < 0.2:
        # Flow code that goes on when the driver closes it: it waits again for what nothing
        # answers, and is ended; or it creates a task, and gets the task's answer; or it
        # creates a Task that waits for what nothing answers, which the next settle closes.
        again = rng.choice(
            [
                [["never"]],
                [["wait", next(source), "completed", False], ["never"]],
                [["task", [["never"]], False], ["never"]],
            ]
        )
        flow = [["task", [["keep", [["never"]]], *again], False], *flow]
    elif opening < 0.4:
        # A cancellable task whose creator is cancelled while another flow call waits for it,
        # which is cancelled later, when the results come in that order.
        key, first, second = next(source), next(source), next(source)
        creator = [["add", key, "completed", True], ["never"]]
        waiter = [["wait", key, "completed", True]]
        flow = [
            ["task", [["catch", [["group", [creator, [["wait", first, "error", False]]]]]]], False],
            ["task", [["catch", [["group", [waiter, [["wait", second, "error", False]]]]]]], False],
            *flow,
        ]
    keys = [f"t{i}" for i in range(count[0])]
    skipped = [key for key in keys if rng.random() < 0.15]
    rng.shuffle(skipped)
    own = [[key, rng.choice(["completed", "completed", "error"])] for key in [*keys, "own"] if rng.random() < 0.12]
    made = {
        "flow": flow,
        "order": rng.randrange(1 << 30),
        "pastGrace": rng.random() < 0.3,
        "lateAttach": rng.random() < 0.3,
        "replay": [[key, place] for place, key in enumerate(skipped)],
        "own": own,
    }
    made["ops"] = _run({**made, "ops": []})[0]
    return made


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
