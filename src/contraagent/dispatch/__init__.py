"""Generic task-dispatch infrastructure: a domain-free envelope
(`Task`/`TaskResult`), its two pluggable extension points
(`TaskScope`/`ResultEnricher`), the queue that dispatches it (`WorkQueue`),
the driver of generator flows over it (`FlowDriver`), and Python tasks
(`make_python_task`), and the record types every layer shares (`records`).
Nothing here knows what a "file" or a "finding" is, and nothing here
depends on the LLM layer.

A domain builds on this by putting its own types in `Task.payload`.
"""

from __future__ import annotations

from contraagent.dispatch.flow import FlowCall, FlowDriver, FlowState, TaskDeferred, TaskFailed, TimeBoxed, result_or_raise, time_box
from contraagent.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent.dispatch.python_task import PythonTaskPayload, make_python_task
from contraagent.dispatch.queue import ClaimCapacity, TaskRunner, WorkQueue
from contraagent.dispatch.records import (
    Changes,
    DeferralCause,
    Executor,
    Frame,
    Hop,
    Loop,
    OtherModel,
    QuotaReading,
    QuotaWindow,
    Rest,
    RestEvent,
    SkippedHop,
    TimeBoxRecord,
    TokenUsage,
    Window,
    WindowSpec,
)
from contraagent.dispatch.task import (
    PYTHON_KEY_PREFIX,
    Deferral,
    Origin,
    Partial,
    Task,
    TaskResult,
    TimeBox,
    kind_name,
)

__all__ = [
    "PYTHON_KEY_PREFIX",
    "Changes",
    "ClaimCapacity",
    "Deferral",
    "DeferralCause",
    "Executor",
    "FlowCall",
    "FlowDriver",
    "FlowState",
    "Frame",
    "Hop",
    "Loop",
    "Origin",
    "OtherModel",
    "Partial",
    "PythonTaskPayload",
    "QuotaReading",
    "QuotaWindow",
    "Rest",
    "RestEvent",
    "ResultEnricher",
    "SkippedHop",
    "Task",
    "TaskDeferred",
    "TaskFailed",
    "TaskResult",
    "TaskRunner",
    "TaskScope",
    "TimeBox",
    "TimeBoxRecord",
    "TimeBoxed",
    "TokenUsage",
    "Window",
    "WindowSpec",
    "WorkQueue",
    "kind_name",
    "make_python_task",
    "result_or_raise",
    "time_box",
]
