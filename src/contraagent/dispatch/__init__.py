"""Generic task-dispatch infrastructure: a domain-free envelope
(`Task`/`TaskResult`), its two pluggable extension points
(`TaskScope`/`ResultEnricher`), the queue that dispatches it (`WorkQueue`),
the driver of generator flows over it (`FlowDriver`), and Python tasks
(`make_python_task`).
Nothing here knows what a "file" or a "finding" is, and nothing here
depends on the LLM layer.

A domain builds on this by putting its own types in `Task.payload`.
"""

from __future__ import annotations

from contraagent.dispatch.flow import FlowCall, FlowDriver, TaskDeferred, TaskFailed, result_or_raise
from contraagent.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent.dispatch.python_task import PythonTaskPayload, make_python_task
from contraagent.dispatch.queue import TaskRunner, WorkQueue
from contraagent.dispatch.task import PYTHON_KEY_PREFIX, Changes, Frame, Loop, Origin, Task, TaskResult, kind_name

__all__ = [
    "PYTHON_KEY_PREFIX",
    "Changes",
    "FlowCall",
    "FlowDriver",
    "Frame",
    "Loop",
    "Origin",
    "PythonTaskPayload",
    "ResultEnricher",
    "Task",
    "TaskDeferred",
    "TaskFailed",
    "TaskResult",
    "TaskRunner",
    "TaskScope",
    "WorkQueue",
    "kind_name",
    "make_python_task",
    "result_or_raise",
]
