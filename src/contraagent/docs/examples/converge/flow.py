"""A loop that stops when it stops improving: a draft is critiqued and revised until
the number of open issues stays the same, the passes run out, or the time box ends.

`improve` writes each unit's first draft, then refines it in a time box. `refine` is a
`for` loop over a range: when the range ends, the loop ends normally. It stops early
when the critique's count of open issues is the same `flat` passes in a row, and when
the time box defers a task (`TaskDeferred`). It returns the last draft in every case,
and keeps why it stopped in the pipeline document `refine-<unit>`.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

import contraagent
from contraagent import TaskDeferred, agent_task, time_box


class Draft(BaseModel):
    unit: str
    text: str


class Critique(BaseModel):
    open_issues: int = Field(ge=0, description="how many problems the draft still has", examples=[3])
    notes: list[str] = Field(description="one short sentence per problem")


class WriteParams(BaseModel):
    subject: str = Field(description="what the draft is about")


class CritiqueParams(BaseModel):
    draft: Draft = Field(description="the draft to critique")


class ReviseParams(BaseModel):
    draft: Draft = Field(description="the draft to revise")
    critique: Critique = Field(description="the problems to fix")


write = agent_task(
    "write", params=WriteParams, instructions="Write a short draft on ${subject}.", output=Draft, max_turns=10, timeout_s=600
)
critique = agent_task(
    "critique",
    params=CritiqueParams,
    instructions="List the problems of params.draft and count them.",
    output=Critique,
    output_from="message",
    max_turns=3,
    timeout_s=300,
)
revise = agent_task(
    "revise",
    params=ReviseParams,
    instructions="Revise params.draft to fix the problems in params.critique.",
    output=Draft,
    max_turns=10,
    timeout_s=600,
)


async def refine(unit: str, draft: Draft, passes: int = 8, flat: int = 2) -> Draft:
    """Critique and revise `draft` at most `passes` times; stop when the count of open
    issues has not changed for `flat` passes, or when the time box defers a task."""
    seen: list[int] = []  # the open issues of each critique, in order
    why = "ceiling"
    try:
        for _ in range(passes):  # the range is the bound: the loop ends normally
            found = await critique(unit, CritiqueParams(draft=draft))
            seen.append(found.open_issues)
            if len(seen) > flat and len(set(seen[-flat - 1 :])) == 1:
                why = "flat"
                break
            draft = await revise(unit, ReviseParams(draft=draft, critique=found))
    except TaskDeferred:  # past the time box's deadline
        why = "time box"
    contraagent.save(f"refine-{unit}", {"open_issues": seen, "why": why})
    return draft


async def improve(units: list[str], deadline_s: float = 30 * 60, passes: int = 8, flat: int = 2) -> dict[str, str]:
    """Each unit's first draft, then its refining in a time box of `deadline_s`."""

    async def one(unit: str) -> Draft:
        draft = await write(unit, WriteParams(subject=unit))
        return await time_box(refine(unit, draft, passes, flat), deadline_s=deadline_s)

    drafts = await asyncio.gather(*[one(unit) for unit in units])
    return {unit: draft.text for unit, draft in zip(units, drafts, strict=True)}
