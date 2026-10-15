"""Recordings and replays (`Pipeline(record=)`, `Pipeline(replay=)`, `contraagent run
--record/--replay`): a run's task attempts kept, then played with nothing spent."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, Stop, agent_task, python_task
from contraagent.cli import main
from contraagent.execution.recording import RecordingError, base_key
from contraagent.monitor import Monitor
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
        execute=["count", "flaky"],
    )


def record(tmp_path, agent=None, flow_=flow, **kwargs):
    cwd = tree(tmp_path / "live")
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=cwd, stub=agent or stub(), record=tmp_path / "rec")
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def replay(tmp_path, flow_=flow, name="replay", execute=(), **kwargs):
    cwd = tree(tmp_path / name)
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / f"{name}-runs", cwd=cwd, replay=tmp_path / "rec", execute=execute)
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def test_a_replay_leaves_the_outputs_and_changes_the_recorded_run_left(tmp_path):
    ran.clear()
    live = record(tmp_path)
    assert live.ok, live.failed
    assert sorted(p.relative_to(tmp_path / "rec").as_posix() for p in (tmp_path / "rec").glob("*/*.json")) == [
        "count/python_count.json",
        "summarize/summarize-alpha.json",
        "write/write-alpha.json",
        "write/write-beta.json",
    ]
    ran.clear()
    played = replay(tmp_path)
    assert played.ok, played.failed
    assert played.run_id == "flow-replay" and played.value == 2
    assert ran == []  # a Python task plays its recording: its function does not run
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


def test_a_python_task_of_a_kind_executed_runs_its_function(tmp_path):
    record(tmp_path)
    ran.clear()
    played = replay(tmp_path, execute=["count"])
    assert played.ok, played.failed
    assert ran == ["count"] and played.value == 2


calls: list[int] = []


@python_task(retries=2, retry_on=(ConnectionError,))
def flaky(n: int) -> Note:
    calls.append(n)
    if len(calls) == 1:
        raise ConnectionError("the index server is not up yet")
    if n < 0:
        raise ValueError("negative")
    return Note(title=f"n={n}")


def test_a_python_task_plays_each_recorded_call_its_retries_included(tmp_path):
    calls.clear()
    live = record(tmp_path, flow_=lambda units: flaky(n=3))
    assert live.ok, live.failed
    assert [r["stop"] for r in journal(live)] == ["error", "completed"]
    body = json.loads((tmp_path / "rec" / "flaky" / "python_flaky.json").read_text())
    assert body["executor"] == "python"
    assert [(a["stop"], a["retry_on"]) for a in body["attempts"]] == [("error", True), ("completed", False)]
    calls.clear()
    played = replay(tmp_path, flow_=lambda units: flaky(n=3))
    assert played.ok, played.failed
    assert calls == []  # the function is not called
    assert [r["stop"] for r in journal(played)] == ["error", "completed"]
    assert played.results["python:flaky"].reason == ""
    assert outputs(played) == outputs(live)


def test_a_python_task_with_no_recording_ends_on_an_error_that_names_it(tmp_path):
    record(tmp_path, flow_=lambda units: write(units[0]))
    ran.clear()
    played = replay(tmp_path, flow_=lambda units: count(notes=[]))
    assert ran == []
    assert played.results["python:count"].stop == "error"
    assert played.results["python:count"].reason == "no recording for python:count"


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
    assert [r["key"] for r in journal(played)] == ["write-beta"]  # one attempt: a retry finds no recording either


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
    assert main([*args, "--replay", "rec", "--execute", "count", "--run-id", "executed"]) == 0
    assert main([*args, "--execute", "count"]) == 2
    assert main([*args, "--record-missing"]) == 2
    assert main([*args, "--replay", "rec", "--record-missing", "--stub"]) == 2


def test_the_monitor_names_a_replay_and_its_recordings(tmp_path):
    live = record(tmp_path)
    played = replay(tmp_path)
    runs = {r["run"]: r for r in Monitor(tmp_path / "replay-runs").runs()}
    assert runs[played.run_id]["stub"] is True
    assert runs[played.run_id]["replay"] == str((tmp_path / "rec").resolve())
    assert {r["replay"] for r in Monitor(tmp_path / "runs").runs()} == {""}
    assert live.ok


def test_record_missing_fills_in_one_missing_recording_and_plays_the_rest(tmp_path):
    record(tmp_path, flow_=lambda units: [write(units[0]), count(notes=[])])
    agent = stub()
    ran.clear()
    cwd = tree(tmp_path / "fill")
    runs, rec = tmp_path / "fill-runs", tmp_path / "rec"
    pipeline = Pipeline(PipelineConfig({}), runs_dir=runs, cwd=cwd, replay=rec, record_missing=True, backends=agent.backends())
    filled = pipeline.run(lambda units: [write(u) for u in units] + [count(notes=[])], run_id="fill", units=["alpha", "beta"])
    assert filled.ok, filled.failed
    assert [launch.key for launch in agent.launches] == ["write-beta"]  # only the task with no recording launched
    assert ran == []  # the Python task played its recording
    assert {r["key"]: r["replayed"] for r in journal(filled)} == {"write-alpha": True, "write-beta": False, "python:count": True}
    assert (tmp_path / "rec" / "write" / "write-beta.json").exists()
    info = json.loads((filled.run_dir / "run.json").read_text())
    assert info["stub"] is False and info["replay"] == str((tmp_path / "rec").resolve())
    # The directory filled in replays every task, nothing launched.
    played = replay(tmp_path, flow_=lambda units: [write(u) for u in units], name="again")
    assert played.ok, played.failed
    assert all(r["replayed"] for r in journal(played))


def test_record_missing_runs_a_python_task_with_no_recording_and_records_it(tmp_path):
    ran.clear()
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, replay=tmp_path / "new", record_missing=True)
    report = pipeline.run(lambda: count(notes=[Note(title="a")]), run_id="fill")
    assert report.ok and ran == ["count"]
    assert json.loads((tmp_path / "new" / "count" / "python_count.json").read_text())["attempts"][0]["stop"] == "completed"


def test_a_file_over_the_cap_is_kept_by_hash_and_its_task_cannot_be_replayed(tmp_path):
    lines: list[str] = []
    cwd = tree(tmp_path / "live")
    rec = tmp_path / "rec"
    pipeline = Pipeline(runs_dir=tmp_path / "runs", cwd=cwd, stub=stub(), record=rec, record_max_file_mb=1e-6, log=lines.append)
    live = pipeline.run(lambda units: [write(units[0]), count(notes=[Note(title="a")] * 10)], units=["alpha"])
    assert live.ok, live.failed
    hashed = [line for line in lines if "stored by hash only" in line]
    assert any(line.startswith("[record] write-alpha: out/write/alpha.json (<0.1 MB)") for line in hashed), lines
    body = json.loads((tmp_path / "rec" / "write" / "write-alpha.json").read_text())
    assert {k["path"] for k in body["attempts"][0]["by_hash"]} >= {"out/write/alpha.json", "topics/alpha/old.md"}
    assert not list((tmp_path / "rec" / "write" / "write-alpha").rglob("alpha.json"))
    summary = lines[-1]
    assert summary.startswith(f"[record] {rec}: ")
    assert summary.endswith("files stored by hash | 2 tasks cannot be replayed: kinds count, write")

    played = replay(tmp_path, flow_=lambda units: [write(units[0]), count(notes=[Note(title="a")] * 10)], units=["alpha"])
    agent, python = played.results["write-alpha"], played.results["python:count"]
    assert agent.stop == python.stop == "error"
    assert agent.reason.startswith("the recording of write-alpha holds out/write/alpha.json (<0.1 MB) by hash only: record it again")
    assert python.reason.endswith("by hash only: run kind count with --execute, or use --record-missing")
    assert [r["key"] for r in journal(played)].count("write-alpha") == 1  # not retried

    ran.clear()
    executed = replay(tmp_path, flow_=lambda units: count(notes=[]), name="executed", execute=["count"])
    assert executed.ok and ran == ["count"]

    agent = stub()
    runs, cwd = tmp_path / "fill-runs", tree(tmp_path / "fill")
    filled = Pipeline(PipelineConfig({}), runs_dir=runs, cwd=cwd, replay=rec, record_missing=True, backends=agent.backends())
    assert filled.run(lambda: write("alpha")).ok
    assert [launch.key for launch in agent.launches] == ["write-alpha"]  # a recording by hash counts as missing
    assert json.loads((rec / "write" / "write-alpha.json").read_text())["attempts"][0]["by_hash"] == []


def test_record_missing_is_refused_where_it_cannot_record(tmp_path):
    with pytest.raises(TypeError, match="give replay= the recordings directory"):
        Pipeline(record_missing=True)
    for given in ({"stub": StubAgent()}, {"record": tmp_path / "x"}):
        with pytest.raises(TypeError, match=f"not with {next(iter(given))}="):
            Pipeline(replay=tmp_path / "rec", record_missing=True, **given)
    with pytest.raises(TypeError, match="execute= is for a replay"):
        Pipeline(execute=["count"])
    with pytest.raises(TypeError, match="record_max_file_mb= caps a recording's files"):
        Pipeline(record_max_file_mb=10)
    with pytest.raises(ValueError, match="not a positive number"):
        Pipeline(record=tmp_path / "x", record_max_file_mb=0)
