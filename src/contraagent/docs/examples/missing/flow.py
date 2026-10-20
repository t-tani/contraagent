"""A task that finds something missing: its output says what, and the flow provides it.

`review` reads the documents of a unit and writes a verdict. A document it needs and
does not have, it names in `missing`, and it writes the verdict it can without it.
`review_unit` reads `missing`: it runs `fetch` for each name, which copies the document
from the archive, and runs `review` again with the documents it now has. What the
archive does not hold stays missing: the flow logs it as the pipeline log `missing`,
and the run panel in `PANELS` shows it in the monitor.

    contraagent monitor --runs-dir runs --panels path/to/flow.py:PANELS
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

import contraagent
from contraagent import agent_task, python_task
from contraagent.monitor import Panel, RunRecords, TableBody, TableColumn

#: A stand-in for an archive of documents, by name.
ARCHIVE = {"terms": "The terms of the service.", "budget": "The budget of the year."}


class Review(BaseModel):
    verdict: str = Field(description="one sentence: the review of the unit")
    missing: list[str] = Field(
        default=[],
        description="the names of the documents the review needs and does not have; empty when it has every one",
    )


class Fetched(BaseModel):
    name: str
    path: str | None = Field(description="where the document is now; None when the archive does not hold it")


review = agent_task(
    "review",
    instructions=(
        "Review the unit from the files in params.documents. When you need a document that is not"
        " among them, put its name in `missing` and write the verdict you can without it."
    ),
    output=Review,
    max_turns=10,
    timeout_s=300,
)


@python_task
def fetch(unit: str, name: str) -> Fetched:
    """Copy the document `name` from the archive into `documents/`, when the archive holds it."""
    text = ARCHIVE.get(name)
    if text is None:
        return Fetched(name=name, path=None)
    path = Path("documents") / f"{name}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return Fetched(name=name, path=path.as_posix())


async def review_unit(unit: str, documents: list[str]):
    """Review a unit; while the review names a missing document that the archive holds,
    fetch it and review again. Log what stays missing."""
    result = await review(unit, documents=documents)
    while result.missing:
        fetched = await asyncio.gather(*[fetch(f"{unit}-{name}", name=name) for name in result.missing])
        found = [f.path for f in fetched if f.path is not None]
        if not found:
            break  # nothing new to review with
        documents = documents + found
        result = await review(unit, documents=documents)  # the same unit again: key review-<unit>~2
    for name in result.missing:
        contraagent.log("missing", {"unit": unit, "document": name})
    return result


async def reviews(units: dict[str, list[str]]):
    """Every unit at once, a flow call each; the reviews of the units that got through. A
    unit whose task failed is its exception in `done`, and the other units go on."""
    done = await asyncio.gather(*[review_unit(unit, documents) for unit, documents in units.items()], return_exceptions=True)
    return [result for result in done if isinstance(result, Review)]


def missing(run: RunRecords) -> TableBody:
    """The documents that are still missing, one row per unit and document."""
    return TableBody(
        columns=[TableColumn(id="unit", label="Unit"), TableColumn(id="document", label="Document")],
        rows=run.log("missing"),
    )


#: What `contraagent monitor --panels flow.py:PANELS` loads.
PANELS = {"missing": Panel(missing, title="Missing documents", description="What the reviews still lack", icon="?")}
