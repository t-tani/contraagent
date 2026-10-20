"""Probes whose answers stop being needed: the first blocking finding settles a review.

`review` asks one probe per question about a change, each in a flow call of its own in
one `asyncio.TaskGroup`. A probe that finds a blocking problem raises `Blocked`, and the
group closes the other flow calls. Their probes are called with
`.options(cancellable=True)`, so a probe still queued is not launched and a running one
has its launch stopped: no flow call waits for their answers any longer. A probe
called without the option would run to its end, and its answer would be in the run.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from contraagent import agent_task


class Finding(BaseModel):
    blocking: bool = Field(description="the change must not be merged as it is")
    note: str = Field(examples=["The new endpoint reads the token from the query string."])


probe = agent_task(
    "probe",
    instructions="Read the change ${unit} and answer the question in params.question.",
    output=Finding,
    max_turns=10,
    timeout_s=600,
)

#: One probe per question, by the name of its key.
QUESTIONS = {
    "security": "Does it expose a secret or skip a permission check?",
    "data": "Can it lose or corrupt stored data?",
    "license": "Does it add code under a license the project cannot take?",
}


class Blocked(Exception):
    """A probe found a problem that blocks the change."""

    def __init__(self, finding: Finding) -> None:
        super().__init__(finding.note)
        self.finding = finding


async def ask(change: str, name: str, question: str) -> Finding:
    finding = await probe.options(key=f"probe-{change}-{name}", cancellable=True)(change, question=question)
    if finding.blocking:
        raise Blocked(finding)
    return finding


async def review(change: str) -> str:
    blocked: list[Finding] = []
    try:
        async with asyncio.TaskGroup() as group:
            for name, question in QUESTIONS.items():
                group.create_task(ask(change, name, question))
    except* Blocked as caught:
        blocked = [error.finding for error in caught.exceptions if isinstance(error, Blocked)]
    return f"blocked: {blocked[0].note}" if blocked else "clear"
