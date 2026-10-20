"""One step, two implementations: the flow chooses one per unit.

Each unit is reviewed, but a Python module and a Go package need different tools:
a different role, different skills and a different MCP server. One declaration
names both implementations, each its own plugin; each is a kind of its own
(`review-python`, `review-go`) and both write the same `Review`. The flow picks
the implementation from a fact about the unit (here, its language).

    contraagent run flow.py:review_all --stub --kwargs '{"units": {"parser": "python", "server": "go"}}'
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from contraagent import agent_task


class Review(BaseModel):
    unit: str
    findings: list[str]


review = agent_task(
    "review",
    implementations={"python": "plugins/review-python", "go": "plugins/review-go"},
    role="reviewer",
    output=Review,
    max_turns=20,
    timeout_s=600,
)


async def review_all(units: dict[str, str]):
    """`units` maps each unit to its language, `python` or `go`. Every unit at once; a unit
    whose review failed is its exception in `done`, and is left out of the counts."""
    done = await asyncio.gather(*[review[lang](unit, path=f"src/{unit}") for unit, lang in units.items()], return_exceptions=True)
    return {unit: len(result.findings) for unit, result in zip(units, done, strict=True) if isinstance(result, Review)}
