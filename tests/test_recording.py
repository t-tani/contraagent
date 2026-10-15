"""Recordings and replays (`Pipeline(record=)`, `Pipeline(replay=)`, `contraagent run
--record/--replay`): a run's agent task attempts kept, then played with nothing spent."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, Stop, agent_task, python_task
from contraagent.cli import main
from contraagent.execution.recording import RecordingError, base_key
from contraagent.testing import StubAgent, fails


class Note(BaseModel):
    title: str


write = agent_task("write", instructions="Write a note on the unit.", output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
summarize = agent_task(
    "summarize", instructions="Summarize the unit.", output=Note, output_from="message", unwrap=True, max_turns=5, timeout_s=60
)
ran: list[str] = []


@python_task
def count(notes: list[Note]) -> int:
    ran.append("count")
    return len(notes)


def flow(units: list[str]):
    notes = yield [write(u) for u in units]
    yield summarize(units[0])
    return (yield count(notes=notes))


def edit(launch):
    """Writes a note, creates and modifies a file under the unit's topic, deletes one."""
    root = Path(launch.call.cwd) / "topics" / launch.unit
    (root / "old.md").write_text(f"old, changed by {launch.key}")
    (root / "gone.md").unlink(missing_ok=True)
    (root / "new" / "a.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "new" / "a.md").write_text(f"new from {launch.key}")
    return {"title": launch.key}


def tree(cwd: Path, units=("alpha", "beta")) -> Path:
    for u in units:
        (cwd / "topics" / u).mkdir(parents=True)
        (cwd / "topics" / u / "old.md").write_text("old")
        (cwd / "topics" / u / "gone.md").write_text("gone")
    return cwd


def topics(cwd: Path) -> dict[str, str]:
    return {p.relative_to(cwd).as_posix(): p.read_text() for p in sorted((cwd / "topics").rglob("*")) if p.is_file()}


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def outputs(report) -> dict[str, str]:
    out = report.run_dir / "out"
    return {p.relative_to(out).as_posix(): p.read_text() for p in sorted(out.rglob("*")) if p.is_file()}


def stub() -> StubAgent:
    return StubAgent(
        {
            "write": edit,
            "summarize": lambda launch: Note(title="summary").model_dump_json().join(["Here it is:\n", "\nDone."]),
        },
        default={"title": "x"},
        execute=["count"],
    )


def record(tmp_path, agent=None, flow_=flow, **kwargs):
    cwd = tree(tmp_path / "live")
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=cwd, stub=agent or stub(), record=tmp_path / "rec")
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def replay(tmp_path, flow_=flow, name="replay", **kwargs):
    cwd = tree(tmp_path / name)
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / f"{name}-runs", cwd=cwd, replay=tmp_path / "rec")
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def test_a_replay_leaves_the_outputs_and_changes_the_recorded_run_left(tmp_path):
    ran.clear()
    live = record(tmp_path)
    assert live.ok, live.failed
    assert sorted(p.relative_to(tmp_path / "rec").as_posix() for p in (tmp_path / "rec").glob("*/*.json")) == [
        "summarize/summarize-alpha.json",
        "write/write-alpha.json",
        "write/write-beta.json",
    ]
    ran.clear()
    played = replay(tmp_path)
    assert played.ok, played.failed
    assert played.run_id == "flow-replay" and played.value == 2
    assert ran == ["count"]  # a Python task runs its function in a replay
    assert outputs(played) == outputs(live)
    assert "summarize/alpha.json.message.txt" in outputs(played)  # the whole final message, beside the unwrapped output
    assert topics(tmp_path / "replay") == topics(tmp_path / "live")
    live_rows = {r["key"]: r for r in journal(live)}
    for row in journal(played):
        assert row["changes"] == live_rows[row["key"]]["changes"]
        assert row["stop"] == live_rows[row["key"]]["stop"]
        assert row["cost_usd"] in (0, None)
    info = json.loads((played.run_dir / "run.json").read_text())
    assert info["stub"] is True and info["replay"] == str((tmp_path / "rec").resolve())
    stream = "streams/write-alpha.stream.jsonl"
    assert (played.run_dir / stream).read_text() == (live.run_dir / stream).read_text()


def test_each_attempt_is_played_in_order_and_the_last_repeats(tmp_path):
    agent = StubAgent({"write": [fails(Stop.TIMEOUT, "killed"), edit]}, default={"title": "x"})
    live = record(tmp_path, agent, flow_=lambda units: write(units[0]))
    assert live.ok
    assert [r["stop"] for r in journal(live)] == ["timeout", "completed"]
    played = replay(tmp_path, flow_=lambda units: write(units[0]))
    assert [r["stop"] for r in journal(played)] == ["timeout", "completed"]
    assert topics(tmp_path / "replay") == topics(tmp_path / "live")


def test_a_task_with_no_recording_ends_on_an_error_that_names_it(tmp_path):
    record(tmp_path, flow_=lambda units: write(units[0]))
    played = replay(tmp_path, flow_=lambda units: write(units[1]))
    result = played.results["write-beta"]
    assert result.stop == Stop.ERROR.value
    assert result.reason == "no recording for write-beta"


def test_a_key_minted_with_a_tilde_takes_the_next_recording_of_its_base(tmp_path):
    record(tmp_path, flow_=lambda units: [write(units[0]), write(units[0], key="write-alpha~5")])
    played = replay(tmp_path, flow_=lambda units: [write(units[0]), write(units[0])])
    assert played.ok, played.failed
    assert json.loads(outputs(played)["write/alpha~2.json"])["title"] == "write-alpha~5"
    assert played.results["write-alpha~2"].reason.startswith("played the recording of write-alpha~5")
    assert base_key("write-alpha~12") == ("write-alpha", 12) and base_key("write-alpha") == ("write-alpha", 1)


def test_a_recording_of_another_fingerprint_is_played_and_noted(tmp_path):
    record(tmp_path, flow_=lambda units: write(units[0]))
    other = agent_task("write", instructions="Write a longer note.", output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
    played = replay(tmp_path, flow_=lambda units: other(units[0]))
    assert played.ok
    assert "the recording has another fingerprint" in played.results["write-alpha"].reason


def test_a_replay_is_not_combined_with_what_would_launch_or_record(tmp_path):
    record(tmp_path, flow_=lambda units: write(units[0]))
    for given in ({"stub": StubAgent()}, {"backends": StubAgent().backends()}, {"record": tmp_path / "x"}, {"preflight": True}):
        with pytest.raises(TypeError, match=f"not with {next(iter(given))}="):
            Pipeline(replay=tmp_path / "rec", **given)
    with pytest.raises(RecordingError, match="not a directory"):
        Pipeline(replay=tmp_path / "missing")
    (tmp_path / "empty").mkdir()
    with pytest.raises(RecordingError, match="holds no recording"):
        Pipeline(replay=tmp_path / "empty")


def cli_flow(units: list[str]):
    yield [write(u) for u in units]


def test_the_cli_records_and_replays(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.chdir(tmp_path)
    args = ["run", f"{__file__}:cli_flow", "--kwargs", '{"units": ["alpha"]}', "--runs-dir", str(tmp_path / "runs")]
    assert main([*args, "--stub", "--record", "rec"]) == 0, capsys.readouterr().out
    assert (tmp_path / "rec" / "write" / "write-alpha.json").exists()
    assert main([*args, "--replay", "rec"]) == 0, capsys.readouterr().out
    assert json.loads((tmp_path / "runs" / "cli_flow-replay" / "run.json").read_text())["replay"] == str(tmp_path / "rec")
    assert main([*args, "--replay", "rec", "--stub"]) == 2
    assert main([*args, "--replay", "rec", "--record", "rec2"]) == 2
    assert main([*args, "--replay", "rec", "--execute", "count"]) == 2
