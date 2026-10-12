"""A flow that depends on results: each unit's summary is reviewed and revised
until the review approves it, every unit at once, then one report over them all.

The flows are generators: `yield` a task call, and the checked output comes
back at the `yield`. Passing it on to another task is the dependency, as
passing the task call itself is in a flow that does not yield.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Summary(BaseModel):
    unit: str
    points: list[str] = Field(description="the main points, one short sentence each")


class Verdict(BaseModel):
    approved: bool
    note: str = Field(description="what to change, when not approved")


summarize = agent_task("summarize", instructions="Summarize the document at params.path.", output=Summary, max_turns=10, timeout_s=300)
review = agent_task("review", instructions="Review params.summary.", output=Verdict, max_turns=10, timeout_s=300)
revise = agent_task(
    "revise", instructions="Revise params.summary as params.verdict.note says.", output=Summary, max_turns=10, timeout_s=300
)


@python_task
def report(summaries: list[Summary]) -> str:
    return "\n".join(f"{s.unit}: {len(s.points)} points" for s in summaries)


def review_loop(unit: str):
    """One unit: summarize, then revise until the review approves (review-<unit>, review-<unit>~2, ...)."""
    summary = yield summarize(unit, path=f"inputs/{unit}.md")
    while True:
        verdict = yield review(unit, summary=summary)
        if verdict.approved:
            return summary
        summary = yield revise(unit, summary=summary, verdict=verdict)


def docs(units: list[str]):
    """Every unit's loop at once (one flow call each), then one report joining them."""
    summaries = yield [review_loop(u) for u in units]
    return (yield report(summaries=summaries))
