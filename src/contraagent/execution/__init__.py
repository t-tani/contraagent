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
"""

from contraagent.execution.adapter import TaskAdapter
from contraagent.execution.cursor import CursorStore
from contraagent.execution.journal import Journal
from contraagent.execution.pipeline_files import NoCurrentRun, log, save
from contraagent.execution.python_tasks import PythonTaskRunner
from contraagent.execution.run import Run, RunExists, RunLocked
from contraagent.execution.runner import AgentRunner, RetryingRunner

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
    "save",
]
