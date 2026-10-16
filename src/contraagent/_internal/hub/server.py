"""`contraagent hub`: receive, store, and serve the monitor.

One ASGI app (`create_hub_app`) over a `Hub`, with two parts that never share a token:

  POST /ingest/records         RecordBatch -> Accepted              (`protocol.py`)
  POST /ingest/heartbeat       Heartbeat   -> HeartbeatAck
  HEAD /ingest/blobs/<sha256>  200 or 404
  PUT  /ingest/blobs/<sha256>  raw bytes -> 204; 400 when they do not hash to <sha256>
  GET  /healthz                Health: 200 when every store answers, 503 naming those that do not
  GET  /login?token=<read>     sets the read cookie and redirects to /
  everything else              the monitor (`contraagent._internal.monitor.server.create_app`)
                               over `hub_monitor(hub)`: API, SSE feeds, the bundled UI

* **Ingest** answers 401 without `Authorization: Bearer <token>` naming one of the ingest
  tokens. A token given for one host (`host_id token` in the token file) answers 403 to a
  batch or heartbeat of another host. A records batch is capped at `MAX_RECORDS_BYTES`
  and a blob at `max_blob_bytes`, after `Content-Encoding: gzip` is undone; beyond the
  cap the answer is 413. The endpoints' contract, for a relay in any language, is
  `contraagent/_internal/hub/openapi.json` (`contraagent hub --openapi PATH`).
* **The monitor** answers 401 without the read token, as `Authorization: Bearer <token>`
  or as the cookie `/login` sets (HttpOnly, SameSite=Strict; an EventSource cannot send
  a header). With no read token the monitor is open to whoever reaches the port. It keeps
  the local monitor's `Host` check (DNS rebinding): only the loopback names, the bound
  address and `--allow-host` names are answered. Ingest is not under the `Host` check:
  a page in a browser has no ingest token.
* **`/healthz`** needs no token and is under no `Host` check, for a container healthcheck
  or a load balancer (`HealthCheck`). It is in the ingest contract, not the monitor's.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import hmac
import json
import logging
import os
import signal
import sys
import threading
import zlib
from collections.abc import Callable, Iterable, Mapping
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

try:
    from fastapi import Depends, FastAPI, HTTPException, Request, Response
    from fastapi.concurrency import run_in_threadpool
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from starlette.types import ASGIApp, Message, Receive, Scope, Send
except ModuleNotFoundError:
    # The extra is optional; `require_extra` says so in words (see monitor.server).
    if TYPE_CHECKING:
        raise

from contraagent._internal.commandline import (
    CommandError,
    UsageError,
    add_command,
    add_http,
    add_openapi,
    address,
    bind_option,
    serve_on,
    setup_logging,
    write_openapi,
)
from contraagent._internal.hub.core import BLOB_GRACE, Hub
from contraagent._internal.hub.protocol import (
    HEALTHZ,
    INGEST_BLOB,
    INGEST_HEARTBEAT,
    INGEST_RECORDS,
    Accepted,
    Health,
    Heartbeat,
    HeartbeatAck,
    RecordBatch,
)
from contraagent._internal.hub.retention import (
    FIRST_PRUNE_AFTER_S,
    PRUNE_EVERY_HOURS,
    SHORT_PRUNE_EVERY_HOURS,
    SHORT_RETENTION_DAYS,
    Pruner,
    default_prune_every,
    report_json,
    report_table,
)
from contraagent._internal.hub.source import DEFAULT_TTL_S
from contraagent._internal.hub.store import BlobStore, DirectoryBlobs, HubStore, MemoryBlobs, MemoryHubStore
from contraagent._internal.hub.streams import MemoryStreamLogs, StreamLogs
from contraagent._internal.monitor.core import Monitor
from contraagent._internal.monitor.server import LOCAL_HOSTS, create_app, host_names, is_loopback, require_extra

log = logging.getLogger(__name__)

OPENAPI_FILE = Path(__file__).parent / "openapi.json"
OPENAPI_TITLE = "contraagent hub ingest"
OPENAPI_VERSION = "1"
INGEST_PREFIX = "/ingest/"
LOGIN = "/login"
#: The cookie `/login` sets; its value is derived from the read token, not the token itself.
COOKIE = "contraagent_hub_read"
#: The largest records batch the hub takes, in bytes after gzip is undone.
MAX_RECORDS_BYTES = 16 * 1024 * 1024
#: The largest blob the hub takes by default (`--max-blob-mb`).
MAX_BLOB_BYTES = 256 * 1024 * 1024
DEFAULT_PORT = 8790
#: Seconds `/healthz` waits for a store's trivial read before it counts the store as failing.
HEALTH_TIMEOUT_S = 3.0

_UNAUTHORIZED = {"description": "no ingest token, or not one the hub was given"}
_TOO_LARGE = {"description": "the body is larger than the hub takes"}
_BINARY = {"type": "string", "format": "binary"}
_OTHER_HOST = {"description": "the token was given for another host"}


def _cookie_value(token: str) -> str:
    return hmac.new(token.encode(), b"contraagent hub read", hashlib.sha256).hexdigest()


def _bearer(headers: Iterable[tuple[bytes, bytes]]) -> str | None:
    for k, v in headers:
        if k == b"authorization":
            scheme, _, value = v.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and value.strip():
                return value.strip()
    return None


def _cookie(headers: Iterable[tuple[bytes, bytes]], name: str) -> str | None:
    for k, v in headers:
        if k == b"cookie":
            jar = SimpleCookie()
            try:
                jar.load(v.decode("latin-1"))
            except Exception:
                continue
            if name in jar:
                return jar[name].value
    return None


async def _plain(send: Send, status: int, text: str, headers: Iterable[tuple[bytes, bytes]] = ()) -> None:
    body = json.dumps({"detail": text}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *headers],
        }
    )
    await send({"type": "http.response.body", "body": body})


class ReadGuard:
    """The monitor behind the read token: `Authorization: Bearer` or the cookie `/login` sets.

    `read_token=None` lets every request through, `/login` included (it then only redirects)."""

    def __init__(self, app: ASGIApp, read_token: str | None) -> None:
        self.app = app
        self.read_token = read_token
        self.cookie = _cookie_value(read_token) if read_token else ""

    def _allowed(self, scope: Scope) -> bool:
        if self.read_token is None:
            return True
        headers = scope.get("headers", [])
        token = _bearer(headers)
        if token is not None and hmac.compare_digest(token.encode(), self.read_token.encode()):
            return True
        got = _cookie(headers, COOKIE)
        return got is not None and hmac.compare_digest(got.encode(), self.cookie.encode())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == LOGIN:
            await self._login(scope, send)
            return
        if not self._allowed(scope):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await _plain(send, 401, "no read token", [(b"www-authenticate", b"Bearer")])
            return
        await self.app(scope, receive, send)

    async def _login(self, scope: Scope, send: Send) -> None:
        headers: list[tuple[bytes, bytes]] = [(b"location", b"/"), (b"cache-control", b"no-store"), (b"content-length", b"0")]
        if self.read_token is not None:
            given = parse_qs(scope.get("query_string", b"").decode("latin-1")).get("token", [""])[0]
            if not hmac.compare_digest(given.encode(), self.read_token.encode()):
                await _plain(send, 401, "not the read token")
                return
            attrs = "; Path=/; HttpOnly; SameSite=Strict" + ("; Secure" if scope.get("scheme") == "https" else "")
            headers.append((b"set-cookie", f"{COOKIE}={self.cookie}{attrs}".encode()))
        await send({"type": "http.response.start", "status": 303, "headers": headers})
        await send({"type": "http.response.body", "body": b""})


class BodyLimit:
    """Reads an ingest request's body whole, undoing `Content-Encoding: gzip`, and answers
    413 once it passes the endpoint's cap; the app downstream reads the plain body."""

    def __init__(self, app: ASGIApp, *, max_records_bytes: int, max_blob_bytes: int) -> None:
        self.app = app
        self.max_records_bytes = max_records_bytes
        self.max_blob_bytes = max_blob_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT"):
            await self.app(scope, receive, send)
            return
        cap = self.max_blob_bytes if scope["path"].startswith("/ingest/blobs/") else self.max_records_bytes
        headers = dict(scope.get("headers", []))
        encoding = headers.get(b"content-encoding", b"identity").decode("latin-1").strip().lower()
        if encoding not in ("identity", "gzip"):
            await _plain(send, 415, f"Content-Encoding {encoding} is not taken; send gzip or none")
            return
        length = headers.get(b"content-length")
        if encoding == "identity" and length is not None and length.isdigit() and int(length) > cap:
            await _plain(send, 413, f"the body is larger than {cap} bytes")
            return
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
        chunks: list[bytes] = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            raw = message.get("body", b"")
            more = message.get("more_body", False)
            try:
                # max_length bounds what one compressed chunk may inflate to (a gzip bomb).
                data = inflate.decompress(raw, cap + 1 - size) if inflate else raw
            except zlib.error:
                await _plain(send, 400, "the body is not valid gzip")
                return
            size += len(data)
            if size > cap or (inflate is not None and inflate.unconsumed_tail):
                await _plain(send, 413, f"the body is larger than {cap} bytes")
                return
            chunks.append(data)
        if inflate is not None and not inflate.eof:
            await _plain(send, 400, "the body is not valid gzip")
            return
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        if inflate is not None:
            plain = [(k, v) for k, v in scope["headers"] if k not in (b"content-encoding", b"content-length")]
            scope = {**scope, "headers": [*plain, (b"content-length", str(len(body)).encode())]}
        await self.app(scope, replay, send)


# --- /healthz --------------------------------------------------------------------------

#: What the probes read: a blob, a run and an object no hub holds. Their absence is the answer.
_NO_SHA = "0" * 64
_NO_NAME = "healthz@healthz"
_NO_OBJECT = "healthz"


def _read_records(store: HubStore) -> None:
    store.entry(_NO_NAME)


def _read_blobs(blobs: BlobStore) -> None:
    # A read, not `has`: S3 answers a HEAD in a missing bucket with a plain 404.
    blobs.get(_NO_SHA)


def _read_transcripts(streams: StreamLogs) -> None:
    streams.logs(_NO_NAME, _NO_NAME)
    objects = getattr(streams, "objects", None)  # SegmentedStreamLogs: the sealed segments
    if objects is not None:
        try:
            objects.get_range(_NO_OBJECT, 0, 1)
        except FileNotFoundError:
            pass
    hot = getattr(streams, "hot_dir", None)  # and the open ones on this host's disk
    if hot is not None and not os.access(hot, os.W_OK | os.X_OK):
        raise PermissionError(f"{hot} is not writable")


class HealthCheck:
    """`GET /healthz`: one trivial read of each of the hub's stores, the record store
    (`records`), the blob store (`blobs`) and the transcripts (`transcripts`: the segment
    index, the sealed segments' object store and the open segments' directory).

    The reads run in a thread pool of their own, at most one per store at a time, and are
    waited for `timeout_s` (default `HEALTH_TIMEOUT_S`); a read still running from an earlier request is waited for
    again rather than started anew, so a store that hangs costs one thread, not one per
    request. The answer names each failing store with the kind of error it raised; the
    error itself goes to the log, once each time a store's state changes."""

    def __init__(self, hub: Hub, *, timeout_s: float | None = None) -> None:
        self.timeout_s = HEALTH_TIMEOUT_S if timeout_s is None else timeout_s
        self.probes: dict[str, Callable[[], None]] = {
            "records": lambda: _read_records(hub.store),
            "blobs": lambda: _read_blobs(hub.blobs),
            "transcripts": lambda: _read_transcripts(hub.streams),
        }
        self._pool = concurrent.futures.ThreadPoolExecutor(len(self.probes), thread_name_prefix="healthz")
        self._lock = threading.Lock()
        self._running: dict[str, concurrent.futures.Future[None]] = {}
        self._failed: dict[str, str] = {}

    def _start(self) -> dict[str, concurrent.futures.Future[None]]:
        with self._lock:
            for name, probe in self.probes.items():
                running = self._running.get(name)
                if running is None or running.done():
                    self._running[name] = self._pool.submit(probe)
            return dict(self._running)

    def check(self) -> Health:
        """Run the reads and wait for them (blocking; the endpoint calls it in a thread)."""
        futures = self._start()
        concurrent.futures.wait(futures.values(), timeout=self.timeout_s)
        failed: dict[str, str] = {}
        errors: dict[str, str] = {}
        for name, future in futures.items():
            if not future.done():
                failed[name], errors[name] = "TimeoutError", f"no answer within {self.timeout_s:g}s"
            elif (exc := future.exception()) is not None:
                failed[name], errors[name] = type(exc).__name__, f"{type(exc).__name__}: {exc}"
        with self._lock:
            before, self._failed = self._failed, failed
        for name in self.probes:
            if name in failed and before.get(name) != failed[name]:
                log.warning("healthz: the %s store fails: %s", name, errors[name])
            elif name in before and name not in failed:
                log.info("healthz: the %s store answers again", name)
        return Health(status="failing" if failed else "ok", failed=failed)


def _tokens(ingest_tokens: Mapping[str, str | None] | Iterable[str]) -> dict[str, str | None]:
    if isinstance(ingest_tokens, Mapping):
        return dict(ingest_tokens)
    return dict.fromkeys(ingest_tokens)


def create_ingest_app(
    hub: Hub,
    ingest_tokens: Mapping[str, str | None] | Iterable[str],
    *,
    max_records_bytes: int = MAX_RECORDS_BYTES,
    max_blob_bytes: int = MAX_BLOB_BYTES,
) -> FastAPI:
    """The ingest endpoints of `protocol.py` as a FastAPI app (the `/ingest/` part of `create_hub_app`).

    `ingest_tokens` maps each token to the host it was given for (`None`: any host), or
    lists tokens good for any host."""
    require_extra()
    tokens = _tokens(ingest_tokens)
    app = FastAPI(
        title=OPENAPI_TITLE,
        version=OPENAPI_VERSION,
        description=(
            "How a relay ships a host's runs to a contraagent hub. "
            "A POST or PUT body may be sent with `Content-Encoding: gzip`; the size caps apply after it is undone."
        ),
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    bearer = HTTPBearer(auto_error=False, description="an ingest token the hub was given")

    def host_of(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str | None:
        """The host the token was given for (`None`: any); 401 when it is no ingest token."""
        given = credentials.credentials.encode() if credentials else None
        if given is not None:
            for token, host in tokens.items():
                if hmac.compare_digest(given, token.encode()):
                    return host
        raise HTTPException(401, "no ingest token, or not one the hub was given", headers={"WWW-Authenticate": "Bearer"})

    def same_host(host: str | None, host_id: str) -> None:
        if host is not None and host != host_id:
            raise HTTPException(403, f"the token was given for host {host!r}, not {host_id!r}")

    errors: dict[int | str, dict[str, Any]] = {401: _UNAUTHORIZED, 413: _TOO_LARGE}
    health = HealthCheck(hub)

    @app.get(HEALTHZ, response_model=Health, responses={503: {"model": Health, "description": "a store did not answer"}})
    async def healthz() -> JSONResponse:
        """Whether the record store, the blob store and the transcripts each answer a trivial
        read; no token. 200 when all do, 503 naming the ones that do not."""
        got = await run_in_threadpool(health.check)
        return JSONResponse(got.model_dump(), status_code=200 if got.status == "ok" else 503)

    @app.post(INGEST_RECORDS, response_model=Accepted, responses={**errors, 403: _OTHER_HOST})
    def records(batch: RecordBatch, host: str | None = Depends(host_of)) -> Accepted:
        """Store a batch of one run's records; how many lines of each log it named the hub holds."""
        same_host(host, batch.run.host_id)
        return hub.records(batch)

    @app.post(INGEST_HEARTBEAT, response_model=HeartbeatAck, responses={**errors, 403: _OTHER_HOST})
    def heartbeat(beat: Heartbeat, host: str | None = Depends(host_of)) -> HeartbeatAck:
        """Keep a host's latest heartbeat; how long the hub counts the host as up without another."""
        same_host(host, beat.host_id)
        return hub.heartbeat(beat)

    @app.head(
        INGEST_BLOB,
        status_code=200,
        response_class=Response,
        responses={200: {"description": "the hub holds that content"}, 404: {"description": "it does not"}, 401: _UNAUTHORIZED},
    )
    def has_blob(sha256: str, host: str | None = Depends(host_of)) -> Response:
        """Whether the hub holds the content named by `sha256`."""
        try:
            held = hub.has_blob(sha256)
        except ValueError:
            held = False
        return Response(status_code=200 if held else 404)

    @app.put(
        INGEST_BLOB,
        status_code=204,
        response_class=Response,
        responses={204: {"description": "stored"}, 400: {"description": "the body does not hash to `sha256`"}, **errors},
        openapi_extra={"requestBody": {"required": True, "content": {"application/octet-stream": {"schema": _BINARY}}}},
    )
    async def put_blob(sha256: str, request: Request, host: str | None = Depends(host_of)) -> Response:
        """Store the raw body as the content named by `sha256`, its SHA-256 in hex."""
        data = await request.body()
        try:
            await run_in_threadpool(hub.put_blob, sha256, data)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return Response(status_code=204)

    return app


class _Dispatch:
    """`/ingest/...` and `/healthz` to the ingest app, everything else to the guarded monitor."""

    def __init__(self, ingest: ASGIApp, monitor: ASGIApp) -> None:
        self.ingest = ingest
        self.monitor = monitor

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and (scope["path"].startswith(INGEST_PREFIX) or scope["path"] == HEALTHZ):
            await self.ingest(scope, receive, send)
        else:
            await self.monitor(scope, receive, send)


def hub_monitor(hub: Hub, **kwargs: Any) -> Monitor:
    """The monitor's views of every host's runs the hub holds: over `Hub.source()` and
    `Hub.liveness()` (`Monitor`'s keyword arguments pass through)."""
    return Monitor(source=hub.source(), liveness=hub.liveness(), many_hosts=True, **kwargs)


def create_hub_app(
    hub: Hub,
    *,
    ingest_tokens: Mapping[str, str | None] | Iterable[str],
    read_token: str | None,
    allowed_hosts: Iterable[str] = (),
    cors_origins: Iterable[str] = (),
    title: str = "contraagent hub",
    max_records_bytes: int = MAX_RECORDS_BYTES,
    max_blob_bytes: int = MAX_BLOB_BYTES,
) -> ASGIApp:
    """The hub as one ASGI app: the ingest endpoints and the monitor (`hub_monitor`).

    `ingest_tokens`: see `create_ingest_app`. `read_token=None` leaves the monitor open.
    `allowed_hosts` and `cors_origins` are the monitor's (`monitor.server.create_app`)."""
    allowed = [*LOCAL_HOSTS, *allowed_hosts]
    ingest = BodyLimit(
        create_ingest_app(hub, ingest_tokens, max_records_bytes=max_records_bytes, max_blob_bytes=max_blob_bytes),
        max_records_bytes=max_records_bytes,
        max_blob_bytes=max_blob_bytes,
    )
    monitor = create_app(hub_monitor(hub, title=title), allowed_hosts=allowed, cors_origins=cors_origins)
    # The Host check comes before the read guard, so /login is under it too.
    guarded = TrustedHostMiddleware(ReadGuard(monitor, read_token), allowed_hosts=allowed)
    return _Dispatch(ingest, guarded)


def openapi_document() -> str:
    """The ingest contract as committed in `openapi.json`."""
    app = create_ingest_app(Hub(MemoryHubStore(), MemoryBlobs()), ())
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


# --- the command -----------------------------------------------------------------------


def read_ingest_tokens(path: str | Path) -> dict[str, str | None]:
    """An ingest token file: one token per line, or `host_id token` for a token good for
    that host only; blank lines and lines starting with `#` are skipped."""
    out: dict[str, str | None] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) == 1:
            out[fields[0]] = None
        elif len(fields) == 2:
            out[fields[1]] = fields[0]
        else:
            raise ValueError(f"{path}: a line holds a token or `host_id token`, not {len(fields)} fields")
    if not out:
        raise ValueError(f"{path}: no token")
    return out


def read_read_token(path: str | Path) -> str:
    """The read token: the first line of the file that is not blank or a `#` comment."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if token and not token.startswith("#"):
            return token
    raise ValueError(f"{path}: no token")


def open_store(spec: str) -> HubStore:
    """`memory`, or a `postgres://` / `postgresql://` DSN."""
    if spec == "memory":
        return MemoryHubStore()
    if spec.startswith(("postgres://", "postgresql://")):
        try:
            from contraagent._internal.hub.postgres import PostgresHubStore  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ValueError(f"--store {spec.split('://')[0]}://: the Postgres store is not available ({exc})") from None
        return PostgresHubStore(spec)
    raise ValueError(f"--store: {spec!r} is neither `memory` nor a postgres:// DSN")


def open_streams(
    streams_dir: str | None, segments: str | None, store: str, *, sweep: bool = True, background: bool = True, **seal: float
) -> StreamLogs:
    """Where transcripts are kept: segmented (open segments in `streams_dir`, sealed ones at
    `segments`, indexed in the `store`'s Postgres database when it is one), or in memory
    when no `streams_dir` is given. `sweep` deletes orphan segment objects on opening;
    `background` and `seal` (`segment_bytes`, `idle_s`, `age_s`, `tick_s`) pass through to
    `SegmentedStreamLogs`."""
    if streams_dir is None:
        if segments is not None:
            raise ValueError("--segments needs --streams-dir")
        log.warning("no --streams-dir: transcripts are kept in memory and lost when the hub stops")
        return MemoryStreamLogs()
    try:
        from contraagent._internal.hub.segments import from_spec
    except ImportError as exc:
        raise ValueError(f"--streams-dir: segmented transcripts are not available ({exc})") from None
    index = store if store.startswith(("postgres://", "postgresql://")) else None
    return from_spec(streams_dir, segments or str(Path(streams_dir) / "segments"), index, sweep=sweep, background=background, **seal)


def open_blobs(spec: str) -> BlobStore:
    """`memory`, `dir:/path`, or `s3://bucket/prefix?endpoint=...`."""
    if spec == "memory":
        return MemoryBlobs()
    if spec.startswith("dir:"):
        return DirectoryBlobs(spec.removeprefix("dir:"))
    if spec.startswith("s3://"):
        try:
            from contraagent._internal.hub.s3 import S3Blobs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ValueError(f"--blobs s3://: the S3 blob store is not available ({exc})") from None
        return S3Blobs(spec)
    raise ValueError(f"--blobs: {spec!r} is neither `memory`, `dir:/path` nor s3://bucket/prefix")


def _exit_on_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(0)


#: The environment variable `--retain-days` falls back to.
RETENTION_ENV = "CONTRAAGENT_RETENTION_DAYS"
#: `--retain-days` not given (an empty value given is None: keep everything).
_UNSET = object()


def _days(text: str) -> float | None:
    """`--retain-days`: a positive number of days; empty means keep everything."""
    if not text.strip():
        return None
    try:
        days = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number of days") from None
    if not days > 0:
        raise argparse.ArgumentTypeError(f"{text!r}: the days must be more than 0")
    return days


def _hours(text: str) -> float:
    try:
        hours = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number of hours") from None
    if not hours > 0:
        raise argparse.ArgumentTypeError(f"{text!r}: the hours must be more than 0")
    return hours


def retain_days(flag: object, environ: Mapping[str, str] = os.environ) -> float | None:
    """The days runs are kept: `--retain-days` when given (`flag` is then a number or None for
    an empty value), else `CONTRAAGENT_RETENTION_DAYS`, else None (keep everything)."""
    if flag is not _UNSET:
        assert flag is None or isinstance(flag, float)
        return flag
    try:
        return _days(environ.get(RETENTION_ENV, ""))
    except argparse.ArgumentTypeError as exc:
        raise UsageError(f"{RETENTION_ENV}: {exc}") from None


def _storage_args(ap: argparse.ArgumentParser) -> None:
    """The options that say where the hub keeps what it holds, shared by serve and prune."""
    ap.add_argument("--store", default="memory", metavar="memory|postgres://...", help="where records are kept (default: memory)")
    ap.add_argument(
        "--blobs", default="memory", metavar="memory|dir:PATH|s3://BUCKET/PREFIX", help="where file contents are kept (default: memory)"
    )
    ap.add_argument(
        "--streams-dir",
        metavar="PATH",
        help="where task transcripts being written are kept on this host's disk; sealed segments go to --segments "
        "(without it transcripts are kept in memory and lost when the hub stops)",
    )
    ap.add_argument(
        "--segments",
        metavar="DIR|s3://BUCKET/PREFIX",
        help="where sealed transcript segments are kept (default: <streams-dir>/segments)",
    )
    ap.add_argument("--ttl", type=float, default=DEFAULT_TTL_S, help="seconds a host counts as up after a heartbeat (default: %(default)g)")


def _retain_arg(ap: argparse.ArgumentParser, help: str) -> None:
    ap.add_argument("--retain-days", type=_days, default=_UNSET, metavar="N", help=help)


def add_arguments(ap: argparse.ArgumentParser) -> None:
    """`contraagent hub`, with `contraagent hub prune` under it."""
    ap.description = (
        "Receive every host's runs from `contraagent relay` and serve their monitor. "
        "Tokens are read from files, never from the command line. "
        "Without --read-token-file the monitor (every transcript) is open to anyone who reaches the port."
    )
    ap.epilog = "`contraagent hub prune --help`: remove old runs once, without serving."
    _storage_args(ap)
    ap.add_argument(
        "--ingest-token-file", metavar="FILE", help="ingest tokens, one per line, or `host_id token` for a token good for that host only"
    )
    ap.add_argument("--read-token-file", metavar="FILE", help="the token that opens the monitor; without it the monitor is open")
    add_http(ap, port=DEFAULT_PORT)
    ap.add_argument("--title", default="contraagent hub")
    ap.add_argument(
        "--max-blob-mb",
        type=float,
        default=MAX_BLOB_BYTES / 2**20,
        help="the largest blob taken, in MiB (default: %(default)g)",
    )
    _retain_arg(
        ap,
        f"remove runs with no activity for N days, while the hub runs (default: ${RETENTION_ENV}; unset or empty: keep every run)",
    )
    ap.add_argument(
        "--prune-every",
        type=_hours,
        metavar="HOURS",
        help=f"hours between prunes; the first is {FIRST_PRUNE_AFTER_S / 60:g} minutes after start "
        f"(default: {PRUNE_EVERY_HOURS:g}, or {SHORT_PRUNE_EVERY_HOURS:g} when --retain-days is under {SHORT_RETENTION_DAYS:g})",
    )
    add_openapi(ap, "ingest OpenAPI document")
    # When an open segment is sealed (`SegmentedStreamLogs`); hidden: for tests that need
    # seals within seconds, not for operators.
    ap.add_argument("--seal-bytes", type=int, dest="segment_bytes", help=argparse.SUPPRESS)
    ap.add_argument("--seal-idle", type=float, dest="idle_s", help=argparse.SUPPRESS)
    ap.add_argument("--seal-age", type=float, dest="age_s", help=argparse.SUPPRESS)
    ap.add_argument("--seal-tick", type=float, dest="tick_s", help=argparse.SUPPRESS)
    # Seconds before the first prune; hidden: for tests.
    ap.add_argument("--first-prune-after", type=float, default=FIRST_PRUNE_AFTER_S, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="hub_cmd", title="commands")
    add_command(
        sub, "prune", help="remove old runs from the hub's storage once, without serving", add_arguments=_prune_arguments, run=prune
    )


def run(args: argparse.Namespace) -> int:
    """`contraagent hub`: serve the hub (the `hub` extra) until stopped, or write its ingest OpenAPI document."""
    require_extra()
    if args.openapi:
        write_openapi(openapi_document(), args.openapi)
        return 0
    setup_logging()
    if not args.ingest_token_file:
        raise UsageError("--ingest-token-file is required: relays need a token to send")
    days = retain_days(args.retain_days)
    if days is None and args.prune_every is not None:
        raise UsageError(f"--prune-every needs --retain-days or ${RETENTION_ENV}")
    sock = bind_option(args.host, args.port)  # a taken port ends the command before the store opens
    try:
        tokens = read_ingest_tokens(args.ingest_token_file)
        read_token = read_read_token(args.read_token_file) if args.read_token_file else None
        seal = {k: v for k in ("segment_bytes", "idle_s", "age_s", "tick_s") if (v := getattr(args, k)) is not None}
        streams = open_streams(args.streams_dir, args.segments, args.store, **seal)
        hub = Hub(open_store(args.store), open_blobs(args.blobs), streams=streams, ttl_s=args.ttl)
    except (OSError, ValueError) as exc:
        raise CommandError(str(exc)) from None
    if read_token is None and not is_loopback(args.host):
        log.warning("bound to %s with no --read-token-file: every run's transcripts are open to anyone who reaches the port", args.host)
    app = create_hub_app(
        hub,
        ingest_tokens=tokens,
        read_token=read_token,
        allowed_hosts=host_names(args.host, args.allow_host),
        cors_origins=args.cors_origin,
        title=args.title,
        max_blob_bytes=int(args.max_blob_mb * 2**20),
    )
    store, blobs = args.store.split("://")[0], args.blobs.split(":")[0]  # a DSN may hold a password
    log.info("%s on %s  store=%s blobs=%s ingest tokens=%d", args.title, address(sock), store, blobs, len(tokens))
    pruner: Pruner | None = None
    if days is not None:
        every = args.prune_every if args.prune_every is not None else default_prune_every(days)
        pruner = Pruner(hub, older_than=timedelta(days=days), every_s=every * 3600, first_after_s=args.first_prune_after)
        log.info("retention: runs with no activity for %g days are removed, every %gh", days, every)
    else:
        log.info("retention: every run is kept (no --retain-days)")
    # uvicorn stops gracefully on SIGTERM and then raises it again to the handler it found;
    # the default handler would end the process before the open segments are shut down.
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    try:
        if pruner is not None:
            pruner.start()
        serve_on(app, sock)
    finally:
        if pruner is not None:
            pruner.stop()
        hub.close()
    return 0


def _prune_arguments(ap: argparse.ArgumentParser) -> None:
    ap.description = (
        "Remove the runs with no activity for N days from the hub's storage, once, and print what was removed. "
        "A run is kept while the heartbeats in the store report it live or unresponsive. "
        "Do not run it while a hub started with --retain-days uses the same storage: one process prunes at a time."
    )
    _storage_args(ap)
    _retain_arg(ap, f"remove runs with no activity for N days (default: ${RETENTION_ENV}; one of the two is required)")
    ap.add_argument("--dry-run", action="store_true", help="remove nothing; report what would be removed")
    ap.add_argument(
        "--blob-grace-hours",
        type=_hours,
        default=BLOB_GRACE / timedelta(hours=1),
        metavar="H",
        help="hours a blob no run references is kept after it was stored (default: %(default)g)",
    )
    ap.add_argument("--json", action="store_true", help="print the report as JSON")


def prune(args: argparse.Namespace) -> int:
    """`contraagent hub prune`: `Hub.prune` once over the hub's storage, its report printed."""
    days = retain_days(args.retain_days)
    if days is None:
        raise UsageError(f"--retain-days N (or ${RETENTION_ENV}) is required")
    setup_logging()
    sys.stderr.write(
        "contraagent hub prune: run it only while no hub started with --retain-days uses the same storage; one process prunes at a time\n"
    )
    try:
        # No background seals and, for a dry run, no sweep: a dry run deletes nothing.
        streams = (
            open_streams(args.streams_dir, args.segments, args.store, sweep=not args.dry_run, background=False)
            if args.streams_dir is not None or args.segments is not None
            else MemoryStreamLogs()
        )
        hub = Hub(open_store(args.store), open_blobs(args.blobs), streams=streams, ttl_s=args.ttl)
    except (OSError, ValueError) as exc:
        raise CommandError(str(exc)) from None
    try:
        report = hub.prune(older_than=timedelta(days=days), blob_grace=timedelta(hours=args.blob_grace_hours), dry_run=args.dry_run)
    finally:
        hub.close()
    sys.stdout.write(report_json(report) + "\n" if args.json else report_table(report))
    return 0
