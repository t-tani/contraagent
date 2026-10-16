"""A service: one local index server that the tasks which claim `index` share.

`index_server` is the service the claim name `index` stands for. The first task that
claims `index` starts it, and the run's end stops it, a failed or interrupted run
included. Every `find_sources` task claims `index` and asks the server by its address
(`service_address`); `CLAIM_CAPACITY` lets four of them ask it at once. `review` is an
agent task that claims `index` too: its coding agent finds the address in
`$CONTRAAGENT_SERVICE_INDEX`. `summarize` claims nothing and runs without the server.
"""

from __future__ import annotations

import contextlib
import json
import threading
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task, service_address

INDEX = {"caching": ["notes/caching.md", "notes/eviction.md"], "queues": ["notes/queues.md"]}


class Sources(BaseModel):
    topic: str
    paths: list[str]


class Summary(BaseModel):
    text: str


class Review(BaseModel):
    missing: list[str]


@python_task(claims=["index"])
def find_sources(unit: str) -> Sources:
    """The files on topic `unit`, from the run's index server."""
    with urllib.request.urlopen(f"{service_address('index')}/{unit}", timeout=10) as response:
        return Sources(topic=unit, paths=json.load(response))


summarize = agent_task(
    "summarize",
    instructions="Summarize the files in params.sources.paths in one paragraph.",
    output=Summary,
    max_turns=10,
    timeout_s=300,
)

review = agent_task(
    "review",
    instructions=(
        "The index server is at $CONTRAAGENT_SERVICE_INDEX: GET <address>/<topic> lists the files on a topic. "
        "List the topics of params.topics that it has no files on."
    ),
    output=Review,
    claims=["index"],
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
def index_server(name: str) -> Iterator[str]:
    """The service of the claim name `index`: a local index server on a free port. It
    gives its address, which reaches every task that claims `index`."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Lookup)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


#: `Pipeline(claim_capacity=CLAIM_CAPACITY)`: four tasks ask the one server at once.
CLAIM_CAPACITY = {"index": 4}


def topics(names: list[str]):
    for name in names:
        summarize(name, sources=find_sources(name))
    review("all", topics=names)


def pipeline(**options: Any) -> Pipeline:
    return Pipeline(services={"index": index_server}, claim_capacity=CLAIM_CAPACITY, **options)
