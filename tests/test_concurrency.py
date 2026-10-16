"""Concurrency of Python tasks beside agent tasks: every running task takes one of the
run's slots, and a claim bounds the long Python tasks so that the agent tasks keep theirs."""

import json
import threading
import time

from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.testing import StubAgent


class Note(BaseModel):
    text: str


class Peak:
    """How many of a group run at once, and the most that ever did."""

    def __init__(self) -> None:
        self.now = 0
        self.most = 0
        self._lock = threading.Lock()

    def __enter__(self) -> "Peak":
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
        return self

    def __exit__(self, *exc: object) -> None:
        with self._lock:
            self.now -= 1


def pipeline(tmp_path, agent: StubAgent, **options) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **options)


def test_many_long_python_tasks_under_a_claim_leave_the_agent_tasks_their_slots(tmp_path):
    computing, agents = Peak(), Peak()
    agents_ran = threading.Event()
    both_agents = threading.Barrier(2, timeout=10)

    @python_task(claims=["local"])
    def crunch(unit: str) -> Note:
        with computing:
            agents_ran.wait(10)  # a long computation: it ends only once the agent tasks ran
            return Note(text=unit)

    def summarized(launch):
        with agents:
            both_agents.wait()  # both agent tasks run at once, beside the Python tasks
        agents_ran.set()
        return {"text": launch.unit}

    summarize = agent_task("summarize", instructions="Summarize.", output=Note, max_turns=3, timeout_s=60)
    agent = StubAgent({"summarize": summarized})

    def flow():
        for i in range(6):  # queued first: they come first in the order
            crunch(f"c{i}")
        summarize("a")
        summarize("b")

    started = time.monotonic()
    report = pipeline(tmp_path, agent, max_concurrent=4, claim_capacity={"local": 2}).run(flow)
    assert report.ok, report.failed
    assert time.monotonic() - started < 10  # no wait timed out
    assert agents.most == 2 and computing.most == 2


def test_without_a_claim_python_tasks_take_the_slots_with_the_agent_tasks(tmp_path):
    running = Peak()

    @python_task
    def crunch(unit: str) -> Note:
        with running:
            time.sleep(0.05)
            return Note(text=unit)

    def summarized(launch):
        with running:
            time.sleep(0.05)
        return {"text": launch.unit}

    summarize = agent_task("summarize", instructions="Summarize.", output=Note, max_turns=3, timeout_s=60)

    def flow():
        for i in range(4):
            crunch(f"c{i}")
            summarize(f"s{i}")

    report = pipeline(tmp_path, StubAgent({"summarize": summarized}), max_concurrent=2).run(flow)
    assert report.ok, report.failed
    assert running.most == 2
    assert json.loads((report.run_dir / "run.json").read_text())["max_workers"] == 2


def test_a_task_table_that_names_a_python_task_is_said_to_bound_nothing(tmp_path, caplog):
    @python_task
    def crunch(unit: str) -> Note:
        return Note(text=unit)

    summarize = agent_task("summarize", instructions="Summarize.", output=Note, max_turns=3, timeout_s=60)
    config = PipelineConfig({"tasks": {"crunch": {"max_concurrent": 1}, "sumarize": {"max_turns": 2}}})
    agent = StubAgent()
    report = Pipeline(config, runs_dir=tmp_path, backends=agent.backends()).check(lambda: [crunch("a"), summarize("a")])
    assert report.ok
    [python_table] = [w for w in report.warnings if "[tasks.crunch]" in w]
    assert "names a Python task" in python_table and "claim_capacity" in python_table
    assert "contraagent docs tasks, Concurrency" in python_table
    assert any("[tasks.sumarize] is not a kind of this run" in w for w in report.warnings)  # a typo, as before
    # A flow of Python tasks only is checked too.
    report = Pipeline(config, runs_dir=tmp_path, backends=agent.backends()).check(lambda: [crunch("a")])
    assert any("[tasks.crunch] names a Python task" in w for w in report.warnings)

    caplog.clear()  # a run logs it as well
    assert Pipeline(config, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(lambda: [crunch("a")]).ok
    assert any("[tasks.crunch] names a Python task" in r.getMessage() for r in caplog.records)


def test_the_concurrency_example_runs_its_measurements_beside_the_summaries(tmp_path):
    from contraagent.docs.examples.concurrency import flow as example

    agent = StubAgent({"summarize": {"text": "A summary."}})
    report = example.pipeline(runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None).run(
        example.reports, ["alpha", "beta", "gamma"]
    )
    assert report.ok, report.failed
    assert len(agent.launches) == 3
    measured = [r for key, r in report.results.items() if key.startswith("python:measure")]
    assert len(measured) == 3 and all(r.stop == "completed" for r in measured)
    assert json.loads((report.run_dir / "run.json").read_text())["max_workers"] == example.MAX_CONCURRENT == 6
