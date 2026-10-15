"""End to end with a stub backend: config -> routing -> Run/AgentRunner/queue -> journal -> monitor."""

import json
import logging
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import (
    Backend,
    CursorStore,
    Launch,
    LaunchResult,
    PipelineConfig,
    RateLimit,
    RetryingRunner,
    Route,
    Router,
    RoutingPlan,
    Run,
    RunLocked,
    Stop,
    Task,
    TaskAdapter,
    register_normalizer,
)
from contraagent.backends.omp import trace as omp_trace
from contraagent.monitor import Monitor

register_normalizer("stub", omp_trace.normalize_event, omp_trace.normalize_text_line)

TOML = """
[defaults]
agent = "stub"
effort = "high"

[tasks.write]
max_turns = 5
timeout_s = 30
model = "m-write"

[tasks.read]
max_turns = 5
timeout_s = 30
retries = 2
"""


class StubBackend(Backend):
    name = "stub"
    binary = "stub"

    def __init__(self, script=None):
        super().__init__()
        self.launches: list[Launch] = []
        self.script = script or (lambda launch, n: Stop.COMPLETED)
        self._n = 0
        self._lock = threading.Lock()

    def argv(self, launch):
        return ["stub", "--model", launch.model]

    def env(self, launch):
        return {}

    def run(self, launch):
        with self._lock:
            self.launches.append(launch)
            self._n += 1
            n = self._n
        stop = self.script(launch, n)
        if launch.stream_path:
            Path(launch.stream_path).parent.mkdir(parents=True, exist_ok=True)
            Path(launch.stream_path).write_text("hello from the agent\n")
        rl = RateLimit(retry_after_s=60) if stop == Stop.RATE_LIMITED else None
        return LaunchResult(
            label=launch.label, agent=self.name, stop=stop, ok=stop == Stop.COMPLETED, model=launch.model, wall_s=0.1, rate_limit=rl
        )


class Adapter(TaskAdapter):
    def prompt(self, task, backend):
        return f"do {task.params.get('what', task.key)}"


def load_config(tmp_path):
    cfg = tmp_path / "pipeline.toml"
    cfg.write_text(TOML)
    return PipelineConfig.load(cfg)


def build(tmp_path, backend, *, routers=None, kinds=("write", "read")):
    plan = RoutingPlan.build(load_config(tmp_path), kinds, {"stub": backend})
    run = Run("r1", tmp_path / "runs", log=lambda line: None)
    runner = run.agent_runner(backend, plan.configs, adapter=Adapter(), routers=routers, keep_transcripts=True, cwd=tmp_path)
    return run, runner, plan


def test_config_routing_and_budgets(tmp_path, caplog):
    backend = StubBackend()
    run, runner, plan = build(tmp_path, backend)
    assert plan.configs["write"].model == "m-write" and plan.configs["write"].effort == "high"
    with pytest.raises(ValueError, match="has no budget"):  # a kind with no [tasks.other] table
        RoutingPlan.build(load_config(tmp_path), ["write", "read", "other"], {"stub": backend})
    with caplog.at_level(logging.WARNING, logger="contraagent.routing"):
        RoutingPlan.build(load_config(tmp_path), ["write"], {"stub": backend})  # a table no kind reads:
    assert "[tasks.read] is not a kind of this run" in caplog.text  # said, not fatal


def test_queue_runs_dag_journals_and_resumes(tmp_path):
    backend = StubBackend()
    run, runner, _ = build(tmp_path, backend)
    retrying = RetryingRunner(runner, on_attempt=run.record_attempt)
    a = Task("write", unit="u", key="write-u")
    b = Task("read", unit="u", key="read-u", after=("write-u",))
    q = run.queue(retrying, max_concurrent=2)
    q.add(b)
    q.add(a)
    q.run()
    rows = run.rows()
    assert [r["key"] for r in rows] == ["write-u", "read-u"]  # `after` ordered them
    assert all(r["ok"] and r["unit"] == "u" and r["run_id"] == "r1" for r in rows)
    # the launch carries the run/task identity for the monitor, in env and prompt
    first = backend.launches[0]
    assert first.env["CONTRAAGENT_TASK"] == "write-u" and first.prompt.startswith("TELEMETRY run=r1")
    assert first.model == "m-write"

    # a resumed run skips what the journal says finished
    backend.launches.clear()
    q2 = run.queue(retrying, resume=True)
    q2.add(Task("write", unit="u", key="write-u"))
    q2.add(Task("read", unit="u", key="read-u", after=("write-u",)))
    q2.run()
    assert backend.launches == []


def test_python_steps_and_run_lock(tmp_path):
    run = Run("r2", tmp_path / "runs", log=lambda line: None)
    order = []
    run.run_python_steps([("one", lambda: order.append(1)), ("two", lambda: order.append(2))])
    assert order == [1, 2]
    assert [(r["kind"], r["executor"], r["agent"]) for r in run.rows()] == [("one", "python", ""), ("two", "python", "")]
    with pytest.raises(RunLocked):
        Run("r2", tmp_path / "runs")
    boom = Run("r3", tmp_path / "runs", log=lambda line: None)
    with pytest.raises(RuntimeError):
        boom.run_python_steps([("bad", lambda: (_ for _ in ()).throw(RuntimeError("x"))), ("never", lambda: None)])
    assert [r["kind"] for r in boom.rows()] == ["bad"]


def test_rate_limit_fails_over_to_next_route(tmp_path):
    def script(launch, n):
        return Stop.RATE_LIMITED if launch.model == "primary" else Stop.COMPLETED

    backend = StubBackend(script)
    router = Router(Route("stub", "primary"), (Route("stub", "backup"),))
    run, runner, _ = build(tmp_path, backend, routers={"write": router})
    runner.configs["write"] = runner.configs["write"].with_(model="primary")
    res = RetryingRunner(runner).run(Task("write", key="w", unit="u"))
    assert res.ok and res.route.endswith("stub/backup")
    assert [h["stop"] for h in res.hops] == ["rate_limited", "completed"]


def test_retry_then_exhausted(tmp_path):
    backend = StubBackend(lambda launch, n: Stop.ERROR)
    run, runner, _ = build(tmp_path, backend)
    seen = []
    runner.configs["read"] = runner.configs["read"].with_(retries=2, retry_backoff_base=0.0)
    res = RetryingRunner(runner, on_attempt=run.record_attempt, on_exhausted=lambda t, r: seen.append(t.key)).run(
        Task("read", key="r", unit="u")
    )
    assert not res.ok and len(backend.launches) == 2 and seen == ["r"]
    assert [row["attempt"] for row in run.rows()] == [0, 1]


def test_cursor_store(tmp_path):
    cur = CursorStore(tmp_path / "cursor.json", "r1", stages=["a", "b"], steps=["s1", "s2"])
    cur.advance_stage("a")
    cur.advance_stage("b")
    assert cur.advance_stage("a").stage == "b"  # back-guard
    with pytest.raises(ValueError):
        cur.advance_stage("zzz")
    cur.advance_step("u", "s1")
    cur.advance_step("u", "s2")
    cur.record("stall", {"why": "x"})
    view = cur.resume_view()
    assert view["resume_stage"] == "b" and view["units"]["u"]["completed"] == ["s1"]
    cur.set_inflight("u", ["h1"])
    assert cur.resume_view()["units"]["u"]["redispatch_item_ids"] == ["h1"]
    with pytest.raises(RuntimeError):  # this very process is alive, so it is not stale
        cur.set_inflight("u", ["h2"])
    cur.clear_inflight("u")
    assert cur.steps_to_run("u") == ["s1", "s2"]


def test_monitor_views(tmp_path):
    backend = StubBackend()
    run, runner, _ = build(tmp_path, backend)
    q = run.queue(RetryingRunner(runner, on_attempt=run.record_attempt), max_concurrent=1)
    q.add(Task("write", unit="u", key="write-u"))
    q.run()
    mon = Monitor(run.runs_dir, panels={"facts": lambda r: {"run": r.id}}, task_detail=lambda r, t, rows: {"extra": len(rows)})
    runs = mon.runs()
    assert runs[0]["run"] == "r1" and runs[0]["attempts"] == 1 and runs[0]["running"]  # this process is the run
    d = mon.task_detail("r1", "write-u")
    assert d["stream"] == "write-u" and d["extra"] == 1 and len(d["rows"]) == 1
    page, total = mon.stream("r1", "write-u", 0)
    assert total == 1 and page["events"] and page["behind"] == 0
    assert mon.panel("facts", "r1") == {"run": "r1"}
    snap = mon.procs("r1")
    assert snap["alive"] and snap["pid"] == run_pid(run)


def run_pid(run):
    return json.loads((run.dir / "run.json").read_text())["pid"]


def test_http_endpoints(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("sse_starlette")
    from fastapi.testclient import TestClient

    from contraagent.monitor.server import create_app

    backend = StubBackend()
    run, runner, _ = build(tmp_path, backend)
    q = run.queue(RetryingRunner(runner, on_attempt=run.record_attempt), max_concurrent=1)
    q.add(Task("write", unit="u", key="write-u"))
    q.run()
    client = TestClient(
        create_app(Monitor(run.runs_dir, panels={"facts": lambda r: {"ok": 1}})), base_url="http://127.0.0.1"
    )  # the monitor answers only local Host names
    assert [x["name"] for x in client.get("/api/info").json()["panels"]] == ["facts"]
    assert client.get("/api/runs").json()[0]["run"] == "r1"
    assert client.get("/api/runs/r1/journal").json()["total"] == 1
    assert client.get("/api/runs/r1/task/write-u").json()["rows"][0]["stop"] == "completed"
    assert client.get("/api/runs/r1/stream/write-u").json()["events"]
    assert client.get("/api/runs/r1/panels/facts").json() == {"ok": 1}
    assert client.get("/api/runs/r1/panels/nope").status_code == 404
    for path in ("/", "/app.js"):  # the built UI: styles live in its elements
        assert client.get(path).status_code == 200
    assert client.get("/etc.passwd").status_code == 404


def test_plan_graph_stages_and_finish(tmp_path):
    from contraagent import make_python_task

    backend = StubBackend()
    run, runner, _ = build(tmp_path, backend)
    q = run.queue(run.python_runner(RetryingRunner(runner, on_attempt=run.record_attempt)), max_concurrent=2)
    for u in ("a", "b"):
        q.add(make_python_task("prepare", lambda: None, unit=u))
        q.add(Task("write", unit=u, key=f"write-{u}", after=(f"python:prepare-{u}",)))
        q.add(Task("read", unit=u, key=f"read-{u}", after=(f"write-{u}",)))
    q.add(Task("read", unit="all", key="late", after=("never-queued",)))  # stays pending
    q.run()
    mon = Monitor(run.runs_dir)
    plan = mon.plan("r1")
    assert [s["id"] for s in plan["groups"]] == ["prepare", "write", "read"]  # by kind, ordered by depth
    read = next(s for s in plan["groups"] if s["id"] == "read")
    assert read["done"] == 2 and read["pending"] == 1 and read["total"] == 3
    assert {n["key"]: n["state"] for n in plan["nodes"]}["late"] == "pending"
    assert json.loads((run.dir / "run.json").read_text())["max_workers"] == 2
    assert mon.runs()[0]["running"]
    run.finish()
    assert not mon.runs()[0]["running"] and not mon.procs("r1")["alive"]


class Doc(BaseModel):
    n: int


def test_python_tasks_are_checked_by_contracts(tmp_path):
    from contraagent import InputContract, OutputContract, make_python_task

    run = Run("rc", tmp_path / "runs", log=lambda line: None)
    out, src = tmp_path / "out.json", tmp_path / "src.json"
    ran = []

    def good():
        ran.append("good")
        out.write_text('{"n": 1}')

    def bad():
        ran.append("bad")
        out.write_text('{"n": "x"}')

    def nothing():
        ran.append("nothing")

    def go(task):
        q = run.queue(run.python_runner(cwd=tmp_path), max_concurrent=1)
        q.add(task)
        q.run()
        return run.rows()[-1]

    row = go(make_python_task("good", good, unit="u", output_contracts=[OutputContract(out, Doc)]))
    assert row["ok"] and row["rounds"] == 1 and row["stop"] == "completed"
    out.unlink()
    row = go(make_python_task("bad", bad, unit="u", output_contracts=[OutputContract(out, Doc)]))
    assert not row["ok"] and row["stop"] == "invalid_output" and "n:" in row["round_errors"][-1][0]
    out.write_text('{"n": 1}')  # a file left by an earlier run must not pass
    row = go(make_python_task("stale", nothing, unit="u", output_contracts=[OutputContract(out, Doc)]))
    assert row["stop"] == "invalid_output" and "was not rewritten" in row["reason"]
    ran.clear()
    row = go(make_python_task("needs", good, unit="u", input_contracts=[InputContract(src, Doc)]))
    assert row["stop"] == "invalid_input" and ran == []  # refused before running
    src.write_text('{"n": 2}')
    assert go(make_python_task("needs2", good, unit="u", input_contracts=[InputContract(src, Doc)]))["ok"]

    mon = Monitor(run.runs_dir)
    outs = {c["key"]: c for c in mon.outputs("rc")["contracts"]}
    assert outs["python:bad-u"]["outputs"][0]["status"] == "invalid"
    assert outs["python:good-u"]["outputs"][0]["status"] == "valid"
    assert outs["python:good-u"]["outputs"][0]["fields"] == [{"name": "n", "type": "integer", "required": True}]
    assert outs["python:good-u"]["executor"] == "python"


def test_an_off_contract_input_is_refused_once_and_shown_as_not_run(tmp_path):
    from contraagent import InputContract, OutputContract

    class Needs(TaskAdapter):
        def input_contracts(self, task):
            return (InputContract(tmp_path / "missing.json", Doc),)

        def output_contracts(self, task):
            return (OutputContract(tmp_path / "out.json", Doc),)

    backend = StubBackend()
    run, runner, _ = build(tmp_path, backend)
    runner.adapter = Needs()
    runner.configs["read"] = runner.configs["read"].with_(retries=3, retry_backoff_base=0.0)
    res = RetryingRunner(runner, on_attempt=run.record_attempt).run(Task("read", key="r", unit="u"))
    assert res.stop == "invalid_input" and backend.launches == []  # refused before any launch
    assert len(run.rows()) == 1  # and not retried: the file will not appear by itself
    out = Monitor(run.runs_dir).outputs("r1")
    assert out["tally"]["refused"] == 1 and out["tally"]["failed"] == 0  # "not run", not "task failed"
    [spec] = out["contracts"][0]["outputs"]
    assert spec["status"] == "refused" and "required input is missing" in spec["errors"][0]


def test_a_retry_waits_up_to_its_base_doubled_per_attempt(monkeypatch):
    """`retry_backoff_base` is seconds, doubled per attempt (full jitter: a draw up to it);
    a base of 0 waits nothing, the first attempt included."""
    from contraagent.execution import runner

    monkeypatch.setattr(runner.random, "uniform", lambda low, high: high)  # the longest wait
    assert [runner.backoff_s(2.0, a) for a in range(3)] == [2.0, 4.0, 8.0]
    assert runner.backoff_s(0.0, 0) == 0.0
