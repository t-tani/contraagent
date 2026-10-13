"""Units and their locks: a task on two units locks both.

`write` rewrites one topic's file; `compare` reads two topics' files and says
whether they cover one subject. A `compare` of `alpha` and `beta` is a task on
unit `alpha` that locks `beta` too (`extra_units`), so no `write` of either topic
runs while it reads them. Its output file and its name stay its own unit's.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contraagent import agent_task


class Written(BaseModel):
    path: str


class Overlap(BaseModel):
    same_subject: bool
    note: str = Field(description="what the two files share, or how they differ")


write = agent_task(
    "write", instructions="Rewrite the file at params.path from the notes on params.topic.", output=Written, max_turns=10, timeout_s=300
)
compare = agent_task(
    "compare",
    instructions="Read the files at params.first and params.second: do they cover one subject?",
    output=Overlap,
    max_turns=5,
    timeout_s=300,
)


def topics(names: list[str], pairs: list[tuple[str, str]]):
    """Rewrite every topic, and compare each pair while neither of its topics is being rewritten."""
    for name in names:
        write(name, topic=name, path=f"topics/{name}.md")
    for first, second in pairs:
        compare(first, key=f"compare-{first}-{second}", extra_units=[second], first=f"topics/{first}.md", second=f"topics/{second}.md")
