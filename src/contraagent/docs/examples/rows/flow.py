"""Rows: a long review that writes each finding as soon as it has it.

`review` reads the documents of one unit and writes one finding per line of its
output, a JSON Lines file (`output=Rows[Finding]`). Each line is checked against
`Finding`, and `distinct` sees the rows as a list. With `partial_on`, a launch the
runner stops for its time limit or for a stall keeps the findings written so far:
the task is partial, and `tally` counts what there is. A resume runs the review
again.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from contraagent import Rows, agent_task, python_task


class Finding(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"document": "docs/{unit}.md", "line": 1, "note": "a broken link"}]})

    document: str = Field(description="the document's path")
    line: int = Field(ge=1, description="the line the finding is on")
    note: str = Field(description="what is wrong, in one sentence")


class Tally(BaseModel):
    findings: int
    documents: int


def distinct(path: Path, findings: Rows[Finding]) -> list[str]:
    """No two findings on the same line of the same document."""
    seen: set[tuple[str, int]] = set()
    errors = []
    for n, f in enumerate(findings, 1):
        if (f.document, f.line) in seen:
            errors.append(f"row {n}: {f.document}:{f.line} has a finding already; give one finding per line")
        seen.add((f.document, f.line))
    return errors


review = agent_task(
    "review",
    instructions="Review every document under docs/ for unit $unit, and write one finding per problem you find.",
    output=Rows[Finding],
    validators=[distinct],
    partial_on=["timeout", "stalled"],
    max_turns=200,
    timeout_s=3600,
    stall_s=600,
)


@python_task
def tally(unit: str, findings: list[Finding]) -> Tally:
    """How many findings, on how many documents."""
    return Tally(findings=len(findings), documents=len({f.document for f in findings}))


def reviews(units: list[str]):
    for unit in units:
        findings = yield review(unit)
        tally(unit, findings=findings)
