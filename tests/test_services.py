"""Services: the long-lived helper a claim name stands for, started for the first task that
claims the name and stopped when the run ends."""

import contextlib
import json
import os
import signal
import threading
import time

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task, service_address
from contraagent.monitor import Monitor
from contraagent.testing import StubAgent


class Written(BaseModel):
    path: str


class Found(BaseModel):
    address: str


def written(launch):
    return {"path": f"out/{launch.unit}.md"}


class Server:
    """A service that counts its starts and stops, and the tasks that hold it at once."""

    def __init__(self, *, fail_start: Exception | None = None, fail_stop: Exception | None = None, start_s: float = 0.0):
        self.calls: list[tuple[str, str]] = []
        self.up: set[str] = set()
        self.fail_start, self.fail_stop, self.start_s = fail_start, fail_stop, start_s
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def __call__(self, name: str):
        time.sleep(self.start_s)
        with self._lock:
            self.calls.append(("start", name))
        if self.fail_start is not None:
            raise self.fail_start
        self.up.add(name)
        try:
            yield f"http://{name}.local:{len(self.calls)}"
        finally:
            self.up.discard(name)
            with self._lock:
                self.calls.append(("stop", name))
            if self.fail_stop is not None:
                raise self.fail_stop


def pipeline(tmp_path, agent=None, **options) -> Pipeline:
    lines: list[str] = options.pop("lines", [])
    return Pipeline(
        None,
        runs_dir=tmp_path / "runs",
        backends=(agent or StubAgent()).backends(),
        cwd=tmp_path,
        log=lines.append,
        retry_wait_s=options.pop("retry_wait_s", 0),
        **options,
    )


def events(report) -> list[dict]:
    path = report.run_dir / "services.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def test_the_first_claim_starts_a_service_that_tasks_share_and_the_run_s_end_stops_it(tmp_path):
    server = Server()
    seen: list[tuple[str, str | None, bool]] = []

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        address = service_address("index")
        seen.append((unit, address, "index" in server.up))
        time.sleep(0.05)
        return Found(address=address or "")

    report = pipeline(tmp_path, services={"index": server}, claim_capacity={"index": 2}).run(lambda: [look(u) for u in "abcd"])
    assert report.ok, report.failed
    assert server.calls == [("start", "index"), ("stop", "index")]  # one service for every task
    assert {address for _, address, _ in seen} == {"http://index.local:1"}
    assert all(up for _, _, up in seen)
    start, stop = events(report)
    assert start["event"] == "start" and start["name"] == "index" and start["address"] == "http://index.local:1"
    assert start["key"] in {f"python:look-{u}" for u in "abcd"} and "error" not in start
    assert stop["event"] == "stop" and stop["cause"] == "run_end" and "error" not in stop


def test_an_agent_task_finds_the_address_in_its_environment(tmp_path):
    server = Server()
    lookup = agent_task("lookup", instructions="Ask the index.", output=Written, claims=["db:{unit}"], max_turns=3, timeout_s=60)
    plain = agent_task("plain", instructions="Write.", output=Written, max_turns=3, timeout_s=60)
    agent = StubAgent({"lookup": written, "plain": written})

    def flow():
        lookup("alpha")
        lookup("beta")
        plain("gamma")

    report = pipeline(tmp_path, agent, services={"db:*": server}).run(flow)
    assert report.ok, report.failed
    env = {launch.key: launch.launch.env for launch in agent.launches}
    assert env["lookup-alpha"]["CONTRAAGENT_SERVICE_DB_ALPHA"].startswith("http://db:alpha.local:")
    assert "CONTRAAGENT_SERVICE_DB_BETA" not in env["lookup-alpha"]  # only the services it claims
    assert env["lookup-beta"]["CONTRAAGENT_SERVICE_DB_BETA"].startswith("http://db:beta.local:")
    assert not any(k.startswith("CONTRAAGENT_SERVICE_") for k in env["plain-gamma"])
    # A pattern starts one service for each name it matches.
    assert sorted(server.calls) == [("start", "db:alpha"), ("start", "db:beta"), ("stop", "db:alpha"), ("stop", "db:beta")]


def test_a_start_that_raises_fails_the_tasks_that_claim_the_name_and_the_run_goes_on(tmp_path):
    server = Server(fail_start=OSError("port 9000 in use"))
    lookup = agent_task("lookup", instructions="Ask.", output=Written, claims=["index"], max_turns=3, timeout_s=60)

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address="x")

    @python_task
    def other(unit: str) -> Found:
        return Found(address="y")

    agent = StubAgent({"lookup": written})

    def flow():
        lookup("a")
        look("b")
        other("c")

    report = pipeline(tmp_path, agent, services={"index": server}).run(flow)
    assert server.calls == [("start", "index")]  # tried once in the run
    assert report.results["python:other-c"].ok
    for key in ("lookup-a", "python:look-b"):
        result = report.results[key]
        assert result.stop == "launch_failed"
        assert result.reason == "service 'index' did not start: OSError: port 9000 in use"
    assert not agent.launches  # no agent launched without its service
    rows = {row["key"]: row for row in journal(report)}
    assert rows["lookup-a"]["stop"] == "launch_failed" and rows["python:look-b"]["stop"] == "launch_failed"
    (start,) = events(report)
    assert start["event"] == "start" and start["error"] == "OSError: port 9000 in use" and "address" not in start


def test_a_stop_that_raises_is_recorded_and_the_service_counts_as_stopped(tmp_path):
    server = Server(fail_stop=RuntimeError("still busy"))
    lines: list[str] = []

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("index") or "")

    report = pipeline(tmp_path, services={"index": server}, lines=lines).run(lambda: look("a"))
    assert report.ok
    _, stop = events(report)
    assert stop["event"] == "stop" and stop["error"] == "RuntimeError: still busy"
    assert any("[service] index: its stop raised RuntimeError: still busy" in line for line in lines)


def test_service_idle_s_stops_an_idle_service_and_the_next_claim_starts_it_again(tmp_path):
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("index") or "")

    def flow():
        yield look("a")
        yield look("b")

    report = pipeline(tmp_path, services={"index": server}, service_idle_s=0).run(flow)
    assert report.ok, report.failed
    assert server.calls == [("start", "index"), ("stop", "index")] * 2
    assert [(e["event"], e.get("cause")) for e in events(report)] == [("start", None), ("stop", "idle")] * 2


def test_an_idle_timer_that_a_new_claim_cancels_keeps_the_service_up(tmp_path):
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("index") or "")

    def flow():
        yield look("a")
        yield look("b")

    report = pipeline(tmp_path, services={"index": server}, service_idle_s=30).run(flow)
    assert report.ok, report.failed
    assert server.calls == [("start", "index"), ("stop", "index")]
    assert events(report)[-1]["cause"] == "run_end"


def test_a_resumed_run_starts_a_service_only_for_tasks_that_run_again(tmp_path):
    server = Server()
    calls = {"n": 0}

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        calls["n"] += 1
        return Found(address=service_address("index") or "")

    p = pipeline(tmp_path, services={"index": server})
    assert p.run(lambda: look("a"), run_id="r").ok
    report = p.run(lambda: look("a"), run_id="r", resume=True)
    assert report.results["python:look-a"].stop == "skipped"
    assert calls["n"] == 1 and server.calls == [("start", "index"), ("stop", "index")]

    failing = Server(fail_start=OSError("down"))
    q = pipeline(tmp_path, services={"index": failing})
    assert not q.run(lambda: look("b"), run_id="s").ok
    report = pipeline(tmp_path, services={"index": server}).run(lambda: look("b"), run_id="s", resume=True)
    assert report.ok  # a resumed run tries the start again
    assert [e["event"] for e in events(report)] == ["start", "start", "stop"]


def test_a_run_that_raises_stops_its_services(tmp_path):
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        raise KeyboardInterrupt  # leaves the queue, as an error of the run's own would

    with pytest.raises(KeyboardInterrupt):
        pipeline(tmp_path, services={"index": server}).run(lambda: look("a"), run_id="r")
    assert server.calls == [("start", "index"), ("stop", "index")]
    rows = [json.loads(line) for line in (tmp_path / "runs" / "r" / "services.jsonl").read_text().splitlines()]
    assert rows[-1]["cause"] == "run_end"


@pytest.mark.skipif(os.name == "nt", reason="a signal to the process itself")
def test_ctrl_c_stops_every_started_service(tmp_path):
    if threading.current_thread() is not threading.main_thread():  # pragma: no cover
        pytest.skip("signal handlers live on the main thread")
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(0.2)  # a Python task runs to its end: the signal stops its service under it
        return Found(address="x")

    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        with pytest.raises(KeyboardInterrupt):
            pipeline(tmp_path, services={"index": server}).run(lambda: look("a"), run_id="r")
    finally:
        signal.signal(signal.SIGINT, previous)
    assert server.calls == [("start", "index"), ("stop", "index")]
    rows = [json.loads(line) for line in (tmp_path / "runs" / "r" / "services.jsonl").read_text().splitlines()]
    assert [(r["event"], r.get("cause")) for r in rows] == [("start", None), ("stop", "interrupted")]


def test_tasks_that_claim_the_name_while_it_starts_wait_for_that_start(tmp_path):
    server = Server(start_s=0.2)

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        assert "index" in server.up
        return Found(address=service_address("index") or "")

    report = pipeline(tmp_path, services={"index": server}, claim_capacity={"index": 3}).run(lambda: [look(u) for u in "abc"])
    assert report.ok, report.failed
    assert server.calls == [("start", "index"), ("stop", "index")]


def test_service_address_names_what_the_running_task_claims(tmp_path):
    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("other") or "")

    report = pipeline(tmp_path, services={"index": Server()}).run(lambda: look("a"))
    assert "claims no service of that name (its services: index)" in report.results["python:look-a"].reason
    with pytest.raises(KeyError, match="its services: none"):
        service_address("index")


def test_a_task_that_claims_two_services_of_one_variable_fails(tmp_path):
    @python_task(claims=["a-b", "a_b"])
    def look(unit: str) -> Found:
        return Found(address="x")

    report = pipeline(tmp_path, services={"a*": Server()}).run(lambda: look("a"))
    result = report.results["python:look-a"]
    assert result.stop == "launch_failed" and "share the variable CONTRAAGENT_SERVICE_A_B" in result.reason


def test_services_are_checked_as_the_pipeline_is_made(tmp_path):
    with pytest.raises(TypeError, match="is not a Service"):
        Pipeline(None, services={"index": "http://localhost"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="is not a claim name"):
        Pipeline(None, services={"": Server()})
    with pytest.raises(ValueError, match="service_idle_s=-1"):
        Pipeline(None, service_idle_s=-1)


def test_check_names_a_service_no_task_claims(tmp_path):
    @python_task(claims=["db:{unit}"])
    def look(unit: str) -> Found:
        return Found(address="x")

    report = pipeline(tmp_path, services={"db:*": Server(), "index": Server()}).check(lambda: look("a"))
    assert report.ok
    assert [w for w in report.warnings if "service" in w] == [
        "services: 'index' is claimed by no task of the run, so it never starts (contraagent docs tasks, Services)"
    ]


def test_check_reports_a_task_whose_services_share_a_variable(tmp_path):
    @python_task(claims=["a-b", "a_b"])
    def look(unit: str) -> Found:
        return Found(address="x")

    report = pipeline(tmp_path, services={"a*": Server()}).check(lambda: look("a"))
    assert not report.ok and "tasks" in report.topics
    assert any("python:look-a: services 'a-b' and 'a_b' share the variable CONTRAAGENT_SERVICE_A_B" in e for e in report.errors)


def test_the_monitor_shows_each_start_of_a_service_with_its_stop(tmp_path):
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("index") or "")

    def flow():
        yield look("a")
        yield look("b")

    report = pipeline(tmp_path, services={"index": server}, service_idle_s=0).run(flow)
    assert report.ok
    plan = Monitor(tmp_path / "runs").plan(report.run_id)
    spans = plan["services"]
    assert [(s["name"], s["address"], s["stop_cause"]) for s in spans] == [
        ("index", "http://index.local:1", "idle"),
        ("index", "http://index.local:3", "idle"),
    ]
    assert all(s["stopped_at"] >= s["started_at"] and s["key"].startswith("python:look-") for s in spans)

    failed = pipeline(tmp_path, services={"index": Server(fail_start=OSError("no"))}).run(lambda: look("c"), run_id="failed")
    (span,) = Monitor(tmp_path / "runs").plan(failed.run_id)["services"]
    assert span["start_error"] == "OSError: no" and not span.get("stopped_at") and span["address"] is None


def test_the_example_shares_one_index_server_among_the_tasks_that_claim_it(tmp_path):
    from contraagent.docs.examples.services import flow

    agent = StubAgent({"summarize": {"text": "t"}, "review": {"missing": []}})
    p = flow.pipeline(runs_dir=tmp_path / "runs", cwd=tmp_path, backends=agent.backends(), log=lambda line: None)
    report = p.run(flow.topics, names=["caching", "queues", "storage"])
    assert report.ok, report.failed
    out = report.run_dir / "out" / "find_sources"
    assert json.loads((out / "caching.json").read_text())["paths"] == ["notes/caching.md", "notes/eviction.md"]
    assert json.loads((out / "storage.json").read_text())["paths"] == []
    (start, stop) = events(report)
    assert start["address"].startswith("http://127.0.0.1:") and stop["cause"] == "run_end"
    (review,) = [launch for launch in agent.launches if launch.kind == "review"]
    assert review.launch.env["CONTRAAGENT_SERVICE_INDEX"] == start["address"]
    assert "$CONTRAAGENT_SERVICE_INDEX" in review.prompt


def test_a_stub_run_starts_services_as_any_run_does(tmp_path):
    server = Server()

    @python_task(claims=["index"])
    def look(unit: str) -> Found:
        return Found(address=service_address("index") or "")

    stub = StubAgent(execute=["look"])
    p = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub, services={"index": server}, log=lambda line: None)
    report = p.run(lambda: look("a"))
    assert report.ok, report.failed
    assert json.loads((report.run_dir / "out" / "look" / "a.json").read_text())["address"] == "http://index.local:1"
    assert server.calls == [("start", "index"), ("stop", "index")]
