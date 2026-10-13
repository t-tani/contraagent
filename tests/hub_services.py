"""Throwaway Postgres and MinIO containers for the hub's tests.

`postgres_dsn()` and `s3_url()` start their container on first use (once per session) and
give each caller a fresh database or a fresh prefix; they skip the test when docker is not
available. `hub_services` is the session fixture that stops the containers at the end; a
module that uses them imports it and marks its tests `usefixtures("hub_services")`."""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid

import pytest

POSTGRES_IMAGE = "postgres:16.4"
MINIO_IMAGE = "minio/minio:RELEASE.2025-04-03T14-56-28Z"
LABEL = "contraagent-test=hub"

MINIO_USER, MINIO_PASSWORD, MINIO_BUCKET = "contraagent", "contraagent-secret", "hub"

_lock = threading.Lock()
_containers: list[str] = []
_started: dict[str, str] = {}
_env_before: dict[str, str | None] = {}
_unavailable: list[str] = []


def _docker(*args: str, timeout: float = 120) -> str:
    done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def _require_docker() -> None:
    if not _unavailable:
        if shutil.which("docker") is None:
            _unavailable.append("docker is not installed")
        else:
            try:
                if not _docker("version", "--format", "{{.Server.Version}}", timeout=20):
                    raise RuntimeError("no docker server")
                _unavailable.append("")
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                _unavailable.append(f"docker is not available: {e}")
    if _unavailable[0]:
        pytest.skip(_unavailable[0])


def _run(image: str, port: int, *args: str, env: dict[str, str]) -> tuple[str, int]:
    """Start `image` with `port` published on a random local port; its id and that port."""
    flags = [f"-e{k}={v}" for k, v in env.items()]
    cid = _docker("run", "-d", "--rm", "--label", LABEL, "-p", f"127.0.0.1::{port}", *flags, image, *args, timeout=300)
    _containers.append(cid)
    published = _docker("port", cid, f"{port}/tcp").splitlines()[0]
    return cid, int(published.rsplit(":", 1)[1])


def _wait(ready, what: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if ready():
                return
        except Exception:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"{what} did not become ready in {timeout}s")
        time.sleep(0.2)


def stop_all() -> None:
    """Remove every container this session started, and restore the AWS environment."""
    with _lock:
        while _containers:
            subprocess.run(["docker", "rm", "-f", _containers.pop()], capture_output=True, timeout=60)
        _started.clear()
        for k, v in _env_before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _env_before.clear()


atexit.register(stop_all)


def _postgres_server() -> str:
    """The admin DSN of the session's Postgres server."""
    with _lock:
        if "postgres" not in _started:
            _require_docker()
            import psycopg

            _, port = _run(
                POSTGRES_IMAGE,
                5432,
                *("-c", "max_connections=500", "-c", "fsync=off"),
                env={"POSTGRES_PASSWORD": "pw", "POSTGRES_USER": "hub"},
            )
            dsn = f"postgresql://hub:pw@127.0.0.1:{port}/postgres"

            def ready() -> bool:
                with psycopg.connect(dsn, connect_timeout=2) as conn:
                    conn.execute("SELECT 1")
                return True

            _wait(ready, POSTGRES_IMAGE)
            _started["postgres"] = dsn
        return _started["postgres"]


def postgres_dsn() -> str:
    """The DSN of a new, empty database on the session's Postgres server."""
    import psycopg

    admin = _postgres_server()
    db = f"t_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE {db}")  # type: ignore[arg-type]  # a generated name
    return admin.rsplit("/", 1)[0] + "/" + db


def _minio_server() -> str:
    """The endpoint of the session's MinIO server, with its bucket made."""
    with _lock:
        if "minio" not in _started:
            _require_docker()
            _, port = _run(MINIO_IMAGE, 9000, "server", "/data", env={"MINIO_ROOT_USER": MINIO_USER, "MINIO_ROOT_PASSWORD": MINIO_PASSWORD})
            endpoint = f"http://127.0.0.1:{port}"
            _wait(lambda: urllib.request.urlopen(f"{endpoint}/minio/health/live", timeout=2).status == 200, MINIO_IMAGE)
            for k, v in {"AWS_ACCESS_KEY_ID": MINIO_USER, "AWS_SECRET_ACCESS_KEY": MINIO_PASSWORD}.items():
                _env_before.setdefault(k, os.environ.get(k))
                os.environ[k] = v
            for k in ("AWS_SESSION_TOKEN", "AWS_PROFILE"):
                _env_before.setdefault(k, os.environ.get(k))
                os.environ.pop(k, None)
            import boto3

            boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1").create_bucket(Bucket=MINIO_BUCKET)
            _started["minio"] = endpoint
        return _started["minio"]


def s3_url() -> str:
    """An `S3Blobs` URL of a new, empty prefix in the session's MinIO bucket."""
    endpoint = _minio_server()
    return f"s3://{MINIO_BUCKET}/t-{uuid.uuid4().hex[:16]}?endpoint={endpoint}&region=us-east-1"


@pytest.fixture(scope="session")
def hub_services():
    """Stops the session's containers at its end."""
    yield
    stop_all()
