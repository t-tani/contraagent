"""A partial result: a lookup that writes a placeholder while its index server is unavailable.

`find_sources` asks a local index server for the files on a topic. When the server
does not answer, the lookup returns `Partial`: an empty list of files as its output,
and why. The run goes on: `summarize` runs on what the lookup wrote. A later resume
runs that lookup again, with the `summarize` that read its output; every other task
it skips.
"""

from __future__ import annotations

from pydantic import BaseModel

from contraagent import Partial, agent_task, python_task


class LocalIndex:
    """A stand-in for a local index server: `lookup` raises ConnectionError while it is down."""

    def __init__(self, entries: dict[str, list[str]]) -> None:
        self.entries = entries
        self.up = True

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


@python_task
def find_sources(unit: str) -> Sources | Partial[Sources]:
    """The files on topic `unit`, from the local index server; none while it is unavailable."""
    try:
        return Sources(topic=unit, paths=index.lookup(unit))
    except ConnectionError:
        return Partial(Sources(topic=unit, paths=[]), reason="index server unavailable")


summarize = agent_task(
    "summarize",
    instructions="Summarize the files in params.sources.paths in one paragraph; with no files, say so.",
    output=Summary,
    max_turns=10,
    timeout_s=300,
)


def topics(names: list[str]):
    for name in names:
        summarize(name, sources=find_sources(name))
