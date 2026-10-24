"""A run that resumes from another run (`Pipeline.run(resume_from=)`, `--resume-from`): a new
run id skips, by the resume's rule, what the other run finished, runs the rest, and holds
the records of the work it took over, so it can be resumed, and resumed from, in turn."""

import asyncio
import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import EarlierRunError, Pipeline, RunExists, agent_task
from contraagent._internal.cli import main
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


class Given(BaseModel):
    doc: Doc


class Order(BaseModel):
    order: str


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


def pipeline(tmp_path, agent, **kw) -> Pipeline:
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None, **kw)


def passing_on(instructions: str = "Write."):
    """`check` is given the output of `write` the flow received."""
    write = agent_task("write", instructions=instructions, output=Doc, max_turns=3, timeout_s=30)
    check = agent_task("check", instructions="Check.", params=Given, output=Doc, max_turns=3, timeout_s=30)

    async def flow():
        await check("u", Given(doc=await write("u")))

    return flow


def keys(agent) -> list[str]:
    return [launch.key for launch in agent.launches]


def rows(rep) -> list[dict]:
    return [json.loads(line) for line in (rep.run_dir / "journal.jsonl").read_text().splitlines()]


def test_a_new_run_skips_what_the_earlier_run_finished_and_holds_its_records(tmp_path):
    agent = Agent()
    old = pipeline(tmp_path, agent).run(passing_on(), run_id="old")
    before = (old.run_dir / "journal.jsonl").read_text()
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on(), run_id="new", resume_from="old")
    assert rep.ok and agent.launches == []
    assert {k: r.stop for k, r in rep.results.items()} == {"write-u": "skipped", "check-u": "skipped"}
    by_key = {r["key"]: r for r in rows(rep)}
    old_rows = {r["key"]: r for r in rows(old)}
    for key in ("write-u", "check-u"):
        assert by_key[key]["stop"] == "skipped" and by_key[key]["resumed_from"] == "old" and by_key[key]["cost_usd"] is None
        assert by_key[key]["fingerprint"] == old_rows[key]["fingerprint"]
        assert by_key[key]["fingerprint_parts"] == old_rows[key]["fingerprint_parts"]
    info = json.loads((rep.run_dir / "run.json").read_text())
    assert info["resumed_from"] == {"run_id": "old", "run_uid": json.loads((old.run_dir / "run.json").read_text())["run_uid"]}
    assert info["run_uid"] != info["resumed_from"]["run_uid"]
    # The outputs, and the records that name them, are the new run's.
    assert json.loads((rep.run_dir / "out" / "write" / "u.json").read_text())["text"] == "first"
    record = json.loads((rep.run_dir / "contracts" / "write-u.json").read_text())
    assert Path(record["outputs"][0]["path"]) == (rep.run_dir / "out" / "write" / "u.json").resolve()
    assert (old.run_dir / "journal.jsonl").read_text() == before


def test_a_task_whose_fingerprint_changed_runs_and_says_why(tmp_path):
    agent = Agent()
    pipeline(tmp_path, agent).run(passing_on(), run_id="old")
    agent.launches.clear()
    rep = pipeline(tmp_path, agent).run(passing_on("Write more."), run_id="new", resume_from="old")
    # write-u wrote the same output again: check-u is taken over still.
    assert rep.ok and keys(agent) == ["write-u"]
    by_key = {r["key"]: r for r in rows(rep)}
    assert by_key["write-u"]["rerun"] == "its fingerprint changed: its definition" and by_key["write-u"]["resumed_from"] == ""
    assert by_key["check-u"]["stop"] == "skipped" and by_key["check-u"]["resumed_from"] == "old"
    agent.launches.clear()
    agent.text = "second"
    rep = pipeline(tmp_path, agent).run(passing_on("Write again."), run_id="newer", resume_from="new")
    assert rep.ok and keys(agent) == ["write-u", "check-u"]


def test_the_new_run_resumes_and_is_resumed_from_as_any_run(tmp_path):
    agent = Agent()
    pipeline(tmp_path, agent).run(passing_on(), run_id="old")
    pipeline(tmp_path, agent).run(passing_on(), run_id="new", resume_from="old")
    agent.launches.clear()
    again = pipeline(tmp_path, agent).run(passing_on(), run_id="new", resume=True)
    assert again.ok and agent.launches == []
    assert json.loads((again.run_dir / "run.json").read_text())["resumed_from"]["run_id"] == "old"
    chained = pipeline(tmp_path, agent).run(passing_on(), run_id="newer", resume_from="new")
    assert chained.ok and agent.launches == []
    assert {r["resumed_from"] for r in rows(chained)} == {"new"}


def in_finishing_order():
    """A flow whose params depend on the order its tasks finish in: `y` is called with the
    higher priority, so with one slot it finishes first."""
    write = agent_task("write", instructions="Write.", output=Doc, max_turns=3, timeout_s=30)
    report = agent_task("report", instructions="Write.", params=Order, output=Doc, max_turns=3, timeout_s=30)

    async def flow():
        order: list[str] = []

        async def one(unit: str, priority: float) -> None:
            await write.options(priority=priority)(unit)
            order.append(unit)

        await asyncio.gather(one("x", 0), one("y", 2))
        await report("r", Order(order=",".join(order)))

    return flow


def test_the_flow_is_given_the_skipped_results_in_the_order_the_earlier_run_recorded_them(tmp_path):
    agent = Agent()
    assert pipeline(tmp_path, agent, max_concurrent=1).run(in_finishing_order(), run_id="old").ok
    assert keys(agent) == ["write-y", "write-x", "report-r"]
    agent.launches.clear()
    rep = pipeline(tmp_path, agent, max_concurrent=1).run(in_finishing_order(), run_id="new", resume_from="old")
    assert rep.ok and agent.launches == []
    # The new journal holds them in the order the flow received them: a resume of it takes that path too.
    assert [r["key"] for r in rows(rep)] == ["write-y", "write-x", "report-r"]
    assert pipeline(tmp_path, agent, max_concurrent=1).run(in_finishing_order(), run_id="new", resume=True).ok
    assert agent.launches == []


def test_what_a_run_cannot_resume_from_is_refused_before_anything_is_written(tmp_path):
    agent = Agent()
    p = pipeline(tmp_path, agent)
    with pytest.raises(EarlierRunError, match="no run 'gone'"):
        p.run(passing_on(), run_id="new", resume_from="gone")
    assert not (tmp_path / "runs" / "new").exists()
    p.run(passing_on(), run_id="old")
    with pytest.raises(ValueError, match="resume=True"):
        p.run(passing_on(), run_id="new", resume_from="old", resume=True)
    with pytest.raises(ValueError, match="cannot resume from itself"):
        p.run(passing_on(), run_id="old", resume_from="old")
    p.run(passing_on(), run_id="taken")
    with pytest.raises(RunExists):
        p.run(passing_on(), run_id="taken", resume_from="old")
    # The earlier run's lock was let go: another run resumes from it.
    assert p.run(passing_on(), run_id="new", resume_from="old").ok


def test_a_run_another_process_drives_is_refused(tmp_path):
    from contraagent._internal.platform.locks import locks

    agent = Agent()
    p = pipeline(tmp_path, agent)
    p.run(passing_on(), run_id="old")
    fd = os.open(tmp_path / "runs" / "old.lock", os.O_RDWR)
    try:
        assert locks.try_lock(fd)
        with pytest.raises(EarlierRunError, match="drives run 'old'"):
            p.run(passing_on(), run_id="new", resume_from="old")
    finally:
        locks.unlock(fd)
        os.close(fd)


def test_the_command_line_refuses_resume_from_with_resume(tmp_path, capsys):
    flow = tmp_path / "flow.py"
    flow.write_text("def docs():\n    pass\n", encoding="utf-8")
    code = main(["run", f"{flow}:docs", "--stub", "--resume", "--resume-from", "old", "--runs-dir", str(tmp_path / "runs")])
    assert code == 2 and "--resume-from: not with --resume" in capsys.readouterr().err


def test_an_import_names_the_tasks_the_run_took_over(tmp_path):
    from contraagent import import_recording

    agent = Agent()
    pipeline(tmp_path, agent).run(passing_on(), run_id="old")
    rep = pipeline(tmp_path, agent).run(passing_on("Write more."), run_id="new", resume_from="old")
    report = import_recording(rep.run_dir, tmp_path / "recordings")
    assert report.imported == ("write-u",)
    assert "took it over from run old" in report.not_imported["check-u"]
