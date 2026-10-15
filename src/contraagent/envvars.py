"""Environment variables set on every agent launch.

They are the protocol between three parts that never import each other at
run time: the runner that sets them (`execution/runner.py`), the hook a task
plugin runs inside the agent (`contraagent call validate`), and the monitor,
which maps a live process back to its run and task without parsing its
command line.
"""

from __future__ import annotations

#: Every variable below starts with this.
PREFIX = "CONTRAAGENT_"

RUN = "CONTRAAGENT_RUN"
TASK = "CONTRAAGENT_TASK"
KIND = "CONTRAAGENT_KIND"
UNIT = "CONTRAAGENT_UNIT"
#: JSON object of the task's scalar params (`Task.params`).
PARAMS = "CONTRAAGENT_PARAMS"
#: The interpreter a plugin's hook should run `python -m contraagent` with.
PYTHON = "CONTRAAGENT_PYTHON"
#: The task's call file (`contraagent.calls`): its parameters and output contract.
CALL = "CONTRAAGENT_CALL"
