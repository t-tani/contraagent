"""HTTP layer of the monitor: FastAPI + Server-Sent Events over a `Monitor`.

Endpoints (all GET; response models in `api.py`):

  /api/info                          Info: title, the panel names the UI should offer, the contract version
  /api/runs                          list[RunSummary]
  /api/hosts                         Hosts: the hosts that drive the runs, and accounts' utilization over every run
  /api/runs/<run>/journal?since=N    JournalPage: journal rows after line offset N
  /api/runs/<run>/plan               Plan: the queued tasks: nodes, dependencies, states, groups
  /api/runs/<run>/definitions        list[TaskDefinition]: what defined each kind of task
  /api/runs/<run>/outputs            Outputs: the contracts tasks must satisfy: file, model, status, content
  /api/runs/<run>/cursor             CursorView: stage, completed stages, each unit's step
  /api/runs/<run>/procs              Procs: live process tree
  /api/runs/<run>/task/<key>         TaskDetail: one task: its journal rows, live launches, stream name
  /api/runs/<run>/stream/<key>       StreamPage: one page of a transcript at an offset ("load earlier")
  /api/runs/<run>/panels/<name>      one registered panel (any JSON object)
  /api/openapi.json                  this contract as OpenAPI (also `contraagent/monitor/openapi.json`)
  /events?run=<run>                  SSE, RunEvent: journal / procs / plan / outputs / cursor / panel:<name>,
                                     and `ready` once the first round (the journal replay) is out
  /events/stream?run=&key=<key>      SSE, StreamMessage: one transcript, tailed live; `id:` is the line
                                     offset after each message, `Last-Event-ID` or `from=N` resumes there

A run id or task key that is not a plain name answers 404: they become file
paths (`paths.py`).

Local and read-only, but what it serves is agent transcripts: no CORS
headers unless origins are opted in, and only requests whose `Host` names
this machine (a DNS-rebinding page names its own domain) are answered.

Async (uvicorn), not threaded: one OS thread per connected tab piles up
threads and TIME_WAIT sockets in a reconnect storm (a laptop sleep/wake)
until the browser can no longer connect; an event loop serves many idle,
mostly-sleeping SSE connections without that per-connection cost.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import signal
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import TypeAdapter

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import FileResponse, JSONResponse
    from sse_starlette.sse import EventSourceResponse
except ModuleNotFoundError:
    # The `monitor` extra is optional; `require_extra` says so in words
    # instead of letting a bare ModuleNotFoundError reach the user. A type
    # checker takes the extra as installed, so these names are always bound.
    if TYPE_CHECKING:
        raise

from contraagent.monitor import api
from contraagent.monitor.core import Monitor
from contraagent.monitor.paths import BadName

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
OPENAPI_FILE = Path(__file__).parent / "openapi.json"
OPENAPI_TITLE = "contraagent monitor"
#: Seconds between two looks at a run for the run feed (`run_feed`).
TICK_S = 1.0
#: Seconds a transcript feed waits for its log to grow before it looks again.
STREAM_WAIT_S = 15.0
#: Host names a local browser uses for this machine. Anything else in `Host` is refused.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")

MISSING_EXTRA = (
    "the monitor needs the `monitor` extra, which is not installed: pip install 'contraagent[monitor]' (or: uv sync --extra monitor)"
)
_EXTRA_MODULES = ("fastapi", "uvicorn", "sse_starlette")


def require_extra() -> None:
    """Raise `ModuleNotFoundError(MISSING_EXTRA)` when a module of the `monitor` extra is missing."""
    missing = [m for m in _EXTRA_MODULES if importlib.util.find_spec(m) is None]
    if missing:
        raise ModuleNotFoundError(f"{MISSING_EXTRA}; missing: {', '.join(missing)}")


_JOURNAL = TypeAdapter(api.JournalRow)
_PROCS = TypeAdapter(api.Procs)
_PLAN = TypeAdapter(api.Plan)
_OUTPUTS = TypeAdapter(api.Outputs)
# `Optional`, not `X | None`: outside an annotation that is a `UnionType`
# value, which type checkers do not accept as a TypeAdapter's type.
_CURSOR = TypeAdapter(Optional[api.CursorView])  # noqa: UP045
_PANEL = TypeAdapter(api.JsonObject)
_STREAM = TypeAdapter(api.StreamPage)
_READY = TypeAdapter(api.FeedReady)


def _json(adapter: TypeAdapter, value: Any) -> str:
    """`value` checked against its contract model and serialized as the wire carries it.
    `exclude_unset`: a key the core did not emit is not invented (see `api`)."""
    return adapter.dump_json(adapter.validate_python(value), exclude_unset=True, by_alias=True).decode()


def _procs_sig(procs: dict) -> str:
    """Change signature: key, pid and command per launch and Python task. `age_s`
    always ticks up, so it is deliberately excluded or every poll would look "changed"."""
    return json.dumps(
        [
            procs.get("alive"),
            [(c.get("key"), c.get("pid"), c.get("cmd")) for c in procs.get("launches", [])],
            [(pt.get("key"), pt.get("pid")) for pt in procs.get("python_tasks", [])],
        ]
    )


def _host_names(host: str) -> list[str]:
    """How a `Host` header names the address the server is bound to; nothing for a wildcard bind."""
    if not host or host in ("0.0.0.0", "::", "*"):
        return []
    return [f"[{host}]" if ":" in host and not host.startswith("[") else host]


async def run_feed(monitor: Monitor, run: str, is_disconnected: Callable[[], Awaitable[bool]]) -> AsyncIterator[dict[str, str]]:
    """One client's live feed. Each view is recomputed every tick but only sent
    when its value changed. The first tick sends everything (the whole journal
    included) and ends with `ready`."""
    jpos, replayed = 0, False
    sigs: dict[str, str] = {}
    while True:
        if await is_disconnected():
            return
        entries, total = monitor.journal(run, jpos)
        if entries:
            jpos = total
            for e in entries:
                yield {"event": "journal", "data": _json(_JOURNAL, e)}
        procs = monitor.procs(run)
        sig = _procs_sig(procs)
        if sig != sigs.get("procs"):
            sigs["procs"] = sig
            yield {"event": "procs", "data": _json(_PROCS, procs)}
        for name in monitor.panels:
            try:
                body = json.dumps(monitor.panel(name, run), default=str)
            except Exception as exc:  # one bad panel must not stop the feed
                body = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
            if body != sigs.get(name):
                sigs[name] = body
                yield {"event": f"panel:{name}", "data": body}
        plan = _json(_PLAN, monitor.plan(run, procs))
        if plan != sigs.get("plan"):
            sigs["plan"] = plan
            yield {"event": "plan", "data": plan}
        outs = _json(_OUTPUTS, monitor.outputs(run))
        if outs != sigs.get("outputs"):
            sigs["outputs"] = outs
            yield {"event": "outputs", "data": outs}
        cur = _json(_CURSOR, monitor.cursor(run))
        if cur != sigs.get("cursor"):
            sigs["cursor"] = cur
            yield {"event": "cursor", "data": cur}
        if not replayed:
            replayed = True
            yield {"event": "ready", "data": _json(_READY, {"journal": jpos})}
        await asyncio.sleep(TICK_S)


def _resume_line(value: str | None) -> int | None:
    """The line a `Last-Event-ID` header or a `from` parameter names; None when it names none."""
    try:
        line = int(value) if value is not None else -1
    except ValueError:
        return None
    return line if line >= 0 else None


async def stream_feed(
    monitor: Monitor, run: str, key: str, start: int | None, is_disconnected: Callable[[], Awaitable[bool]]
) -> AsyncIterator[dict[str, str]]:
    """One client's feed of task `key`'s transcript.

    With no `start`, the first message is the tail page; with one, the feed resumes at
    that line. Each message carries the events of the lines after the previous one, and
    its `id` is the line offset after it, so the pages hand over by offset: nothing is
    read twice and no line is skipped. A log shorter than the offset (another run under
    the same name) starts over with its tail page.

    The feed keeps only its line offset: when it has read up to the end it waits on the
    source (`Monitor.wait_stream`) and then reads the new lines from it, so a slow
    client only lags and holds no lines in memory. After each read it pauses as long as
    the read took, so a source whose reads are slow (a long file read from its start)
    is never read more than half the time. Each feed normalizes its own pages; when
    many clients watch one log, a cache of encoded pages shared by them is the next step.
    """
    since = start
    while True:
        if await is_disconnected():
            return
        marker = await asyncio.to_thread(monitor.stream_size, run, key)
        began = time.monotonic()
        page, end = await asyncio.to_thread(monitor.stream_from, run, key, since)
        took = time.monotonic() - began
        if since is not None and page["total"] < since:
            since = None
            continue
        tail, read, since = since is None, since is None or end > since, end
        if tail or page["events"]:
            yield {"event": "stream", "id": str(end), "data": _json(_STREAM, page)}
        await asyncio.sleep(took)
        if end >= page["total"] or not read:
            await monitor.wait_stream(run, key, marker, STREAM_WAIT_S)


def create_app(monitor: Monitor, *, allowed_hosts: Iterable[str] = (), cors_origins: Iterable[str] = (), docs: bool = False) -> FastAPI:
    """The monitor as an ASGI app.

    `allowed_hosts` adds `Host` names to the local ones (the bound address, a
    LAN name); `cors_origins` lets a front end served from another origin (a
    dev server) read the API; `docs` serves the interactive API docs at
    `/api/docs`.
    """
    require_extra()
    app = FastAPI(
        title=OPENAPI_TITLE,
        version=api.API_VERSION,
        description="Read-only views over a contraagent runs directory. Models: contraagent.monitor.api.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[*LOCAL_HOSTS, *allowed_hosts])
    origins = list(cors_origins)
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"])
    static = monitor.static_dir or STATIC

    @app.exception_handler(BadName)
    async def bad_name(request: Request, exc: BadName) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    def route(path: str, model: Any):
        """A JSON route checked against its contract model; `exclude_unset`: see `api`."""
        return app.get(path, response_model=model, response_model_exclude_unset=True)

    @route("/api/info", api.Info)
    def api_info() -> dict:
        """The title, the panel tabs to offer, and the version of this contract."""
        return {"title": monitor.title, "panels": monitor.panel_info(), "api_version": api.API_VERSION, "hosts": monitor.many_hosts}

    @route("/api/runs", list[api.RunSummary])
    def api_runs() -> list[dict]:
        """Every run directory, newest activity first."""
        return monitor.runs()

    @route("/api/hosts", api.Hosts)
    def api_hosts() -> dict:
        """The hosts that drive the runs, and each account's utilization over every run."""
        return monitor.hosts()

    @route("/api/runs/{run}/journal", api.JournalPage)
    def api_journal(run: str, since: int = 0) -> dict:
        """Journal rows after line offset `since`; `total` is the next offset."""
        entries, total = monitor.journal(run, since)
        return {"entries": entries, "total": total}

    @route("/api/runs/{run}/plan", api.Plan)
    def api_plan(run: str) -> dict:
        """Every queued task with its dependencies and state, and the groups the UI draws as columns."""
        return monitor.plan(run)

    @route("/api/runs/{run}/outputs", api.Outputs)
    def api_outputs(run: str) -> dict:
        """Every declared output/input contract: its file, the model it must satisfy, its status."""
        return monitor.outputs(run)

    @route("/api/runs/{run}/definitions", list[api.TaskDefinition])
    def api_definitions(run: str) -> list[dict]:
        """What defined each kind of task in this run."""
        return monitor.definitions(run)

    @route("/api/runs/{run}/cursor", api.CursorView)
    def api_cursor(run: str) -> dict:
        """The resume cursor; `{}` when the run keeps none."""
        return monitor.cursor(run) or {}

    @route("/api/runs/{run}/procs", api.Procs)
    def api_procs(run: str) -> dict:
        """The run's live agent launches, process tree and Python tasks."""
        return monitor.procs(run)

    @route("/api/runs/{run}/task/{key}", api.TaskDetail)
    def api_task(run: str, key: str) -> dict:
        """One task, by its key: journal rows, live launches, definition, input/output, transcript name."""
        return monitor.task_detail(run, key)

    @route("/api/runs/{run}/stream/{key}", api.StreamPage)
    def api_stream(run: str, key: str, since: int = 0) -> dict:
        """A page of task `key`'s normalized transcript from line `since`; `since=0` is the tail page."""
        page, total = monitor.stream(run, key, since)
        return {**page, "total": total}

    @app.get("/api/runs/{run}/panels/{name}", response_model=api.JsonObject, responses={404: {"description": "no panel of that name"}})
    def api_panel(run: str, name: str) -> dict:
        """One registered panel's body: a JSON object whose shape the domain chooses."""
        monitor.check_run(run)
        try:
            return monitor.panel(name, run)
        except KeyError:
            raise HTTPException(404, f"no panel {name!r}") from None

    @app.get(
        "/events",
        response_class=EventSourceResponse,
        responses={
            200: {
                "description": "Server-Sent Events; each message is one `RunEvent`",
                "content": {"text/event-stream": {"schema": {"$ref": "#/components/schemas/RunEvent"}}},
            },
            404: {"description": "not a plain run id"},
        },
    )
    async def events(run: str, request: Request) -> EventSourceResponse:
        """The run, live: journal rows as they land, then each other view when it changes."""
        monitor.check_run(run)
        return EventSourceResponse(run_feed(monitor, run, request.is_disconnected), ping=15)

    @app.get(
        "/events/stream",
        response_class=EventSourceResponse,
        responses={
            200: {
                "description": "Server-Sent Events; each message is one `StreamMessage`",
                "content": {"text/event-stream": {"schema": {"$ref": "#/components/schemas/StreamMessage"}}},
            },
            404: {"description": "not a plain run id or task key"},
        },
    )
    async def events_stream(run: str, key: str, request: Request) -> EventSourceResponse:
        """Task `key`'s transcript, live: the tail page, then the events after it as they are written."""
        # `Last-Event-ID` and `from` (see `stream_feed`) are read here rather than declared,
        # so the committed contract and the UI's generated types stay as they are.
        monitor.check_run(run)
        monitor.stream_size(run, key)
        start = _resume_line(request.headers.get("last-event-id"))
        start = start if start is not None else _resume_line(request.query_params.get("from"))
        return EventSourceResponse(stream_feed(monitor, run, key, start, request.is_disconnected), ping=15)

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static / "index.html")

    @app.get("/{name}.{ext}", include_in_schema=False)
    def asset(name: str, ext: str) -> FileResponse:
        if ext not in ("js", "css") or "/" in name or name.startswith("."):
            raise HTTPException(404)
        path = static / f"{name}.{ext}"
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    def openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = _openapi(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


def _openapi(app: FastAPI) -> dict:
    """FastAPI's document plus the SSE message models, which no JSON route
    references: each feed's `text/event-stream` response points at them."""
    doc = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schemas = doc.setdefault("components", {}).setdefault("schemas", {})
    ref = "#/components/schemas/{model}"
    for name, adapter, title in (
        ("RunEvent", TypeAdapter(api.RunEvent), "One message of /events?run="),
        ("StreamMessage", TypeAdapter(api.StreamMessage), None),
    ):
        schema = adapter.json_schema(mode="serialization", ref_template=ref)
        for sub, body in schema.pop("$defs", {}).items():
            schemas.setdefault(sub, body)
        if title:
            schema.update(title=name, description=title)
        schemas[name] = schema
    doc["components"]["schemas"] = dict(sorted(schemas.items()))
    return doc


def openapi_document() -> str:
    """The contract as committed in `openapi.json`: independent of any run or domain."""
    return json.dumps(create_app(Monitor()).openapi(), indent=2, ensure_ascii=False) + "\n"


def serve(
    monitor: Monitor,
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    allowed_hosts: Iterable[str] = (),
    cors_origins: Iterable[str] = (),
    docs: bool = False,
) -> None:
    import uvicorn

    names = _host_names(host)
    if not names and not list(allowed_hosts):
        log.warning("bound to %s: only requests addressed to %s are answered; name others with --allow-host", host, ", ".join(LOCAL_HOSTS))
    log.info("%s on http://%s:%s  runs=%s", monitor.title, host, port, monitor.runs_dir)
    app = create_app(monitor, allowed_hosts=[*names, *allowed_hosts], cors_origins=cors_origins, docs=docs)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main(argv: list[str] | None = None) -> int:
    import argparse

    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["export"]:  # needs no server, so not the `monitor` extra
        from contraagent.monitor.export import main as export_main

        return export_main(argv[1:])
    ap = argparse.ArgumentParser(prog="contraagent monitor", description="Live monitor for contraagent pipeline runs")
    ap.add_argument("--runs-dir", default="runs", help="directory holding runs/<run-id>/ (default: ./runs)")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--title", default="contraagent")
    ap.add_argument(
        "--stream-format",
        action="append",
        default=[],
        metavar="AGENT=FORMAT",
        help="render a custom coding agent's transcript as a built-in format (claude or omp), e.g. --stream-format myagent=claude",
    )
    ap.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NAME",
        help="also answer requests addressed to this host name (default: localhost, 127.0.0.1, [::1] and the --host address)",
    )
    ap.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="let a page from this origin read the API, e.g. http://localhost:5173 for a UI dev server",
    )
    ap.add_argument("--docs", action="store_true", help="serve interactive API docs at /api/docs")
    ap.add_argument(
        "--openapi",
        nargs="?",
        const="-",
        metavar="PATH",
        help="write the OpenAPI document to PATH (default: stdout) and exit",
    )
    args = ap.parse_args(argv)
    try:
        require_extra()
    except ModuleNotFoundError as exc:
        sys.stderr.write(f"contraagent monitor: {exc}\n")
        return 2
    if args.openapi:
        doc = openapi_document()
        if args.openapi == "-":
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # piped into `head`: end quietly
            sys.stdout.write(doc)
        else:
            Path(args.openapi).write_text(doc)
        return 0
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    formats = dict(item.split("=", 1) for item in args.stream_format if "=" in item)
    serve(
        Monitor(args.runs_dir, title=args.title, stream_formats=formats),
        args.host,
        args.port,
        allowed_hosts=args.allow_host,
        cors_origins=args.cors_origin,
        docs=args.docs,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
