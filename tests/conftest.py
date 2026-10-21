"""Fixtures shared by the test modules, and what the whole test process does alike."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.hookimpl(tryfirst=True)  # before pytest's tmpdir plugin reads --basetemp
def pytest_configure(config) -> None:
    """A retried attempt does not wait out its backoff here: the wait is random and seconds
    long, and what it is (`backoff_s`) has a test of its own. Subprocesses (the docs' example
    tests) keep the real wait.

    Each session has a temporary root of its own, unless `--basetemp` names one. pytest's
    shared root, `<temp dir>/pytest-of-<user>`, is cleaned by every session that ends: it
    removes the old directories of other sessions there, and two sessions that end at once
    can remove the same one. The one that loses that race warns, which fails the session
    after every test passed. A pytest-xdist worker is given a directory under its
    controller's root; the controller removes the root at the end (`pytest_unconfigure`)."""
    from contraagent.engine import RetryingRunner

    RetryingRunner.backoff = staticmethod(lambda base, attempt: 0.0)
    if config.option.basetemp is None and not hasattr(config, "workerinput"):
        config.option.basetemp = config._contraagent_basetemp = tempfile.mkdtemp(prefix="contraagent-pytest-")


def pytest_unconfigure(config) -> None:
    """The controller removes the session's own temporary root (`pytest_configure`)."""
    root = getattr(config, "_contraagent_basetemp", None)
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)


@pytest.hookimpl(tryfirst=True)  # before xdist reads the groups
def pytest_collection_modifyitems(config, items) -> None:
    """Live and perf tests run on one worker each under pytest-xdist: the live modules share the
    `live-demo` directory (one wipes it as it starts) and the coding agents' rate limits; a perf
    test times itself and needs the machine to itself as far as it can."""
    for item in items:
        for name in ("live", "perf"):
            if item.get_closest_marker(name) is not None:
                item.add_marker(pytest.mark.xdist_group(name))


def pytest_sessionfinish(session) -> None:
    """Each process removes the Postgres and RustFS containers it started (`hub_services`);
    under pytest-xdist the workers share theirs, and the controller removes those."""
    from hub_services import stop_all, stop_shared

    stop_all()
    if not hasattr(session.config, "workerinput"):
        stop_shared(os.getpid())


#: The home directory of the user running the tests, before any test is given its own.
_HOST_HOME = Path.home()

#: Where a coding agent, a tool or contraagent itself keeps a user's config, cache, data and state.
USER_DIRS = ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")


def _become_new_user(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make this process's environment that of a user of its own: an empty home and empty
    config, cache, data and state directories under `root`, and none of the host's
    credentials.

    Removed are the variables a coding agent reads a credential from (`scrubbed`), those that
    tie a process to a Claude Code session (`PARENT_SESSION_ENV`), every `AWS_*` one (boto3
    reads its credentials, profile, config files, endpoint and region from them) and every
    `CONTRAAGENT_*` one. boto3 does not ask the instance metadata service for a role either,
    which is a network call. A test that needs a credential sets it itself.

    Docker keeps the host's config (`DOCKER_CONFIG`): the hub's tests run their containers
    on the host's docker (`hub_services`), and that config names the daemon to use."""
    from contraagent._internal.backends.base import PARENT_SESSION_ENV
    from contraagent._internal.backends.credentials import scrubbed

    docker_config = os.environ.get("DOCKER_CONFIG") or str(_HOST_HOME / ".docker")
    kept = scrubbed(dict(os.environ), PARENT_SESSION_ENV)
    for name in list(os.environ):
        if name not in kept or name.startswith(("AWS_", "CONTRAAGENT_")):
            monkeypatch.delenv(name)
    dirs = {"HOME": root / "home", **{name: root / name.lower() for name in USER_DIRS}}
    for name, path in dirs.items():
        path.mkdir(parents=True)
        monkeypatch.setenv(name, str(path))
    monkeypatch.setenv("USERPROFILE", str(dirs["HOME"]))  # Path.home() on Windows
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("DOCKER_CONFIG", docker_config)


@pytest.fixture(scope="session", autouse=True)
def isolated_session(tmp_path_factory) -> Iterator[None]:
    """The session's and the modules' fixtures run as a user of their own (`_become_new_user`)."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        _become_new_user(monkeypatch, tmp_path_factory.mktemp("session-user"))
        yield


@pytest.fixture(autouse=True)
def isolated_test(tmp_path_factory, monkeypatch) -> None:
    """Each test runs as a user of its own (`_become_new_user`): what it sees is the same on
    every machine, and it reads and writes none of the developer's files."""
    _become_new_user(monkeypatch, tmp_path_factory.mktemp("user"))


@pytest.fixture(scope="session")
def host_home() -> Path:
    """The home directory of the user running the tests, for a test about this machine; each
    test's own home is another one (`isolated_test`)."""
    return _HOST_HOME


@pytest.fixture(scope="session")
def demo_runs(tmp_path_factory) -> Path:
    """The demo pipeline's runs (failover, resends, refused inputs, transcripts, contracts),
    made once per test process. Tests read them; one that changes a run copies it first."""
    from contraagent.docs.examples.demo import run as demo

    where = tmp_path_factory.mktemp("demo")
    old = Path.cwd()
    os.chdir(where)
    try:
        demo.main(["--no-serve", "--fast"])
    finally:
        os.chdir(old)
    return where / "demo-runs"
