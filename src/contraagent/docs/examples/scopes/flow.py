"""A scope around each attempt of a Python task: a local index server of its own.

`find_sources` asks a local index server for the files on a topic. The scope
`index_server` starts the server before each attempt of a `find_sources` task and
stops it after, a failed attempt included; every other task runs without one. The
server listens on a free port, and the scope gives the attempt its address by the
task's unit, so two tasks that run at once each ask their own server. A dropped
connection is worth a fresh attempt (`retry_on`), and the fresh attempt gets a fresh
server. `summarize` then reads the files the lookup found.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pydantic import BaseModel

from contraagent import Pipeline, Task, agent_task, python_task

INDEX = {"caching": ["notes/caching.md", "notes/eviction.md"], "queues": ["notes/queues.md"]}

#: The address of the index server the running attempt of each unit asks.
servers: dict[str, str] = {}


class Sources(BaseModel):
    topic: str
    paths: list[str]


class Summary(BaseModel):
    text: str


@python_task(retries=2, retry_on=(ConnectionError, TimeoutError))
def find_sources(unit: str) -> Sources:
    """The files on topic `unit`, from the attempt's local index server."""
    with urllib.request.urlopen(f"{servers[unit]}/{unit}", timeout=10) as response:
        return Sources(topic=unit, paths=json.load(response))


summarize = agent_task(
    "summarize",
    instructions="Summarize the files in params.sources.paths in one paragraph.",
    output=Summary,
    max_turns=10,
    timeout_s=300,
)


class _Lookup(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(INDEX.get(self.path.strip("/"), [])).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextlib.contextmanager
def _serving(task: Task) -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Lookup)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    servers[task.unit] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield
    finally:
        servers.pop(task.unit, None)
        server.shutdown()
        server.server_close()


def index_server(task: Task) -> contextlib.AbstractContextManager[None]:
    """A `TaskScope`: a local index server for each attempt of a `find_sources` task."""
    return _serving(task) if task.kind == find_sources.kind else contextlib.nullcontext()


async def topic(name: str) -> None:
    """One topic: its sources, then its summary."""
    await summarize(name, sources=await find_sources(name))


async def topics(names: list[str]):
    """Every topic at once (a flow call each): a topic that fails stops only its own."""
    await asyncio.gather(*[topic(name) for name in names], return_exceptions=True)


def pipeline(**options: Any) -> Pipeline:
    return Pipeline(scopes=[index_server], **options)
