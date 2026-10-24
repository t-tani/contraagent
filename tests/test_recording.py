"""Recordings and replays (`Pipeline(record=)`, `Pipeline(replay=)`, `contraagent run
--record/--replay`): a run's task attempts kept, then played with nothing spent."""

import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Partial, Pipeline, PipelineConfig, RecordingError, agent_task, python_task
from contraagent._internal.cli import main
from contraagent._internal.execution.recording import Recorder, base_key
from contraagent.backends import Stop
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
    ran.clear()
    every = replay(tmp_path, name="every", execute=["*"])
    assert every.ok, every.failed
    assert ran == ["count"] and every.value == 2  # every Python task's function, the agent tasks played


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
    record(tmp_path, flow_=lambda units: [write(units[0]), write.options(key="write-alpha~5")(units[0])])
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
    # The journal row names the recording it played: its fingerprint is not the row's.
    row = next(r for r in journal(played) if r["key"] == "write-alpha")
    assert row["replayed"] and row["played"]["key"] == "write-alpha"
    assert row["played"]["fingerprint"] and row["played"]["fingerprint"] != row["fingerprint"]
    assert played.results["write-alpha"].played is not None


def test_a_recording_of_the_same_fingerprint_names_it_too(tmp_path):
    record(tmp_path, flow_=lambda units: write(units[0]))
    played = replay(tmp_path, flow_=lambda units: write(units[0]))
    row = next(r for r in journal(played) if r["key"] == "write-alpha")
    assert row["played"] == {"key": "write-alpha", "fingerprint": row["fingerprint"], "outside": ""}


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


async def cli_flow(units: list[str]):
    await asyncio.gather(*[write(u) for u in units])


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
    assert main([*args, "--replay", "rec", "--execute", "*", "--run-id", "every"]) == 0
    assert main([*args, "--execute", "count"]) == 2
    assert main([*args, "--record-missing"]) == 2
    assert main([*args, "--replay", "rec", "--record-missing", "--stub"]) == 2
    assert (
        main([*args, "--stub", "--record", "rec", "--record-exclude", ".venv", "--record-exclude", "**/node_modules", "--run-id", "x"]) == 0
    )
    assert json.loads((tmp_path / "rec" / "undeclared.json").read_text())["excluded"] == [".venv", "**/node_modules"]
    assert main([*args, "--stub", "--record-exclude", ".venv", "--run-id", "y"]) == 1


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
    with pytest.raises(TypeError, match="record_exclude= narrows a recording run's comparison"):
        Pipeline(record_exclude=[".venv"])
    with pytest.raises(ValueError, match=r"record_exclude=\['!keep'\]: .* without '!'"):
        Pipeline(record=tmp_path / "x", record_exclude=[".venv", "!keep"])
    with pytest.raises(TypeError, match="is one string"):
        Pipeline(record=tmp_path / "x", record_exclude=".venv")


stray: list[Path] = []


@python_task
def publish(title: str) -> Note:
    for path in stray:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(title)
    return Note(title=title)


def test_a_recording_run_reports_the_changes_no_task_declared(tmp_path):
    cwd = tree(tmp_path / "live")
    (cwd / ".git").mkdir()
    (cwd / "old-report.txt").write_text("old")
    stray[:] = [cwd / "report.txt", cwd / ".git" / "index", cwd / "pkg" / "__pycache__" / "m.pyc"]

    async def flow(units):
        (cwd / "old-report.txt").unlink()  # the flow's own side effect
        await write(units[0])
        return await publish(title="done")

    lines: list[str] = []
    agent = StubAgent({"write": edit}, execute=["publish"])
    rec = tmp_path / "rec"
    report = Pipeline(runs_dir=tmp_path / "runs", cwd=cwd, stub=agent, record=rec, log=lines.append).run(flow, units=["alpha"])
    assert report.ok, report.failed
    body = json.loads((rec / "undeclared.json").read_text())
    # topics/alpha/** is write's changes=, so its files are declared; .git and __pycache__ are left out.
    assert body == {"run": report.run_id, "excluded": [], "created": ["report.txt"], "modified": [], "deleted": ["old-report.txt"]}
    warned = [line for line in lines if "undeclared" in line]
    assert warned == ["[record] undeclared change: old-report.txt", "[record] undeclared change: report.txt"]


def test_with_the_run_directory_as_cwd_only_its_outputs_are_compared(tmp_path):
    runs = tmp_path / "runs"
    cwd = runs / "inside"
    cwd.mkdir(parents=True)
    stray[:] = [cwd / "out" / "extra.json"]
    rec = tmp_path / "rec"
    pipeline = Pipeline(runs_dir=runs, cwd=cwd, stub=StubAgent(default={"title": "x"}, execute=["publish"]), record=rec)
    report = pipeline.run(lambda: [write("alpha"), publish(title="t")], run_id="inside")
    assert report.ok, report.failed
    assert (cwd / "journal.jsonl").exists() and (cwd / "out" / "write" / "alpha.json").exists()
    body = json.loads((rec / "undeclared.json").read_text())
    assert body["created"] == ["out/extra.json"] and body["modified"] == body["deleted"] == []


def test_record_exclude_leaves_a_directory_out_and_the_comparison_does_not_enter_it(tmp_path, monkeypatch):
    cwd = tree(tmp_path / "live")
    (cwd / ".venv" / "lib").mkdir(parents=True)
    (cwd / ".venv" / "lib" / "site.py").write_text("old")
    stray[:] = [cwd / "report.txt", cwd / ".venv" / "lib" / "site.py", cwd / "web" / "node_modules" / "m.js", cwd / "web" / "app.js"]
    entered: list[tuple[str, ...]] = []
    scandir = os.scandir
    monkeypatch.setattr(os, "scandir", lambda path: entered.append(Path(path).parts) or scandir(path))
    rec = tmp_path / "rec"
    agent = StubAgent({"write": edit}, execute=["publish"])
    pipeline = Pipeline(runs_dir=tmp_path / "runs", cwd=cwd, stub=agent, record=rec, record_exclude=[".venv", "**/node_modules", "topics"])
    report = pipeline.run(lambda: [write("alpha"), publish(title="done")])
    assert report.ok, report.failed
    body = json.loads((rec / "undeclared.json").read_text())
    assert body == {
        "run": report.run_id,
        "excluded": [".venv", "**/node_modules", "topics"],
        "created": ["report.txt", "web/app.js"],
        "modified": [],
        "deleted": [],
    }
    assert entered and not [parts for parts in entered if ".venv" in parts or "node_modules" in parts]
    # An exclusion narrows the comparison only: write's changes= under topics/ are recorded all the same.
    assert [p.read_text() for p in rec.rglob("files/topics/alpha/new/a.md")] == ["new from write-alpha"]


def test_a_top_level_directory_with_more_than_20_undeclared_changes_is_one_warning(tmp_path):
    cwd = tmp_path / "live"
    cwd.mkdir()
    stray[:] = [cwd / "build" / f"{n:02}.o" for n in range(21)] + [cwd / "docs" / f"{n:02}.md" for n in range(20)] + [cwd / "z.txt"]
    lines: list[str] = []
    rec = tmp_path / "rec"
    pipeline = Pipeline(runs_dir=tmp_path / "runs", cwd=cwd, stub=StubAgent(execute=["publish"]), record=rec, log=lines.append)
    report = pipeline.run(lambda: publish(title="done"))
    assert report.ok, report.failed
    warned = [line for line in lines if "undeclared" in line]
    assert warned == [
        f"[record] undeclared changes: build/ (21 paths), see {(rec / 'undeclared.json').as_posix()}",
        *[f"[record] undeclared change: docs/{n:02}.md" for n in range(20)],
        "[record] undeclared change: z.txt",
    ]
    assert json.loads((rec / "undeclared.json").read_text())["created"] == sorted(p.relative_to(cwd).as_posix() for p in stray)


looked_up: list[str] = []


@python_task
def look_up(topic: str) -> Note | Partial[Note]:
    looked_up.append(topic)
    return Partial(Note(title=f"{topic}, from the cache"), reason="the local index server is not up")


def test_a_replayed_partial_is_partial_again_and_a_resume_runs_it(tmp_path):
    agent = StubAgent(execute=["look_up"])
    live = Pipeline(runs_dir=tmp_path / "runs", cwd=tmp_path, stub=agent, record=tmp_path / "rec").run(lambda: look_up(topic="alpha"))
    assert live.results["python:look_up"].stop == "partial"
    looked_up.clear()
    played = replay(tmp_path, flow_=lambda units: look_up(topic="alpha"))
    result = played.results["python:look_up"]
    assert looked_up == [] and result.ok and result.stop == "partial"
    assert result.reason == "the local index server is not up"
    assert played.value.output.title == "alpha, from the cache"
    assert outputs(played) == outputs(live)
    # A resume runs a partial task again: here it plays its recording again.
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "replay-runs", cwd=tmp_path / "replay", replay=tmp_path / "rec")
    again = pipeline.run(lambda units: look_up(topic="alpha"), resume=True, units=["alpha"])
    assert [r["stop"] for r in journal(again)] == ["partial", "partial"] and all(r["replayed"] for r in journal(again))


def test_a_scope_and_an_enricher_see_each_replayed_python_attempt(tmp_path):
    record(tmp_path)
    seen: list[str] = []

    @contextlib.contextmanager
    def scope(task):
        seen.append(f"enter {task.key}")
        yield
        seen.append(f"exit {task.key}")

    class Enricher:
        def snapshot(self, task):
            return None

        def enrich(self, task, before, result):
            seen.append(f"{task.key} replayed={result.replayed}")

    cwd = tree(tmp_path / "scoped")
    pipeline = Pipeline(runs_dir=tmp_path / "scoped-runs", cwd=cwd, replay=tmp_path / "rec", scopes=[scope], enrichers=[Enricher()])
    played = pipeline.run(flow, units=["alpha", "beta"])
    assert played.ok, played.failed
    assert seen[-3:] == ["enter python:count", "exit python:count", "python:count replayed=True"]


tallied: list[str] = []


@python_task
def tally(unit: str, words: int) -> Note:
    import contraagent

    tallied.append(unit)
    contraagent.log("counts", {"unit": unit, "words": words})
    contraagent.log("counts", {"unit": unit, "words": words + 1})
    contraagent.save("total", {"last": unit, "words": words})
    contraagent.save("total", {"last": unit, "words": words * 2})
    return Note(title=unit)


async def tally_flow(units: list[str]):
    await asyncio.gather(*[tally(u, words=len(u)) for u in units])


def counts_panel(run) -> dict:
    return {"rows": run.log("counts"), "total": run.document("total")}


def pipeline_files(report) -> dict[str, str]:
    folder = report.run_dir / "pipeline"
    return {p.name: p.read_text() for p in sorted(folder.iterdir())}


def test_a_python_task_logs_and_saves_are_recorded_and_played_back(tmp_path):
    from contraagent.monitor import Panel

    agent = StubAgent(execute=["tally"])
    live = Pipeline(runs_dir=tmp_path / "runs", cwd=tmp_path, stub=agent, record=tmp_path / "rec").run(tally_flow, units=["alpha"])
    assert live.ok, live.failed
    tallied.clear()
    played = replay(tmp_path, flow_=tally_flow, units=["alpha"])
    assert played.ok, played.failed
    assert tallied == []  # nothing called: the rows and the document come from the recording
    assert pipeline_files(played) == pipeline_files(live)
    assert json.loads(pipeline_files(played)["total.json"]) == {"last": "alpha", "words": 10}
    panels = {"counts": Panel(counts_panel)}
    assert Monitor(tmp_path / "replay-runs", panels=panels).panel("counts", played.run_id) == Monitor(
        tmp_path / "runs", panels=panels
    ).panel("counts", live.run_id)

    # record_missing: one unit plays its recording, the other runs and is recorded.
    tallied.clear()
    runs, cwd = tmp_path / "fill-runs", tmp_path / "fill"
    cwd.mkdir()
    filled = Pipeline(runs_dir=runs, cwd=cwd, replay=tmp_path / "rec", record_missing=True).run(tally_flow, units=["alpha", "beta"])
    assert filled.ok, filled.failed
    assert tallied == ["beta"]
    rows = [json.loads(line) for line in pipeline_files(filled)["counts.jsonl"].splitlines()]
    assert sorted((r["unit"], r["words"]) for r in rows) == [("alpha", 5), ("alpha", 6), ("beta", 4), ("beta", 5)]
    body = json.loads((tmp_path / "rec" / "tally" / "python_tally-beta.json").read_text())
    assert body["attempts"][0]["pipeline"] == {"logs": ["counts"], "documents": ["total"]}


def test_a_pipeline_document_over_the_cap_makes_the_attempt_unplayable(tmp_path):
    lines: list[str] = []
    agent = StubAgent(execute=["tally"])
    rec = tmp_path / "rec"
    pipeline = Pipeline(runs_dir=tmp_path / "runs", cwd=tmp_path, stub=agent, record=rec, record_max_file_mb=1e-5, log=lines.append)
    assert pipeline.run(tally_flow, units=["alpha"]).ok
    assert any(line.startswith("[record] python:tally-alpha: pipeline/counts.jsonl") for line in lines), lines
    body = json.loads((rec / "tally" / "python_tally-alpha.json").read_text())
    assert {k["path"] for k in body["attempts"][0]["by_hash"]} >= {"pipeline/counts.jsonl", "pipeline/total.json"}
    played = replay(tmp_path, flow_=tally_flow, units=["alpha"])
    assert "by hash only: run kind tally with --execute" in played.results["python:tally-alpha"].reason
    assert not (played.run_dir / "pipeline").exists()


def test_an_undeclared_rewrite_at_the_same_size_within_one_mtime_tick_is_seen(tmp_path):
    work, run_dir = tmp_path / "work", tmp_path / "runs" / "r"
    work.mkdir()
    run_dir.mkdir(parents=True)
    report = work / "report.txt"
    report.write_text("draft 1\n", encoding="utf-8", newline="\n")
    recorder = Recorder(tmp_path / "rec", lambda task: (), cwd=work, run_dir=run_dir, run_id="r")
    recorder.start()
    tick = report.stat().st_mtime_ns
    report.write_text("draft 2\n", encoding="utf-8", newline="\n")
    os.utime(report, ns=(tick, tick))  # the same size and mtime, as on a file system with coarse ticks
    assert recorder.finish() == ["report.txt"]
