"""The types a user's checker infers for the public typed surface. `tests/test_typing.py`
checks this file with `mypy --strict` and pyright `strict`; it is never run.

A line that must not type-check ends with `# type: ignore[<mypy code>]`: both checkers
report an ignore comment that silences nothing (mypy's `--warn-unused-ignores`, part of
`--strict`; pyright's `reportUnnecessaryTypeIgnoreComment`), so each such line is an
error under both, and under mypy the error of that code."""

import asyncio
from pathlib import Path
from typing import Annotated, assert_type

from pydantic import BaseModel, Field

from contraagent import AgentTask, Implementations, InputFile, Partial, Pending, PythonTask, Rows, agent_task, python_task


class Triage(BaseModel):
    severity: int


class Finding(BaseModel):
    line: int


class TriageParams(BaseModel):
    text: str = Field(description="the report to triage")
    depth: int = Field(default=1, ge=1, description="how far to follow a call")


class LaneParams(TriageParams):
    lane: str = Field(description="the lane the finding belongs to")


class NoteParams(BaseModel):
    note: InputFile = Field(description="the note to review")


Note = Annotated[str, Field(examples=["One paragraph."])]

triage = agent_task("triage", params=TriageParams, output=Triage)
assert_type(triage, AgentTask[TriageParams, Triage])

finding = agent_task("finding", params=TriageParams, output=Rows[Finding])
assert_type(finding, AgentTask[TriageParams, Rows[Finding]])

note = agent_task("note", params=TriageParams, output=str)
assert_type(note, AgentTask[TriageParams, str])

summary = agent_task("summary", params=TriageParams, output=Note)
assert_type(summary, AgentTask[TriageParams, str])

survey = agent_task("survey", output=Triage)
assert_type(survey, AgentTask[None, Triage])

publish = agent_task("publish")
assert_type(publish, AgentTask[None, None])

tidy = agent_task("tidy", params=LaneParams)
assert_type(tidy, AgentTask[LaneParams, None])

review = agent_task("review", params=TriageParams, output=Triage, implementations={"fast": "fast.md", "deep": "deep.md"})
assert_type(review, Implementations[TriageParams, Triage])
assert_type(review["fast"], AgentTask[TriageParams, Triage])

review_note = agent_task("review_note", params=TriageParams, output=Note, implementations={"fast": "fast.md"})
assert_type(review_note, Implementations[TriageParams, str])

check = agent_task("check", implementations={"fast": "fast.md"})
assert_type(check, Implementations[None, None])

read_note = agent_task("read_note", params=NoteParams, output=Triage)
assert_type(read_note, AgentTask[NoteParams, Triage])


def output_of[**P, Out](task: PythonTask[P, Out]) -> Out:
    """The output type of a Python task, whose parameters `P` assert_type cannot spell."""
    raise NotImplementedError


@python_task
def count(unit: str, *, text: str) -> int:
    return len(text)


assert_type(output_of(count), int)


@python_task(kind="score", retries=1, retry_on=(ConnectionError,))
def score(unit: str, *, triage: Triage) -> float:
    return triage.severity / 10


assert_type(output_of(score), float)


@python_task
def lookup(unit: str, *, topic: str) -> Triage | Partial[Triage]:
    if not topic:
        return Partial(Triage(severity=0), reason="index server unavailable")
    return Triage(severity=1)


assert_type(output_of(lookup), Triage)


@python_task(kind="sources", retries=1, retry_on=(ConnectionError,))
def sources(topic: str) -> list[str] | Partial[list[str]]:
    return [topic]


assert_type(output_of(sources), list[str])


@python_task
def placeholder(topic: str) -> Partial[list[str]]:
    return Partial([], reason="index server unavailable")


assert_type(output_of(placeholder), list[str])


@python_task
def measure(unit: str, *, note: InputFile) -> int:
    assert_type(note.path, Path)
    assert_type(note.sha256, str | None)
    assert_type(note.read_bytes(), bytes)
    return len(note.read_text())


assert_type(output_of(measure), int)


def flow() -> None:
    params = TriageParams(text="...")
    triaged = triage("a", params)
    assert_type(triaged, Pending[Triage])
    assert_type(triaged.output, Triage)
    assert_type(triage(params), Pending[Triage])  # a task with no unit
    assert_type(count("a", text="..."), Pending[int])
    assert_type(score("a", triage=Triage(severity=1)), Pending[float])
    assert_type(lookup("a", topic="x"), Pending[Triage])
    assert_type(lookup("a", topic="x").output, Triage)
    assert_type(sources(topic="x"), Pending[list[str]])
    assert_type(publish("a"), Pending[None])
    assert_type(publish(), Pending[None])
    assert_type(survey("a"), Pending[Triage])
    assert_type(review["fast"]("a", params), Pending[Triage])
    assert_type(read_note("a", NoteParams(note=InputFile("in/a.md"))), Pending[Triage])
    assert_type(note("a", params).input_file(), InputFile)
    assert_type(measure("a", note=InputFile(Path("in/a.md"))), Pending[int])


async def waits() -> None:
    params = TriageParams(text="...")
    assert_type(await triage("a", params), Triage)
    assert_type(await finding("a", params), Rows[Finding])
    assert_type(await summary("a", params), str)
    assert_type(await tidy("a", LaneParams(text="...", lane="py")), None)
    assert_type(await review_note["fast"]("a", params), str)
    assert_type(await lookup("a", topic="x"), Triage)
    assert_type(await placeholder(topic="x"), list[str])
    both = await asyncio.gather(lookup("a", topic="x"), count("b", text="..."))
    assert_type(both, tuple[Triage, int])


# Call options: `.options()` returns the task as it is typed, so a call through it keeps its
# params and output types, and a generic helper that gives a key keeps them too.
assert_type(triage.options(key="k", priority=2, credential="team", cancellable=True), AgentTask[TriageParams, Triage])
assert_type(review["fast"].options(after=["triage-a"]), AgentTask[TriageParams, Triage])
assert_type(output_of(count.options(key="k").options(priority=1, cancellable=True)), int)
assert_type(triage.options(key="k").options(key=None, credential=None), AgentTask[TriageParams, Triage])


async def attempt[P: BaseModel, Out](task: AgentTask[P, Out], unit: str, params: P, *, key: str) -> Out:
    return await task.options(key=key)(unit, params)


async def keyed() -> None:
    params = TriageParams(text="...")
    assert_type(await triage.options(key="k")("a", params), Triage)
    assert_type(await attempt(triage, "a", params, key="k"), Triage)
    assert_type(await attempt(review["deep"], "a", params, key="k"), Triage)
    assert_type(count.options(cancellable=True)("a", text="..."), Pending[int])
    assert_type(await publish.options(key="p")("a"), None)


# What must not type-check.
def refused() -> None:
    params = TriageParams(text="...")
    TriageParams(txet="...")  # type: ignore[call-arg]  # a misspelled field
    TriageParams(text=3)  # type: ignore[arg-type]  # a field of another type
    TriageParams()  # type: ignore[call-arg]  # a required field left out
    triage("a", Triage(severity=1))  # type: ignore[call-overload]  # another model
    triage("a")  # type: ignore[call-overload]  # params left out
    triage("a", text="...")  # type: ignore[call-overload]  # params as keywords
    triage("a", params, key="k")  # type: ignore[call-overload]  # a call option on the call, not in .options()
    publish("a", params)  # type: ignore[call-overload]  # params to a task that declares none
    survey("a", params)  # type: ignore[call-overload]  # params to a task that declares none
    tidy("a", params)  # type: ignore[call-overload]  # the base model of the task's own
    review["fast"]("a", Triage(severity=1))  # type: ignore[call-overload]  # an implementation keeps the model
    count("a", txt="...")  # type: ignore[call-arg]  # a misspelled parameter of a Python task
    count("a", text=3)  # type: ignore[arg-type]  # a Python task's parameter of another type
    count("a", text="...", key="k")  # type: ignore[call-arg]  # a call option on a Python task's call
    count.options(credential="team")  # type: ignore[call-arg]  # a Python task has no credential
    triage.options(priorty=2)  # type: ignore[call-arg]  # a misspelled call option
    NoteParams(note="in/a.md")  # type: ignore[arg-type]  # a path where an input file goes
    measure("a", note="in/a.md")  # type: ignore[arg-type]  # a path where a Python task takes an input file
    InputFile(3)  # type: ignore[arg-type]  # an input file is made from a path


async def refused_helper() -> None:
    await attempt(triage, "a", Triage(severity=1), key="k")  # type: ignore[misc]  # the helper keeps the model
