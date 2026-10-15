"""An agent task that adds to a file, and a validator that compares the file with what it held before.

`start` writes each topic's backlog with the ideas it was given. `grow` writes the same
file (`output_of=start`) with more ideas; `adds_an_idea` takes `before`, the backlog as it
was before `grow`, so a round that adds nothing goes back to the agent as a check error.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Backlog(BaseModel):
    topic: str
    ideas: list[str] = Field(description="one line per idea")


@python_task
def start(unit: str, ideas: list[str]) -> Backlog:
    """The topic's backlog, with the ideas it starts from."""
    return Backlog(topic=unit, ideas=ideas)


def adds_an_idea(path: Path, backlog: Backlog, *, before: Backlog | None):
    """At least one idea more than the file held before the task, and none of those removed."""
    if before is None:
        return None  # no backlog before the task: any backlog is an addition
    gone = [idea for idea in before.ideas if idea not in backlog.ideas]
    errors = [f"ideas: {idea!r} was removed; keep every idea the file held" for idea in gone]
    if len(backlog.ideas) <= len(before.ideas):
        errors.append(f"ideas: add at least one idea to the {len(before.ideas)} the file held")
    return errors


grow = agent_task(
    "grow",
    instructions="Add one new idea to the topic's backlog.",
    output=Backlog,
    output_of=start,  # the file start wrote for the same unit
    validators=[adds_an_idea],
    max_turns=10,
    timeout_s=300,
)


def backlogs(topics: dict[str, list[str]]):
    for topic, ideas in topics.items():
        start(topic, ideas=ideas)
        grow(topic)
