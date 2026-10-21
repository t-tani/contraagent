"""Throwaway Postgres and RustFS containers for the hub's tests.

`postgres_dsn()` and `s3_url()` start their container on first use (once per session) and
give each caller a fresh database or a fresh prefix; they skip the test when docker cannot
run Linux containers (`linux_containers` says why). `hub_services` is the fixture that gives a
test the RustFS server's credentials (`S3_ENV`), in the environment where the hub's S3 clients
read them; a module that uses the services imports it and marks its tests
`usefixtures("hub_services")`. A process the test starts is given `S3_ENV` too. The
containers are removed when the session ends (`stop_all`, from `conftest.py`).

Under pytest-xdist the workers share one container of each: the first to need it starts it
and records it in a file the others read (`_shared_state`, under a lock), and the controller
removes them when the run ends (`stop_shared`, from `conftest.py`)."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from contraagent._internal.platform.locks import locks

POSTGRES_IMAGE = "postgres:16.4"
RUSTFS_IMAGE = "rustfs/rustfs:1.0.0"
LABEL = "contraagent-test=hub"
#: The pytest process a container belongs to (the xdist controller, or the process itself):
#: a container whose owner is gone was left by a run that was killed before `atexit` ran.
OWNER = "contraagent-test-owner"
#: A container from before the owner label is left alone while younger than this.
_UNOWNED_GRACE_S = 3600

RUSTFS_USER, RUSTFS_PASSWORD, RUSTFS_BUCKET = "contraagent", "contraagent-secret", "hub"
#: The RustFS server's credentials, as an S3 client reads them from its environment.
S3_ENV = {"AWS_ACCESS_KEY_ID": RUSTFS_USER, "AWS_SECRET_ACCESS_KEY": RUSTFS_PASSWORD}

_lock = threading.Lock()
_containers: list[str] = []
_started: dict[str, str] = {}
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
                server_os = _docker("version", "--format", "{{.Server.Os}}", timeout=20)
                if not server_os:
                    raise RuntimeError("no docker server")
                if server_os != "linux":
                    _unavailable.append(f"docker runs {server_os} containers here, and these images are Linux ones")
                else:
                    _unavailable.append("")
                    _reap_orphans()
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                _unavailable.append(f"docker is not available: {e}")
    if _unavailable[0]:
        pytest.skip(_unavailable[0])


def linux_containers() -> str:
    """Why docker cannot run the Linux images these tests use (no docker, no server, or a
    server of Windows containers, as on a Windows runner); "" when it can."""
    try:
        _require_docker()
    except pytest.skip.Exception as e:
        return str(e.msg)
    return ""


def _owner() -> int:
    """The pytest process this one's containers belong to: the xdist controller for a worker."""
    return os.getppid() if os.environ.get("PYTEST_XDIST_WORKER") else os.getpid()


def _reap_orphans() -> None:
    """Remove the hub containers of test runs that were killed (SIGKILL, a timeout) before they
    could remove their own: those whose owner process is gone, and those from before the owner
    label once they are older than `_UNOWNED_GRACE_S`. A run still going keeps its containers."""
    try:
        rows = _docker("ps", "-a", "--filter", f"label={LABEL}", "--format", f'{{{{.ID}}}} {{{{.Label "{OWNER}"}}}}', timeout=30)
    except (RuntimeError, subprocess.TimeoutExpired):
        return
    for row in rows.splitlines():
        cid, _, owner = row.partition(" ")
        if owner.strip().isdigit():
            if _pid_alive(int(owner)):
                continue
        else:
            try:
                created = _docker("inspect", "-f", "{{.Created}}", cid, timeout=30)
                started = datetime.fromisoformat(created.split(".")[0].rstrip("Z")).replace(tzinfo=UTC)
            except (RuntimeError, subprocess.TimeoutExpired, ValueError):
                continue
            if (datetime.now(UTC) - started).total_seconds() < _UNOWNED_GRACE_S:
                continue
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=60)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _shared_file(controller: int | None = None) -> Path | None:
    """The file pytest-xdist's workers share the containers through, named by the controller's
    pid (each worker's parent); None outside a worker unless `controller` names one."""
    if controller is None:
        if not os.environ.get("PYTEST_XDIST_WORKER"):
            return None
        controller = os.getppid()
    return Path(tempfile.gettempdir()) / f"contraagent-hub-services-{controller}.json"


@contextmanager
def _shared_state() -> Iterator[dict | None]:
    """What the workers have started (`{"postgres": dsn, "postgres-container": id, "rustfs":
    endpoint, "rustfs-container": id, "containers": [...]}`), held under a lock and written
    back, also when the caller fails (the controller removes the containers it names); None
    when this process is not an xdist worker."""
    path = _shared_file()
    if path is None:
        yield None
        return
    with open(path.with_suffix(".lock"), "a") as lock:
        locks.lock(lock.fileno())
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            state = {}
        try:
            yield state
        finally:
            path.write_text(json.dumps(state))


def _recorded(shared: dict | None, name: str) -> str | None:
    """The address another worker recorded for `name` (`postgres`, `rustfs`) while its
    container runs; None otherwise. The file is named by the controller's pid, so it can be
    one an earlier run left, whose containers were removed since."""
    if shared is None or name not in shared or f"{name}-container" not in shared:
        return None
    try:
        running = _docker("inspect", "-f", "{{.State.Running}}", shared[f"{name}-container"], timeout=30)
    except (RuntimeError, subprocess.TimeoutExpired):
        return None
    return shared[name] if running == "true" else None


def stop_shared(controller: int) -> None:
    """Remove the containers the xdist workers of controller pid `controller` started."""
    path = _shared_file(controller)
    if path is None or not path.exists():
        return
    try:
        containers = json.loads(path.read_text()).get("containers", [])
    except (OSError, ValueError):
        containers = []
    for cid in containers:
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=60)
    path.unlink(missing_ok=True)
    path.with_suffix(".lock").unlink(missing_ok=True)


def _run(image: str, port: int, *args: str, env: dict[str, str], shared: dict | None = None) -> tuple[str, int]:
    """Start `image` with `port` published on a random local port; its id and that port. A
    container started for xdist's workers is the controller's to remove, not this process's."""
    flags = [f"-e{k}={v}" for k, v in env.items()]
    cid = _docker(
        "run",
        "-d",
        "--rm",
        "--label",
        LABEL,
        "--label",
        f"{OWNER}={_owner()}",
        "-p",
        f"127.0.0.1::{port}",
        *flags,
        image,
        *args,
        timeout=300,
    )
    if shared is None:
        _containers.append(cid)
    else:
        shared.setdefault("containers", []).append(cid)
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
    """Remove every container this process started."""
    with _lock:
        while _containers:
            subprocess.run(["docker", "rm", "-f", _containers.pop()], capture_output=True, timeout=60)
        _started.clear()


atexit.register(stop_all)


def _postgres_server() -> str:
    """The admin DSN of the session's Postgres server."""
    with _lock:
        if "postgres" not in _started:
            _require_docker()
            with _shared_state() as shared:
                if (recorded := _recorded(shared, "postgres")) is not None:
                    _started["postgres"] = recorded
                    return recorded
                import psycopg

                cid, port = _run(
                    POSTGRES_IMAGE,
                    5432,
                    *("-c", "max_connections=500", "-c", "fsync=off"),
                    env={"POSTGRES_PASSWORD": "pw", "POSTGRES_USER": "hub"},
                    shared=shared,
                )
                dsn = f"postgresql://hub:pw@127.0.0.1:{port}/postgres"

                def ready() -> bool:
                    with psycopg.connect(dsn, connect_timeout=2) as conn:
                        conn.execute("SELECT 1")
                    return True

                _wait(ready, POSTGRES_IMAGE)
                _started["postgres"] = dsn
                if shared is not None:
                    shared["postgres"], shared["postgres-container"] = dsn, cid
        return _started["postgres"]


def postgres_dsn() -> str:
    """The DSN of a new, empty database on the session's Postgres server."""
    import psycopg

    admin = _postgres_server()
    db = f"t_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE {db}")  # type: ignore[arg-type]  # a generated name
    return admin.rsplit("/", 1)[0] + "/" + db


def _rustfs_server() -> str:
    """The endpoint of the session's RustFS server, with its bucket made."""
    with _lock:
        if "rustfs" not in _started:
            _require_docker()
            with _shared_state() as shared:
                if (recorded := _recorded(shared, "rustfs")) is not None:
                    _started["rustfs"] = recorded
                    return recorded
                env = {"RUSTFS_ACCESS_KEY": RUSTFS_USER, "RUSTFS_SECRET_KEY": RUSTFS_PASSWORD}
                cid, port = _run(RUSTFS_IMAGE, 9000, env=env, shared=shared)
                endpoint = f"http://127.0.0.1:{port}"

                def healthy() -> bool:
                    with urllib.request.urlopen(f"{endpoint}/health", timeout=2) as answer:
                        return answer.status == 200

                _wait(healthy, RUSTFS_IMAGE)
                import boto3
                from botocore.exceptions import ClientError

                s3 = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    region_name="us-east-1",
                    aws_access_key_id=RUSTFS_USER,
                    aws_secret_access_key=RUSTFS_PASSWORD,
                )

                def bucket() -> bool:
                    try:
                        s3.create_bucket(Bucket=RUSTFS_BUCKET)
                    except ClientError as e:
                        # A create the server did although its answer failed: the bucket is there.
                        if e.response.get("Error", {}).get("Code") not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                            raise
                    return True

                # /health answers before every part of the server does: the bucket is made once it can be.
                _wait(bucket, f"{RUSTFS_IMAGE} bucket")
                _started["rustfs"] = endpoint
                if shared is not None:
                    shared["rustfs"], shared["rustfs-container"] = endpoint, cid
        return _started["rustfs"]


def s3_url() -> str:
    """An `S3Blobs` URL of a new, empty prefix in the session's RustFS bucket."""
    endpoint = _rustfs_server()
    return f"s3://{RUSTFS_BUCKET}/t-{uuid.uuid4().hex[:16]}?endpoint={endpoint}&region=us-east-1"


@pytest.fixture
def hub_services(monkeypatch):
    """The RustFS server's credentials (`S3_ENV`) in the test's environment, where the S3
    clients of the hub's code read them; the test's environment holds no other ones."""
    for name, value in S3_ENV.items():
        monkeypatch.setenv(name, value)
