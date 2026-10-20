"""A record of a run that cannot be written is never silent: a journal row fails the run at
its end (a resume reads the journal), a record only the monitor reads is a warning line
and a count in `RunReport.summary["record_failures"]`, and the run goes on."""

import json
from dataclasses import replace

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent._internal.backends.launch import LaunchResult
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.dispatch.records import Rest
from contraagent._internal.errors import ContraagentError
from contraagent._internal.execution.journal import Journal
from contraagent._internal.execution.run import Run
from contraagent.testing import StubAgent, writes_example


class Count(BaseModel):
    n: int


class Note(BaseModel):
    note: str


calls: list[str] = []


@python_task(name="count")
def count(unit: str) -> Count:
    calls.append(unit)
    return Count(n=len(calls))


note = agent_task("note", instructions="Write a note.", output=Note, max_turns=5, timeout_s=60, retries=0)


def failing_append(monkeypatch, key: str) -> list[str]:
    """`Journal.append` raises OSError for `key`; the keys it was asked to write."""
    asked: list[str] = []
    append = Journal.append

    def fake(self, result, on_launch_error=None):
        asked.append(result.task.key)
        if result.task.key == key:
            raise OSError(28, "No space left on device")
        return append(self, result, on_launch_error)

    monkeypatch.setattr(Journal, "append", fake)
    return asked


def info(run_dir) -> dict:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def test_a_python_task_s_journal_row_not_written_fails_the_run_at_its_end(tmp_path, monkeypatch):
    calls.clear()
    asked = failing_append(monkeypatch, "python:count-a")
    lines: list[str] = []
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lines.append)
    with pytest.raises(ContraagentError, match=r"1 journal row of run r could not be written to .*journal\.jsonl") as raised:
        pipeline.run(lambda: [count("a"), count("b")], run_id="r")
    assert isinstance(raised.value.__cause__, OSError)
    assert sorted(calls) == ["a", "b"]  # run once each: the failed write is no failed task
    assert sorted(asked) == ["python:count-a", "python:count-b"]
    [warning] = [line for line in lines if line.startswith("[error]")]
    assert "journal.jsonl not written for python:count-a: OSError" in warning and "a resume runs the task again" in warning
    run_dir = tmp_path / "runs" / "r"
    assert [json.loads(row)["key"] for row in (run_dir / "journal.jsonl").read_text().splitlines()] == ["python:count-b"]
    assert "finished_at" not in info(run_dir)  # unfinished: a resume runs count-a again


def test_an_agent_task_s_journal_row_not_written_is_not_launched_again(tmp_path, monkeypatch):
    asked = failing_append(monkeypatch, "note-a")
    lines: list[str] = []
    stub = StubAgent(default=writes_example())
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub, log=lines.append)
    with pytest.raises(ContraagentError, match="journal row"):
        pipeline.run(lambda: note("a"), run_id="n")
    assert [launch.key for launch in stub.launches] == ["note-a"] and asked == ["note-a"]
    assert any("journal.jsonl not written for note-a" in line for line in lines)


def test_a_launch_record_not_written_is_counted_and_the_run_goes_on(tmp_path, monkeypatch):
    def fail(self, path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(LaunchResult, "record", fail)
    lines: list[str] = []
    stub = StubAgent(default=writes_example())
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub, log=lines.append)
    report = pipeline.run(lambda: [note("a"), note("b")], run_id="n")
    assert report.ok and report.summary["record_failures"] == {"launches.jsonl": 2}
    assert len([line for line in lines if "launches.jsonl not written" in line and "PermissionError" in line]) == 2
    assert len((report.run_dir / "journal.jsonl").read_text().splitlines()) == 2  # the rows a resume reads
    assert "finished_at" in info(report.run_dir)


def test_a_flow_call_s_end_not_written_is_counted_and_the_flow_goes_on(tmp_path, monkeypatch):
    calls.clear()
    record = Run.record_flow_call

    def fake(self, event, call_id, **fields):
        if event == "end":
            raise OSError(5, "Input/output error")
        record(self, event, call_id, **fields)

    monkeypatch.setattr(Run, "record_flow_call", fake)

    async def flow():
        return (await count("a")).n

    lines: list[str] = []
    report = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lines.append).run(flow, run_id="f")
    assert report.ok and report.value == 1
    assert report.summary["record_failures"] == {"flow_calls.jsonl": 1}
    assert any("flow_calls.jsonl not written for flow call 0: OSError" in line for line in lines)


def test_a_run_whose_records_were_all_written_has_no_count(tmp_path):
    calls.clear()
    report = Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None).run(lambda: count("a"), run_id="ok")
    assert report.ok and "record_failures" not in report.summary


def test_a_rest_not_written_is_a_warning_and_a_count(tmp_path, monkeypatch):
    lines: list[str] = []
    run = Run("r", tmp_path / "runs", lock=False, log=lines.append)
    monkeypatch.setattr(run, "_append", lambda name, row: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    run._record_rest("start", Rest(credential="work", window="five_hour", pct=91.0, cap=90.0))
    assert run._record_failures() == {"rests.jsonl": 1} and run._journal_failure() is None
    assert any(line.startswith("[error]") and "rests.jsonl not written for credential work" in line for line in lines)
    assert any(line.startswith("[rest]") for line in lines)  # the rest itself is still said


class _Hooks:
    """A runner whose hooks raise: its deferral check and the completion of a fingerprint."""

    def __init__(self, inner):
        self._inner = inner

    def config(self, task):
        return self._inner.config(task)

    def run(self, task):
        return self._inner.run(task)

    def deferral(self, task):
        raise KeyError("rests")

    def starting(self, task):
        raise RuntimeError("outside state unreadable")


def test_a_hook_that_raises_around_a_task_is_a_warning_line(tmp_path):
    lines: list[str] = []
    run = Run("q", tmp_path / "runs", lock=False, log=lines.append)
    queue = run.queue(_Hooks(run.python_runner()))
    queue.add(replace(make_python_task("step", lambda: None), fingerprint_at_start=True))
    summary = queue.run()
    assert summary["ok"] == 1
    said = [line for line in lines if line.startswith("[error] python:step: ")]
    assert any("its deferral check raised KeyError" in line and line.endswith("; launched") for line in said)
    assert any("completing its fingerprint raised RuntimeError" in line and "a resume runs it again" in line for line in said)
