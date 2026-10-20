"""A task that changes files beside its output, and a pipeline that hooks its dispatch.

`write` may change the files under `topics/<unit>/`: each attempt's changes are
recorded in its journal row, and the files a failed attempt created are removed.
`Effect`, a `ResultEnricher`, names what the attempt did to the topic from those
changes, and `row_extras` puts that in the journal row beside them. `study` keeps
the notes a failed attempt wrote under `notes/<unit>/` (`keep_failed_changes`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pydantic import BaseModel, Field

from contraagent import Pipeline, Task, TaskResult, agent_task


class Written(BaseModel):
    topic: str = Field(description="the topic file written, relative to the working directory")


class WriteParams(BaseModel):
    subject: str = Field(description="what the topic is about")


write = agent_task(
    "write",
    params=WriteParams,
    instructions="Write or update the topic file under topics/${unit}/ for params.subject.",
    output=Written,
    changes=["topics/{unit}/**"],
    max_turns=20,
    timeout_s=600,
)


class Effect:
    """What an attempt did to its topic: `new`, `updated` or `unchanged`."""

    def snapshot(self, task: Task) -> Any:
        return None

    def enrich(self, task: Task, before: Any, result: TaskResult) -> TaskResult | None:
        c = result.changes
        if not result.ok or c is None:
            return None
        return replace(result, payload={"effect": "new" if c.created else "updated" if c.modified else "unchanged"})


def topics(subjects: dict[str, str]):
    for unit, subject in subjects.items():
        write(unit, WriteParams(subject=subject))


study = agent_task(
    "study",
    instructions="Study the topic under topics/${unit}/ and keep your working notes under notes/${unit}/.",
    output=Written,
    changes=["notes/{unit}/**", "!notes/{unit}/.cache/**"],  # but its tools' cache
    keep_failed_changes=True,  # a failed attempt's notes stay: they say how far it got
    max_turns=40,
    timeout_s=1800,
)


def pipeline(**options: Any) -> Pipeline:
    return Pipeline(enrichers=[Effect()], row_extras=lambda result: result.payload if isinstance(result.payload, dict) else {}, **options)
