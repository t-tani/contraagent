"""The hub's deployment example (`docs/examples/hub`): the image, compose.yaml, the tokens
`make-tokens` writes, and the relay's systemd unit.

The fast tests read the files (and validate compose.yaml with `docker compose config` when
docker is available). The `e2e` test builds the image, starts the compose project on a
random port under a project name of its own, ships the demo runs to it with a relay on
this host, and removes the project and its volumes: `uv run pytest -m e2e -k deploy`."""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from contraagent import docs
from contraagent.hub.server import read_ingest_tokens, read_read_token
from test_hub_contract import demo_runs  # noqa: F401  (a fixture)

HUB = docs.DIR / "examples" / "hub"
COMPOSE = HUB / "compose.yaml"
DOCKERFILE = HUB / "Dockerfile"
REPO = Path(__file__).resolve().parent.parent
#: A tag that names a version: digits, not `latest` or a bare major version.
PINNED = re.compile(r"^[\w./-]+:(?!latest$)[\w.-]*\d[\w.-]*\.[\w.-]*\d[\w.-]*$|^[\w./-]+:RELEASE\.[\w.-]+$")


def _docker() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "version"], capture_output=True, timeout=20).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _make_tokens(where: Path, *hosts: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(HUB / "make-tokens"), "-d", str(where), *hosts], capture_output=True, text=True)


def _env_file(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _compose(where: Path, project: str, *args: str, env: dict[str, str] | None = None, timeout: float = 120):
    argv = ["docker", "compose", "-p", project, "-f", str(COMPOSE), "--env-file", str(where / ".env"), *args]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**_outside_env(), **(env or {})},
    )


def _outside_env() -> dict[str, str]:
    """This process's environment without the variables compose.yaml reads, so a shell's
    settings do not leak into the test's project."""
    settings = set(_env_file(HUB / ".env.example")) | {"CONTRAAGENT_SECRETS_DIR", "CONTRAAGENT_HUB_IMAGE"}
    return {k: v for k, v in os.environ.items() if k not in settings and k != "COMPOSE_PROJECT_NAME"}


# --- the files ---------------------------------------------------------------------------


def test_the_dockerfile_pins_its_bases_and_runs_the_hub_as_a_user_with_a_data_volume():
    lines = DOCKERFILE.read_text().replace("\\\n", " ").splitlines()
    instructions = [line.split(None, 1) for line in lines if line.strip() and not line.lstrip().startswith("#")]
    by = lambda op: [rest for o, rest in instructions if o == op]
    bases = [rest.split()[0] for rest in by("FROM")]
    assert bases and all(PINNED.match(b) for b in bases), bases
    assert any(b.startswith("python:3.12") and b.endswith("-slim-bookworm") for b in bases)
    assert json.loads(by("ENTRYPOINT")[-1]) == ["contraagent", "hub"]
    assert by("USER")[-1] not in ("root", "0")
    assert by("VOLUME") == ["/data"] and "8790" in by("EXPOSE")
    assert "/data/streams" in by("CMD")[-1] and "/run/secrets/ingest-tokens" in by("CMD")[-1]
    assert "/healthz" in by("HEALTHCHECK")[-1]


def test_the_build_context_holds_only_what_the_image_installs():
    ignore = [line for line in (HUB / "Dockerfile.dockerignore").read_text().splitlines() if line and not line.startswith("#")]
    assert ignore[0] == "*"
    assert {line[1:].rstrip("/") for line in ignore if line.startswith("!")} == {"pyproject.toml", "uv.lock", "LICENSE", "src"}
    copied = {p for rest in re.findall(r"^COPY (?!--from)(.+)$", DOCKERFILE.read_text(), re.M) for p in rest.split()[:-1]}
    assert copied == {"pyproject.toml", "uv.lock", "LICENSE", "src"}
    assert all((REPO / p).exists() for p in copied)


def test_every_image_compose_uses_is_pinned():
    images = re.findall(r"^\s+image:\s*(\S+)\s*$", COMPOSE.read_text(), re.M)
    assert len(images) == 4
    fixed = [i for i in images if not i.startswith("${")]
    assert len(fixed) == 3 and all(PINNED.match(i) for i in fixed), fixed


def test_no_secret_is_in_the_example():
    for path in HUB.rglob("*"):
        if path.is_file():
            assert not re.search(r"\b[0-9a-f]{32,}\b", path.read_text()), f"{path.name} holds what looks like a token"
    for placeholder in ("ingest-tokens.example", "read-token.example"):
        with pytest.raises(ValueError, match="no token"):
            (read_ingest_tokens if placeholder.startswith("ingest") else read_read_token)(HUB / "secrets" / placeholder)
    env = _env_file(HUB / ".env.example")
    assert env["POSTGRES_PASSWORD"] == env["MINIO_ROOT_PASSWORD"] == "change-me"
    assert {p.name for p in (HUB / "secrets").iterdir()} == {"ingest-tokens.example", "read-token.example"}


def test_make_tokens_writes_tokens_the_hub_reads_and_keeps_them(tmp_path):
    done = _make_tokens(tmp_path, "build-01", "build-02")
    assert done.returncode == 0, done.stderr
    secrets = tmp_path / "secrets"
    tokens = read_ingest_tokens(secrets / "ingest-tokens")
    assert sorted(tokens.values()) == ["build-01", "build-02"]
    for host in ("build-01", "build-02"):
        relay = _env_file(secrets / f"relay-{host}.env")
        assert relay["CONTRAAGENT_HOST_ID"] == host and tokens[relay["CONTRAAGENT_HUB_TOKEN"]] == host
        assert (secrets / f"relay-{host}.env").stat().st_mode & 0o077 == 0
    assert re.fullmatch(r"[0-9a-f]{64}", read_read_token(secrets / "read-token"))
    assert secrets.stat().st_mode & 0o077 == 0
    env = _env_file(tmp_path / ".env")
    assert set(env) == set(_env_file(HUB / ".env.example")) and "change-me" not in env.values()
    assert env["POSTGRES_PASSWORD"] != env["MINIO_ROOT_PASSWORD"]
    before = (secrets / "ingest-tokens").read_text()
    again = _make_tokens(tmp_path)
    assert again.returncode == 1 and "exists" in again.stderr
    assert (secrets / "ingest-tokens").read_text() == before


def test_make_tokens_without_hosts_makes_one_token_for_any_host(tmp_path):
    assert _make_tokens(tmp_path).returncode == 0
    tokens = read_ingest_tokens(tmp_path / "secrets" / "ingest-tokens")
    assert list(tokens.values()) == [None]
    assert _env_file(tmp_path / "secrets" / "relay.env")["CONTRAAGENT_HUB_TOKEN"] in tokens


def test_the_relay_unit_restarts_and_takes_its_token_from_a_file():
    unit = configparser.ConfigParser(strict=False, interpolation=None)
    unit.optionxform = str  # type: ignore[assignment]  # systemd keys are case-sensitive
    unit.read_string((HUB / "contraagent-relay.service").read_text())
    service = unit["Service"]
    assert service["Restart"] == "always"
    assert service["EnvironmentFile"].startswith("/etc/")
    assert " relay " in service["ExecStart"] and "--hub ${CONTRAAGENT_HUB_URL}" in service["ExecStart"]
    assert "TOKEN" not in service["ExecStart"]
    assert unit["Install"]["WantedBy"] == "multi-user.target"


@pytest.mark.skipif(not _docker(), reason="docker is not available")
def test_compose_config_validates(tmp_path):
    assert _make_tokens(tmp_path, "h1").returncode == 0
    secrets = {"CONTRAAGENT_SECRETS_DIR": str(tmp_path / "secrets")}
    done = _compose(tmp_path, "contraagent-config", "config", "--format", "json", env=secrets)
    assert done.returncode == 0, done.stderr
    config = json.loads(done.stdout)
    services = config["services"]
    assert set(services) == {"hub", "postgres", "minio", "minio-init"}
    hub = services["hub"]
    assert {s["source"] for s in hub["secrets"]} == {"ingest-tokens", "read-token"}
    assert {k: v["condition"] for k, v in hub["depends_on"].items()} == {
        "postgres": "service_healthy",
        "minio": "service_healthy",
        "minio-init": "service_completed_successfully",
    }
    assert all("healthcheck" in services[s] for s in ("hub", "postgres", "minio"))
    assert hub["ports"][0]["target"] == 8790
    assert Path(hub["build"]["context"]) == REPO
    assert not any("PASSWORD" in arg or "secret" in arg.lower() for arg in hub["command"] if "secrets/" not in arg)
    assert config["secrets"]["read-token"]["file"] == str(tmp_path / "secrets" / "read-token")


# --- end to end ----------------------------------------------------------------------------


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, token: str | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


@pytest.mark.e2e
@pytest.mark.skipif(not _docker(), reason="docker is not available")
def test_deploy_the_compose_hub_and_ship_the_demo_runs_to_it(tmp_path, demo_runs):  # noqa: F811
    began = time.monotonic()
    tag = uuid.uuid4().hex[:10]
    project, image, port = f"contraagent-e2e-{tag}", f"contraagent-hub:e2e-{tag}", _free_port()
    assert _make_tokens(tmp_path, "e2e-host").returncode == 0
    env = {
        "CONTRAAGENT_SECRETS_DIR": str(tmp_path / "secrets"),
        "CONTRAAGENT_HUB_IMAGE": image,
        "CONTRAAGENT_HUB_BIND": "127.0.0.1",
        "CONTRAAGENT_HUB_PORT": str(port),
    }
    url = f"http://127.0.0.1:{port}"
    read = read_read_token(tmp_path / "secrets" / "read-token")
    relay_env = _env_file(tmp_path / "secrets" / "relay-e2e-host.env")
    try:
        up = _compose(tmp_path, project, "up", "--detach", "--build", env=env, timeout=600)
        assert up.returncode == 0, up.stderr
        deadline = time.monotonic() + 120
        while True:
            try:
                status, body = _get(f"{url}/healthz")
                if status == 200:
                    break
            except OSError:
                status, body = 0, b""
            assert time.monotonic() < deadline, f"/healthz: {status} {body!r}\n{_compose(tmp_path, project, 'logs', env=env).stdout}"
            time.sleep(0.5)
        assert json.loads(body) == {"status": "ok", "failed": {}}
        healthy = time.monotonic() - began
        assert _get(f"{url}/api/runs")[0] == 401

        relay = subprocess.run(
            [sys.executable, "-m", "contraagent", "relay", "--once", "--runs-dir", str(demo_runs), "--hub", url],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, **relay_env},
        )
        assert relay.returncode == 0, relay.stderr
        status, body = _get(f"{url}/api/runs", read)
        assert status == 200, body
        local = sorted(p.name for p in demo_runs.iterdir() if (p / "run.json").is_file())
        assert local and sorted(r["run"] for r in json.loads(body)) == sorted(f"{r}@e2e-host" for r in local)
        relayed = time.monotonic() - began

        assert _compose(tmp_path, project, "stop", "postgres", env=env).returncode == 0
        status, body = _get(f"{url}/healthz")
        assert status == 503 and json.loads(body)["failed"].keys() >= {"records"}, body
        print(f"\ndeploy e2e: healthy after {healthy:.1f}s, relayed after {relayed:.1f}s")
    finally:
        down = _compose(tmp_path, project, "down", "--volumes", "--remove-orphans", env=env, timeout=180)
        subprocess.run(["docker", "image", "rm", "--force", image], capture_output=True, timeout=60)
        assert down.returncode == 0, down.stderr
