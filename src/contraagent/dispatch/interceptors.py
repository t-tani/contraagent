"""The two pluggable extension points a task's dispatch is wrapped in --
the only things about a dispatch a domain is meant to vary. Zero domain
knowledge lives here; see `contraagent.dispatch.task` for the envelope these
operate on.

Modeled on interceptor chains (gRPC interceptors, Temporal's
`ActivityInboundCallsInterceptor`): ordered, scoped to one dispatch, each
seeing the task before and (for enrichers) the result after.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Protocol

from contraagent.dispatch.task import Task, TaskResult

#: Wraps one task's whole dispatch (every failover hop) in a `with`-block:
#: entered right before the first attempt, exited exactly once after the
#: last one, regardless of which of the dispatch loop's several return
#: points is actually taken. Pure lifecycle -- no return value is used, see
#: `ResultEnricher` for the sibling that needs one.
TaskScope = Callable[[Task], AbstractContextManager[None]]


class ResultEnricher(Protocol):
    """The interceptor-style sibling `TaskScope` doesn't cover: needs to see
    a value from *before* dispatch again *after* it, to compute something
    (a domain's own progress delta, an override of the generic `ok`/`stop`
    verdict) that a plain context manager's `__exit__` has no way to hand
    back to the caller. `AgentRunner.run()` calls `snapshot()` once before
    dispatch and `enrich()` once after, in the order `enrichers` were
    given; `enrich()` mutates `result` in place (`.payload`, and optionally
    `.ok`/`.stop`) rather than returning a value to merge, matching how
    `TaskResult`'s own domain fields were already set post-construction
    before this split.
    """

    def snapshot(self, task: Task) -> Any: ...

    def enrich(self, task: Task, before: Any, result: TaskResult) -> None: ...
