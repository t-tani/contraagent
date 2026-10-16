"""MCP servers built for each task: a search index over one collection of documents.

`answer` asks one question about one collection. Its plugin gives every task the same
`glossary` server (`plugins/research/.mcp.json`). The search index is different for
each collection, so `index_for` adds an `index` server built from the task's params:
it serves `params.collection` and nothing else. A task of another kind gets its
plugin's servers as they are. A function is no command-line argument, so a program
runs it: `pipeline().run(ask_all, questions={...})`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from contraagent import Pipeline, Task, agent_task


class Question(BaseModel):
    collection: str = Field(description="the folder of the documents, relative to the working directory")
    question: str


class Answer(BaseModel):
    text: str
    sources: list[str] = Field(description="the documents the answer rests on")


answer = agent_task("answer", plugin="plugins/research", params=Question, output=Answer, max_turns=30, timeout_s=900)


def index_for(task: Task, params: dict[str, Any], servers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    """The plugin's servers and an `index` over the task's own collection, for `answer`;
    None (the plugin's as they are) for any other kind."""
    if task.kind != "answer":
        return None
    index = {"command": "index-server", "args": ["--stdio", "--root", params["collection"]]}
    return {**servers, "index": index}


def ask_all(questions: dict[str, str]):
    """`questions` maps each collection to its question."""
    answers = yield [answer(name, collection=f"collections/{name}", question=q) for name, q in questions.items()]
    return {name: a.text for name, a in zip(questions, answers, strict=True)}


def pipeline(**options: Any) -> Pipeline:
    return Pipeline(mcp_servers=index_for, **options)
