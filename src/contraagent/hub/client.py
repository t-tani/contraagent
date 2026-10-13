"""How a relay reaches a hub: `HubClient`. `DirectClient` calls a `Hub` in the same
process (tests, a relay and a hub in one program); `HttpClient` speaks the protocol over
HTTP (`contraagent relay`). Either raises `HubUnavailable` when the hub cannot take a
request."""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING, Protocol

from contraagent.errors import ContraagentError
from contraagent.hub.core import Hub
from contraagent.hub.protocol import INGEST_BLOB, INGEST_HEARTBEAT, INGEST_RECORDS, Accepted, Heartbeat, HeartbeatAck, RecordBatch

if TYPE_CHECKING:
    import httpx


class HubUnavailable(ContraagentError):
    """The hub did not take a request: no connection, a timeout, or an answer other than 2xx."""


class HubRefused(HubUnavailable):
    """The hub refused the relay's token (HTTP 401), or the token is bound to another host
    (HTTP 403): a configuration error that waiting does not fix."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class HubClient(Protocol):
    """The four requests of the protocol (`protocol.py`)."""

    def send_records(self, batch: RecordBatch) -> Accepted: ...

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck: ...

    def has_blob(self, sha256: str) -> bool: ...

    def put_blob(self, sha256: str, data: bytes) -> None: ...


class DirectClient:
    """A `HubClient` that calls a `Hub` in-process."""

    def __init__(self, hub: Hub) -> None:
        self.hub = hub

    def send_records(self, batch: RecordBatch) -> Accepted:
        return self.hub.records(RecordBatch.model_validate(batch.model_dump()))

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        return self.hub.heartbeat(Heartbeat.model_validate(heartbeat.model_dump()))

    def has_blob(self, sha256: str) -> bool:
        return self.hub.has_blob(sha256)

    def put_blob(self, sha256: str, data: bytes) -> None:
        self.hub.put_blob(sha256, data)


class HttpClient:
    """A `HubClient` over HTTP (httpx, from the `hub` extra).

    `base_url` is the hub's address (`http://hub:8790`); `token`, when not empty, goes in
    every request as `Authorization: Bearer <token>`; `timeout` is in seconds per request.
    `transport` replaces httpx's own (tests: `httpx.MockTransport`). Every failure, a
    connection error, a timeout, an answer other than 2xx or a body that is not the
    protocol's, raises `HubUnavailable`; HTTP 401 and 403 raise `HubRefused`. The bodies of
    records and heartbeats are sent gzipped (`Content-Encoding: gzip`), blobs as they are."""

    def __init__(self, base_url: str, token: str = "", timeout: float = 30.0, *, transport: httpx.BaseTransport | None = None) -> None:
        import httpx

        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, ok: tuple[int, ...] = (), **kwargs) -> httpx.Response:
        import httpx

        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HubUnavailable(f"{method} {self.base_url}{path}: {exc or type(exc).__name__}") from exc
        status = response.status_code
        if not (200 <= status < 300 or status in ok):
            body = response.text[:200].strip() if method != "HEAD" else ""
            message = f"{method} {self.base_url}{path}: HTTP {status}" + (f": {body}" if body else "")
            if status in (401, 403):
                raise HubRefused(message, status)
            raise HubUnavailable(message)
        return response

    def _json(self, path: str, body: str) -> bytes:
        headers = {"Content-Type": "application/json", "Content-Encoding": "gzip"}
        return self._request("POST", path, content=gzip.compress(body.encode(), compresslevel=6), headers=headers).content

    def send_records(self, batch: RecordBatch) -> Accepted:
        content = self._json(INGEST_RECORDS, batch.model_dump_json())
        try:
            return Accepted.model_validate_json(content)
        except ValueError as exc:
            raise HubUnavailable(f"POST {self.base_url}{INGEST_RECORDS}: not an Accepted answer: {exc}") from exc

    def send_heartbeat(self, heartbeat: Heartbeat) -> HeartbeatAck:
        content = self._json(INGEST_HEARTBEAT, heartbeat.model_dump_json())
        try:
            return HeartbeatAck.model_validate_json(content)
        except ValueError as exc:
            raise HubUnavailable(f"POST {self.base_url}{INGEST_HEARTBEAT}: not a HeartbeatAck answer: {exc}") from exc

    def has_blob(self, sha256: str) -> bool:
        return self._request("HEAD", INGEST_BLOB.format(sha256=sha256), ok=(404,)).status_code != 404

    def put_blob(self, sha256: str, data: bytes) -> None:
        self._request("PUT", INGEST_BLOB.format(sha256=sha256), content=data, headers={"Content-Type": "application/octet-stream"})
