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
the same inputs would write the same file. The failure is the result, except
for an exception the task names in `retry_on` (`@python_task(retries=, retry_on=)`):
a call that raised one gets a fresh attempt, up to `retries` of them, after
`RetryingRunner`'s backoff. Each attempt is its own journal row.

With a recorder (`execution.recording.Recorder`), each call is recorded: how it ended and
its output files. With a replay (`execution.recording.Replay`), a call is played from its
recording instead, and the function does not run (but for the kinds the replay executes).

Contracts come from the task itself (`make_python_task(..., input_contracts=, output_contracts=)`)
and, when given, from a `TaskAdapter`, exactly as for agent tasks.
"""

from __future__ import annotations

import contextlib
import json
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from contraagent import rundir
from contraagent.contracts import check_input, record_contracts
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
from contraagent.execution.runner import RetryingRunner
from contraagent.routing.kind_config import KindConfig


@dataclass(frozen=True)
class _PythonTaskConfig:
    """A Python task has no per-kind launch budget: no cap beyond the queue's own."""

    max_concurrent: int | None = None


class PythonTaskRunner:
    """Runs Python tasks (`Task.fn`) in-process, checking their declared input and
    output contracts; forwards every agent task to `inner` (`RetryingRunner(...)`).

    The queue's runner for a run that mixes Python tasks with agent tasks.
    Without `inner`, an agent task reaching it is a wiring mistake, and it says so.

    A Python task with `retries` (`PythonTaskPayload`) calls its function again after
    an exception of its `retry_on`. `on_failed_attempt` sees each attempt a fresh one
    follows (`Run.record_attempt` journals it); the last attempt is the task's result,
    which the queue records.

    `recorder` (`Recorder.record_python`) keeps each call's recording; `replay`
    (`Replay.play_python`) plays a call from its recording in place of the function.
    """

    def __init__(
        self,
        inner=None,
        *,
        adapter=None,
        run_dir: str | Path | None = None,
        cwd: str | Path | None = None,
        on_failed_attempt: Callable[[TaskResult], None] | None = None,
        recorder=None,
        replay=None,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._replay = replay
        self._on_failed_attempt = on_failed_attempt
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
            return self._attempts(task)
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
        before = {c.resolve(self._cwd): c.before(self._cwd) for c in outs}
        res = self._attempts(task)
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

    def _attempts(self, task: Task) -> TaskResult:
        """Call the function, and again after an exception of the task's `retry_on`, up to
        `retries` more times; the last call's result."""
        retries = getattr(task.payload, "retries", 0)
        retry_on = tuple(getattr(task.payload, "retry_on", ()))
        attempt = 0
        while True:
            task.attempt = attempt
            res, retry = self._call(task, retry_on)
            if not retry or attempt >= retries:
                return res
            if self._on_failed_attempt is not None:
                try:
                    self._on_failed_attempt(res)
                except Exception:  # a journal write must not fail the task
                    traceback.print_exc()
            time.sleep(RetryingRunner.backoff(KindConfig.retry_backoff_base, attempt))
            attempt += 1

    def _call(self, task: Task, retry_on: tuple[type[Exception], ...]) -> tuple[TaskResult, bool]:
        """Call the function: its result, and whether it raised an exception of `retry_on`. An
        exception is the task's result, never a crash of the queue. With a run directory, it
        is the current run of `contraagent.log` and `save` while the function runs, on
        whichever thread the queue calls it. A replay plays the call instead, when it can."""
        assert task.fn is not None
        outs = self.contracts(task)[0]
        if self._replay is not None:
            played = self._replay.play_python(task, outs, self._cwd)
            if played is not None:
                return played
        t0 = time.monotonic()
        reason = ""
        error: Exception | None = None
        try:
            with writing_into(self._run_dir.resolve()) if self._run_dir is not None else contextlib.nullcontext():
                task.fn()
            stop = STOP_COMPLETED
        except Exception as exc:  # a Python task's failure is its result
            stop, error = STOP_ERROR, exc
            reason = f"{type(exc).__name__}: {exc}"[:300]
        result = TaskResult(task=task, ok=stop == STOP_COMPLETED, stop=stop, wall_s=time.monotonic() - t0, reason=reason)
        retry = error is not None and isinstance(error, retry_on)
        if self._recorder is not None:
            self._recorder.record_python(task, result, outs, retry)
        return result, retry
