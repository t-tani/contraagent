"""The telemetry line: the first line of every agent task's prompt, naming its run and task.

    TELEMETRY run=r1 kind=summarize unit=alpha key=summarize-alpha role=writer

`AgentRunner` writes it (`line`); the monitor reads it from a live process's command line
(`parse`) for the role it runs as, which its environment (`envvars`) does not carry. A
value that is empty is written `-`. A leaf module, like `envvars`.
"""

from __future__ import annotations

import re
from typing import NamedTuple

PREFIX = "TELEMETRY"

_LINE = re.compile(rf"{PREFIX} run=(\S+) kind=(\S+) unit=(\S+) key=(\S+)(?: role=(\S+))?")


class Telemetry(NamedTuple):
    """The values of a telemetry line, as written (`-` for an empty one)."""

    run: str
    kind: str
    unit: str
    key: str
    role: str


def line(run: str, kind: str, unit: str, key: str, role: str | None) -> str:
    """The telemetry line of a task: one line, greppable."""
    return f"{PREFIX} run={run or '-'} kind={kind} unit={unit or '-'} key={key} role={role or '-'}"


def parse(text: str) -> Telemetry | None:
    """The first telemetry line in `text` (a prompt, a command line); None when it has none."""
    m = _LINE.search(text)
    if m is None:
        return None
    run, kind, unit, key, role = m.group(1, 2, 3, 4, 5)
    return Telemetry(run, kind, unit, key, role or "")
