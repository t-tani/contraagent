"""A judgement in one turn: a light launch (`agent_task(tools=())`).

`classify` reads one news item and answers in its final message. It has no tool:
its instructions replace the coding agent's own system prompt, the item reaches it
in the prompt with the output's JSON Schema, and no plugin, settings or MCP server
is loaded. A launch of it reads a few hundred tokens where a launch with tools
reads tens of thousands.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from contraagent import agent_task


class Classified(BaseModel):
    category: Literal["security", "product", "other"]
    promo: bool = Field(description="true when the item advertises a product or a service")


class ItemParams(BaseModel):
    title: str = Field(description="the news item's title")


classify = agent_task(
    "classify",
    params=ItemParams,
    instructions="You classify one news item: its category, and whether it is promotional.",
    output=Classified,
    output_from="message",
    tools=(),
    max_turns=2,
    timeout_s=120,
)


def items(titles: dict[str, str]):
    """Classify every item at once."""
    for unit, title in titles.items():
        classify(unit, ItemParams(title=title))
