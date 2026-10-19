"""A flow that depends on results: each unit's summary is reviewed and revised
until the review approves it, every unit at once, then one report over them all.

The flows are `async def` functions: `await` a task call, and the checked output
comes back at the `await`. Passing it on to another task is the dependency, as
passing the task call itself is in a flow that does not wait.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Summary(BaseModel):
    unit: str
    points: list[str] = Field(description="the main points, one short sentence each")


class Verdict(BaseModel):
    approved: bool
    note: str = Field(description="what to change, when not approved")


summarize = agent_task("summarize", instructions="Summarize the document at params.path.", output=Summary, max_turns=10, timeout_s=300)
# A verdict needs no tool: the reviewer's final message is its output (no turn spent on a Write).
# A verdict is short: one correction round is enough to fix its form (default: 3).
review = agent_task(
    "review",
    instructions="Review params.summary.",
    output=Verdict,
    output_from="message",
    max_corrections=1,
    max_turns=3,
    timeout_s=300,
)
revise = agent_task(
    "revise", instructions="Revise params.summary as params.verdict.note says.", output=Summary, max_turns=10, timeout_s=300
)


@python_task
def report(summaries: list[Summary]) -> str:
    return "\n".join(f"{s.unit}: {len(s.points)} points" for s in summaries)


async def review_loop(unit: str):
    """One unit: summarize, then revise until the review approves (review-<unit>, review-<unit>~2, ...)."""
    summary = await summarize(unit, path=f"inputs/{unit}.md")
    while True:
        verdict = await review(unit, summary=summary)
        if verdict.approved:
            return summary
        summary = await revise(unit, summary=summary, verdict=verdict)


async def docs(units: list[str]):
    """Every unit's loop at once (one flow call each), then one report joining them."""
    summaries = await asyncio.gather(*[review_loop(u) for u in units])
    return await report(summaries=summaries)
