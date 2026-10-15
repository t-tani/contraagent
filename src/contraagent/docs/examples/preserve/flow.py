"""An agent task that fills in a file a Python task wrote, and keeps what that task wrote.

`outline` writes each report's source and its items, with empty summaries. `fill` writes
the same file (`output_of=outline`) with the summaries filled in; `preserve` names
the parts it must keep as they were, so an item's id or title that changed goes back to
the agent as a check error.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Item(BaseModel):
    id: str
    title: str
    summary: str = Field(default="", description="two sentences on the item; empty until it is filled in")


class Report(BaseModel):
    source: str = Field(description="the document the items come from, relative to the working directory")
    items: list[Item]


@python_task
def outline(unit: str, titles: list[str]) -> Report:
    """The report's skeleton: an item per title, each with an id of its own."""
    return Report(source=f"inputs/{unit}.md", items=[Item(id=f"{unit}-{i}", title=t) for i, t in enumerate(titles, 1)])


fill = agent_task(
    "fill",
    instructions="Write the summary of each item of the report from its source document.",
    output=Report,
    output_of=outline,  # the file outline wrote for the same unit
    preserve=["/source", "/items/*/id", "/items/*/title"],
    max_turns=20,
    timeout_s=600,
)


def reports(units: dict[str, list[str]]):
    for unit, titles in units.items():
        outline(unit, titles=titles)
        fill(unit)  # writes outline's file for the unit, after outline
