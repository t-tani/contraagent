"""Recordings imported from a run that was not recorded (`import_recording`, `contraagent
recording import`): what a replay then plays, and what the import leaves out."""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Partial, Pipeline, PipelineConfig, RecordingError, agent_task, import_recording, python_task
from contraagent._internal.cli import main
from contraagent.backends import Stop
from contraagent.testing import StubAgent, fails, writes


class Note(BaseModel):
    title: str


write = agent_task("write", instructions="Write a note on the unit.", output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
summarize = agent_task(
    "summarize", instructions="Summarize the unit.", output=Note, output_from="message", unwrap=True, max_turns=5, timeout_s=60
)
tidy = agent_task("tidy", instructions="Tidy every topic.", output=Note, changes=["topics/**"], max_turns=5, timeout_s=60)
ran: list[str] = []


@python_task
def count(notes: list[Note]) -> int:
    ran.append("count")
    return len(notes)


@python_task
def look_up(topic: str) -> Note | Partial[Note]:
    ran.append("look_up")
    return Partial(Note(title=f"{topic}, from the cache"), reason="the local index server is not up")


async def flow(units: list[str]):
    notes = await asyncio.gather(*[write(u) for u in units])
    await summarize(units[0])
    return await count(notes=notes)


def edit(launch):
    """Writes a note, creates and modifies a file under the unit's topic, deletes one."""
    root = Path(launch.call.cwd) / "topics" / launch.unit
    (root / "old.md").write_text(f"old, changed by {launch.key}")
    (root / "gone.md").unlink(missing_ok=True)
    (root / "new" / "a.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "new" / "a.md").write_text(f"new from {launch.key}")
    return {"title": launch.key}


def stub(**script) -> StubAgent:
    return StubAgent(
        {
            "write": edit,
            "summarize": lambda launch: Note(title="summary").model_dump_json().join(["Here it is:\n", "\nDone."]),
            **script,
        },
        default={"title": "x"},
        execute=["count", "look_up"],
    )


def tree(cwd: Path, units=("alpha", "beta")) -> Path:
    for u in units:
        (cwd / "topics" / u).mkdir(parents=True)
        (cwd / "topics" / u / "old.md").write_text("old")
        (cwd / "topics" / u / "gone.md").write_text("gone")
    return cwd


def topics(cwd: Path) -> dict[str, str]:
    return {p.relative_to(cwd).as_posix(): p.read_text() for p in sorted((cwd / "topics").rglob("*")) if p.is_file()}


def outputs(report) -> dict[str, str]:
    out = report.run_dir / "out"
    return {p.relative_to(out).as_posix(): p.read_text() for p in sorted(out.rglob("*")) if p.is_file()}


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def stub_run(tmp_path, flow_=flow, agent=None, **kwargs):
    """A stub run with no recording, as a pipeline's past runs are."""
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tree(tmp_path / "live"), stub=agent or stub())
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def replay(tmp_path, flow_=flow, name="replay", **kwargs):
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / f"{name}-runs", cwd=tree(tmp_path / name), replay=tmp_path / "rec")
    return pipeline.run(flow_, **({"units": ["alpha", "beta"]} | kwargs))


def test_a_run_imported_replays_with_nothing_launched_or_called(tmp_path):
    ran.clear()
    live = stub_run(tmp_path)
    assert live.ok, live.failed and ran == ["count"]
    assert not (tmp_path / "rec").exists()
    report = import_recording(live.run_dir, tmp_path / "rec")
    assert report.ok, str(report)
    assert sorted(report.imported) == ["python:count", "summarize-alpha", "write-alpha", "write-beta"]
    entry = json.loads((tmp_path / "rec" / "write" / "write-alpha.json").read_text())
    assert entry["imported"]["run"] == live.run_id
    assert entry["attempts"][0]["fingerprint"] == live.results["write-alpha"].task.fingerprint
    ran.clear()
    played = replay(tmp_path)
    assert played.ok, played.failed
    assert ran == [] and played.value == 2  # the Python task played its imported output
    assert all(r["replayed"] and not r["reason"] for r in journal(played))  # same fingerprints: no note
    assert outputs(played) == outputs(live)
    assert "summarize/alpha.json.message.txt" in outputs(played)  # the whole final message, beside the unwrapped output
    assert topics(tmp_path / "replay") == topics(tmp_path / "live")  # the changes, written and deleted again
    stream = "streams/write-alpha.stream.jsonl"
    assert (played.run_dir / stream).read_text() == (live.run_dir / stream).read_text()


def test_a_changed_definition_does_not_play_the_imported_recording(tmp_path):
    live = stub_run(tmp_path, flow_=lambda units: write(units[0]))
    assert import_recording(live.run_dir, tmp_path / "rec").ok
    longer = agent_task("write", instructions="Write a longer note.", output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
    played = replay(tmp_path, flow_=lambda units: longer(units[0]))
    result = played.results["write-alpha"]
    assert not result.ok and result.stop == "error"
    assert f"was imported from run {live.run_id} with another fingerprint" in result.reason
    assert not (played.run_dir / "out" / "write" / "alpha.json").exists()  # the stale output was not written
    # With record_missing, the stale recording counts as missing: the task launches and is recorded again.
    agent = stub()
    cwd = tree(tmp_path / "fill")
    runs, rec = tmp_path / "fill-runs", tmp_path / "rec"
    pipeline = Pipeline(PipelineConfig({}), runs_dir=runs, cwd=cwd, replay=rec, record_missing=True, backends=agent.backends())
    filled = pipeline.run(lambda units: longer(units[0]), units=["alpha"])
    assert filled.ok, filled.failed
    assert [launch.key for launch in agent.launches] == ["write-alpha"]
    entry = json.loads((tmp_path / "rec" / "write" / "write-alpha.json").read_text())
    assert "imported" not in entry and entry["attempts"][0]["fingerprint"] == filled.results["write-alpha"].task.fingerprint


def test_an_imported_recording_plays_only_for_its_own_key(tmp_path):
    keyed = write.options(key="write-alpha~5")
    live = stub_run(tmp_path, flow_=lambda units: [write(units[0]), keyed(units[0])], agent=stub(write={"title": "x"}))
    assert import_recording(live.run_dir, tmp_path / "rec").ok
    played = replay(tmp_path, flow_=lambda units: [write(units[0]), write(units[0])])
    assert played.results["write-alpha"].ok
    assert played.results["write-alpha~2"].reason == "no recording for write-alpha~2"


def test_what_did_not_finish_or_cannot_be_imported_is_reported(tmp_path):
    async def three(units):
        await asyncio.gather(*[write(u) for u in units])
        await tidy("all")
        await summarize(units[0])

    def tidied(launch):
        (Path(launch.call.cwd) / "topics" / "alpha" / "old.md").write_text("tidied")
        return {"title": "tidy"}

    live = stub_run(tmp_path, flow_=three, agent=stub(tidy=tidied, summarize=fails(Stop.ERROR, "no summary")))
    (live.run_dir / "out" / "write" / "beta.json").unlink()
    report = import_recording(live.run_dir, tmp_path / "rec")
    assert report.imported == ("tidy-all",), str(report)
    assert report.unfinished == {"summarize-alpha": "error: no summary"}
    assert set(report.not_imported) == {"write-alpha", "write-beta"}
    assert report.not_imported["write-alpha"].endswith("topics/alpha/old.md was written again by tidy-all after it")
    assert report.not_imported["write-beta"].endswith("out/write/beta.json is missing")
    assert not report.ok
    assert not (tmp_path / "rec" / "write").exists()


def test_a_partial_is_imported_as_partial(tmp_path):
    long = agent_task("long", instructions="x", output=Note, partial_on=["timeout"], max_turns=5, timeout_s=60)
    agent = stub(long=writes({"title": "half"}, stop=Stop.TIMEOUT))
    live = stub_run(tmp_path, flow_=lambda units: [look_up(topic="alpha"), long("alpha")], agent=agent)
    assert {k: r.stop for k, r in live.results.items()} == {"python:look_up": "partial", "long-alpha": "partial"}
    assert import_recording(live.run_dir, tmp_path / "rec").ok
    ran.clear()
    played = replay(tmp_path, flow_=lambda units: [look_up(topic="alpha"), long("alpha")])
    assert ran == []
    assert played.results["python:look_up"].stop == "partial"
    assert played.results["python:look_up"].reason == "the local index server is not up"
    assert played.results["long-alpha"].stop == "partial" and played.results["long-alpha"].reason == "timeout"
    assert outputs(played) == outputs(live)


def test_a_run_that_cannot_be_read_is_refused(tmp_path):
    with pytest.raises(RecordingError, match="not a run directory"):
        import_recording(tmp_path / "nothing", tmp_path / "rec")
    live = stub_run(tmp_path, flow_=lambda units: write(units[0]))
    info = json.loads((live.run_dir / "run.json").read_text())
    (live.run_dir / "run.json").write_text(json.dumps(info | {"format": 99}))
    with pytest.raises(RecordingError, match="run format 99"):
        import_recording(live.run_dir, tmp_path / "rec")


def test_a_file_over_the_cap_leaves_its_task_unimported(tmp_path):
    live = stub_run(tmp_path, flow_=lambda units: write(units[0]), agent=stub(write={"title": "x" * 2048}))
    report = import_recording(live.run_dir, tmp_path / "rec", record_max_file_mb=0.001)
    assert "is over the 0.001 MB cap" in report.not_imported["write-alpha"]


def test_the_cli_imports_a_run(tmp_path, monkeypatch, capsys):
    live = stub_run(tmp_path, flow_=lambda units: write(units[0]))
    monkeypatch.chdir(tmp_path)
    assert main(["recording", "import", str(live.run_dir), "rec"]) == 0
    assert capsys.readouterr().out.startswith(f"✓ 1 task imported from {live.run_dir.as_posix()} into rec")
    assert main(["recording", "import", str(tmp_path / "nothing"), "rec"]) == 1
    (live.run_dir / "out" / "write" / "alpha.json").unlink()
    assert main(["recording", "import", str(live.run_dir), "rec"]) == 1
    assert "not imported write-alpha:" in capsys.readouterr().out


def test_an_import_by_key_plays_for_a_changed_definition_and_says_so(tmp_path):
    live = stub_run(tmp_path, flow_=lambda units: write(units[0]))
    assert import_recording(live.run_dir, tmp_path / "rec", by_key=True).ok
    entry = json.loads((tmp_path / "rec" / "write" / "write-alpha.json").read_text())
    assert entry["imported"]["by_key"] is True
    longer = agent_task("write", instructions="Write a longer note.", output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
    played = replay(tmp_path, flow_=lambda units: longer(units[0]))
    result = played.results["write-alpha"]
    assert result.ok and "the recording has another fingerprint" in result.reason
    row = next(r for r in journal(played) if r["key"] == "write-alpha")
    assert row["played"]["fingerprint"] == live.results["write-alpha"].task.fingerprint != row["fingerprint"]
