"""A deadline over one part of a flow: the agent work has its time, the steps after it always run.

`cycle` writes each topic, then publishes what it wrote. Writing is the part that
can run long, so it runs in a time box: `topic_work` has `deadline_s` from its
start. A `write` it creates past the deadline is not launched: the flow receives
`TaskDeferred` and leaves the rest for the next cycle. `summarize` is a finishing
kind: it still launches past the deadline, for `grace_s`. `publish`, created after
the time box, is outside it, so the box's deadline never stops it.
"""

from __future__ import annotations

from pydantic import BaseModel

from contraagent import TaskDeferred, agent_task, python_task, time_box


class Note(BaseModel):
    topic: str
    summary: str


class Digest(BaseModel):
    text: str


write = agent_task("write", instructions="Write a short note on ${subject}.", output=Note, max_turns=10, timeout_s=600)
summarize = agent_task("summarize", instructions="Summarize the notes in one paragraph.", output=Digest, max_turns=5, timeout_s=300)


@python_task
def publish(count: int) -> int:
    """Outside the time box: runs whatever happened inside it."""
    return count


async def topic_work(topics: list[str]):
    notes: list[Note] = []
    for topic in topics:
        try:
            notes.append(await write(topic, subject=topic))
        except TaskDeferred:
            break  # past the deadline: the other topics wait for the next cycle
    if notes:
        await summarize(notes=[n.model_dump() for n in notes])
    return notes


async def cycle(topics: list[str], deadline_s: float = 45 * 60):
    notes = await time_box(topic_work(topics), deadline_s=deadline_s, grace_s=15 * 60, finishing_kinds=["summarize"])
    await publish(count=len(notes))
    return [n.topic for n in notes]
