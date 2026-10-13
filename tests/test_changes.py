"""A task's changes (`agent_task(changes=...)`) and the dispatch hooks a `Pipeline` passes
to its runner (`scopes`, `enrichers`, `row_extras`)."""

import contextlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, Stop, agent_task
from contraagent.execution.changes import compare, scan
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
    return [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]


def edits(*files: str, fail: bool = False):
    """A reply that writes `files` (relative to the agent's cwd) beside its output."""

    def reply(launch):
        for f in files:
            path = Path(launch.call.cwd) / f
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{launch.n}\n")
        return fails(Stop.TIMEOUT, "killed") if fail else {"title": launch.unit}

    return reply


def test_each_attempt_records_what_it_created_modified_and_deleted(tmp_path, plugin_dir):
    (tmp_path / "topics" / "alpha").mkdir(parents=True)
    (tmp_path / "topics" / "alpha" / "old.md").write_text("old")
    (tmp_path / "topics" / "alpha" / "gone.md").write_text("gone")
    (tmp_path / "topics" / "beta.md").write_text("not under the pattern")
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60)

    def reply(launch):
        root = Path(launch.call.cwd) / "topics" / launch.unit
        (root / "old.md").write_text("old, longer")
        (root / "gone.md").unlink()
        (root / "new" / "a.md").parent.mkdir()
        (root / "new" / "a.md").write_text("a")
        (Path(launch.call.cwd) / "topics" / "beta.md").write_text("changed outside")
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
    }


def test_a_failed_attempt_has_the_files_it_created_removed(tmp_path, plugin_dir):
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "kept.md").write_text("kept")
    write = agent_task("write", plugin=plugin_dir, output=Note, changes=["topics/{unit}/**"], max_turns=5, timeout_s=60, retries=0)
    report = run(tmp_path, StubAgent({"write": edits("topics/alpha/draft/x.md", "topics/alpha/y.md", fail=True)}), lambda: write("alpha"))
    assert not report.ok
    [row] = journal(report)
    assert row["stop"] == "timeout"
    assert row["changes"]["created"] == row["changes"]["removed"] == ["topics/alpha/draft/x.md", "topics/alpha/y.md"]
    assert not (tmp_path / "topics" / "alpha").exists()  # the directories it created, emptied, go too
    assert (tmp_path / "topics" / "kept.md").exists()


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


@pytest.mark.parametrize("pattern", ["/etc/**", "../x/**", "topics/{run}/**", ""])
def test_a_pattern_outside_the_working_directory_or_naming_an_unknown_field_is_refused(plugin_dir, pattern):
    with pytest.raises((ValueError, TypeError)):
        agent_task("write", plugin=plugin_dir, output=Note, changes=[pattern], max_turns=5, timeout_s=60)


def test_scan_covers_everything_under_a_matched_directory(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "x.md").write_text("x")
    (tmp_path / "a" / "y.txt").write_text("y")
    files, dirs = scan(tmp_path, ["a/**"])
    assert sorted(files) == ["a/b/x.md", "a/y.txt"]
    assert dirs == {"a", "a/b"}
    assert sorted(scan(tmp_path, ["a/*.txt"])[0]) == ["a/y.txt"]
    assert compare({"k": (1, 1), "d": (1, 1)}, {"k": (2, 1), "n": (1, 1)}).modified == ("k",)


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
            result.payload = {"effect": "new" if result.changes and result.changes.created else "none", "before": before}

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
    (tmp_path / "topics" / "beta" / "index.md").write_text("old")

    def reply(launch):
        path = Path(launch.call.cwd) / "topics" / launch.unit / "index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(launch.params["subject"])
        return {"topic": f"topics/{launch.unit}/index.md"}

    stub = StubAgent({"write": reply})
    pipeline = example.pipeline(runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path)
    report = pipeline.run(example.topics, subjects={"alpha": "a new one", "beta": "an update"})
    assert report.ok, report.failed
    assert {r["unit"]: r["effect"] for r in journal(report)} == {"alpha": "new", "beta": "updated"}
