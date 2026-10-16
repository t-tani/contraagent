"""Concurrency: long computations on this host beside agent tasks that wait on a model.

`measure` is a long computation on this host, and `summarize` an agent task, which
mostly waits on a remote model. Every running task takes one of the run's slots
(`Pipeline(max_concurrent=)`), so without a bound of their own, measurements could take
every slot and keep the summaries waiting. Every `measure` claims `local`, and
`CLAIM_CAPACITY` lets two tasks hold it at once: at most two of the six slots compute,
so four summaries always run at once beside them. `measure` runs its computation in a
child process, so the threads of this process keep running while it computes.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task

#: The child process's computation: the sum of the squares below its argument.
COMPUTE = "import sys; print(sum(i * i for i in range(int(sys.argv[1]))))"

#: Two measurements at a time; the rest of the run's slots stay for the agent tasks.
CLAIM_CAPACITY = {"local": 2}

#: The agent tasks' four slots, plus one for each task that may hold `local`.
MAX_CONCURRENT = 4 + CLAIM_CAPACITY["local"]


class Stats(BaseModel):
    unit: str
    total: int


class Summary(BaseModel):
    text: str


@python_task(claims=["local"])
def measure(unit: str) -> Stats:
    """A long computation, in a child process: this process's threads keep running."""
    done = subprocess.run([sys.executable, "-c", COMPUTE, "200000"], capture_output=True, text=True, encoding="utf-8", check=True)
    return Stats(unit=unit, total=int(done.stdout))


summarize = agent_task(
    "summarize",
    instructions="Summarize the document of this unit in one paragraph.",
    output=Summary,
    max_turns=10,
    timeout_s=300,
)


def reports(units: list[str]):
    for unit in units:
        measure(unit)  # holds `local`: at most two at a time
        summarize(unit)  # claims nothing: runs in any free slot, beside the measurements


def pipeline(**options: Any) -> Pipeline:
    """Six slots, of which the measurements take at most two."""
    return Pipeline(max_concurrent=MAX_CONCURRENT, claim_capacity=CLAIM_CAPACITY, **options)
