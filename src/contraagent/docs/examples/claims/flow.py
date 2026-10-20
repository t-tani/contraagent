"""Claims: writes to one topic, one at a time, whatever their kind.

`style` and `terms` each rewrite a topic's file; both claim `topic:<unit>`, so
no two of them, of either kind, write one topic at once. `merge` writes two
topics: it claims each topic it names (`{params.topics}`), so it waits while a
write of either runs. `triage` only reads: it claims nothing, so it runs beside
anything, a write of the same topic included. `lookup` starts a local index
server of about 1.5 GB: every lookup claims `index`, and `CLAIM_CAPACITY` runs
as many at once as the host's free memory and cores hold.
"""

from __future__ import annotations

from pydantic import BaseModel

from contraagent import PerTask, agent_task


class Written(BaseModel):
    path: str


class Verdict(BaseModel):
    relevant: bool


style = agent_task(
    "style",
    instructions="Rewrite the file topics/${unit}.md in short sentences.",
    output=Written,
    claims=["topic:{unit}"],
    max_turns=10,
    timeout_s=300,
)
terms = agent_task(
    "terms",
    instructions="Rewrite the file topics/${unit}.md with the glossary's terms.",
    output=Written,
    claims=["topic:{unit}"],
    max_turns=10,
    timeout_s=300,
)
merge = agent_task(
    "merge",
    instructions="Merge the topics named in params.topics into the first of them.",
    output=Written,
    claims=["topic:{params.topics}"],
    max_turns=10,
    timeout_s=300,
)
triage = agent_task(
    "triage",
    instructions="Read the file topics/${unit}.md. Is it relevant to params.subject?",
    output=Verdict,
    max_turns=5,
    timeout_s=300,
)

lookup = agent_task(
    "lookup",
    instructions="Start the local index server, find the passages on params.subject, and stop it.",
    output=Written,
    claims=["index"],
    max_turns=10,
    timeout_s=300,
)

#: `Pipeline(claim_capacity=CLAIM_CAPACITY)`: one lookup needs 1.5 GB and one core.
CLAIM_CAPACITY = {"index": PerTask(memory_mb=1500, cores=1)}


def topics(names: list[str]):
    for name in names:
        style(name)
        terms(name)  # one topic's rewrites run one after the other
        triage(name, subject="security")  # claims nothing: runs beside them
    merge.options(key="merge")(names[0], topics=names)  # claims every topic it names
