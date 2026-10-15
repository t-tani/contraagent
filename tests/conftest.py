"""Fixtures shared by the test modules, and what the whole test process does alike."""

import os
from pathlib import Path

import pytest


def pytest_configure(config) -> None:
    """A retried attempt does not wait out its backoff here: the wait is random and seconds
    long, and what it is (`backoff_s`) has a test of its own. Subprocesses (the docs' example
    tests) keep the real wait."""
    from contraagent.execution.runner import RetryingRunner

    RetryingRunner.backoff = staticmethod(lambda base, attempt: 0.0)


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
