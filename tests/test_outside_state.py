"""Outside state (`outside_state=`): a function of a task's unit and params whose value its
fingerprint covers, worked out when the task is about to start, so a resume runs the task
again when the state it reads beside its params changed, and skips it when it did not."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task
from contraagent.testing import StubAgent


class Count(BaseModel):
    n: int


class Note(BaseModel):
    text: str


def pipeline(tmp_path, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None, **kw)


def rows(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def digest_of(path: Path) -> str:
    """What a pipeline's outside_state returns for a file it reads: its digest, or "" when missing."""
    try:
        with path.open("rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except FileNotFoundError:
        return ""


def counting(tmp_path, calls: list[str]):
    state = tmp_path / "state.json"

    @python_task(outside_state=lambda unit, params: digest_of(state))
    def tally(unit: str) -> Count:
        calls.append(unit)
        return Count(n=len(json.loads(state.read_text())["items"]) if state.exists() else 0)

    return state, tally


def test_a_changed_state_runs_the_task_again_on_resume_and_says_why(tmp_path):
    calls: list[str] = []
    state, tally = counting(tmp_path, calls)
    state.write_text('{"items": [1]}')
    first = pipeline(tmp_path).run(lambda: tally("a"), run_id="r")
    assert first.ok and calls == ["a"]
    [row] = rows(first)
    assert row["outside"] == hashlib.sha256(json.dumps(digest_of(state)).encode()).hexdigest() and row["rerun"] == ""

    state.write_text('{"items": [1, 2]}')
    again = pipeline(tmp_path).run(lambda: tally("a"), run_id="r", resume=True)
    assert again.ok and calls == ["a", "a"]
    assert json.loads((again.run_dir / "out" / "tally" / "a.json").read_text()) == {"n": 2}
    last = rows(again)[-1]
    assert last["stop"] == "completed" and last["rerun"] == "its outside state changed"


def test_an_unchanged_state_skips_the_task_on_resume(tmp_path):
    calls: list[str] = []
    state, tally = counting(tmp_path, calls)
    state.write_text('{"items": [1]}')
    pipeline(tmp_path).run(lambda: tally("a"), run_id="r")
    again = pipeline(tmp_path).run(lambda: tally("a"), run_id="r", resume=True)
    assert again.ok and calls == ["a"]
    assert again.results["python:tally-a"].stop == "skipped"


def test_a_missing_file_is_a_state_of_its_own(tmp_path):
    calls: list[str] = []
    state, tally = counting(tmp_path, calls)
    first = pipeline(tmp_path).run(lambda: tally("a"), run_id="r")  # no state file: no error
    assert first.ok and calls == ["a"]
    pipeline(tmp_path).run(lambda: tally("a"), run_id="r", resume=True)
    assert calls == ["a"]  # still missing: skipped
    state.write_text('{"items": [1, 2, 3]}')
    pipeline(tmp_path).run(lambda: tally("a"), run_id="r", resume=True)
    assert calls == ["a", "a"]  # it appeared: runs again


def test_a_function_that_raises_refuses_the_task(tmp_path):
    def broken(unit, params):
        raise RuntimeError("state store unreachable")

    @python_task(outside_state=broken)
    def tally(unit: str) -> Count:
        raise AssertionError("never called")

    @python_task
    def after(n: int) -> Count:
        return Count(n=n)

    def flow():
        c = yield tally("a")
        after(n=c.n)

    report = pipeline(tmp_path).run(flow)
    result = report.results["python:tally-a"]
    assert result.stop == "invalid_input" and "outside_state raised RuntimeError: state store unreachable" in result.reason
    [row] = rows(report)
    assert row["stop"] == "invalid_input" and row["outside"] == ""


def test_a_value_that_is_not_json_refuses_the_task(tmp_path):
    @python_task(outside_state=lambda unit, params: object())
    def tally(unit: str) -> Count:
        return Count(n=1)

    report = pipeline(tmp_path).run(lambda: tally("a"))
    assert report.results["python:tally-a"].stop == "invalid_input"
    assert "which is not JSON" in report.results["python:tally-a"].reason


def test_the_function_is_called_when_the_task_starts_with_its_params_resolved(tmp_path):
    """It sees what an earlier task wrote, and the outputs it is given."""
    seen: list[tuple[str, dict]] = []
    state = tmp_path / "state.txt"

    @python_task
    def write(unit: str) -> Count:
        state.write_text("written")
        return Count(n=7)

    def outside(unit, params):
        seen.append((unit, params, state.read_text()))
        return state.read_text()

    @python_task(outside_state=outside)
    def read(unit: str, count: Count) -> Count:
        return Count(n=count.n)

    def flow():
        c = write("a")
        read("a", count=c)  # not yielded: a Pending, resolved when the task starts

    report = pipeline(tmp_path).run(flow)
    assert report.ok
    [(unit, params, text)] = seen
    assert unit == "a" and params["count"] == Count(n=7) and text == "written"


def test_a_task_that_waits_for_one_that_ran_again_runs_again_too(tmp_path):
    """In a flow that does not receive the output, the later task's fingerprint is that of the
    task it waits for as it started: a changed state reaches it."""
    calls: list[str] = []
    state, tally = counting(tmp_path, calls)

    @python_task
    def report_on(count: Count) -> Count:
        calls.append("report")
        return Count(n=count.n)

    def flow():
        report_on(count=tally("a"))

    state.write_text('{"items": [1]}')
    pipeline(tmp_path).run(flow, run_id="r")
    pipeline(tmp_path).run(flow, run_id="r", resume=True)
    assert calls == ["a", "report"]  # nothing changed: both skipped
    state.write_text('{"items": [1, 2]}')
    again = pipeline(tmp_path).run(flow, run_id="r", resume=True)
    assert calls == ["a", "report", "a", "report"]
    reruns = {r["key"]: r["rerun"] for r in rows(again)[-2:]}
    assert reruns["python:tally-a"] == "its outside state changed"
    assert reruns["python:report_on"].startswith("its fingerprint changed")


def test_an_agent_task_takes_it_too(tmp_path):
    guide = tmp_path / "guide.md"
    guide.write_text("Write short notes.")
    note = agent_task(
        "note",
        instructions="Write a note.",
        output=Note,
        max_turns=3,
        timeout_s=60,
        outside_state=lambda unit, params: digest_of(guide),
    )
    stub = StubAgent(default={"text": "ok"})
    first = pipeline(tmp_path, stub=stub).run(lambda: note("a"), run_id="r")
    assert first.ok
    skipped = pipeline(tmp_path, stub=stub).run(lambda: note("a"), run_id="r", resume=True)
    assert skipped.results["note-a"].stop == "skipped"
    guide.write_text("Write long notes.")
    again = pipeline(tmp_path, stub=stub).run(lambda: note("a"), run_id="r", resume=True)
    assert again.results["note-a"].stop == "completed" and rows(again)[-1]["rerun"] == "its outside state changed"


def test_an_agent_task_whose_function_raises_is_refused_and_journaled(tmp_path):
    def broken(unit, params):
        raise ValueError("no state")

    note = agent_task("note", instructions="Write a note.", output=Note, max_turns=3, timeout_s=60, outside_state=broken)
    report = pipeline(tmp_path, stub=StubAgent(default={"text": "ok"})).run(lambda: note("a"))
    assert report.results["note-a"].stop == "invalid_input"
    [row] = rows(report)
    assert row["stop"] == "invalid_input" and "outside_state raised ValueError: no state" in row["reason"]


def test_the_declaration_is_checked():
    with pytest.raises(TypeError, match="outside_state must be a function"):
        python_task(outside_state="state.json")(lambda unit: None)  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError, match="rerun_on_resume runs every task of it again"):
        python_task(outside_state=lambda unit, params: 1, rerun_on_resume=True)(lambda unit: None)


def test_the_function_is_part_of_the_definition():
    def one(unit, params):
        return 1

    def two(unit, params):
        return 2

    a = agent_task("x", instructions="i", outside_state=one)
    b = agent_task("x", instructions="i", outside_state=two)
    assert a.digest() != b.digest() and "outside_state" in a.differences(b)


def test_check_reports_a_function_that_raises(tmp_path):
    def broken(unit, params):
        raise KeyError(params["missing"])

    @python_task(outside_state=broken)
    def tally(unit: str) -> Count:
        return Count(n=1)

    report = pipeline(tmp_path).check(lambda: tally("a"))
    assert not report.ok and "tasks" in report.topics
    assert any("python:tally-a: tally: outside_state raised KeyError" in e for e in report.errors)
    fine = python_task(name="fine", outside_state=lambda unit, params: unit)(lambda unit: None)
    assert pipeline(tmp_path).check(lambda: fine("a")).ok


def test_the_example_runs_the_tasks_again_once_the_backlog_changed(tmp_path, monkeypatch):
    from contraagent.docs.examples.outside import flow

    monkeypatch.chdir(tmp_path)
    (tmp_path / "state").mkdir()
    flow.BACKLOG.write_text('{"caching": ["a"], "queues": []}')
    agent = StubAgent({"summarize": {"text": "t"}})

    def run(**kw):
        return pipeline(tmp_path, backends=agent.backends()).run(flow.topics, names=["caching", "queues"], run_id="topics", **kw)

    assert run().ok
    same = run(resume=True)
    assert {r.stop for r in same.results.values()} == {"skipped"}
    flow.BACKLOG.write_text('{"caching": ["a", "b"], "queues": []}')
    again = run(resume=True)
    assert {r.stop for r in again.results.values()} == {"completed"}
    assert json.loads((again.run_dir / "out" / "count_open" / "caching.json").read_text())["count"] == 2
