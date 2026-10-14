"""Tags: writes to one topic, one at a time, whatever their kind.

`draft` writes a topic's file and `fix` rewrites it; both hold the tag
`topic:<unit>`, and `tag_capacity` (or the config's `[defaults.tag_capacity]`)
caps every `topic:*` tag at 1, each topic on its own. The unit lock already
keeps tasks of different kinds on one topic apart, but it lets tasks of one
kind share it: two `fix` tasks of one topic would write it at once. The tag
does not. `triage` only reads: it holds no tag, so the triages of one topic
run at once.
"""

from __future__ import annotations

from pydantic import BaseModel

from contraagent import Pipeline, agent_task


class Written(BaseModel):
    path: str


class Verdict(BaseModel):
    relevant: bool


draft = agent_task(
    "draft",
    instructions="Write the file topics/${unit}.md from params.notes.",
    output=Written,
    tags=["topic:{unit}"],
    max_turns=10,
    timeout_s=300,
)
fix = agent_task(
    "fix",
    instructions="Rewrite the file topics/${unit}.md so that it follows params.rule.",
    output=Written,
    tags=["topic:{unit}"],
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


def topics(names: list[str]):
    for name in names:
        written = draft(name, notes=f"notes on {name}")
        # Two fixes of one kind on one topic: the unit lock lets them overlap, the tag does not.
        fixed = [
            fix(name, key=f"fix-{name}-style", after=[written], rule="short sentences"),
            fix(name, key=f"fix-{name}-terms", after=[written], rule="the glossary's terms"),
        ]
        # Two triages of one topic: no tag, so they run at once.
        for subject in ("security", "privacy"):
            triage(name, key=f"triage-{name}-{subject}", after=fixed, subject=subject)


def pipeline(**options) -> Pipeline:
    return Pipeline(tag_capacity={"topic:*": 1}, **options)
