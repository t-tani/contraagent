"""A task call's `priority`: a tie-breaker the queue reads, recorded in the plan, outside the fingerprint."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, agent_task, python_task
from contraagent.testing import StubAgent


class Written(BaseModel):
    path: str


def written(launch):
    return {"path": f"topics/{launch.unit}.md"}


def run(tmp_path, flow, agent=None, **options):
    agent = agent or StubAgent()
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **options).run(flow)


def lines(report, name: str) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / name).read_text().splitlines()]


def test_ready_python_tasks_start_by_priority_and_the_plan_records_it(tmp_path):
    started: list[str] = []

    @python_task
    def note(unit: str) -> None:
        started.append(unit)

    def flow():
        note("plain")
        note("high", priority=3)
        note("mid", priority=1.5)

    report = run(tmp_path, flow, max_concurrent=1)
    assert report.ok, report.failed
    assert started == ["high", "mid", "plain"]
    priorities = {row["unit"]: row["priority"] for row in lines(report, "plan.jsonl")}
    assert priorities == {"plain": 0.0, "high": 3.0, "mid": 1.5}


def test_priority_leaves_the_fingerprint_alone(tmp_path):
    task = agent_task("summarize", instructions="x", output=Written, max_turns=1, timeout_s=1)

    def fingerprint(priority: float) -> str:
        report = run(tmp_path / str(priority), lambda: task("alpha", priority=priority), StubAgent({"summarize": written}))
        return lines(report, "journal.jsonl")[0]["fingerprint"]

    assert fingerprint(0) == fingerprint(7.5)


def test_a_params_field_or_a_function_parameter_named_priority_is_refused_at_declaration():
    class Params(BaseModel):
        topic: str
        priority: int

    with pytest.raises(TypeError, match="params Params has a field named priority"):
        agent_task("summarize", instructions="x", params=Params, max_turns=1, timeout_s=1)

    with pytest.raises(TypeError, match="has a parameter named priority"):

        @python_task
        def rank(topic: str, priority: int) -> None: ...


def test_a_priority_that_is_not_a_finite_number_is_refused_at_the_task_call(tmp_path):
    @python_task
    def note() -> None: ...

    for bad in ("high", float("nan"), True):
        with pytest.raises(TypeError, match="priority must be a finite number"):
            run(tmp_path / repr(bad), lambda bad=bad: note("a", priority=bad))
