"""The demo pipeline's tasks and flows: the part of a pipeline that is its own.

Each agent task is an interface (parameters, output, budget) whose
implementation is a role of the `plugins/docs` plugin. A flow is a plain
function: passing one task's result to another is the dependency. `docs` is a
generator: it waits for results and decides on them (a review loop per unit).
`docs_one_review` creates the same kinds of tasks without waiting for any.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

from contraagent import CommandValidator, TaskFailed, agent_task, python_task

INPUT_DIR = Path("inputs")


class Prepared(BaseModel):
    unit: str
    path: str = Field(description="the document to summarize, relative to the working directory")
    words: int


class Summary(BaseModel):
    unit: str = Field(description="the unit this summary is for, copied from the call file")
    points: list[str] = Field(description="the main points, one short sentence each")


class Score(BaseModel):
    points: int
    words: int


class Verdict(BaseModel):
    approved: bool
    note: str = Field(description="one sentence: what to change, when not approved")


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
    plugin="plugins/docs",
    role="summarizer",
    output=Summary,
    validators=[three_points, its_own_unit],
    max_turns=10,
    timeout_s=300,
    retry_backoff_base=0.5,
)
review = agent_task(
    "review", plugin="plugins/docs", role="reviewer", output=Verdict, max_turns=10, timeout_s=300, retries=3, retry_backoff_base=0.5
)
revise = agent_task("revise", plugin="plugins/docs", role="reviser", output=Summary, validators=[three_points], max_turns=10, timeout_s=300)
write_note = agent_task(
    "write_note", plugin="plugins/docs", role="writer", output=str, validators=[has_heading, names_its_unit], max_turns=10, timeout_s=300
)


@python_task
def prepare(unit: str) -> Prepared:
    """A Python task: leave a checked description of the input for the agent."""
    path = INPUT_DIR / f"{unit}.md"
    if unit == "zeta":
        raise ValueError("zeta's input is malformed")  # its downstream tasks are refused, not launched
    return Prepared(unit=unit, path=str(path), words=len(path.read_text().split()))


@python_task
def score(unit: str, summary: Summary) -> Score:
    """A Python task: figures the reviewer reads beside the summary."""
    return Score(points=len(summary.points), words=sum(len(p.split()) for p in summary.points))


@python_task
def report(summaries: list[Summary]) -> str:
    return "\n".join(f"{s.unit}: {len(s.points)} points" for s in summaries)


def docs_one_review(units: list[str]):
    """Per unit: prepare -> summarize -> score -> review, and a note; then one report, returned."""
    summaries = []
    for u in units:
        summary = summarize(u, prepared=prepare(u))
        review(u, summary=summary, score=score(u, summary=summary))
        write_note(u, summary=summary)
        summaries.append(summary)
    return report(summaries=summaries)


def review_loop(unit: str):
    """One unit: its summary, revised until the review approves it, then its note.
    None when the summary could not be made."""
    try:
        summary = yield summarize(unit, prepared=prepare(unit))
    except TaskFailed:
        return None
    while True:
        figures = yield score(unit, summary=summary)
        verdict = yield review(unit, summary=summary, score=figures)
        if verdict.approved:
            break
        summary = yield revise(unit, summary=summary, verdict=verdict)
    yield write_note(unit, summary=summary)
    return summary


def docs(units: list[str]):
    """Every unit's review loop at once (a flow call each), then one report over the approved summaries."""
    summaries = yield [review_loop(u) for u in units]
    return (yield report(summaries=[s for s in summaries if s is not None]))
