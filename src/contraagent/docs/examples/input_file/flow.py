"""A large input: a long text output given to a reviewer as an input file.

`draft` writes a long report as text. `review` is given the report as an input file: its
params hold the report's path and the SHA-256 of its content, not the text, and the
reviewer reads the file with its tools. `count_words`, a Python task, is given the same
file and reads it with `read_text`. A resume runs `review` again only when the report's
content changed.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from contraagent import InputFile, agent_task, python_task


class DraftParams(BaseModel):
    topic: str = Field(description="what the report is about")


class Verdict(BaseModel):
    approved: bool
    note: str = Field(description="what to change, when not approved")


class ReviewParams(BaseModel):
    report: InputFile = Field(description="the report to review")
    audience: str = Field(description="who reads the report")


draft = agent_task(
    "draft",
    params=DraftParams,
    output=str,
    instructions="Write a detailed report on params.topic, in Markdown.",
    max_turns=20,
    timeout_s=900,
)
review = agent_task(
    "review",
    params=ReviewParams,
    output=Verdict,
    output_from="message",
    instructions="Read the report at params.report.path and judge whether params.audience can follow it.",
    max_turns=10,
    timeout_s=600,
)


@python_task
def count_words(unit: str, report: InputFile) -> int:
    """How many words the report has: the file is read here, in this process."""
    return len(report.read_text().split())


async def report(topic: str) -> tuple[Verdict, int]:
    """One topic: the draft, then its review and its word count, both given the draft's file."""
    written = draft(topic, DraftParams(topic=topic))
    await written  # the draft is in its output file now
    assert written.path is not None  # a task with an output has an output file
    file = InputFile(written.path)
    return await asyncio.gather(
        review(topic, ReviewParams(report=file, audience="new team members")),
        count_words(topic, report=file),
    )


async def reports(topics: list[str]) -> list[tuple[Verdict, int]]:
    """Every topic at once."""
    return await asyncio.gather(*[report(t) for t in topics])
