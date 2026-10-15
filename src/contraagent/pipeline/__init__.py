"""Writing a pipeline: declare tasks, call them from a plain function, run it.

* `spec.py`      `agent_task` (an interface; its plugin is the implementation) and `@python_task`
* `graph.py`     the graph a flow builds, and `Pending`: a task's future output
* `origin.py`    where flow code created a task: its frames
* `loops.py`     the loops of flow code, and the pass of each, counted as the code runs
* `reach.py`     the task declarations a flow's code can reach, without running it
* `adapter.py`   how declarations reach the runner: call files, plugins, contracts
* `pipeline.py`  `Pipeline.run(flow, ...)` and its `RunReport`
* `check.py`     `Pipeline.check(flow, ...)`: what can be found wrong without a launch
"""

from contraagent.pipeline.check import CheckReport
from contraagent.pipeline.graph import Pending, TooManyPasses
from contraagent.pipeline.pipeline import Pipeline, RunReport
from contraagent.pipeline.spec import AgentTask, Implementations, PythonTask, agent_task, python_task

__all__ = [
    "AgentTask",
    "CheckReport",
    "Implementations",
    "Pending",
    "Pipeline",
    "PythonTask",
    "RunReport",
    "TooManyPasses",
    "agent_task",
    "python_task",
]
