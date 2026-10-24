"""HTTP layer of the monitor: FastAPI + Server-Sent Events over a `Monitor`.

Endpoints (all GET; response models in `api.py`):

  /api/info                          Info: title, the panel names the UI should offer, the contract version
  /api/runs                          list[RunSummary]
  /api/hosts                         Hosts: the hosts that drive the runs, and accounts' utilization over every run
  /api/trends?from=&to=&tz=&run_group=  Trends: what the runs of a period add up to, day by day
  /api/trends/panels/<name>?from=...    one trend panel a domain registered (`Panel(scope="trends")`), a `PanelBody`
  /api/runs/<run>/journal?since=N    JournalPage: journal rows after line offset N
  /api/runs/<run>/plan               Plan: the queued tasks: nodes, dependencies, states, groups
  /api/runs/<run>/definitions        list[TaskDefinition]: what defined each kind of task
  /api/runs/<run>/outputs            Outputs: the contracts tasks must satisfy: file, model, status, content
  /api/runs/<run>/forecast           Forecast: the tasks the run is expected to create and has not yet, from an earlier run
  /api/runs/<run>/cursor             CursorView: stage, completed stages, each unit's step
  /api/runs/<run>/procs              Procs: live process tree
  /api/runs/<run>/task/<key>         TaskDetail: one task: its journal rows, live launches, stream name
  /api/runs/<run>/stream/<key>       StreamPage: one page of a transcript at an offset ("load earlier")
  /api/runs/<run>/panels/<name>      one registered panel, a `PanelBody`

Panels, a domain's own code, run on threads of their own (`PANEL_WORKERS`), so a slow
one never holds the other endpoints back; the views a run feed sends are read off the
event loop.
  /api/openapi.json                  this contract as OpenAPI (also `openapi.json` here)
  /events?run=<run>                  SSE, RunEvent: journal / procs / plan / outputs / forecast / cursor / panel:<name>,
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

import argparse
import asyncio
import functools
import html
import importlib.util
import ipaddress
import json
import logging
import re
import socket
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from sse_starlette.sse import EventSourceResponse
except ModuleNotFoundError:
    # The `monitor` extra is optional; `require_extra` says so in words
    # instead of letting a bare ModuleNotFoundError reach the user. A type
    # checker takes the extra as installed, so these names are always bound.
    if TYPE_CHECKING:
        raise

from contraagent._internal.backends.streams import agent_formats
from contraagent._internal.commandline import (
    MissingExtra,
    add_command,
    add_extensions,
    add_http,
    add_openapi,
    add_runs_dir,
    address,
    bind,
    bind_option,
    load_extensions,
    serve_on,
    setup_logging,
    write_openapi,
)
from contraagent._internal.commandline import (
    base_path as _base_path,
)
from contraagent._internal.monitor import api, export
from contraagent._internal.monitor.core import Monitor
from contraagent._internal.monitor.export import STATIC
from contraagent._internal.monitor.trends import Period, PeriodError
from contraagent._internal.monitor.views import VIEWS, View, serialize, serialize_kept
from contraagent._internal.runs.names import BadName, is_plain

log = logging.getLogger(__name__)

OPENAPI_FILE = Path(__file__).parent / "openapi.json"
OPENAPI_TITLE = "contraagent monitor"
#: Seconds between two looks at a run for the run feed (`run_feed`).
TICK_S = 1.0
#: Seconds a transcript feed waits for its log to grow before it looks again.
STREAM_WAIT_S = 15.0
#: Host names a local browser uses for this machine. Anything else in `Host` is refused,
#: but the names `host_names` adds.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")

MISSING_EXTRA = (
    "the monitor needs the `monitor` extra, which is not installed: pip install 'contraagent[monitor]' (or: uv sync --extra monitor)"
)
_EXTRA_MODULES = ("fastapi", "uvicorn", "sse_starlette")

#: The media type of each kind of file the page loads.
_MEDIA_TYPES = {"js": "text/javascript", "css": "text/css", "svg": "image/svg+xml", "png": "image/png"}


#: A URL of the page's own (`./app.js`, `./favicon.svg`): relative to the page, as the build writes them.
_PAGE_URL = re.compile(r'(\s(?:href|src)=")\./')


def page(html_text: str, base: str) -> str:
    """The page `index.html` for a monitor served under the base path `base` (`base_path`):
    `<ca-monitor base-url="<base>">`, and each URL of its own (scripts, styles, icons)
    under `base`; for no base, the page as it is."""
    if not base:
        return html_text
    attr = html.escape(base, quote=True)
    html_text = _PAGE_URL.sub(lambda m: f"{m.group(1)}{attr}/", html_text)
    return html_text.replace("<ca-monitor></ca-monitor>", f'<ca-monitor base-url="{attr}"></ca-monitor>', 1)


def require_extra() -> None:
    """Raise `MissingExtra` (a `ModuleNotFoundError` that says `MISSING_EXTRA`) when a module
    of the `monitor` extra is missing."""
    missing = [m for m in _EXTRA_MODULES if importlib.util.find_spec(m) is None]
    if missing:
        raise MissingExtra(f"{MISSING_EXTRA}; missing: {', '.join(missing)}")


def host_names(bind: str, names: Iterable[str] = ()) -> list[str]:
    """The `Host` names a server bound to `bind` answers beside `LOCAL_HOSTS` (DNS
    rebinding): the bound address (none for a wildcard bind) and `names`. Logs a warning
    when that leaves only the local names."""
    wildcard = not bind or bind in ("0.0.0.0", "::", "*")
    bound = [] if wildcard else [f"[{bind}]" if ":" in bind and not bind.startswith("[") else bind]
    out = [*bound, *names]
    if not out:
        local = ", ".join(LOCAL_HOSTS)
        log.warning("bound to %s: only monitor requests addressed to %s are answered; name others with --allow-host", bind, local)
    return out


def is_loopback(bind: str) -> bool:
    """Whether the address a server is bound to is reached only from this machine."""
    if bind == "localhost":
        return True
    try:
        return ipaddress.ip_address(bind.strip("[]")).is_loopback
    except ValueError:
        return False


#: Threads that compute panels, a domain's own code that may take a minute: apart from the
#: threads that answer every other endpoint, so a slow panel (or a page asking for many) never
#: holds the run list or a run's views back. Its threads start on first use.
PANEL_WORKERS = 2
_PANEL_POOL = ThreadPoolExecutor(max_workers=PANEL_WORKERS, thread_name_prefix="contraagent-panel")


async def in_panel_pool(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """`fn(*args, **kwargs)` on a panel thread (`PANEL_WORKERS`), awaited."""
    return await asyncio.get_running_loop().run_in_executor(_PANEL_POOL, functools.partial(fn, *args, **kwargs))


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


async def run_feed(monitor: Monitor, run: str, is_disconnected: Callable[[], Awaitable[bool]]) -> AsyncIterator[dict[str, str]]:
    """One client's live feed. Each view is recomputed every tick but only sent
    when its value changed. The first tick sends everything (the whole journal
    included) and ends with `ready`. The journal goes row by row and the cursor is
    `null` for a run that keeps none; the other views are as their endpoints answer them
    (`VIEWS`)."""
    jpos, replayed = 0, False
    sigs: dict[str, str] = {}
    # The views are read off the event loop, which serves every other client meanwhile.
    off = asyncio.to_thread
    while True:
        if await is_disconnected():
            return
        entries, total = await off(monitor.journal, run, jpos)
        if entries:
            jpos = total
            for e in entries:
                yield {"event": "journal", "data": serialize(api.JournalRow, e)}
        procs = await off(monitor.procs, run)
        sig = _procs_sig(procs)
        if sig != sigs.get("procs"):
            sigs["procs"] = sig
            yield {"event": "procs", "data": serialize(VIEWS["procs"].model, procs)}
        for name in monitor.run_panels():
            body = await _panel_body(monitor, name, run)
            if body != sigs.get(name):
                sigs[name] = body
                yield {"event": f"panel:{name}", "data": body}
        plan = serialize_kept(VIEWS["plan"].model, await off(monitor.plan, run, procs))  # over the processes just read
        if plan != sigs.get("plan"):
            sigs["plan"] = plan
            yield {"event": "plan", "data": plan}
        outs = serialize_kept(VIEWS["outputs"].model, await off(VIEWS["outputs"].read, monitor, run))
        if outs != sigs.get("outputs"):
            sigs["outputs"] = outs
            yield {"event": "outputs", "data": outs}
        forecast = serialize(VIEWS["forecast"].model, await off(monitor.forecast, run))
        if forecast != sigs.get("forecast"):
            sigs["forecast"] = forecast
            yield {"event": "forecast", "data": forecast}
        cursor = await off(monitor.cursor, run)
        cur = "null" if cursor is None else serialize(VIEWS["cursor"].model, cursor)
        if cur != sigs.get("cursor"):
            sigs["cursor"] = cur
            yield {"event": "cursor", "data": cur}
        if not replayed:
            replayed = True
            yield {"event": "ready", "data": serialize(api.FeedReady, {"journal": jpos})}
        await asyncio.sleep(TICK_S)


#: Each run panel's body as a feed last sent it: (monitor, panel, run) -> (when, the body),
#: and the lock of each, so that one client's feed calls a panel and the others of the same
#: tick are given its body.
_panel_bodies: dict[tuple[int, str, str], tuple[float, str]] = {}
_panel_locks: dict[tuple[int, str, str], asyncio.Lock] = {}


async def _panel_body(monitor: Monitor, name: str, run: str) -> str:
    """Run panel `name`'s body for `run` as the feed sends it (JSON), called at most once a
    tick (`TICK_S`) for every client that watches the run."""
    key = (id(monitor), name, run)
    lock = _panel_locks.setdefault(key, asyncio.Lock())
    async with lock:
        held = _panel_bodies.get(key)
        if held is not None and time.monotonic() - held[0] < TICK_S:
            return held[1]
        try:
            body = json.dumps(api.panel_data(await in_panel_pool(monitor.panel, name, run)), default=str)
        except Exception as exc:  # one bad panel must not stop the feed
            body = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        _panel_bodies[key] = (time.monotonic(), body)
        return body


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
            yield {"event": "stream", "id": str(end), "data": serialize(api.StreamPage, page)}
        await asyncio.sleep(took)
        if end >= page["total"] or not read:
            await monitor.wait_stream(run, key, marker, STREAM_WAIT_S)


def create_app(
    monitor: Monitor,
    *,
    allowed_hosts: Iterable[str] = (),
    cors_origins: Iterable[str] = (),
    docs: bool = False,
    base_path: str = "",
) -> FastAPI:
    """The monitor as an ASGI app.

    `allowed_hosts` adds `Host` names to `LOCAL_HOSTS` (the bound address, a LAN
    name: `host_names`); `cors_origins` lets a front end served from another origin (a
    dev server) read the API; `docs` serves the interactive API docs at
    `/api/docs`. `base_path` is the path a reverse proxy serves the monitor under
    (`/monitor`): the page names it in every URL it reads (`<ca-monitor base-url>`, its
    scripts and icons), and the API docs in theirs (the OpenAPI document's `servers`).
    The app answers at `/` only: the proxy takes the base path off before it passes a
    request on, and a request that still carries it (`/monitor/api/runs`) gets 404, so a
    proxy that does not take it off fails at its first request instead of half working.
    A value that is not such a path raises `ValueError`.
    """
    require_extra()
    base = _base_path(base_path)
    app = FastAPI(
        title=OPENAPI_TITLE,
        version=api.API_VERSION,
        description="Read-only views over a contraagent runs directory. Models: contraagent.monitor.api.",
        openapi_url="/api/openapi.json",
        docs_url=None,
        redoc_url=None,
        # Not `root_path`: Starlette would answer `/monitor/api/runs` beside `/api/runs`.
        servers=[{"url": base}] if base else None,
    )
    if docs:

        @app.get("/api/docs", include_in_schema=False)
        def api_docs() -> HTMLResponse:
            return get_swagger_ui_html(openapi_url=f"{base}/api/openapi.json", title=f"{OPENAPI_TITLE} - Swagger UI")

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[*LOCAL_HOSTS, *allowed_hosts])
    origins = list(cors_origins)
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"])
    static = monitor.static_dir or STATIC

    @app.exception_handler(BadName)
    async def bad_name(request: Request, exc: BadName) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    def endpoint(path: str, model: Any):
        """A JSON endpoint checked against its contract model; `exclude_unset`: see `api`."""
        return app.get(path, response_model=model, response_model_exclude_unset=True)

    def view_endpoint(view: View) -> None:
        """`/api/runs/{run}/<name>`: a view of a run, as `VIEWS` reads it."""

        def answer(run: str) -> Any:
            return view.read(monitor, run)

        path = f"/api/runs/{{run}}/{view.name}"
        app.get(path, name=f"api_{view.name}", description=view.doc, response_model=view.model, response_model_exclude_unset=True)(answer)

    @endpoint("/api/info", api.Info)
    def api_info() -> dict:
        """The title, the panel tabs to offer, and the version of this contract."""
        return {"title": monitor.title, "panels": monitor.panel_info(), "api_version": api.API_VERSION, "hosts": monitor.many_hosts}

    @endpoint("/api/runs", list[api.RunSummary])
    def api_runs() -> list[dict]:
        """Every run directory, newest activity first."""
        return monitor.runs()

    @endpoint("/api/hosts", api.Hosts)
    def api_hosts() -> dict:
        """The hosts that drive the runs, and each account's utilization over every run."""
        return monitor.hosts()

    def period_of(start: str, end: str, tz: str) -> Period:
        try:
            return Period.parse(start, end, tz)
        except PeriodError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get(
        "/api/trends",
        response_model=api.Trends,
        response_model_exclude_unset=True,
        responses={400: {"description": "a period it cannot read"}},
    )
    def api_trends(
        start: str = Query("", alias="from", description="the first day, YYYY-MM-DD (default: 13 days before `to`)"),
        end: str = Query("", alias="to", description="the last day, YYYY-MM-DD (default: today in `tz`)"),
        tz: str = Query("", description="the time zone the days are in, an IANA name (default UTC)"),
        run_group: str = Query("", description="only the runs of this run group"),
        stub: bool = Query(False, description="count stub runs too"),
    ) -> dict:
        """What the runs of a period add up to, day by day."""
        return monitor.trends(period_of(start, end, tz), run_group=run_group, stub=stub)

    @app.get(
        "/api/trends/panels/{name}",
        response_model=api.PanelBody,
        response_model_exclude_unset=True,
        responses={400: {"description": "a period it cannot read"}, 404: {"description": "no trend panel of that name"}},
    )
    async def api_trend_panel(
        name: str,
        start: str = Query("", alias="from"),
        end: str = Query("", alias="to"),
        tz: str = Query(""),
        run_group: str = Query(""),
    ) -> Any:
        """One trend panel's body: its `fn(runs, period)` over the runs of the period, made on a
        panel thread, and kept for the same period over the same runs (`Monitor.trends_panel`)."""
        period = period_of(start, end, tz)
        if name not in monitor.panels or monitor.panels[name].scope != "trends":
            raise HTTPException(404, f"no trend panel {name!r}")
        try:
            return await in_panel_pool(monitor.trends_panel, name, period, run_group=run_group)
        except KeyError:
            raise HTTPException(404, f"no trend panel {name!r}") from None

    journal = VIEWS["journal"]

    @app.get("/api/runs/{run}/journal", response_model=journal.model, response_model_exclude_unset=True, description=journal.doc)
    def api_journal(run: str, since: int = 0) -> dict:
        entries, total = monitor.journal(run, since)
        return {"entries": entries, "total": total}

    for view in VIEWS.values():
        if view is not journal:
            view_endpoint(view)

    @endpoint("/api/runs/{run}/task/{key}", api.TaskDetail)
    def api_task(run: str, key: str) -> dict:
        """One task, by its key: journal rows, live launches, definition, input/output, transcript name."""
        return monitor.task_detail(run, key)

    @endpoint("/api/runs/{run}/stream/{key}", api.StreamPage)
    def api_stream(run: str, key: str, since: int = 0) -> dict:
        """A page of task `key`'s normalized transcript from line `since`; `since=0` is the tail page."""
        page, total = monitor.stream(run, key, since)
        return {**page, "total": total}

    @app.get(
        "/api/runs/{run}/panels/{name}",
        response_model=api.PanelBody,
        response_model_exclude_unset=True,
        responses={404: {"description": "no run panel of that name"}},
    )
    async def api_panel(run: str, name: str) -> Any:
        """One run panel's body: a typed body (tiles, a table, charts), or any JSON object;
        made on a panel thread."""
        monitor.check_run(run)
        if name not in monitor.panels or monitor.panels[name].scope != "run":
            raise HTTPException(404, f"no panel {name!r}")
        try:
            return await in_panel_pool(monitor.panel, name, run)
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
    def index() -> Any:
        if not base:
            return FileResponse(static / "index.html")
        return HTMLResponse(page((static / "index.html").read_text(encoding="utf-8"), base))

    @app.get("/{name}.{ext}", include_in_schema=False)
    def asset(name: str, ext: str) -> FileResponse:
        if ext not in ("js", "css", "svg", "png") or not is_plain(name):  # the scripts, the styles, the page's icons
            raise HTTPException(404)
        path = static / f"{name}.{ext}"
        if not path.is_file():
            raise HTTPException(404)
        # Named here, not guessed: on Windows the guess comes from the registry, which may
        # call a script text/plain, and a browser then refuses to run the page's module.
        return FileResponse(path, media_type=_MEDIA_TYPES[ext])

    # The pipeline's own pages, each under apps/<name>/ (`Monitor(apps=)`), behind the same host check.
    for name, sub in monitor.apps.items():
        app.mount(f"/apps/{name}", sub, name=f"app_{name}")

    def openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = _openapi(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


def _openapi(app: FastAPI) -> dict:
    """FastAPI's document plus the SSE message models, which no JSON endpoint
    references: each feed's `text/event-stream` response points at them."""
    doc = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes, servers=app.servers or None)
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
    base_path: str = "",
) -> None:
    """Serve `monitor` on `host`:`port` until stopped (`create_app`). `allowed_hosts` adds
    `Host` names to the local ones and the bound address (`host_names`); `base_path` is the
    path a reverse proxy serves it under. A port it cannot listen on raises `OSError`
    (`EADDRINUSE` when another server holds it)."""
    base = _base_path(base_path)  # before the port is taken
    _serve(monitor, bind(host, port), host, allowed_hosts=allowed_hosts, cors_origins=cors_origins, docs=docs, base_path=base)


def _serve(
    monitor: Monitor,
    sock: socket.socket,
    host: str,
    *,
    allowed_hosts: Iterable[str],
    cors_origins: Iterable[str],
    docs: bool,
    base_path: str = "",
) -> None:
    """Serve `monitor` on the bound `sock`, announcing its address first."""
    app = create_app(monitor, allowed_hosts=host_names(host, allowed_hosts), cors_origins=cors_origins, docs=docs, base_path=base_path)
    under = f"  base path={base_path}" if base_path else ""
    log.info("%s on %s  runs=%s%s", monitor.title, address(sock), monitor.runs_dir, under)
    serve_on(app, sock)


# --- the command -----------------------------------------------------------------------


def add_arguments(ap: argparse.ArgumentParser) -> None:
    """`contraagent monitor`, with `contraagent monitor export` under it."""
    ap.description = "Live monitor for contraagent pipeline runs"
    add_runs_dir(ap)
    add_http(ap, port=8787)
    ap.add_argument("--title", default="contraagent")
    ap.add_argument(
        "--stream-format",
        action="append",
        default=[],
        metavar="AGENT=FORMAT",
        help=f"render a custom coding agent's transcript as a built-in format ({', '.join(agent_formats())}), "
        "e.g. --stream-format myagent=claude",
    )
    add_extensions(ap)
    ap.add_argument("--docs", action="store_true", help="serve interactive API docs at /api/docs")
    add_openapi(ap, "OpenAPI document")
    sub = ap.add_subparsers(dest="monitor_cmd", title="commands")
    add_command(sub, "export", help=export.HELP, add_arguments=export.add_arguments, run=export.run)


def run(args: argparse.Namespace) -> int:
    """`contraagent monitor`: serve the monitor (the `monitor` extra), or write its OpenAPI document."""
    require_extra()
    if args.openapi:
        write_openapi(openapi_document(), args.openapi)
        return 0
    setup_logging()
    formats = dict(item.split("=", 1) for item in args.stream_format if "=" in item)
    monitor = Monitor(args.runs_dir, title=args.title, stream_formats=formats, **load_extensions(args))
    sock = bind_option(args.host, args.port)
    _serve(monitor, sock, args.host, allowed_hosts=args.allow_host, cors_origins=args.cors_origin, docs=args.docs, base_path=args.base_path)
    return 0
