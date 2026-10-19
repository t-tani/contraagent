"""The hub's deployment example (`docs/examples/hub`): the image, compose.yaml, the tokens
`make-tokens` writes, and the relay's systemd unit; and the developer's hub image built
from this repository (`Dockerfile` at its root).

The fast tests read the files (and validate compose.yaml with `docker compose config` when
docker is available). The `e2e` test starts the compose project on a random port under a
project name of its own, with the hub's image built either as a user builds it (the
example alone, copied out of the package, installing a wheel built from this checkout) or
from the repository's Dockerfile; it ships the demo runs to it with a relay on this host,
and removes the project, its volumes and the image: `uv run pytest -m e2e -k deploy`."""

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
from importlib import metadata
from pathlib import Path

import pytest

from contraagent._internal import docs
from contraagent._internal.hub.server import read_ingest_tokens, read_read_token
from hub_services import linux_containers

HUB = docs.DIR / "examples" / "hub"
COMPOSE = HUB / "compose.yaml"
DOCKERFILE = HUB / "Dockerfile"
REPO = Path(__file__).resolve().parent.parent
#: The developer's hub image: this checkout's sources and uv.lock.
REPO_DOCKERFILE = REPO / "Dockerfile"
VERSION = metadata.version("contraagent")
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


def _private(path: Path) -> bool:
    """Whether only the owner may read `path`. `make-tokens` sets POSIX modes; on Windows
    a file takes its directory's access list, which a POSIX mode does not describe."""
    return os.name != "posix" or path.stat().st_mode & 0o077 == 0


def _env_file(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _compose(where: Path, project: str, *args: str, env: dict[str, str] | None = None, timeout: float = 120, compose: Path = COMPOSE):
    argv = ["docker", "compose", "-p", project, "-f", str(compose), "--env-file", str(where / ".env"), *args]
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


@pytest.mark.parametrize("dockerfile", [DOCKERFILE, REPO_DOCKERFILE], ids=["example", "repository"])
def test_the_dockerfile_pins_its_bases_and_runs_the_hub_as_a_user_with_a_data_volume(dockerfile):
    lines = dockerfile.read_text().replace("\\\n", " ").splitlines()
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


def test_the_example_builds_from_its_own_directory_with_the_version_it_came_with():
    """Copied out of the installed package, the example has no source tree: its image
    installs contraagent[hub] at CONTRAAGENT_VERSION, or a wheel beside it, and copies
    nothing else in."""
    text = DOCKERFILE.read_text()
    assert not re.findall(r"^COPY (?!--from)", text, re.M)
    assert not re.search(r"pyproject|uv\.lock|\bsrc/", text)
    assert "contraagent[hub]==$CONTRAAGENT_VERSION" in text and "$CONTRAAGENT_WHEEL[hub]" in text
    ignore = [line for line in (HUB / ".dockerignore").read_text().splitlines() if line and not line.startswith("#")]
    assert ignore == ["*", "!*.whl"]
    env = _env_file(HUB / ".env.example")
    assert env["CONTRAAGENT_VERSION"] == VERSION and env["CONTRAAGENT_WHEEL"] == ""


def test_the_repository_image_builds_only_from_what_it_installs():
    ignore = [line for line in (REPO / ".dockerignore").read_text().splitlines() if line and not line.startswith("#")]
    assert ignore[0] == "*"
    assert {line[1:].rstrip("/") for line in ignore if line.startswith("!")} == {"pyproject.toml", "uv.lock", "LICENSE", "src"}
    copied = {p for rest in re.findall(r"^COPY (?!--from)(.+)$", REPO_DOCKERFILE.read_text(), re.M) for p in rest.split()[:-1]}
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
    assert env["POSTGRES_PASSWORD"] == env["RUSTFS_SECRET_KEY"] == "change-me"
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
        assert _private(secrets / f"relay-{host}.env")
    assert re.fullmatch(r"[0-9a-f]{64}", read_read_token(secrets / "read-token"))
    assert _private(secrets)
    env = _env_file(tmp_path / ".env")
    assert set(env) == set(_env_file(HUB / ".env.example")) and "change-me" not in env.values()
    assert env["POSTGRES_PASSWORD"] != env["RUSTFS_SECRET_KEY"]
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
    assert set(services) == {"hub", "postgres", "rustfs", "rustfs-init"}
    hub = services["hub"]
    assert {s["source"] for s in hub["secrets"]} == {"ingest-tokens", "read-token"}
    assert {k: v["condition"] for k, v in hub["depends_on"].items()} == {
        "postgres": "service_healthy",
        "rustfs": "service_healthy",
        "rustfs-init": "service_completed_successfully",
    }
    assert all("healthcheck" in services[s] for s in ("hub", "postgres", "rustfs"))
    assert hub["ports"][0]["target"] == 8790
    assert Path(hub["build"]["context"]) == HUB
    assert hub["build"]["args"] == {"CONTRAAGENT_VERSION": VERSION, "CONTRAAGENT_WHEEL": ""}
    assert hub["image"] == f"contraagent-hub:{VERSION}"
    assert not any("PASSWORD" in arg or "secret" in arg.lower() for arg in hub["command"] if "secrets/" not in arg)
    assert "--retain-days=30" in hub["command"]
    assert Path(config["secrets"]["read-token"]["file"]) == tmp_path / "secrets" / "read-token"


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
        with e:  # an error answer holds its body open until it is closed
            return e.code, e.read()


def _copy_of_the_example(to: Path) -> Path:
    """The example as a user copies it out of the installed package: its own files, none of
    the tokens, passwords or wheels a checkout may hold beside them."""

    def local(where: str, names: list[str]) -> list[str]:
        made = lambda n: n == ".env" or n.endswith(".whl") or (Path(where).name == "secrets" and not n.endswith(".example"))
        return [n for n in names if made(n)]

    shutil.copytree(HUB, to, ignore=local)
    return to


def _build(built_from: str, tmp_path: Path, image: str) -> tuple[Path, Path, dict[str, str]]:
    """Where the compose project's .env and secrets are, its compose.yaml, and the settings
    that build or name its hub image.

    `package`: a copy of the example alone, with a wheel of this checkout beside it (the
    example's local-wheel option), built by compose. `repository`: the image built from the
    repository's Dockerfile, named by CONTRAAGENT_HUB_IMAGE."""
    if built_from == "package":
        if shutil.which("uv") is None:
            pytest.skip("uv is not available to build the wheel")
        where = _copy_of_the_example(tmp_path / "hub")
        built = subprocess.run(["uv", "build", "--wheel", "--out-dir", str(where), str(REPO)], capture_output=True, text=True, timeout=300)
        assert built.returncode == 0, built.stderr
        (wheel,) = where.glob("*.whl")
        settings = {"CONTRAAGENT_WHEEL": wheel.name}
        compose = where / "compose.yaml"
    else:
        built = subprocess.run(["docker", "build", "--tag", image, str(REPO)], capture_output=True, text=True, timeout=600)
        assert built.returncode == 0, built.stderr
        where, settings, compose = tmp_path, {}, COMPOSE
    tokens = subprocess.run(["sh", str(compose.parent / "make-tokens"), "-d", str(where), "e2e-host"], capture_output=True, text=True)
    assert tokens.returncode == 0, tokens.stderr
    return where, compose, {**settings, "CONTRAAGENT_HUB_IMAGE": image, "CONTRAAGENT_SECRETS_DIR": str(where / "secrets")}


@pytest.mark.e2e
@pytest.mark.skipif(not _docker(), reason="docker is not available")
@pytest.mark.parametrize("built_from", ["package", "repository"])
def test_deploy_the_compose_hub_and_ship_the_demo_runs_to_it(tmp_path, demo_runs, built_from):
    if why := linux_containers():
        pytest.skip(why)
    began = time.monotonic()
    tag = uuid.uuid4().hex[:10]
    project, image = f"contraagent-e2e-{tag}", f"contraagent-hub:e2e-{tag}"
    where, compose, env = tmp_path, COMPOSE, {}
    compose_ = lambda *args, timeout=120: _compose(where, project, *args, env=env, timeout=timeout, compose=compose)
    try:
        where, compose, env = _build(built_from, tmp_path, image)
        read = read_read_token(where / "secrets" / "read-token")
        relay_env = _env_file(where / "secrets" / "relay-e2e-host.env")
        port = _free_port()  # after the build, so little time passes before compose binds it
        url = f"http://127.0.0.1:{port}"
        env |= {"CONTRAAGENT_HUB_BIND": "127.0.0.1", "CONTRAAGENT_HUB_PORT": str(port)}
        up = compose_("up", "--detach", "--build" if built_from == "package" else "--no-build", timeout=600)
        assert up.returncode == 0, up.stderr
        deadline = time.monotonic() + 120
        while True:
            try:
                status, body = _get(f"{url}/healthz")
                if status == 200:
                    break
            except OSError:
                status, body = 0, b""
            assert time.monotonic() < deadline, f"/healthz: {status} {body!r}\n{compose_('logs').stdout}"
            time.sleep(0.5)
        assert json.loads(body) == {"status": "ok", "failed": {}}
        healthy = time.monotonic() - began
        assert _get(f"{url}/api/runs")[0] == 401
        version = compose_("exec", "-T", "hub", "contraagent", "--version")
        assert version.stdout.strip() == f"contraagent {VERSION}", version.stderr

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

        assert compose_("stop", "postgres").returncode == 0
        status, body = _get(f"{url}/healthz")
        assert status == 503 and json.loads(body)["failed"].keys() >= {"records"}, body
        print(f"\ndeploy e2e ({built_from}): healthy after {healthy:.1f}s, relayed after {relayed:.1f}s")
    finally:
        down = compose_("down", "--volumes", "--remove-orphans", timeout=180) if env else None
        subprocess.run(["docker", "image", "rm", "--force", image], capture_output=True, timeout=60)
        assert down is None or down.returncode == 0, down.stderr
