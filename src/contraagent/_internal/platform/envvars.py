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
#: The interpreter a plugin's hook should run `python -m contraagent` with.
PYTHON = "CONTRAAGENT_PYTHON"
#: The task's call file (`contraagent._internal.contracts.calls`): its parameters and output
#: contract. The params reach an agent only there: a value in the environment counts toward
#: the operating system's limit on a launch's arguments and environment.
CALL = "CONTRAAGENT_CALL"
#: The corrections a round may still make (`max_corrections` less those made before it): a
#: stop hook that sends the output's errors back makes one, so at 0 it lets the agent stop.
CORRECTIONS_LEFT = "CONTRAAGENT_CORRECTIONS_LEFT"
#: The bash a plugin's hook scripts run under, set where it is not the `bash` on PATH
#: (on Windows, the one of Git for Windows: `commands.bash`).
BASH = "CONTRAAGENT_BASH"

#: The start of the variable that holds the address of a service the task claims
#: (`service(name)`).
SERVICE_PREFIX = "CONTRAAGENT_SERVICE_"


def service(name: str) -> str:
    """The variable that holds the address of the service claim name `name` stands for:
    `CONTRAAGENT_SERVICE_` and the name in capitals, each character but a letter or a
    digit turned into `_` (`db:alpha` -> `CONTRAAGENT_SERVICE_DB_ALPHA`)."""
    return SERVICE_PREFIX + "".join(c if c.isascii() and c.isalnum() else "_" for c in name.upper())
