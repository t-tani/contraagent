"""Skills several tasks share: a skill plugin beside each task's own plugin.

Each task keeps its own role, and with it its own permissions and hooks, in its
plugin. The house style every writing task follows is a skill plugin of its own,
which each of them names in `skills_from`.
"""

from __future__ import annotations

from contraagent import agent_task
from contraagent.docs.examples.demo.tasks import Summary

summarize = agent_task(
    "summarize",
    plugin="../demo/plugins/docs",
    role="summarizer",
    skills_from=["plugins/house-style"],
    output=Summary,
    max_turns=10,
    timeout_s=300,
)
write_note = agent_task(
    "write_note",
    plugin="../demo/plugins/docs",
    role="writer",
    skills_from=["plugins/house-style"],
    output=str,
    max_turns=10,
    timeout_s=300,
)


def notes(units: list[str]):
    for unit in units:
        summarize(unit, path=f"in/{unit}.md")
        write_note(unit, path=f"in/{unit}.md")
