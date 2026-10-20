"""Summaries of documents, one of them under another account.

`pipeline.toml` runs `summarize` as `team`. The data of a document in `RESTRICTED`
may go only under the company's account: its call options name the credential
`company`, so that task runs as `company` on every route of the kind, its failover
hop included. Every other document runs as the kind's own credential.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from contraagent import agent_task


class Summary(BaseModel):
    text: str = Field(examples=["The document describes the release plan."])


summarize = agent_task(
    "summarize",
    instructions="Summarize the document docs/${unit}.md in three sentences. Do not change it.",
    output=Summary,
)

#: The documents whose data may go only under the company's account.
RESTRICTED = {"contract"}


def summarize_all(documents: list[str]):
    """Summarize every document at once."""
    for document in documents:
        summarize.options(credential="company" if document in RESTRICTED else None)(document)
