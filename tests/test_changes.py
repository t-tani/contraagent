"""A task's changes (`agent_task(changes=...)`) and the dispatch hooks a `Pipeline` passes
to its runner (`scopes`, `enrichers`, `row_extras`)."""

import contextlib
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.dispatch.task import TaskResult
from contraagent._internal.execution.changes import ChangesEnricher, compare, scan
from contraagent.backends import Stop
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent, fails


class Note(BaseModel):
    title: str


@pytest.fixture
def plugin_dir(tmp_path):
    new_plugin(tmp_path / "plugins" / "write")
    return tmp_path / "plugins" / "write"


def run(tmp_path, agent, flow, **options):
    return Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, **options).run(flow)


def journal(report) -> list[dict]:
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()]


def edits(*files: str, fail: bool = False):
    """A reply that writes `files` (relative to the agent's cwd) beside its output."""

    def reply(launch):
        for f in files:
            path = Path(launch.call.cwd) / f
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{launch.n}\n", encoding="utf-8", newline="\n")
        return fails(Stop.TIMEOUT, "killed") if fail else {"title": launch.unit}

    return reply


def test_each_attempt_records_what_it_created_modified_and_deleted(tmp_path, plugin_dir):
    (tmp_path / "topics" / "alpha").mkdir(parents=True)
    (tmp_path / "topics" / "alpha" / "old.md").write_text("old", encoding="utf-8", newline="\n")
    (tmp_path / "topics" / "alpha" / "gone.md").write_text("gone", encoding="utf-8", newline="\n")
    (tmp_path / "topics" / "beta.md").write_text("not under the pattern", encoding="utf-8", newline="\n")
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)

    def reply(launch):
        root = Path(launch.call.cwd) / "topics" / launch.unit
        (root / "old.md").write_text("old, longer", encoding="utf-8", newline="\n")
        (root / "gone.md").unlink()
        (root / "new" / "a.md").parent.mkdir()
        (root / "new" / "a.md").write_text("a", encoding="utf-8", newline="\n")
        (Path(launch.call.cwd) / "topics" / "beta.md").write_text("changed outside", encoding="utf-8", newline="\n")
        return {"title": launch.unit}

    report = run(tmp_path, StubAgent({"write": reply}), lambda: write("alpha"))
    assert report.ok, report.failed
    assert report.results["write-alpha"].changes is not None
    [row] = journal(report)
    assert row["changes"] == {
        "created": ["topics/alpha/new/a.md"],
        "modified": ["topics/alpha/old.md"],
        "deleted": ["topics/alpha/gone.md"],
        "removed": [],
        "kept": [],
    }


def test_a_failed_attempt_has_the_files_it_created_removed(tmp_path, plugin_dir):
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "kept.md").write_text("kept", encoding="utf-8", newline="\n")
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60, retries=0)
    report = run(tmp_path, StubAgent({"write": edits("topics/alpha/draft/x.md", "topics/alpha/y.md", fail=True)}), lambda: write("alpha"))
    assert not report.ok
    [row] = journal(report)
    assert row["stop"] == "timeout"
    assert row["changes"]["created"] == row["changes"]["removed"] == ["topics/alpha/draft/x.md", "topics/alpha/y.md"]
    assert not (tmp_path / "topics" / "alpha").exists()  # the directories it created, emptied, go too
    assert (tmp_path / "topics" / "kept.md").exists()


def test_a_kind_that_keeps_failed_changes_leaves_them_for_the_next_attempt(tmp_path, plugin_dir):
    write = agent_task(
        "write",
        plugin=plugin_dir,
        output=Note,
        changes=["topics/{unit}/**"],
        max_turns=5,
        timeout_s=60,
        retries=1,
        keep_failed_changes=True,
    )

    def reply(launch):
        root = Path(launch.call.cwd) / "topics" / launch.unit
        root.mkdir(parents=True, exist_ok=True)
        (root / "log.md").write_text(f"attempt {launch.n}\n", encoding="utf-8", newline="\n")
        return fails(Stop.API_ERROR, "the service went away") if launch.n == 1 else {"title": launch.unit}

    report = run(tmp_path, StubAgent({"write": reply}), lambda: write("alpha"))
    assert report.ok, report.failed
    first, second = journal(report)
    assert not first["ok"] and first["changes"]["created"] == first["changes"]["kept"] == ["topics/alpha/log.md"]
    assert first["changes"]["removed"] == []
    assert second["changes"]["created"] == [] and second["changes"]["modified"] == ["topics/alpha/log.md"]


def test_a_task_table_turns_keeping_failed_changes_on(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60, retries=0)
    agent = StubAgent({"write": edits("topics/alpha/x.md", fail=True)})
    config = PipelineConfig({"tasks": {"write": {"keep_failed_changes": True}}})
    report = Pipeline(config, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path).run(lambda: write("alpha"))
    [row] = journal(report)
    assert row["changes"]["kept"] == ["topics/alpha/x.md"] and (tmp_path / "topics" / "alpha" / "x.md").exists()
    with pytest.raises(ValueError, match=r"keep_failed_changes = 'yes' is not a boolean"):
        PipelineConfig({"tasks": {"write": {"keep_failed_changes": "yes"}}}).task_tables()


def test_a_resume_finds_the_notes_the_example_s_failed_study_kept(tmp_path):
    from contraagent.docs.examples.changes import flow as example

    def study(launch):
        notes = Path(launch.call.cwd) / "notes" / launch.unit
        notes.mkdir(parents=True, exist_ok=True)
        seen = sorted(p.name for p in notes.iterdir() if p.name != ".cache")
        (notes / ".cache").mkdir(exist_ok=True)
        (notes / ".cache" / "index").write_text("cache\n", encoding="utf-8", newline="\n")  # left out of changes
        (notes / f"run-{len(seen) + 1}.md").write_text(f"saw {seen}\n", encoding="utf-8", newline="\n")
        if not seen:
            return fails(Stop.TIMEOUT, "out of time")
        return {"topic": f"notes/{launch.unit}/run-{len(seen) + 1}.md"}

    config = PipelineConfig({"tasks": {"study": {"retries": 0}}})
    pipeline = Pipeline(config, runs_dir=tmp_path / "runs", backends=StubAgent({"study": study}).backends(), cwd=tmp_path)
    first = pipeline.run(lambda: example.study("alpha"), run_id="r")
    assert not first.ok
    assert journal(first)[0]["changes"]["kept"] == journal(first)[0]["changes"]["created"] == ["notes/alpha/run-1.md"]
    again = pipeline.run(lambda: example.study("alpha"), run_id="r", resume=True)
    assert again.ok, again.failed
    assert journal(again)[-1]["changes"]["created"] == ["notes/alpha/run-2.md"]
    assert (tmp_path / "notes" / "alpha" / "run-2.md").read_text(encoding="utf-8") == "saw ['run-1.md']\n"


def test_keeping_failed_changes_needs_patterns(tmp_path, plugin_dir):
    with pytest.raises(TypeError, match="keep_failed_changes keeps the files under changes="):
        agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60, keep_failed_changes=True)
    write = agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60)
    config = PipelineConfig({"tasks": {"write": {"keep_failed_changes": True}}})
    report = Pipeline(config, runs_dir=tmp_path / "runs", backends=StubAgent({}).backends(), cwd=tmp_path).check(lambda: write("alpha"))
    assert any("keep_failed_changes" in e and "declares no changes" in e for e in report.errors), report.errors
    assert "tasks" in report.topics


def test_a_task_that_declares_no_changes_records_none(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, max_turns=5, timeout_s=60)
    report = run(tmp_path, StubAgent({"write": edits("topics/alpha/x.md")}), lambda: write("alpha"))
    assert report.ok
    assert journal(report)[0]["changes"] is None
    assert (tmp_path / "topics" / "alpha" / "x.md").exists()


def test_the_patterns_are_part_of_the_task_definition(tmp_path, plugin_dir):
    a = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
    b = agent_task("write", plugin=plugin_dir, output=Note, changes=["notes/{unit}/**"], max_turns=5, timeout_s=60)
    assert a.digest() != b.digest()
    assert a.differences(b) == ["changes"]


@pytest.mark.parametrize("pattern", ["/etc/**", "C:/x/**", "\\x/**", "..\\x/**", "../x/**", "topics/{run}/**", ""])
def test_a_pattern_outside_the_working_directory_or_naming_an_unknown_field_is_refused(plugin_dir, pattern):
    with pytest.raises((ValueError, TypeError)):
        agent_task("write", plugin=plugin_dir, output=Note, changes=[pattern], max_turns=5, timeout_s=60)


def test_a_rewrite_at_the_same_size_within_one_mtime_tick_is_a_modification(tmp_path):
    enricher = ChangesEnricher(lambda task: ["notes/**"], tmp_path)
    task = make_python_task("write", lambda: None, unit="a")
    (tmp_path / "notes").mkdir()
    rewritten, untouched, old = (tmp_path / "notes" / name for name in ("rewritten.md", "untouched.md", "old.md"))
    for path in (rewritten, untouched, old):
        path.write_text("attempt 1\n", encoding="utf-8", newline="\n")
    long_ago = rewritten.stat().st_mtime_ns - 3_600_000_000_000
    os.utime(old, ns=(long_ago, long_ago))
    before = enricher.snapshot(task)
    assert before is not None and sorted(before.digests) == ["notes/rewritten.md", "notes/untouched.md"]
    tick = rewritten.stat().st_mtime_ns
    rewritten.write_text("attempt 2\n", encoding="utf-8", newline="\n")
    os.utime(rewritten, ns=(tick, tick))  # the same size and mtime, as on a file system with coarse ticks
    result = enricher.enrich(task, before, TaskResult(task, True, "completed"))
    assert result is not None and result.changes is not None
    assert result.changes.modified == ("notes/rewritten.md",)


@pytest.mark.skipif(sys.platform == "win32", reason="the stamp is the mtime and the size alone on Windows")
def test_a_rewrite_that_puts_back_an_old_mtime_and_size_is_a_modification(tmp_path):
    enricher = ChangesEnricher(lambda task: ["notes/**"], tmp_path)
    task = make_python_task("write", lambda: None, unit="a")
    (tmp_path / "notes").mkdir()
    restored = tmp_path / "notes" / "restored.md"
    restored.write_text("attempt 1\n", encoding="utf-8", newline="\n")
    long_ago = restored.stat().st_mtime_ns - 3_600_000_000_000
    os.utime(restored, ns=(long_ago, long_ago))
    before = enricher.snapshot(task)
    assert before is not None and before.digests == {}  # written long before: the stamp alone tells
    time.sleep(0.05)  # past the tick of the status change time
    restored.write_text("attempt 2\n", encoding="utf-8", newline="\n")
    os.utime(restored, ns=(long_ago, long_ago))  # as `cp -p` or `touch -r` would leave it
    result = enricher.enrich(task, before, TaskResult(task, True, "completed"))
    assert result is not None and result.changes is not None
    assert result.changes.modified == ("notes/restored.md",)


def test_scan_covers_everything_under_a_matched_directory(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "x.md").write_text("x", encoding="utf-8", newline="\n")
    (tmp_path / "a" / "y.txt").write_text("y", encoding="utf-8", newline="\n")
    files, dirs = scan(tmp_path, ["a/**"])
    assert sorted(files) == ["a/b/x.md", "a/y.txt"]
    assert dirs == {"a", "a/b"}
    assert sorted(scan(tmp_path, ["a/*.txt"])[0]) == ["a/y.txt"]
    assert compare({"k": (1, 1), "d": (1, 1)}, {"k": (2, 1), "n": (1, 1)}).modified == ("k",)


def test_a_pattern_with_a_bang_leaves_paths_out_and_its_folders_are_not_walked(tmp_path, monkeypatch):
    for rel in (".git/objects/ab/cd", ".git/HEAD", "a.md", ".env", "src/b.py", "src/__pycache__/b.pyc", "cache/x/y"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8", newline="\n")
    files, dirs = scan(tmp_path, ["**", "!.git/**", "!**/__pycache__", "!cache"])
    assert sorted(files) == [".env", "a.md", "src/b.py"]
    assert ".git" not in dirs and "src/__pycache__" not in dirs and "src" in dirs
    assert sorted(scan(tmp_path, ["src/*.py", "!src/b.py"])[0]) == []
    assert sorted(scan(tmp_path, ["[!.]*", "!cache"])[0]) == ["a.md", "src/__pycache__/b.pyc", "src/b.py"]
    walked = []
    real = os.walk
    monkeypatch.setattr(os, "walk", lambda top, *a, **k: (walked.append(step[0]) or step for step in real(top, *a, **k)))
    scan(tmp_path, ["**", "!.git"])
    assert not any(".git" in Path(w).parts for w in walked)


def test_a_task_leaves_out_what_its_bang_pattern_names(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["**", "!.git/**", "!runs/**"], max_turns=5, timeout_s=60)
    report = run(tmp_path, StubAgent({"write": edits(".git/index", "notes/a.md")}), lambda: write("alpha"))
    assert report.ok, report.failed
    created = journal(report)[0]["changes"]["created"]
    assert "notes/a.md" in created and ".git/index" not in created
    with pytest.raises(TypeError, match="only patterns that leave paths out"):
        agent_task("write", plugin=plugin_dir, output=Note, changes=["!.git/**"], max_turns=5, timeout_s=60)
    with pytest.raises(ValueError, match="not inside the working directory"):
        agent_task("write", plugin=plugin_dir, output=Note, changes=["**", "!../x"], max_turns=5, timeout_s=60)


def test_scopes_enrichers_and_row_extras_reach_each_attempt(tmp_path, plugin_dir):
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)
    seen: list[str] = []

    @contextlib.contextmanager
    def scope(task):
        seen.append(f"enter {task.key}")
        yield
        seen.append(f"exit {task.key}")

    class Effect:
        def snapshot(self, task):
            return "before"

        def enrich(self, task, before, result):
            # Built-in changes are recorded before a pipeline's own enrichers run.
            return replace(result, payload={"effect": "new" if result.changes and result.changes.created else "none", "before": before})

    report = run(
        tmp_path,
        StubAgent({"write": edits("topics/alpha/x.md")}),
        lambda: write("alpha"),
        scopes=[scope],
        enrichers=[Effect()],
        row_extras=lambda result: {"effect": (result.payload or {}).get("effect")},
    )
    assert report.ok
    assert seen == ["enter write-alpha", "exit write-alpha"]
    assert report.results["write-alpha"].payload == {"effect": "new", "before": "before"}
    assert journal(report)[0]["effect"] == "new"


def test_the_example_names_each_attempts_effect_from_its_changes(tmp_path):
    from contraagent.docs.examples.changes import flow as example

    (tmp_path / "topics" / "beta").mkdir(parents=True)
    (tmp_path / "topics" / "beta" / "index.md").write_text("old", encoding="utf-8", newline="\n")

    def reply(launch):
        path = Path(launch.call.cwd) / "topics" / launch.unit / "index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(launch.params["subject"], encoding="utf-8", newline="\n")
        return {"topic": f"topics/{launch.unit}/index.md"}

    stub = StubAgent({"write": reply})
    pipeline = example.pipeline(runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path)
    report = pipeline.run(example.topics, subjects={"alpha": "a new one", "beta": "an update"})
    assert report.ok, report.failed
    assert {r["unit"]: r["effect"] for r in journal(report)} == {"alpha": "new", "beta": "updated"}
