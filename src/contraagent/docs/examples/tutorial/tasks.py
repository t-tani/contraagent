"""The tutorial's pipeline: triage a folder of bug reports (`contraagent docs tutorial`).

`triage_all` triages every report and writes one table. `triage_and_plan` waits
for each triage and plans a fix for the reports it finds high severity.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class Triage(BaseModel):
    severity: Literal["low", "medium", "high"] = Field(description="high: users lose data or cannot work")
    area: str = Field(description="the part of the product the report is about, in one or two words")
    summary: str = Field(description="what goes wrong, in one sentence")


class FixPlan(BaseModel):
    cause: str = Field(description="the most likely cause, in one sentence")
    steps: list[str] = Field(description="what to change, in order, one short sentence each")


def short_summary(path, triage: Triage):
    """A rule the schema cannot express: a summary of 25 words or fewer."""
    words = len(triage.summary.split())
    if words > 25:
        return [f"summary: at most 25 words, got {words}"]


triage = agent_task(
    "triage",
    plugin="plugins/triage",
    role="triager",
    output=Triage,
    validators=[short_summary],
    max_turns=10,
    timeout_s=300,
)
plan_fix = agent_task("plan_fix", plugin="plugins/triage", role="planner", output=FixPlan, max_turns=20, timeout_s=600)


@python_task
def write_table(triaged: dict[str, Triage]) -> str:
    """A Python task: one Markdown table, the most severe reports first."""
    order = {"high": 0, "medium": 1, "low": 2}
    rows = sorted(triaged.items(), key=lambda item: (order[item[1].severity], item[0]))
    lines = ["| Report | Severity | Area | Summary |", "|---|---|---|---|"]
    lines += [f"| {name} | {t.severity} | {t.area} | {t.summary} |" for name, t in rows]
    return "\n".join(lines) + "\n"


def report_path(name: str) -> str:
    return f"issues/{name}.md"


def triage_all(reports: list[str]):
    """Triage every report at once, then write one table."""
    triaged = {name: triage(name, report=report_path(name)) for name in reports}
    return write_table(triaged=triaged)


async def triage_one(name: str):
    """One report: its triage, and a fix plan when it is high severity."""
    found = await triage(name, report=report_path(name))
    if found.severity == "high":
        await plan_fix(name, report=report_path(name), triage=found)
    return found


async def triage_and_plan(reports: list[str]):
    """Every report's triage_one at once, then one table."""
    triaged = await asyncio.gather(*[triage_one(name) for name in reports])
    return await write_table(triaged=dict(zip(reports, triaged, strict=True)))
