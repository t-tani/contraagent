"""Running tasks: the agent runner, Python tasks, the run directory, resume.

* `adapter.py`   `TaskAdapter`: the domain's prompt, plugin dirs and contracts
* `runner.py`    `AgentRunner` (one task on a backend, with failover) and `RetryingRunner`
* `python_tasks.py` `PythonTaskRunner`: Python tasks with the same contracts as agent tasks
* `run.py`       `Run`: `runs/<id>/`, its lock, plan, journal and queues
* `journal.py`   `Journal`: `journal.jsonl` rows, written and read back
* `pipeline_files.py` `log`, `save`: a pipeline's own logs and documents in its run
* `cursor.py`    `CursorStore`: where a run is (stage, per-unit step, in-flight work)
* `schemas.py`   the pydantic models of the files a run leaves on disk
* `estimates.py` task durations and tails, from recent runs and this one, for the queue
* `teardown.py`  stopping what a run started, however it ends
* `recording.py` `Recorder` (each agent task attempt kept) and `Replay` (played again, nothing spent)
"""

from contraagent._internal.execution.adapter import TaskAdapter
from contraagent._internal.execution.cursor import CursorStore
from contraagent._internal.execution.journal import Journal
from contraagent._internal.execution.pipeline_files import NoCurrentRun, log, pipeline_table, save
from contraagent._internal.execution.python_tasks import PythonTaskRunner
from contraagent._internal.execution.run import Run, RunExists, RunLocked
from contraagent._internal.execution.runner import AgentRunner, RetryingRunner

__all__ = [
    "AgentRunner",
    "CursorStore",
    "Journal",
    "NoCurrentRun",
    "PythonTaskRunner",
    "RetryingRunner",
    "Run",
    "RunExists",
    "RunLocked",
    "TaskAdapter",
    "log",
    "pipeline_table",
    "save",
]
