"""Retries of a Python task (`@python_task(retries=, retry_on=)`): a fresh attempt after an
exception of a class it names, each attempt a journal row of its own."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, python_task


class Count(BaseModel):
    n: int


def pipeline(tmp_path) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None)


def rows(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def failing(*errors: Exception):
    """A function that raises each of `errors` in turn, then returns."""
    left = list(errors)
    calls: list[int] = []

    def fn(unit: str) -> Count:
        calls.append(1)
        if left:
            raise left.pop(0)
        return Count(n=len(calls))

    return fn, calls


def test_an_exception_of_retry_on_gets_a_fresh_attempt_each_a_journal_row(tmp_path):
    fn, calls = failing(ConnectionError("refused"), TimeoutError("slow"))
    count = python_task(name="count", retries=2, retry_on=(ConnectionError, TimeoutError))(fn)
    report = pipeline(tmp_path).run(lambda: count("a"))
    result = report.results["python:count-a"]
    assert result.ok and len(calls) == 3
    journal = rows(report)
    assert [(r["attempt"], r["stop"]) for r in journal] == [(0, "error"), (1, "error"), (2, "completed")]
    assert journal[0]["reason"] == "ConnectionError: refused" and journal[1]["reason"] == "TimeoutError: slow"
    assert json.loads((report.run_dir / "out" / "count" / "a.json").read_text()) == {"n": 3}


def test_an_exception_retry_on_does_not_name_fails_the_task_at_once(tmp_path):
    fn, calls = failing(ValueError("bad topic"))
    count = python_task(name="count", retries=2, retry_on=(ConnectionError,))(fn)
    report = pipeline(tmp_path).run(lambda: count("a"))
    assert not report.results["python:count-a"].ok and len(calls) == 1
    [row] = rows(report)
    assert row["attempt"] == 0 and row["stop"] == "error" and row["reason"] == "ValueError: bad topic"


def test_the_last_attempt_s_failure_is_the_task_s_result_and_a_subclass_is_retried(tmp_path):
    fn, calls = failing(ConnectionRefusedError("refused"), ConnectionResetError("reset"), ConnectionError("again"))
    count = python_task(name="count", retries=1, retry_on=(ConnectionError,))(fn)
    report = pipeline(tmp_path).run(lambda: count("a"))
    result = report.results["python:count-a"]
    assert not result.ok and result.reason == "ConnectionResetError: reset" and len(calls) == 2
    assert [r["attempt"] for r in rows(report)] == [0, 1]


def test_an_off_contract_output_is_not_retried(tmp_path):
    calls: list[int] = []

    def never(path, value):
        return ["n: never valid"]

    @python_task(retries=2, retry_on=(ConnectionError,), validators=[never])
    def count(unit: str) -> Count:
        calls.append(1)
        return Count(n=1)

    report = pipeline(tmp_path).run(lambda: count("a"))
    [row] = rows(report)
    assert row["stop"] == "invalid_output" and len(calls) == 1


def test_a_resume_skips_a_task_finished_after_a_retry(tmp_path):
    fn, calls = failing(ConnectionError("refused"))
    count = python_task(name="count", retries=1, retry_on=(ConnectionError,))(fn)
    first = pipeline(tmp_path).run(lambda: count("a"), run_id="r")
    assert first.ok and len(calls) == 2
    second = pipeline(tmp_path).run(lambda: count("a"), run_id="r", resume=True)
    assert second.ok and len(calls) == 2


@pytest.mark.parametrize(
    ("kwargs", "error", "says"),
    [
        ({"retries": 2}, ValueError, "retries=2 with no retry_on"),
        ({"retry_on": (ConnectionError,)}, ValueError, "retry_on with retries=0"),
        ({"retries": -1, "retry_on": (ConnectionError,)}, TypeError, "retries must be an int of 0 or more"),
        ({"retries": True, "retry_on": (ConnectionError,)}, TypeError, "retries must be an int"),
        ({"retries": 1, "retry_on": ConnectionError}, TypeError, "retry_on must be a tuple of exception classes"),
        ({"retries": 1, "retry_on": ("ConnectionError",)}, TypeError, "each item is an exception class"),
        ({"retries": 1, "retry_on": (KeyboardInterrupt,)}, TypeError, "each item is an exception class"),
    ],
)
def test_retries_and_retry_on_are_checked_at_the_decorator(kwargs, error, says):
    with pytest.raises(error, match=says):

        @python_task(**kwargs)
        def count() -> int:
            return 1


def test_retries_show_in_the_definition_and_leave_the_digest_alone():
    def count(unit: str) -> int:
        return 1

    plain = python_task(name="count")(count)
    retried = python_task(name="count", retries=2, retry_on=(ConnectionError, TimeoutError))(count)
    assert retried.digest() == plain.digest()  # how a task runs, not what it produces
    body = retried.definition()
    assert body["retries"] == 2 and body["retry_on"] == ["ConnectionError", "TimeoutError"]
    assert "retries" not in plain.definition()


def test_the_retries_example_restores_the_index_and_its_second_attempt_succeeds(tmp_path, monkeypatch):
    from contraagent.docs.examples.retries import flow
    from contraagent.testing import StubAgent

    stops: list[int] = []
    lookup = flow.LocalIndex.lookup

    def drops_once(self, topic):
        if not stops:  # the server goes down once, after a start
            stops.append(1)
            self.up = False
        return lookup(self, topic)

    monkeypatch.setattr(flow.index, "up", False)
    monkeypatch.setattr(flow.LocalIndex, "lookup", drops_once)
    agent = StubAgent({"summarize": {"text": "t"}})
    report = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, backends=agent.backends(), log=lambda line: None).run(
        flow.topics, names=["caching"]
    )
    assert report.ok
    tries = [r for r in rows(report) if r["kind"] == "find_sources"]
    assert [(r["attempt"], r["stop"]) for r in tries] == [(0, "error"), (1, "completed")]
    assert tries[0]["reason"] == "ConnectionError: index server is not running"
    assert json.loads((report.run_dir / "out" / "find_sources" / "caching.json").read_text())["paths"] == [
        "notes/caching.md",
        "notes/eviction.md",
    ]


def test_make_python_task_takes_the_same_retries():
    from contraagent import PythonTaskRunner
    from contraagent.dispatch.python_task import make_python_task

    left = [ConnectionError("refused")]

    def fn():
        if left:
            raise left.pop()

    failed: list = []
    task = make_python_task("ping", fn, retries=1, retry_on=(ConnectionError,))
    result = PythonTaskRunner(on_failed_attempt=failed.append).run(task)
    assert result.ok and task.attempt == 1 and [r.reason for r in failed] == ["ConnectionError: refused"]
    with pytest.raises(ValueError, match=r"make_python_task\('ping'\): retries=1 with no retry_on"):
        make_python_task("ping", fn, retries=1)
