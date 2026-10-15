"""Python tasks: Python functions scheduled like any other task.

A task with `fn` set is a Python task: work the scheduler runs itself, on a
pool thread, instead of a coding-agent launch. Its `kind` is its own name.
`make_python_task` builds one; `execution.python_tasks.PythonTaskRunner`
runs it (and hands every agent task to the runner it wraps).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from contraagent.dispatch.task import PYTHON_KEY_PREFIX, Task


@dataclass(frozen=True)
class PythonTaskPayload:
    """The payload of a Python task: the contracts it declares, and its retries.

    The contracts are opaque here; `execution.python_tasks.PythonTaskRunner`
    checks them.
    """

    input_contracts: tuple = ()
    output_contracts: tuple = ()
    #: What defines the task's kind, as JSON for `definitions/<kind>.json` (opaque here).
    definition: dict | None = None
    #: Fresh attempts after the first, each after an exception of `retry_on` (`@python_task(retries=)`).
    retries: int = 0
    #: The exception classes that give an attempt a fresh one.
    retry_on: tuple[type[Exception], ...] = ()


def make_python_task(
    name: str, fn: Callable[[], None], *, unit: str = "", after: tuple[str, ...] = (), input_contracts=(), output_contracts=()
) -> Task:
    """A Python function as a schedulable task of kind `name`.

    Its key (`python:<name>`, or `python:<name>-<unit>` with a unit) is
    stable, so a resumed run recognizes it and `after=("python:<name>",)`
    can depend on it. `unit` is what it is applied to. `input_contracts` /
    `output_contracts` are `InputContract`s / `OutputContract`s checked around the function by
    `PythonTaskRunner` (`Run.python_runner()`), exactly as for an agent task.
    """
    return Task(
        kind=name,
        unit=unit,
        after=after,
        key=f"{PYTHON_KEY_PREFIX}{name}-{unit}" if unit else f"{PYTHON_KEY_PREFIX}{name}",
        fn=fn,
        payload=PythonTaskPayload(input_contracts=tuple(input_contracts), output_contracts=tuple(output_contracts)),
    )
