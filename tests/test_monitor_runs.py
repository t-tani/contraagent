"""The monitor's list of runs: a run's row is made again only when a record it is made of
changes, and a run directory may be a link to a directory kept elsewhere."""

import json

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, agent_task
from contraagent._internal.runs.names import BadName
from contraagent.monitor import DirectorySource, Monitor
from contraagent.testing import StubAgent


class Doc(BaseModel):
    unit: str
    text: str


def make_run(runs, run_id: str, units=("a", "b")) -> None:
    write = agent_task("write", instructions="Write.", output=Doc, max_turns=3, timeout_s=30)
    agent = StubAgent({"write": lambda launch: {"unit": launch.unit, "text": "t"}})
    Pipeline(None, runs_dir=runs, backends=agent.backends(), cwd=runs.parent, log=lambda line: None).run(
        lambda: [write(u) for u in units], run_id=run_id
    )


def test_a_run_s_row_is_made_again_only_when_a_record_of_it_changes(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    make_run(runs, "one")
    make_run(runs, "two")
    monitor = Monitor(runs)
    made: list[str] = []
    real = monitor._run_row
    monkeypatch.setattr(monitor, "_run_row", lambda run, live: made.append(run) or real(run, live=live))
    first = monitor.runs()
    assert sorted(made) == ["one", "two"] and {r["run"]: r["attempts"] for r in first} == {"one": 2, "two": 2}
    made.clear()
    assert monitor.runs() == first and made == []
    journal = runs / "one" / "journal.jsonl"
    row = json.loads(journal.read_text().splitlines()[0])
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**row, "key": "write-c", "unit": "c"}) + "\n")
    again = monitor.runs()
    assert made == ["one"] and {r["run"]: r["attempts"] for r in again} == {"one": 3, "two": 2}


def test_a_run_directory_linked_into_the_runs_directory_is_a_run(tmp_path):
    kept, runs = tmp_path / "kept", tmp_path / "runs"
    make_run(kept, "old")
    make_run(runs, "new")
    (runs / "old").symlink_to(kept / "old", target_is_directory=True)
    (runs / "old.lock").write_text("", encoding="utf-8")  # beside the runs, as a run's lock is
    monitor = Monitor(runs)
    assert sorted(r["run"] for r in monitor.runs()) == ["new", "old"]
    assert monitor.plan("old")["nodes"]
    source = DirectorySource(runs)
    assert source.info("old")["run_id"] == "old"
    # A link inside the linked run that leads out of it is refused still.
    (kept / "old" / "streams" / "out.stream.jsonl").symlink_to(tmp_path / "elsewhere.jsonl")
    with pytest.raises(BadName, match="leaves"):
        source.path("old", "streams/out.stream.jsonl")


def test_a_link_to_a_file_is_no_run(tmp_path):
    runs = tmp_path / "runs"
    make_run(runs, "one")
    (tmp_path / "file").write_text("x", encoding="utf-8")
    (runs / "notes").symlink_to(tmp_path / "file")
    assert [r["run"] for r in Monitor(runs).runs()] == ["one"]
