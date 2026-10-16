"""The two pluggable extension points a task's dispatch is wrapped in --
the only things about a dispatch a domain is meant to vary. Zero domain
knowledge lives here; see `contraagent._internal.dispatch.task` for the envelope these
operate on.

Modeled on interceptor chains (gRPC interceptors, Temporal's
`ActivityInboundCallsInterceptor`): ordered, scoped to one dispatch, each
seeing the task before and (for enrichers) the result after.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import Any, Protocol

from contraagent._internal.dispatch.task import Task, TaskResult


class TaskScope(Protocol):
    """A function of a task that returns a context manager: `scope(task)`, called once per
    attempt of the task, agent or Python, and the attempt runs inside `with scope(task):`
    (`Pipeline(scopes=)`). A generator function decorated with `contextlib.contextmanager`
    is one.

    For an agent task the block is entered right before its first failover hop and exited
    once after its last, whichever way the attempt ends (a timeout included); for a Python
    task it is around its input check, its call and its output check. The function's
    exception is the attempt's result, so the block exits without one. A scope returns no
    value to the attempt (`ResultEnricher` does). A scope for some tasks only tests
    `task.kind` or `task.executor` and returns `contextlib.nullcontext()` for the others."""

    def __call__(self, task: Task, /) -> AbstractContextManager[None]: ...


class ResultEnricher(Protocol):
    """The interceptor-style sibling `TaskScope` doesn't cover: needs to see
    a value from *before* dispatch again *after* it, to compute something
    (a domain's own progress delta, an override of the generic `ok`/`stop`
    verdict) that a plain context manager's `__exit__` has no way to hand
    back to the caller. `AgentRunner.run()` (an attempt of an agent task) and
    `PythonTaskRunner` (an attempt of a Python task) call `snapshot()` once
    before the attempt and `enrich()` once after, in the order `enrichers`
    were given. `task` and `result` are frozen: `enrich()` returns the result as it should
    be (`dataclasses.replace(result, payload=..., ok=..., stop=...)`), or None to leave
    it as it was; the next enricher is given what it returned.
    """

    def snapshot(self, task: Task) -> Any: ...

    def enrich(self, task: Task, before: Any, result: TaskResult) -> TaskResult | None: ...


def enriched(snapshots: Iterable[tuple[ResultEnricher, Any]], task: Task, result: TaskResult) -> TaskResult:
    """`result` after each enricher in turn, given its snapshot: the result it returned,
    or the one it was given when it returned None."""
    for enricher, before in snapshots:
        new = enricher.enrich(task, before, result)
        if new is not None:
            result = new
    return result
