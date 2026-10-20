"""The types a user's checker infers for the public typed surface. `tests/test_typing.py`
checks this file with `mypy --strict` and pyright `strict`; it is never run."""

import asyncio
from collections.abc import Mapping
from typing import Annotated, Any, assert_type

from pydantic import BaseModel, Field

from contraagent import AgentTask, Partial, Pending, PythonTask, Rows, agent_task, python_task


class Triage(BaseModel):
    severity: int


class Finding(BaseModel):
    line: int


triage = agent_task("triage", output=Triage)
assert_type(triage, AgentTask[Triage])

finding = agent_task("finding", output=Rows[Finding])
assert_type(finding, AgentTask[Rows[Finding]])

note = agent_task("note", output=str)
assert_type(note, AgentTask[str])

summary = agent_task("summary", output=Annotated[str, Field(examples=["One paragraph."])])
assert_type(summary, AgentTask[Any])

publish = agent_task("publish")
assert_type(publish, AgentTask[None])

review = agent_task("review", output=Triage, implementations={"fast": "fast.md", "deep": "deep.md"})
assert_type(review, Mapping[str, AgentTask[Triage]])

check = agent_task("check", implementations={"fast": "fast.md"})
assert_type(check, Mapping[str, AgentTask[None]])


@python_task
def count(text: str) -> int:
    return len(text)


assert_type(count, PythonTask[int])


@python_task(name="score", retries=1, retry_on=(ConnectionError,))
def score(triage: Triage) -> float:
    return triage.severity / 10


assert_type(score, PythonTask[float])


@python_task
def lookup(topic: str) -> Triage | Partial[Triage]:
    if not topic:
        return Partial(Triage(severity=0), reason="index server unavailable")
    return Triage(severity=1)


assert_type(lookup, PythonTask[Triage])


@python_task(name="sources", retries=1, retry_on=(ConnectionError,))
def sources(topic: str) -> list[str] | Partial[list[str]]:
    return [topic]


assert_type(sources, PythonTask[list[str]])


@python_task
def placeholder(topic: str) -> Partial[list[str]]:
    return Partial([], reason="index server unavailable")


assert_type(placeholder, PythonTask[list[str]])


def flow() -> None:
    triaged = triage("a", text="...")
    assert_type(triaged, Pending[Triage])
    assert_type(triaged.output, Triage)
    assert_type(count("a", text="..."), Pending[int])
    assert_type(score("a", triage=triaged), Pending[float])
    assert_type(lookup("a", topic="x"), Pending[Triage])
    assert_type(lookup("a", topic="x").output, Triage)
    assert_type(publish("a"), Pending[None])
    assert_type(review["fast"]("a"), Pending[Triage])


async def waits() -> None:
    assert_type(await triage("a", text="..."), Triage)
    assert_type(await lookup("a", topic="x"), Triage)
    assert_type(await placeholder("a", topic="x"), list[str])
    both = await asyncio.gather(lookup("a", topic="x"), count("b", text="..."))
    assert_type(both, tuple[Triage, int])
