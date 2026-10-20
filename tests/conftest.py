"""Fixtures shared by the test modules, and what the whole test process does alike."""

import os
import shutil
import tempfile
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
    """Under pytest-xdist the controller removes the Postgres and RustFS containers its workers
    shared (`hub_services`); a worker leaves them to it."""
    if not hasattr(session.config, "workerinput"):
        from hub_services import stop_shared

        stop_shared(os.getpid())


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
