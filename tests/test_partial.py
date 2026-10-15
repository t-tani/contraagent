"""A partial result (`Partial`): a Python task that writes a placeholder output finishes ok
with stop `partial`; the flow and later tasks go on, and a resume runs it again with the
tasks that wait for it."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Partial, Pipeline, PythonTaskRunner, python_task
from contraagent.dispatch.python_task import make_python_task
from contraagent.monitor import Monitor, api
from contraagent.testing import StubAgent


class Count(BaseModel):
    n: int


def pipeline(tmp_path, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", cwd=tmp_path, log=lambda line: None, **kw)


def rows(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def test_a_partial_result_is_ok_its_value_the_output_and_the_flow_receives_it(tmp_path):
    @python_task
    def count(unit: str) -> Count | Partial[Count]:
        return Partial(Count(n=0), reason="counter unavailable")

    @python_task
    def double(n: int) -> Count:
        return Count(n=n * 2 + 1)

    def flow():
        c = yield count("a")
        double(n=c.n)

    report = pipeline(tmp_path).run(flow)
    result = report.results["python:count-a"]
    assert result.ok and result.stop == "partial" and result.reason == "counter unavailable"
    assert report.ok and report.partial == [result] and report.summary["by_stop"] == {"partial": 1, "completed": 1}
    assert json.loads((report.run_dir / "out" / "count" / "a.json").read_text()) == {"n": 0}
    assert report.results["python:double"].ok  # the later task ran on the placeholder
    [row] = [r for r in rows(report) if r["kind"] == "count"]
    assert row["stop"] == "partial" and row["ok"] and row["reason"] == "counter unavailable"


def test_a_partial_value_is_checked_like_any_output(tmp_path):
    @python_task
    def count(unit: str) -> Count | Partial[Count]:
        return Partial({"n": "many"}, reason="counter unavailable")

    report = pipeline(tmp_path).run(lambda: count("a"))
    result = report.results["python:count-a"]
    assert not result.ok and result.stop == "error" and "ValidationError" in result.reason


def test_a_partial_needs_a_reason():
    with pytest.raises(TypeError, match="reason must say why"):
        Partial(Count(n=0), reason=" ")


def test_the_annotation_without_partial_is_the_output_schema():
    @python_task
    def count(unit: str) -> Count | Partial[Count]:
        return Count(n=1)

    @python_task
    def words(unit: str) -> Partial[list[str]]:
        return Partial([], reason="none")

    assert count.output_schema is Count
    assert words.output_schema is not None and words.output_schema.model_validate(["a"]).root == ["a"]


def test_make_python_task_returns_a_partial_too():
    task = make_python_task("ping", lambda: Partial(None, reason="host unavailable"))
    result = PythonTaskRunner().run(task)
    assert result.ok and result.stop == "partial" and result.reason == "host unavailable"


def resume_example(tmp_path, monkeypatch):
    from contraagent.docs.examples.partial import flow

    lookup = flow.LocalIndex.lookup
    down = {"queues"}

    def answers(self, topic):
        if topic in down:
            raise ConnectionError("index server is not running")
        return lookup(self, topic)

    monkeypatch.setattr(flow.LocalIndex, "lookup", answers)
    agent = StubAgent({"summarize": {"text": "t"}})

    def run(**kw):
        return pipeline(tmp_path, backends=agent.backends()).run(flow.topics, names=["caching", "queues"], run_id="topics", **kw)

    return run, down


def test_the_example_goes_on_past_a_partial_lookup_and_a_resume_runs_only_it_again(tmp_path, monkeypatch):
    run, down = resume_example(tmp_path, monkeypatch)
    first = run()
    assert first.ok and [r.task.key for r in first.partial] == ["python:find_sources-queues"]
    assert first.results["summarize-queues"].ok  # it ran on the empty list of files
    out = tmp_path / "runs" / "topics" / "out" / "find_sources"
    assert json.loads((out / "queues.json").read_text())["paths"] == []

    down.clear()  # the server answers again
    second = run(resume=True)
    stops = {k: r.stop for k, r in second.results.items()}
    assert stops == {
        "python:find_sources-caching": "skipped",
        "summarize-caching": "skipped",
        "python:find_sources-queues": "completed",
        "summarize-queues": "completed",  # it waits for the lookup that ran again
    }
    assert json.loads((out / "queues.json").read_text())["paths"] == ["notes/queues.md"]
    assert not second.partial


def test_a_resume_runs_a_partial_lookup_again_while_it_stays_partial(tmp_path, monkeypatch):
    run, _ = resume_example(tmp_path, monkeypatch)
    run()
    again = run(resume=True)
    assert again.results["python:find_sources-queues"].stop == "partial"
    assert again.results["summarize-queues"].stop == "completed"
    assert again.results["summarize-caching"].stop == "skipped"


def test_the_monitor_shows_a_partial_task_as_its_own_state(tmp_path, monkeypatch):
    run, _ = resume_example(tmp_path, monkeypatch)
    run()
    m = Monitor(tmp_path / "runs")
    nodes = {n["key"]: n for n in m.plan("topics")["nodes"]}
    assert nodes["python:find_sources-queues"]["state"] == "partial"
    assert nodes["summarize-queues"]["state"] == "done"
    [summary] = m.runs()
    assert summary["tasks"]["partial"] == 1 and summary["tasks"]["done"] == 3
    assert (summary["ok"], summary["partial"]) == (3, 1)
    api.RunSummary.model_validate(summary)
    group = next(g for g in m.plan("topics")["groups"] if g["id"] == "find_sources")
    assert (group["done"], group["partial"]) == (1, 1)
