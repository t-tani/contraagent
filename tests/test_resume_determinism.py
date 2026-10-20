"""A resume takes the path the run took: it gives the flow the results of the tasks it skips
in the order the journal recorded them, names each part of a fingerprint that changed when it
runs a task again (and a divergence: other params for the same outputs), compares the file an
`output_of` task fills in with what the earlier attempts left in it, and skips a task whose
fingerprint is complete only when it starts before that task waits for a slot or a deadline
defers it."""

import asyncio
import json
import threading
from types import SimpleNamespace

from pydantic import BaseModel

from contraagent import Pipeline, Task, TaskResult, agent_task, python_task
from contraagent.engine import WorkQueue
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


class Item(BaseModel):
    id: str
    summary: str = ""


class Report(BaseModel):
    items: list[Item]


def pipeline(tmp_path, agent, log=None, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=log or (lambda line: None), **kw)


def keys(agent) -> list[str]:
    return [launch.key for launch in agent.launches]


def reruns(rep) -> dict[str, str]:
    rows = [json.loads(line) for line in (rep.run_dir / "journal.jsonl").read_text().splitlines()]
    return {r["key"]: r["rerun"] for r in rows if r["rerun"]}


class Agent(StubAgent):
    """A stub whose `write` writes `text`, which a test changes between runs."""

    def __init__(self) -> None:
        self.text = "first"
        super().__init__(
            {
                "write": lambda launch: {"unit": launch.unit, "text": self.text},
                "check": lambda launch: {"unit": launch.unit, "text": "checked"},
                "report": lambda launch: {"unit": launch.unit, "text": str(launch.params)},
            }
        )


def doc_task(kind: str, instructions: str = "Write."):
    return agent_task(kind, instructions=instructions, output=Doc, max_turns=3, timeout_s=30)


# --- the order the results of skipped tasks are given in ------------------------------------


def in_finishing_order():
    """A flow whose params depend on the order its tasks finish in: `y` is called with the
    higher priority, so with one slot it finishes first."""
    write, report = doc_task("write"), doc_task("report")

    async def flow():
        order: list[str] = []

        async def one(unit: str, priority: float) -> None:
            await write.options(priority=priority)(unit)
            order.append(unit)

        await asyncio.gather(one("x", 0), one("y", 2))
        await report("r", order=",".join(order))

    return flow


def test_a_resume_gives_the_skipped_results_in_the_order_the_journal_recorded_them(tmp_path):
    agent = Agent()
    first = pipeline(tmp_path, agent, max_concurrent=1).run(in_finishing_order(), run_id="r")
    assert first.ok and keys(agent) == ["write-y", "write-x", "report-r"]
    agent.launches.clear()
    rep = pipeline(tmp_path, agent, max_concurrent=1).run(in_finishing_order(), run_id="r", resume=True)
    # Given in the order they were queued (x first), the flow would call report with other params.
    assert rep.ok and agent.launches == []
    assert {key: r.stop for key, r in rep.results.items()} == {"write-x": "skipped", "write-y": "skipped", "report-r": "skipped"}


# --- why a task runs again ---------------------------------------------------------------------


def reading(state: dict[str, str]):
    """`check` is given the output of `write` the flow received, and a note from `state`."""
    write, check = doc_task("write", state.get("instructions", "Write.")), doc_task("check")

    async def flow():
        doc = await write("u")
        await check("u", doc=doc, note=state["note"])

    return flow


def test_a_changed_definition_is_named(tmp_path):
    agent = Agent()
    state = {"note": "a"}
    assert pipeline(tmp_path, agent).run(reading(state), run_id="r").ok
    agent.launches.clear()
    state["instructions"] = "Write more."
    rep = pipeline(tmp_path, agent).run(reading(state), run_id="r", resume=True)
    # write-u wrote the same output again: check-u is skipped.
    assert rep.ok and keys(agent) == ["write-u"]
    assert reruns(rep) == {"write-u": "its fingerprint changed: its definition"}


def test_a_changed_input_is_named(tmp_path):
    agent = Agent()
    state = {"note": "a"}
    assert pipeline(tmp_path, agent).run(reading(state), run_id="r").ok
    agent.launches.clear()
    state["instructions"], agent.text = "Write more.", "second"
    rep = pipeline(tmp_path, agent).run(reading(state), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["write-u", "check-u"]
    assert reruns(rep)["check-u"] == "its fingerprint changed: its params"  # the output it is given is part of them


def test_changed_params_for_the_same_outputs_are_a_divergence_and_a_warning(tmp_path):
    agent = Agent()
    state = {"note": "a"}
    assert pipeline(tmp_path, agent).run(reading(state), run_id="r").ok
    agent.launches.clear()
    state["note"] = "b"  # what a clock or randomness gives the flow
    lines: list[str] = []
    rep = pipeline(tmp_path, agent, log=lines.append).run(reading(state), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["check-u"]
    why = reruns(rep)["check-u"]
    assert why.startswith("divergence: the flow gave it other params for the same outputs") and why.endswith("changed: its params")
    assert [line for line in lines if line.startswith("[resume]")] == [f"[resume] check-u: {why}"]


def test_changed_params_beside_a_changed_input_are_no_divergence(tmp_path):
    agent = Agent()
    state = {"note": "a"}
    assert pipeline(tmp_path, agent).run(reading(state), run_id="r").ok
    agent.launches.clear()
    state["instructions"], state["note"], agent.text = "Write more.", "b", "second"
    rep = pipeline(tmp_path, agent).run(reading(state), run_id="r", resume=True)
    assert reruns(rep)["check-u"] == "its fingerprint changed: its params"  # write-u ran again: no divergence


# --- a file an output_of task fills in ---------------------------------------------------------


@python_task
def outline(unit: str) -> Report:
    return Report(items=[Item(id=f"{unit}-1"), Item(id=f"{unit}-2")])


fill = agent_task("fill", instructions="Summarize.", output=Report, output_of=outline, max_turns=3, timeout_s=30)
polish = agent_task("polish", instructions="Polish.", output=Report, output_of=outline, max_turns=3, timeout_s=30)


def filling():
    outline("a")
    fill("a")
    polish("a")


def filler() -> StubAgent:
    return StubAgent(
        {
            "fill": lambda launch: {"items": [{"id": "a-1", "summary": "one"}, {"id": "a-2", "summary": "two"}]},
            "polish": lambda launch: {"items": [{"id": "a-1", "summary": "One."}, {"id": "a-2", "summary": "Two."}]},
        }
    )


def test_an_unchanged_file_leaves_the_tasks_that_fill_it_in_skipped(tmp_path):
    agent = filler()
    first = pipeline(tmp_path, agent).run(filling, run_id="r")
    assert first.ok and keys(agent) == ["fill-a", "polish-a"]
    rows = {r["key"]: r for r in map(json.loads, (first.run_dir / "journal.jsonl").read_text().splitlines())}
    # What fill left is what polish found.
    assert rows["fill-a"]["output_of_after"] == rows["polish-a"]["fingerprint_parts"]["output_of"]
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(filling, run_id="r", resume=True)
    assert rep.ok and agent.launches == []
    assert {key: r.stop for key, r in rep.results.items()} == {"python:outline-a": "skipped", "fill-a": "skipped", "polish-a": "skipped"}


def test_a_file_changed_by_hand_runs_again_the_tasks_after_its_writer(tmp_path):
    agent = filler()
    first = pipeline(tmp_path, agent).run(filling, run_id="r")
    assert first.ok
    path = first.run_dir / "out/outline/a.json"
    path.write_text(json.dumps({"items": [{"id": "a-1", "summary": "edited"}]}))
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(filling, run_id="r", resume=True)
    assert rep.results["python:outline-a"].stop == "skipped"  # its output still reads
    assert rep.ok and keys(agent) == ["fill-a", "polish-a"]
    why = "the file it fills in (output_of) is not as the earlier attempts left it"
    assert reruns(rep) == {"fill-a": why, "polish-a": why}


# --- a task whose fingerprint is complete only when it starts ------------------------------------


class Runner:
    """Runs a task by waiting up to 10 seconds for the gate its params name, if any."""

    def __init__(self) -> None:
        self.gates: dict[str, threading.Event] = {}
        self.launched: list[str] = []

    def config(self, task: Task) -> SimpleNamespace:
        return SimpleNamespace(max_concurrent=None)

    def run(self, task: Task) -> TaskResult:
        self.launched.append(task.key)
        if "gate" in task.params:
            self.gates.setdefault(task.params["gate"], threading.Event()).wait(timeout=10)
        return TaskResult(task=task, ok=True, stop="completed")


def test_a_resume_skips_a_task_complete_at_its_start_while_every_slot_is_taken(tmp_path):
    runner = Runner()
    runner.gates["slow"] = threading.Event()
    ends: list[str] = []

    def follow_up(result: TaskResult) -> list[Task]:
        ends.append(result.task.key)
        if result.task.key == "late":
            runner.gates["slow"].set()  # the slow task ends once the skip came
        return []

    q = WorkQueue(runner, follow_up=follow_up, max_concurrent=1, skip=lambda task: task.key in ("dep", "late"))
    q.add(Task("slow", key="slow", params={"gate": "slow"}, estimate_s=1000))
    q.add(Task("late", key="late", after=("dep",), fingerprint_at_start=True))  # waits for dep
    q.add(Task("dep", key="dep"))  # skipped at once: late's dependencies are done
    q.run()
    assert runner.launched == ["slow"]
    assert ends == ["dep", "late", "slow"]


def test_a_resume_skips_a_task_complete_at_its_start_that_a_deadline_would_defer(tmp_path):
    runner = Runner()
    # From the start, the endgame: a task whose work is longer than the time left is deferred.
    q = WorkQueue(runner, max_concurrent=1, deadline_s=600, slack_s=600, skip=lambda task: True)
    q.add(Task("late", key="late", fingerprint_at_start=True, estimate_s=3600))
    summary = q.run()
    assert runner.launched == [] and summary["by_stop"] == {"skipped": 1} and summary["deferred"] == []
