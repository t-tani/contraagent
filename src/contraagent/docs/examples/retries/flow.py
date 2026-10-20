"""Retries of a Python task: a lookup on a local index server that may drop a connection.

`find_sources` asks a local index server for the files on a topic. A dropped
connection or a timeout is worth a fresh attempt (`retry_on`), up to two more
(`retries=2`); any other exception fails the task at once. The function restores
what it needs at its start: `ensure_running()` starts the server when it is down,
so a fresh attempt after the server stopped finds it running again. `summarize`
then reads the files the lookup found.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from contraagent import agent_task, python_task


class LocalIndex:
    """A stand-in for a local index server: `lookup` raises ConnectionError while it is down."""

    def __init__(self, entries: dict[str, list[str]]) -> None:
        self.entries = entries
        self.up = False

    def ensure_running(self) -> None:
        if not self.up:
            self.up = True  # a real server: start its process and wait for its port

    def lookup(self, topic: str) -> list[str]:
        if not self.up:
            raise ConnectionError("index server is not running")
        return self.entries.get(topic, [])


index = LocalIndex({"caching": ["notes/caching.md", "notes/eviction.md"], "queues": ["notes/queues.md"]})


class Sources(BaseModel):
    topic: str
    paths: list[str]


class Summary(BaseModel):
    text: str


class SummarizeParams(BaseModel):
    sources: Sources = Field(description="the topic and the files found on it")


@python_task(retries=2, retry_on=(ConnectionError, TimeoutError))
def find_sources(unit: str) -> Sources:
    """The files on topic `unit`, from the local index server."""
    index.ensure_running()  # each attempt restores the server first
    return Sources(topic=unit, paths=index.lookup(unit))


summarize = agent_task(
    "summarize",
    params=SummarizeParams,
    instructions="Summarize the files in params.sources.paths in one paragraph.",
    output=Summary,
    max_turns=10,
    timeout_s=300,
)


async def topic(name: str) -> None:
    """One topic: its sources, then its summary."""
    await summarize(name, SummarizeParams(sources=await find_sources(name)))


async def topics(names: list[str]):
    """Every topic at once (a flow call each): a topic that fails stops only its own."""
    await asyncio.gather(*[topic(name) for name in names], return_exceptions=True)
