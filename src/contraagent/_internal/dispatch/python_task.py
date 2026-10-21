"""Python tasks: Python functions scheduled like any other task.

A task with `fn` set is a Python task: work the scheduler runs itself, on a
pool thread, instead of a coding-agent launch. Its `kind` is its own name.
`make_python_task` builds one; `execution.python_tasks.PythonTaskRunner`
runs it (and hands every agent task to the runner it wraps).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from contraagent._internal.dispatch.task import PYTHON_KEY_PREFIX, Task


class InvalidInput(ValueError):
    """Raised by a Python task's call before its function runs: an argument does not match
    its parameter's annotation; or while it runs, by an input file whose content changed
    after the task call (`InputFile.read_bytes`). The task ends `invalid_input`, its reason
    the message (`invalid input: <message>`), and is not retried."""


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
    #: The task's params as JSON (an input file among them as its `{"path", "sha256"}`, with `root` for one of an input root), as
    #: its contract record keeps them for the monitor; None when not known (opaque here).
    params: dict | None = None


def make_python_task(
    name: str,
    fn: Callable[[], object],
    *,
    unit: str = "",
    after: tuple[str, ...] = (),
    input_contracts=(),
    output_contracts=(),
    retries: int = 0,
    retry_on: tuple[type[Exception], ...] = (),
) -> Task:
    """A Python function as a schedulable task of kind `name`.

    Its key (`python:<name>`, or `python:<name>-<unit>` with a unit) is
    stable, so a resumed run recognizes it and `after=("python:<name>",)`
    can depend on it. `unit` is what it is applied to. `input_contracts` /
    `output_contracts` are `InputContract`s / `OutputContract`s checked around the function by
    `PythonTaskRunner` (`Run.python_runner()`), exactly as for an agent task.
    `retries` and `retry_on`, as for `@python_task`: the fresh attempts after an
    exception of a class in `retry_on`; checked here. A function that returns a `Partial`
    finishes ok with stop `partial` (its `reason` the result's), and a resume runs it again.
    """
    tries, on = checked_retries(f"make_python_task({name!r})", retries, retry_on)
    return Task(
        kind=name,
        unit=unit,
        after=after,
        key=f"{PYTHON_KEY_PREFIX}{name}-{unit}" if unit else f"{PYTHON_KEY_PREFIX}{name}",
        fn=fn,
        payload=PythonTaskPayload(
            input_contracts=tuple(input_contracts), output_contracts=tuple(output_contracts), retries=tries, retry_on=on
        ),
    )


def checked_retries(owner: str, retries: object, retry_on: object) -> tuple[int, tuple[type[Exception], ...]]:
    """`retries` and `retry_on` as declared, checked: a count of 0 or more, a tuple of
    exception classes, and each given with the other."""
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
        raise TypeError(f"{owner}: retries must be an int of 0 or more, not {retries!r}")
    if isinstance(retry_on, type) or not isinstance(retry_on, (tuple, list)):
        raise TypeError(f"{owner}: retry_on must be a tuple of exception classes, such as (ConnectionError,), not {retry_on!r}")
    for cls in retry_on:
        if not (isinstance(cls, type) and issubclass(cls, Exception)):
            raise TypeError(f"{owner}: retry_on holds {cls!r}; each item is an exception class, such as ConnectionError")
    if retries and not retry_on:
        raise ValueError(f"{owner}: retries={retries} with no retry_on; name the exception classes that give a fresh attempt")
    if retry_on and not retries:
        raise ValueError(f"{owner}: retry_on with retries=0; give the number of fresh attempts (retries=1 or more)")
    return retries, tuple(retry_on)
