"""A task's fingerprint is what it is given and what it observes: an output it is given is part of
its params, by its content, and a task it only waits for (`after=`) is no part of it. A resume
skips a matching task only when its output still reads under its output schema."""

import json

from pydantic import BaseModel

from contraagent import Pipeline, agent_task
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


def pipeline(tmp_path, agent):
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)


def tasks(instructions: str = "Write."):
    write = agent_task("write", instructions=instructions, output=Doc, max_turns=3, timeout_s=30)
    check = agent_task("check", instructions="Check.", output=Doc, max_turns=3, timeout_s=30)
    return write, check


def passing_on(instructions: str = "Write."):
    """`check` is given the output of `write` the flow received."""
    write, check = tasks(instructions)

    async def flow():
        await check("u", doc=await write("u"))

    return flow


def ordering(instructions: str = "Write."):
    """`check` only waits for `write` (`.options(after=)`): it reads nothing of it."""
    write, check = tasks(instructions)

    def flow():
        check.options(after=[write("u")])("u")

    return flow


class Agent(StubAgent):
    """A stub whose `write` writes `text`, which a test changes between runs."""

    def __init__(self) -> None:
        self.text = "first"
        super().__init__(
            {
                "write": lambda launch: {"unit": launch.unit, "text": self.text},
                "check": lambda launch: {"unit": launch.unit, "text": "checked"},
            }
        )


def keys(agent) -> list[str]:
    return [launch.key for launch in agent.launches]


def reruns(rep) -> dict[str, str]:
    rows = [json.loads(line) for line in (rep.run_dir / "journal.jsonl").read_text().splitlines()]
    return {r["key"]: r["rerun"] for r in rows if r["rerun"]}


def test_an_upstream_task_that_runs_again_and_writes_the_same_output_leaves_the_reader_skipped(tmp_path):
    agent = Agent()
    assert pipeline(tmp_path, agent).run(passing_on(), run_id="r").ok
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on("Write more."), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["write-u"]
    assert rep.results["check-u"].stop == "skipped"


def test_an_upstream_task_that_runs_again_and_writes_another_output_runs_the_reader_again(tmp_path):
    agent = Agent()
    assert pipeline(tmp_path, agent).run(passing_on(), run_id="r").ok
    agent.launches.clear()
    agent.text = "second"
    rep = pipeline(tmp_path, agent).run(passing_on("Write more."), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["write-u", "check-u"]
    assert reruns(rep)["check-u"].startswith("its fingerprint changed")


def test_an_output_rewritten_under_a_skipped_task_runs_its_reader_again(tmp_path):
    agent = Agent()
    first = pipeline(tmp_path, agent).run(passing_on(), run_id="r")
    assert first.ok
    (first.run_dir / "out/write/u.json").write_text(json.dumps({"unit": "u", "text": "edited"}))
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on(), run_id="r", resume=True)
    assert rep.results["write-u"].stop == "skipped"  # its fingerprint matches, and its output reads
    assert keys(agent) == ["check-u"]  # what it reads is not what the earlier attempt read


def test_an_output_that_no_longer_reads_runs_its_task_again(tmp_path):
    agent = Agent()
    first = pipeline(tmp_path, agent).run(passing_on(), run_id="r")
    assert first.ok
    (first.run_dir / "out/write/u.json").write_text("{}")
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on(), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["write-u"]  # it writes the same output again: check-u is skipped
    assert reruns(rep) == {"write-u": "its output no longer reads under its output schema"}


def test_an_unchanged_run_resumes_with_nothing_launched(tmp_path):
    agent = Agent()
    assert pipeline(tmp_path, agent).run(passing_on(), run_id="r").ok
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on(), run_id="r", resume=True)
    assert rep.ok and agent.launches == []


def test_a_task_that_only_waits_is_skipped_when_the_task_it_waits_for_runs_again(tmp_path):
    agent = Agent()
    assert pipeline(tmp_path, agent).run(ordering(), run_id="r").ok
    agent.launches.clear()
    agent.text = "second"
    rep = pipeline(tmp_path, agent).run(ordering("Write more."), run_id="r", resume=True)
    assert rep.ok and keys(agent) == ["write-u"]  # after= is no part of check's fingerprint
    assert rep.results["check-u"].stop == "skipped"


def test_after_does_not_change_the_fingerprint(tmp_path):
    write, check = tasks()

    def alone():
        check("u")

    def after():
        check.options(after=[write("u")])("u")

    agent = Agent()
    first = pipeline(tmp_path, agent).run(alone, run_id="a")
    second = pipeline(tmp_path, agent).run(after, run_id="b")
    assert first.results["check-u"].task.fingerprint == second.results["check-u"].task.fingerprint
