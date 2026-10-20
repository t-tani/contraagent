"""The demo pipeline's tasks and flows: the part of a pipeline that is its own.

Each agent task is an interface (a params model, an output, a budget) whose
implementation is a role of the `plugins/docs` plugin; a task call passes an instance
of its params model. A flow that gives one task
another's output is an `async def` function: it awaits the output and passes the
value on. `docs_one_review` reviews each unit once; `docs` decides on the results
(a review loop per unit). Each runs a flow call per unit, so a unit that fails stops
only its own.

Each output declares an example that passes its validators (`examples` in its JSON
Schema), so a stub run (`contraagent run tasks.py:docs --stub`) writes it and goes
through the whole flow. The examples agree with each other: the summary's unit is the
prepared unit, and the note names it.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from contraagent import CommandValidator, Partial, agent_task, python_task

INPUT_DIR = Path("inputs")


class Prepared(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"unit": "alpha", "path": "inputs/alpha.md", "words": 12}]})

    unit: str
    path: str = Field(description="the document to summarize, relative to the working directory")
    words: int


class Summary(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"unit": "alpha", "points": ["parses a config file", "validates it", "reports errors"]}]}
    )

    unit: str = Field(description="the unit this summary is for, copied from the call file")
    points: list[str] = Field(description="the main points, one short sentence each")


class Score(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"points": 3, "words": 8}]})

    points: int
    words: int


class Verdict(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"approved": True, "note": "Accurate."}]})

    approved: bool
    note: str = Field(description="one sentence: what to change, when not approved")


#: A text output with an example: the note starts with a heading and names its unit.
Note = Annotated[str, Field(examples=["# alpha\n\nThe alpha component parses a config file.\n"])]


class SummarizeParams(BaseModel):
    prepared: Prepared = Field(description="the unit's input, prepared: the document to summarize and its size")


class ReviewParams(BaseModel):
    summary: Summary = Field(description="the summary to review")
    score: Score = Field(description="figures about the summary, worked out beside it")


class ReviseParams(BaseModel):
    summary: Summary = Field(description="the summary to revise")
    verdict: Verdict = Field(description="the review that did not approve it")


class NoteParams(BaseModel):
    summary: Summary = Field(description="the summary to write the note from")


def three_points(path: Path, summary: Summary):
    """A structural check the schema cannot express."""
    if len(summary.points) != 3:
        return [f"points: exactly three expected, got {len(summary.points)}"]


def its_own_unit(path: Path, summary: Summary, *, params: dict):
    """A check against the task's own params: the summary names the unit it was given."""
    if summary.unit != params["prepared"]["unit"]:
        return [f"unit: {params['prepared']['unit']!r} expected (the call file's params.prepared.unit)"]


#: A linter for the Japanese note, as an external command (`textlint` in a real setup).
has_heading = CommandValidator(
    [
        sys.executable,
        "-c",
        "import sys; t = open(sys.argv[1], encoding='utf-8').read(); "
        "sys.exit(None if t.startswith('# ') else '1:1 the note must start with a # heading')",
        "{path}",
    ],
    name="heading",
)

#: A rule about the output and the input, as a command given the call file: the agent's own stop hook runs it too.
names_its_unit = CommandValidator(
    [sys.executable, "-m", "contraagent.docs.examples.demo.checks", "{path}", "{call}"],
    name="names-its-unit",
)

summarize = agent_task(
    "summarize",
    params=SummarizeParams,
    plugin="plugins/docs",
    role="summarizer",
    output=Summary,
    validators=[three_points, its_own_unit],
    max_turns=10,
    timeout_s=300,
    retry_backoff_base=0.5,
)
review = agent_task(
    "review",
    params=ReviewParams,
    plugin="plugins/docs",
    role="reviewer",
    output=Verdict,
    max_turns=10,
    timeout_s=300,
    retries=2,
    retry_backoff_base=0.5,
)
revise = agent_task(
    "revise",
    params=ReviseParams,
    plugin="plugins/docs",
    role="reviser",
    output=Summary,
    validators=[three_points],
    max_turns=10,
    timeout_s=300,
)
write_note = agent_task(
    "write_note",
    params=NoteParams,
    plugin="plugins/docs",
    role="writer",
    output=Note,
    validators=[has_heading, names_its_unit],
    max_turns=10,
    timeout_s=300,
)


@python_task
def prepare(unit: str) -> Prepared:
    """A Python task: leave a checked description of the input for the agent."""
    path = INPUT_DIR / f"{unit}.md"
    if unit == "zeta":
        raise ValueError("zeta's input is malformed")  # its flow call stops: its later tasks are not created
    return Prepared(unit=unit, path=str(path), words=len(path.read_text(encoding="utf-8").split()))


@python_task
def score(unit: str, summary: Summary) -> Score | Partial[Score]:
    """A Python task: figures the reviewer reads beside the summary. For `epsilon` the
    word counter is unavailable: a partial result, its words 0 (a resume scores it again)."""
    points = len(summary.points)
    if unit == "epsilon":
        return Partial(Score(points=points, words=0), reason="the word counter is unavailable: words left at 0")
    return Score(points=points, words=sum(len(p.split()) for p in summary.points))


@python_task
def report(summaries: list[Summary]) -> str:
    return "\n".join(f"{s.unit}: {len(s.points)} points" for s in summaries)


async def one_review(unit: str) -> Summary:
    """One unit: prepare -> summarize -> score -> review, and a note beside the review."""
    summary = await summarize(unit, SummarizeParams(prepared=await prepare(unit)))
    figures = await score(unit, summary=summary)
    await asyncio.gather(review(unit, ReviewParams(summary=summary, score=figures)), write_note(unit, NoteParams(summary=summary)))
    return summary


async def docs_one_review(units: list[str]):
    """Every unit's review at once (a flow call each), then one report over the units that
    got through, returned."""
    done = await asyncio.gather(*[one_review(u) for u in units], return_exceptions=True)
    return await report(summaries=[s for s in done if isinstance(s, Summary)])


async def review_loop(unit: str):
    """One unit: its summary, revised until the review approves it, then its note. A task
    that fails ends this flow call, and only this one."""
    summary = await summarize(unit, SummarizeParams(prepared=await prepare(unit)))
    while True:
        figures = await score(unit, summary=summary)
        verdict = await review(unit, ReviewParams(summary=summary, score=figures))
        if verdict.approved:
            break
        summary = await revise(unit, ReviseParams(summary=summary, verdict=verdict))
    await write_note(unit, NoteParams(summary=summary))
    return summary


async def docs(units: list[str]):
    """Every unit's review loop at once (a flow call each), then one report over the approved
    summaries. A unit that failed is its exception in `done`; the other units go on."""
    done = await asyncio.gather(*[review_loop(u) for u in units], return_exceptions=True)
    return await report(summaries=[s for s in done if isinstance(s, Summary)])
