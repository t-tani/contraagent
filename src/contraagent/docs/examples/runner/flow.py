"""A flow that `run.py` runs: one review of each unit's release notes.

`contraagent run flow.py:reviews` runs it too; `run.py` adds what the command line
cannot pass.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task


class Review(BaseModel):
    severity: Literal["low", "medium", "high"] = Field(description="how much the changes can break for a user")
    summary: str


review = agent_task(
    "review",
    instructions="Read the release notes in ${path} and say how much they can break for a user.",
    output=Review,
    max_turns=10,
    timeout_s=300,
)


def reviews(units: list[str]):
    for unit in units:
        review(unit, path=f"in/{unit}.md")
