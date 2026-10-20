"""Probes whose answers stop being needed: the first blocking finding settles a review.

`review` asks one probe per question about a change, each in a flow call of its own.
The flow call whose probe finds a blocking problem cancels the others, which closes them.
Their probes are called with `.options(cancellable=True)`, so a probe still queued is
not launched and a running one has its launch stopped: no flow call waits for their
answers any longer. A probe called without the option would run to its end, and its
answer would be in the run.
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


async def ask(change: str, name: str, question: str, probes: list[asyncio.Task[Finding]]) -> Finding:
    finding = await probe.options(key=f"probe-{change}-{name}", cancellable=True)(change, question=question)
    if finding.blocking:  # the review is settled: the other probes' answers are not needed
        for other in probes:
            if other is not asyncio.current_task():
                other.cancel()
    return finding


async def review(change: str) -> str:
    probes: list[asyncio.Task[Finding]] = []
    for name, question in QUESTIONS.items():
        probes.append(asyncio.create_task(ask(change, name, question, probes)))
    answers = await asyncio.gather(*probes, return_exceptions=True)
    blocked = [answer for answer in answers if isinstance(answer, Finding) and answer.blocking]
    return f"blocked: {blocked[0].note}" if blocked else "clear"
