"""Python tasks, run with the same input/output contracts as agent tasks.

A Python task is `Task.fn`, a function the queue runs in-process. Its exit
says nothing about the file it was meant to produce, for the same reason an
agent's does not: a function can return cleanly having written nothing, or a
document with a field renamed, and the task that reads it next fails far
from the cause. `PythonTaskRunner` checks, around each Python task:

* before: every input contract the task declares (a missing required file, or
  one off-contract, refuses the task: `invalid_input`, nothing runs);
* after: every output contract (`invalid_output`, not ok), including the
  freshness check, so a stale file from an earlier run does not pass.

There is no resume: a Python task is deterministic, so running it again with
the same inputs would write the same file. The failure is the result.

Contracts come from the task itself (`make_python_task(..., input_contracts=, output_contracts=)`)
and, when given, from a `TaskAdapter`, exactly as for agent tasks.
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from contraagent import rundir
from contraagent.contracts import check_input, file_stamp, record_contracts
from contraagent.dispatch.task import (
    STOP_COMPLETED,
    STOP_ERROR,
    STOP_INVALID_INPUT,
    STOP_INVALID_OUTPUT,
    Deferral,
    Task,
    TaskResult,
)
from contraagent.execution.pipeline_files import writing_into


@dataclass(frozen=True)
class _PythonTaskConfig:
    """A Python task has no per-kind launch budget: no cap beyond the queue's own."""

    max_concurrent: int | None = None


class PythonTaskRunner:
    """Runs Python tasks (`Task.fn`) in-process, checking their declared input and
    output contracts; forwards every agent task to `inner` (`RetryingRunner(...)`).

    The queue's runner for a run that mixes Python tasks with agent tasks.
    Without `inner`, an agent task reaching it is a wiring mistake, and it says so.
    """

    def __init__(self, inner=None, *, adapter=None, run_dir: str | Path | None = None, cwd: str | Path | None = None) -> None:
        self._inner = inner
        self._adapter = adapter
        self._run_dir = Path(run_dir) if run_dir else None
        self._cwd = Path(cwd) if cwd else Path.cwd()
        self._defined: set[str] = set()

    def config(self, task: Task):
        if task.fn is not None or self._inner is None:
            return _PythonTaskConfig()
        return self._inner.config(task)

    def deferral(self, task: Task) -> Deferral | None:
        """Why an agent task cannot launch now (`inner`'s); a Python task always can."""
        ask = getattr(self._inner, "deferral", None) if task.fn is None else None
        return ask(task) if ask is not None else None

    def contracts(self, task: Task) -> tuple[list, list]:
        """(outputs, inputs) declared for `task`, by the task and by the adapter."""
        payload = task.payload
        outs = list(getattr(payload, "output_contracts", ()) or ())
        ins = list(getattr(payload, "input_contracts", ()) or ())
        if self._adapter is not None:
            outs += list(self._adapter.output_contracts(task))
            ins += list(self._adapter.input_contracts(task))
        return outs, ins

    def run(self, task: Task) -> TaskResult:
        if task.fn is None:
            if self._inner is None:
                raise TypeError(f"{task.key}: an agent task, and no runner to launch it")
            return self._inner.run(task)
        self._record_definition(task)
        outs, ins = self.contracts(task)
        if not (outs or ins):
            return self._call(task)
        if self._run_dir is not None:
            record_contracts(self._run_dir, task, outs, ins, self._cwd)
        bad = [e for c in ins for e in check_input(c, self._cwd)]
        if bad:
            return TaskResult(
                task=task,
                ok=False,
                stop=STOP_INVALID_INPUT,
                reason=f"invalid input: {bad[0]}"[:240],
                rounds=0,
            )
        before = {c.resolve(self._cwd): file_stamp(c.resolve(self._cwd)) for c in outs}
        res = self._call(task)
        if res.stop != STOP_COMPLETED:
            return res  # the function itself failed; its own error is the story
        t0 = time.monotonic()
        errors: list[str] = []
        for c in outs:
            p = c.resolve(self._cwd)
            errors += c.check(self._cwd, before.get(p)).errors
        res.wall_s += time.monotonic() - t0
        res.rounds = 1
        if errors:
            res.ok, res.stop = False, STOP_INVALID_OUTPUT
            res.reason = "; ".join(errors)[:240]
            res.round_errors = (tuple(errors[:5]),)
        return res

    def _record_definition(self, task: Task) -> None:
        """`definitions/<kind>.json`, once per kind per run, as for agent tasks: what
        defines the kind (the function, its signature, docstring and source)."""
        definition = getattr(task.payload, "definition", None)
        if self._run_dir is None or not definition or task.kind in self._defined:
            return
        self._defined.add(task.kind)
        try:
            d = self._run_dir / rundir.DEFINITIONS
            d.mkdir(parents=True, exist_ok=True)
            rundir.write_document(d / f"{task.kind}.json", json.dumps({"kind": task.kind, **definition}, default=str))
        except OSError:  # a definition the monitor cannot show must not fail the task
            pass

    def _call(self, task: Task) -> TaskResult:
        """Call the function; an exception is the task's result, never a crash of the queue.
        With a run directory, it is the current run of `contraagent.log` and `save` while
        the function runs, on whichever thread the queue calls it."""
        assert task.fn is not None
        t0 = time.monotonic()
        reason = ""
        try:
            with writing_into(self._run_dir.resolve()) if self._run_dir is not None else contextlib.nullcontext():
                task.fn()
            stop = STOP_COMPLETED
        except Exception as exc:  # a Python task's failure is its result
            stop = STOP_ERROR
            reason = f"{type(exc).__name__}: {exc}"[:300]
        return TaskResult(task=task, ok=stop == STOP_COMPLETED, stop=stop, wall_s=time.monotonic() - t0, reason=reason)
