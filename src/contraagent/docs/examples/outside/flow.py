"""Outside state: tasks that read a file the pipeline keeps beside their params.

`state/backlog.json` lists the open items of each topic; another process adds to it
between runs. `count_open` reads it for its topic, and `summarize` is told to read it
too. Neither gets the file's content as a parameter, so each declares
`outside_state=backlog_digest`: its fingerprint covers the file, and a resume runs the
tasks of the topics again once the file changed, and skips them while it did not.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task

BACKLOG = Path("state/backlog.json")


def backlog_digest(unit: str, params: dict[str, Any]) -> str:
    """The digest of the backlog file, read in blocks; empty while there is none."""
    try:
        with BACKLOG.open("rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except FileNotFoundError:
        return ""


class OpenItems(BaseModel):
    topic: str
    count: int


class Summary(BaseModel):
    text: str


class SummarizeParams(BaseModel):
    counts: OpenItems = Field(description="the topic and how many open items the backlog holds for it")


@python_task(outside_state=backlog_digest)
def count_open(unit: str) -> OpenItems:
    """How many items of topic `unit` the backlog holds."""
    items = json.loads(BACKLOG.read_text(encoding="utf-8")) if BACKLOG.exists() else {}
    return OpenItems(topic=unit, count=len(items.get(unit, [])))


summarize = agent_task(
    "summarize",
    params=SummarizeParams,
    instructions="Summarize the open items of topic params.counts.topic in state/backlog.json in one paragraph.",
    output=Summary,
    outside_state=backlog_digest,
    max_turns=10,
    timeout_s=300,
)


async def topic(name: str) -> None:
    """One topic: its open items counted, then its summary."""
    await summarize(name, SummarizeParams(counts=await count_open(name)))


async def topics(names: list[str]):
    """Every topic at once (a flow call each): a topic that fails stops only its own."""
    await asyncio.gather(*[topic(name) for name in names], return_exceptions=True)
