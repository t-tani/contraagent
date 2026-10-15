"""`Pipeline(scopes=, enrichers=)` around each attempt of a Python task, as around each
attempt of an agent task."""

import contextlib
import json

from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task
from contraagent.testing import StubAgent


class Count(BaseModel):
    n: int


class Note(BaseModel):
    text: str


def pipeline(tmp_path, **options) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None, **options)


def rows(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def recording_scope(seen: list):
    @contextlib.contextmanager
    def scope(task):
        seen.append(("enter", task.executor, task.kind, task.attempt))
        try:
            yield
        except BaseException as exc:  # pragma: no cover - the test fails on it
            seen.append(("raised", exc))
            raise
        seen.append(("exit", task.executor, task.kind, task.attempt))

    return scope


def test_a_scope_is_entered_and_exited_around_each_attempt_retries_included(tmp_path):
    seen: list = []
    left = [ConnectionError("refused"), TimeoutError("slow")]

    @python_task(retries=2, retry_on=(ConnectionError, TimeoutError))
    def count(unit: str) -> Count:
        seen.append(("call", len(left)))
        if left:
            raise left.pop(0)
        return Count(n=1)

    report = pipeline(tmp_path, scopes=[recording_scope(seen)]).run(lambda: count("a"))
    assert report.results["python:count-a"].ok
    # The function's exception is the attempt's result: each scope exits without one.
    assert seen == [
        ("enter", "python", "count", 0),
        ("call", 2),
        ("exit", "python", "count", 0),
        ("enter", "python", "count", 1),
        ("call", 1),
        ("exit", "python", "count", 1),
        ("enter", "python", "count", 2),
        ("call", 0),
        ("exit", "python", "count", 2),
    ]


def test_scopes_nest_in_order_and_wrap_the_output_check(tmp_path):
    seen: list[str] = []

    def named(name):
        @contextlib.contextmanager
        def scope(task):
            seen.append(f"enter {name}")
            yield
            seen.append(f"exit {name}")

        return scope

    def check(path, value):
        seen.append("check")
        return []

    @python_task(validators=[check])
    def count(unit: str) -> Count:
        return Count(n=1)

    report = pipeline(tmp_path, scopes=[named("outer"), named("inner")]).run(lambda: count("a"))
    assert report.ok
    assert seen == ["enter outer", "enter inner", "check", "exit inner", "exit outer"]


def test_an_enricher_changes_a_python_task_s_verdict_and_adds_a_payload(tmp_path):
    calls: list[str] = []

    class Empty:
        """A count of 0 is no result."""

        def snapshot(self, task):
            calls.append(f"snapshot {task.attempt}")
            return "before"

        def enrich(self, task, before, result):
            calls.append(f"enrich {task.attempt} {result.stop}")
            n = json.loads(next((tmp_path / "runs").glob("*/out/count/a.json")).read_text())["n"]
            result.payload = {"n": n, "before": before}
            if n == 0:
                result.ok, result.stop, result.reason = False, "empty", "count is 0"

    @python_task
    def count(unit: str) -> Count:
        return Count(n=0)

    report = pipeline(tmp_path, enrichers=[Empty()], row_extras=lambda r: r.payload or {}).run(lambda: count("a"))
    result = report.results["python:count-a"]
    assert not result.ok and result.stop == "empty" and result.payload == {"n": 0, "before": "before"}
    assert calls == ["snapshot 0", "enrich 0 completed"]
    [row] = rows(report)
    assert row["stop"] == "empty" and row["n"] == 0


def test_an_enricher_sees_each_attempt_of_a_retried_python_task(tmp_path):
    seen: list[tuple[int, str]] = []
    left = [ConnectionError("refused")]

    class Stops:
        def snapshot(self, task):
            return None

        def enrich(self, task, before, result):
            seen.append((task.attempt, result.stop))
            result.payload = {"seen": len(seen)}

    @python_task(retries=1, retry_on=(ConnectionError,))
    def count(unit: str) -> Count:
        if left:
            raise left.pop(0)
        return Count(n=1)

    report = pipeline(tmp_path, enrichers=[Stops()], row_extras=lambda r: r.payload or {}).run(lambda: count("a"))
    assert report.ok and seen == [(0, "error"), (1, "completed")]
    assert [(r["attempt"], r["seen"]) for r in rows(report)] == [(0, 1), (1, 2)]


def test_a_refused_input_is_an_attempt_the_scope_and_the_enricher_see(tmp_path):
    from contraagent import InputContract
    from contraagent._internal.dispatch import make_python_task
    from contraagent.engine import PythonTaskRunner

    seen: list = []

    class Stops:
        def snapshot(self, task):
            return None

        def enrich(self, task, before, result):
            seen.append(("enrich", result.stop))

    ran: list[int] = []
    task = make_python_task("needs", lambda: ran.append(1), unit="u", input_contracts=[InputContract(tmp_path / "missing.json", Count)])
    runner = PythonTaskRunner(cwd=tmp_path, scopes=[recording_scope(seen)], enrichers=[Stops()])
    result = runner.run(task)
    assert result.stop == "invalid_input" and not ran
    assert seen == [("enter", "python", "needs", 0), ("exit", "python", "needs", 0), ("enrich", "invalid_input")]


def test_a_scope_for_one_executor_leaves_the_other_and_agent_tasks_keep_theirs(tmp_path):
    seen: list = []
    note = agent_task("note", instructions="Write a note.", output=Note, max_turns=5, timeout_s=60)

    @python_task
    def count(unit: str) -> Count:
        return Count(n=1)

    def python_only(task):
        return recording_scope(seen)(task) if task.executor == "python" else contextlib.nullcontext()

    every: list = []
    agent = StubAgent({"note": {"text": "t"}})
    report = pipeline(tmp_path, backends=agent.backends(), scopes=[python_only, recording_scope(every)]).run(
        lambda: note("a", n=count("a"))
    )
    assert report.ok, report.failed
    assert seen == [("enter", "python", "count", 0), ("exit", "python", "count", 0)]
    assert every == [
        ("enter", "python", "count", 0),
        ("exit", "python", "count", 0),
        ("enter", "agent", "note", 0),
        ("exit", "agent", "note", 0),
    ]


def test_a_scope_that_raises_on_enter_fails_a_python_task_as_it_fails_an_agent_task(tmp_path):
    calls: list[int] = []
    note = agent_task("note", instructions="Write a note.", output=Note, max_turns=5, timeout_s=60)

    @python_task
    def count(unit: str) -> Count:
        calls.append(1)
        return Count(n=1)

    def broken(task):
        raise RuntimeError(f"no server for {task.kind}")

    agent = StubAgent({"note": {"text": "t"}})

    def flow():
        count("a")
        note("b")

    report = pipeline(tmp_path, backends=agent.backends(), scopes=[broken], retry_wait_s=0).run(flow)
    python, agentic = report.results["python:count-a"], report.results["note-b"]
    assert not calls and not python.ok and not agentic.ok
    assert python.stop == agentic.stop
    assert python.reason == "exception: RuntimeError('no server for count')"
    assert agentic.reason == "exception: RuntimeError('no server for note')"


def test_the_example_starts_an_index_server_for_each_attempt_of_find_sources(tmp_path, monkeypatch):
    from contraagent.docs.examples.scopes import flow

    seen_kinds: list[str] = []

    def watching(task):
        seen_kinds.append(task.kind)
        return flow.index_server(task)

    agent = StubAgent({"summarize": {"text": "t"}})
    report = Pipeline(
        None, runs_dir=tmp_path / "runs", cwd=tmp_path, backends=agent.backends(), scopes=[watching], log=lambda line: None
    ).run(flow.topics, names=["caching", "queues"])
    assert report.ok, report.failed
    assert sorted(seen_kinds) == ["find_sources", "find_sources", "summarize", "summarize"]
    assert flow.servers == {}  # each server stopped after its attempt
    out = report.run_dir / "out" / "find_sources"
    assert json.loads((out / "caching.json").read_text())["paths"] == ["notes/caching.md", "notes/eviction.md"]
    assert json.loads((out / "queues.json").read_text())["paths"] == ["notes/queues.md"]
    assert flow.pipeline(runs_dir=tmp_path / "other", backends=agent.backends()).scopes == (flow.index_server,)
