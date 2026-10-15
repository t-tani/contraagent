"""One step, two implementations: the flow chooses one per unit.

Each unit is reviewed, but a Python module and a Go package need different tools:
a different role, different skills and a different MCP server. Each implementation
is a kind of its own with its own plugin; both write the same `Review`. The flow
picks the kind from a fact about the unit (here, its language).

    contraagent run flow.py:review_all --stub --kwargs '{"units": {"parser": "python", "server": "go"}}'
    contraagent monitor --groups flow.py:GROUPS
"""

from __future__ import annotations

from pydantic import BaseModel

from contraagent import agent_task


class Review(BaseModel):
    unit: str
    findings: list[str]


review_python = agent_task("review-python", plugin="plugins/review-python", role="reviewer", output=Review, max_turns=20, timeout_s=600)
review_go = agent_task("review-go", plugin="plugins/review-go", role="reviewer", output=Review, max_turns=20, timeout_s=600)


def review_all(units: dict[str, str]):
    """`units` maps each unit to its language, `python` or `go`."""
    counts = {}
    for unit, lang in units.items():
        review = {"python": review_python, "go": review_go}[lang]
        result = yield review(unit, path=f"src/{unit}")
        counts[unit] = len(result.findings)
    return counts


#: The monitor draws both kinds as one column, `review` (`Monitor(groups=GROUPS)`).
GROUPS = [{"id": "review", "label": "review", "kinds": ["review-python", "review-go"]}]
