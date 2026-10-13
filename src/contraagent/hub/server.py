"""`contraagent hub`: receive, store, and serve the monitor.

One ASGI app (`create_hub_app`) over a `Hub`, with two parts that never share a token:

  POST /ingest/records         RecordBatch -> Accepted              (`protocol.py`)
  POST /ingest/heartbeat       Heartbeat   -> HeartbeatAck
  HEAD /ingest/blobs/<sha256>  200 or 404
  PUT  /ingest/blobs/<sha256>  raw bytes -> 204; 400 when they do not hash to <sha256>
  GET  /login?token=<read>     sets the read cookie and redirects to /
  everything else              the monitor (`contraagent.monitor.server.create_app`)
                               over `Hub.monitor()`: API, SSE feeds, the bundled UI

* **Ingest** answers 401 without `Authorization: Bearer <token>` naming one of the ingest
  tokens. A token given for one host (`host_id token` in the token file) answers 403 to a
  batch or heartbeat of another host. A records batch is capped at `MAX_RECORDS_BYTES`
  and a blob at `max_blob_bytes`, after `Content-Encoding: gzip` is undone; beyond the
  cap the answer is 413. The routes' contract, for a relay in any language, is
  `contraagent/hub/openapi.json` (`python -m contraagent.hub.server --openapi PATH`).
* **The monitor** answers 401 without the read token, as `Authorization: Bearer <token>`
  or as the cookie `/login` sets (HttpOnly, SameSite=Strict; an EventSource cannot send
  a header). With no read token the monitor is open to whoever reaches the port. It keeps
  the local monitor's `Host` check (DNS rebinding): only the loopback names, the bound
  address and `--allow-host` names are answered. Ingest is not under the `Host` check:
  a page in a browser has no ingest token.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import signal
import sys
import zlib
from collections.abc import Iterable, Mapping
from http.cookies import SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

try:
    from fastapi import Depends, FastAPI, HTTPException, Request, Response
    from fastapi.concurrency import run_in_threadpool
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from starlette.types import ASGIApp, Message, Receive, Scope, Send
except ModuleNotFoundError:
    # The extra is optional; `require_extra` says so in words (see monitor.server).
    if TYPE_CHECKING:
        raise

from contraagent.hub.core import Hub
from contraagent.hub.protocol import (
    INGEST_BLOB,
    INGEST_HEARTBEAT,
    INGEST_RECORDS,
    Accepted,
    Heartbeat,
    HeartbeatAck,
    RecordBatch,
)
from contraagent.hub.source import DEFAULT_TTL_S
from contraagent.hub.store import BlobStore, DirectoryBlobs, HubStore, MemoryBlobs, MemoryHubStore
from contraagent.hub.streams import MemoryStreamLogs, StreamLogs
from contraagent.monitor.server import LOCAL_HOSTS, _host_names, create_app, require_extra

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
    413 once it passes the route's cap; the app downstream reads the plain body."""

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
    """The ingest routes of `protocol.py` as a FastAPI app (the `/ingest/` part of `create_hub_app`).

    `ingest_tokens` maps each token to the host it was given for (`None`: any host), or
    lists tokens good for any host."""
    require_extra()
    tokens = _tokens(ingest_tokens)
    app = FastAPI(
        title=OPENAPI_TITLE,
        version=OPENAPI_VERSION,
        description=(
            "How a relay ships a host's runs to a contraagent hub. Models: contraagent.hub.protocol. "
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
    """`/ingest/...` to the ingest app, everything else to the guarded monitor."""

    def __init__(self, ingest: ASGIApp, monitor: ASGIApp) -> None:
        self.ingest = ingest
        self.monitor = monitor

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(INGEST_PREFIX):
            await self.ingest(scope, receive, send)
        else:
            await self.monitor(scope, receive, send)


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
    """The hub as one ASGI app: the ingest routes and the monitor over `hub.monitor()`.

    `ingest_tokens`: see `create_ingest_app`. `read_token=None` leaves the monitor open.
    `allowed_hosts` and `cors_origins` are the monitor's (`monitor.server.create_app`)."""
    allowed = [*LOCAL_HOSTS, *allowed_hosts]
    ingest = BodyLimit(
        create_ingest_app(hub, ingest_tokens, max_records_bytes=max_records_bytes, max_blob_bytes=max_blob_bytes),
        max_records_bytes=max_records_bytes,
        max_blob_bytes=max_blob_bytes,
    )
    monitor = create_app(hub.monitor(title=title), allowed_hosts=allowed, cors_origins=cors_origins)
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
    for line in Path(path).read_text().splitlines():
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
    for line in Path(path).read_text().splitlines():
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
            from contraagent.hub.postgres import PostgresHubStore  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ValueError(f"--store {spec.split('://')[0]}://: the Postgres store is not available ({exc})") from None
        return PostgresHubStore(spec)
    raise ValueError(f"--store: {spec!r} is neither `memory` nor a postgres:// DSN")


def open_streams(streams_dir: str | None, segments: str | None, store: str) -> StreamLogs:
    """Where transcripts are kept: segmented (open segments in `streams_dir`, sealed ones at
    `segments`, indexed in the `store`'s Postgres database when it is one), or in memory
    when no `streams_dir` is given."""
    if streams_dir is None:
        if segments is not None:
            raise ValueError("--segments needs --streams-dir")
        log.warning("no --streams-dir: transcripts are kept in memory and lost when the hub stops")
        return MemoryStreamLogs()
    try:
        from contraagent.hub.segments import from_spec
    except ImportError as exc:
        raise ValueError(f"--streams-dir: segmented transcripts are not available ({exc})") from None
    index = store if store.startswith(("postgres://", "postgresql://")) else None
    return from_spec(streams_dir, segments or str(Path(streams_dir) / "segments"), index)


def open_blobs(spec: str) -> BlobStore:
    """`memory`, `dir:/path`, or `s3://bucket/prefix?endpoint=...`."""
    if spec == "memory":
        return MemoryBlobs()
    if spec.startswith("dir:"):
        return DirectoryBlobs(spec.removeprefix("dir:"))
    if spec.startswith("s3://"):
        try:
            from contraagent.hub.s3 import S3Blobs  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ValueError(f"--blobs s3://: the S3 blob store is not available ({exc})") from None
        return S3Blobs(spec)
    raise ValueError(f"--blobs: {spec!r} is neither `memory`, `dir:/path` nor s3://bucket/prefix")


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="contraagent hub",
        description=(
            "Receive every host's runs from `contraagent relay` and serve their monitor. "
            "Tokens are read from files, never from the command line. "
            "Without --read-token-file the monitor (every transcript) is open to anyone who reaches the port."
        ),
    )
    ap.add_argument("--store", default="memory", metavar="memory|postgres://...", help="where records are kept (default: memory)")
    ap.add_argument(
        "--blobs", default="memory", metavar="memory|dir:PATH|s3://BUCKET/PREFIX", help="where file contents are kept (default: memory)"
    )
    ap.add_argument(
        "--ingest-token-file", metavar="FILE", help="ingest tokens, one per line, or `host_id token` for a token good for that host only"
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
    ap.add_argument("--read-token-file", metavar="FILE", help="the token that opens the monitor; without it the monitor is open")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--ttl", type=float, default=DEFAULT_TTL_S, help="seconds a host counts as up after a heartbeat (default: %(default)g)")
    ap.add_argument("--title", default="contraagent hub")
    ap.add_argument(
        "--max-blob-mb",
        type=float,
        default=MAX_BLOB_BYTES / 2**20,
        help="the largest blob taken, in MiB (default: %(default)g)",
    )
    ap.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NAME",
        help="also answer monitor requests addressed to this host name (default: localhost, 127.0.0.1, [::1] and the --host address)",
    )
    ap.add_argument("--cors-origin", action="append", default=[], metavar="ORIGIN", help="let a page from this origin read the monitor API")
    ap.add_argument(
        "--openapi",
        nargs="?",
        const="-",
        metavar="PATH",
        help="write the ingest OpenAPI document to PATH (default: stdout) and exit",
    )
    args = ap.parse_args(argv)
    try:
        require_extra()
    except ModuleNotFoundError as exc:
        sys.stderr.write(f"contraagent hub: {exc}\n")
        return 2
    if args.openapi:
        doc = openapi_document()
        if args.openapi == "-":
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
            sys.stdout.write(doc)
        else:
            Path(args.openapi).write_text(doc)
        return 0
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.ingest_token_file:
        ap.error("--ingest-token-file is required: relays need a token to send")
    try:
        tokens = read_ingest_tokens(args.ingest_token_file)
        read_token = read_read_token(args.read_token_file) if args.read_token_file else None
        streams = open_streams(args.streams_dir, args.segments, args.store)
        hub = Hub(open_store(args.store), open_blobs(args.blobs), streams=streams, ttl_s=args.ttl)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"contraagent hub: {exc}\n")
        return 2
    names = _host_names(args.host)
    if read_token is None and not _loopback(args.host):
        log.warning("bound to %s with no --read-token-file: every run's transcripts are open to anyone who reaches the port", args.host)
    if not names and not args.allow_host:
        local = ", ".join(LOCAL_HOSTS)
        log.warning("bound to %s: only monitor requests addressed to %s are answered; name others with --allow-host", args.host, local)
    app = create_hub_app(
        hub,
        ingest_tokens=tokens,
        read_token=read_token,
        allowed_hosts=[*names, *args.allow_host],
        cors_origins=args.cors_origin,
        title=args.title,
        max_blob_bytes=int(args.max_blob_mb * 2**20),
    )
    import uvicorn

    store, blobs = args.store.split("://")[0], args.blobs.split(":")[0]  # a DSN may hold a password
    log.info("%s on http://%s:%s  store=%s blobs=%s ingest tokens=%d", args.title, args.host, args.port, store, blobs, len(tokens))
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        shutdown = getattr(hub.streams, "shutdown", None)
        if shutdown is not None:
            shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
