"""What each `WorkQueue` reports while it runs, checked against what the Lean specification
proves of the queue.

A scenario of `queue_scenarios.py` plays the queue on a clock that the scenario moves, one
step at a time. A trace is of a queue that ran as it does in a run: with its runner, its
thread pool and the real clock. `Recorder` notes what every queue made while it is on
reports, and `breaks` gives each trace to `lake exe contraagent-lean trace`, which checks
it against the conclusions of the theorems (`lean/Conformance/Trace.lean`).

    CONTRAAGENT_TRACE=<folder> uv run pytest ...   # notes every queue of the session (tests/conftest.py)
    uv run python tests/lean/trace.py <folder>     # checks what was noted; needs Lean

The first command works with any tests: the whole suite, `-m e2e`, or `-m live` with real
coding agents. It notes the queues of the test process, not those of a process a test
starts.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from contraagent import Task, TaskResult
from contraagent.engine import WorkQueue


def _note(trace: dict[str, Any], queue: WorkQueue, event: str, task: Task, **more: Any) -> None:
    if event == "queued":
        for name in task.claims:
            entry = queue._entry(name)
            if isinstance(entry, int):
                trace["capacity"][name] = entry
            else:
                trace["sized"].add(name)
    blank = {"attempt": 0, "running": 0, "slots": 0, "stop": ""}
    trace["events"].append(
        {"event": event, "id": task.id, "key": task.key, "after": list(task.after), "claims": list(task.claims), **blank, **more}
    )


def _follow(queue: WorkQueue, trace: dict[str, Any]) -> None:
    """Note in `trace` what `queue` reports from now on: its events, each attempt's result,
    and each result it finishes."""
    on_event, on_result, finish = queue.on_event, queue._on_result, queue._finish

    def event(name: str, task: Task | None, **fields: Any) -> None:
        if task is not None:
            if name == "queued":
                _note(trace, queue, "queued", task)
            elif name == "duplicate_key_refused":
                _note(trace, queue, "refused", task)
            elif name == "start":
                _note(trace, queue, "start", task, attempt=fields["attempt"], running=fields["running"], slots=int(fields["slots"]))
            elif name == "end":
                _note(trace, queue, "end", task, attempt=int(fields.get("attempt") or 0), stop=str(fields.get("stop") or ""))
            elif name in ("retry", "throttle", "deferred"):
                _note(trace, queue, name, task)
        on_event(name, task, **fields)

    def result(res: TaskResult, attempt: int) -> None:
        _note(trace, queue, "result", res.task, attempt=attempt, stop=res.stop)
        assert on_result is not None
        on_result(res, attempt)

    def finished(res: TaskResult) -> None:
        _note(trace, queue, "finished", res.task, stop=res.stop)
        finish(res)

    queue.on_event = event
    if on_result is not None:
        queue._on_result = result
    queue._finish = finished  # type: ignore[method-assign]


class Recorder:
    """Notes what every `WorkQueue` made while it is on reports (`traces`)."""

    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []
        self._real: tuple[Any, Any] | None = None

    def __enter__(self) -> Recorder:
        init, run = WorkQueue.__init__, WorkQueue.run_async
        self._real = (init, run)
        traces = self.traces

        @functools.wraps(init)  # the queue's own signature, for whoever reads it
        def __init__(queue: WorkQueue, *args: Any, **kwargs: Any) -> None:
            init(queue, *args, **kwargs)
            trace = {
                "test": os.environ.get("PYTEST_CURRENT_TEST", "").split(" ")[0],
                "maxConcurrent": queue.max_concurrent,
                "capacity": {},
                "sized": set(),
                "complete": False,
                "events": [],
            }
            traces.append(trace)
            queue._trace = trace  # type: ignore[attr-defined]
            _follow(queue, trace)

        @functools.wraps(run)
        async def run_async(queue: WorkQueue) -> dict[str, Any]:
            summary = await run(queue)
            trace = getattr(queue, "_trace", None)
            if trace is not None:
                trace["complete"] = True
            return summary

        WorkQueue.__init__ = __init__  # type: ignore[method-assign]
        WorkQueue.run_async = run_async  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc: object) -> None:
        if self._real is not None:
            WorkQueue.__init__, WorkQueue.run_async = self._real  # type: ignore[method-assign]
            self._real = None


def as_json(trace: dict[str, Any]) -> dict[str, Any]:
    return {**trace, "capacity": sorted(trace["capacity"].items()), "sized": sorted(trace["sized"])}


def _exe() -> Any:
    spec = importlib.util.spec_from_file_location("lean_exe", Path(__file__).with_name("exe.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Loaded as this module is, before a test is given a home of its own: it reads where elan is.
exe = _exe()


def breaks(traces: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """What each trace's log breaks of what the specification proves: (the test that ran the
    queue, the breaks), for the traces that break something. Needs Lean."""
    given = [as_json(trace) for trace in traces if trace["events"]]
    answers = exe.specified("trace", given) if given else []
    return [(answer["test"], answer["breaks"]) for answer in answers if answer["breaks"]]


def write(traces: list[dict[str, Any]], folder: Path) -> Path:
    """Write the traces that hold an event as `<folder>/<process id>.jsonl`, one on each line."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{os.getpid()}.jsonl"
    lines = [json.dumps(as_json(trace), separators=(",", ":")) for trace in traces if trace["events"]]
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def main(folder: Path) -> int:
    """Check every trace noted under `folder`; print what each breaks. 1 when one breaks."""
    given = [json.loads(line) for path in sorted(folder.glob("*.jsonl")) for line in path.read_text(encoding="utf-8").splitlines()]
    answers = exe.specified("trace", given) if given else []
    broken = [(answer["test"], answer["breaks"]) for answer in answers if answer["breaks"]]
    starts = sum(1 for trace in given for event in trace["events"] if event["event"] == "start")
    print(f"{len(given)} queues, {starts} starts, {len(broken)} of them break what the specification proves")
    for test, lines in broken:
        for line in lines:
            print(f"{test}: {line}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
