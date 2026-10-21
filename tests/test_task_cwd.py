"""A task call's working directory (`.options(cwd=)`): an agent task's coding agent, call
file, validators, `changes` patterns and input files are of it; it is checked when the
task starts, recorded in the plan, outside the fingerprint, and recorded, replayed and
imported with its changes; a Python task has none. The run's `out/` is writable to each
coding agent when it is outside the task's working directory (`Launch.out_dir`)."""

import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import CommandValidator, InputFile, Pipeline, PipelineConfig, Task, agent_task, import_recording, python_task
from contraagent.backends import ClaudeBackend, CodexBackend, Launch, OpencodeBackend
from contraagent.testing import StubAgent


class Note(BaseModel):
    text: str


class Given(BaseModel):
    spec: InputFile


#: Passes only in a directory that holds `marker`.
in_marked_dir = CommandValidator(
    [sys.executable, "-c", "import os, sys; sys.exit(None if os.path.exists('marker') else 'no marker in ' + os.getcwd())"],
    name="marked",
)

edit = agent_task("edit", instructions="e", output=Note, changes=["src/**"], validators=[in_marked_dir], max_turns=1, timeout_s=10)
read = agent_task("read", params=Given, instructions="r", output=Note, max_turns=1, timeout_s=10)


def edits(launch):
    """Writes `src/<unit>.txt` in the launch's working directory, and names that directory."""
    cwd = Path(launch.launch.cwd)
    (cwd / "src").mkdir(exist_ok=True)
    (cwd / "src" / f"{launch.unit}.txt").write_text(f"{launch.unit}\n")
    return {"text": f"{cwd}|{launch.call.cwd}"}


def tree(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "marker").write_text("")
    return path


def pipeline(tmp_path, agent, **options) -> Pipeline:
    return Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path / "repo", **options)


def rows(report, name: str) -> list[dict]:
    path = report.run_dir / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# --- the call option ---------------------------------------------------------------


def test_the_option_is_made_absolute_kept_and_cleared_and_refuses_what_is_no_path(tmp_path):
    repo, own = tree(tmp_path / "repo"), tree(tmp_path / "trees" / "a")
    given = edit.options(cwd="../trees/a")

    def flow():
        given.options(priority=2)("a")  # an option not given keeps its value
        given.options(cwd=None)("b")
        edit.options(cwd=own)("c")

    report = pipeline(tmp_path, StubAgent({"edit": edits})).run(flow)
    assert report.ok, report.failed
    plan = {row["key"]: row for row in rows(report, "plan.jsonl")}
    assert plan["edit-a"]["cwd"] == plan["edit-c"]["cwd"] == own.as_posix() and plan["edit-a"]["priority"] == 2
    assert "cwd" not in plan["edit-b"] and (repo / "src" / "b.txt").exists()
    for wrong in ("", b"trees/a", 3):
        with pytest.raises(TypeError, match="cwd must be a directory's path"):
            edit.options(cwd=wrong)  # pyright: ignore[reportArgumentType]


def test_a_python_task_has_no_working_directory():
    @python_task
    def count(unit: str) -> int:
        return 1

    with pytest.raises(TypeError, match="cwd= names the working directory of an agent task"):
        count("a", cwd="trees/a")  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        count.options(cwd="trees/a")  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValueError, match="a Python task \\(fn\\) has no cwd"):
        Task("count", fn=lambda: None, cwd=Path("/x"))


# --- a run --------------------------------------------------------------------------


def test_the_agent_its_call_file_its_validators_and_its_changes_work_in_the_task_s_directory(tmp_path):
    repo, own = tree(tmp_path / "repo"), tree(tmp_path / "trees" / "a")
    (repo / "marker").unlink()  # the validator would fail in the run's working directory
    report = pipeline(tmp_path, StubAgent({"edit": edits})).run(lambda: edit.options(cwd="../trees/a")("a"))
    assert report.ok, report.failed
    out = json.loads((report.run_dir / "out" / "edit" / "a.json").read_text())
    assert out["text"] == f"{own}|{own.resolve()}"
    [row] = rows(report, "journal.jsonl")
    assert row["changes"]["created"] == ["src/a.txt"] and (own / "src" / "a.txt").exists() and not (repo / "src").exists()
    [plan] = rows(report, "plan.jsonl")
    assert plan["cwd"] == own.as_posix()


def test_a_task_that_names_none_works_in_the_run_s_and_its_plan_row_has_no_cwd(tmp_path):
    repo = tree(tmp_path / "repo")
    report = pipeline(tmp_path, StubAgent({"edit": edits})).run(lambda: edit("a"))
    assert report.ok, report.failed
    assert (repo / "src" / "a.txt").exists()
    assert "cwd" not in rows(report, "plan.jsonl")[0]


def test_a_directory_that_is_not_there_when_the_task_starts_refuses_it(tmp_path):
    tree(tmp_path / "repo")
    report = pipeline(tmp_path, StubAgent({"edit": edits})).run(lambda: edit.options(cwd="gone")("a"))
    [row] = rows(report, "journal.jsonl")
    assert row["stop"] == "invalid_input" and "working directory" in row["reason"] and "gone" in row["reason"]


def test_a_task_that_made_the_directory_first_may_name_it(tmp_path):
    tree(tmp_path / "repo")

    @python_task
    def make(unit: str) -> str:
        return str(tree(tmp_path / "trees" / unit))

    async def flow():
        await edit.options(cwd=await make("a"))("a")

    report = pipeline(tmp_path, StubAgent({"edit": edits})).run(flow)
    assert report.ok, report.failed


def test_an_input_file_is_of_the_task_s_directory_or_of_out(tmp_path):
    repo, own = tree(tmp_path / "repo"), tree(tmp_path / "trees" / "a")
    (own / "spec.md").write_text("in the tree")
    (repo / "spec.md").write_text("in the repo")
    seen = []

    def reads(launch):
        path = Path(launch.call.params["spec"]["path"])
        seen.append((path.as_posix(), (Path(launch.launch.cwd) / path).read_text()))
        return {"text": "ok"}

    agent = StubAgent({"read": reads})
    report = pipeline(tmp_path, agent).run(lambda: read.options(cwd=own)("a", Given(spec=InputFile("spec.md"))))
    assert report.ok, report.failed
    assert seen == [("spec.md", "in the tree")]
    with pytest.raises(ValueError, match="outside the working directory"):
        pipeline(tmp_path, agent).run(lambda: read.options(cwd=own)("b", Given(spec=InputFile(repo / "spec.md"))), run_id="b")


def test_two_directories_with_the_same_content_give_one_fingerprint(tmp_path):
    tree(tmp_path / "repo")
    for unit in ("a", "b"):
        tree(tmp_path / "trees" / unit)
        (tmp_path / "trees" / unit / "spec.md").write_text("same")

    def flow(unit):
        return lambda: read.options(cwd=f"../trees/{unit}", key="read")("x", Given(spec=InputFile("spec.md")))

    p = pipeline(tmp_path, StubAgent({"read": lambda launch: {"text": "ok"}}))
    first, other = p.run(flow("a"), run_id="r"), p.run(flow("b"), run_id="s")
    assert first.ok and other.ok
    assert rows(first, "journal.jsonl")[0]["fingerprint"] == rows(other, "journal.jsonl")[0]["fingerprint"]


def test_a_resume_skips_a_task_whose_directory_is_gone(tmp_path):
    tree(tmp_path / "repo")
    own = tree(tmp_path / "trees" / "a")
    calls = []

    def counted(launch):
        calls.append(launch.key)
        return edits(launch)

    p = pipeline(tmp_path, StubAgent({"edit": counted}))
    assert p.run(lambda: edit.options(cwd=own)("a"), run_id="r").ok
    for path in (own / "src" / "a.txt", own / "src", own / "marker", own):
        path.unlink() if path.is_file() else path.rmdir()
    again = p.run(lambda: edit.options(cwd=own)("a"), run_id="r", resume=True)
    assert again.ok, again.failed
    assert calls == ["edit-a"]  # skipped: not launched again


# --- recordings ---------------------------------------------------------------------


def test_a_recording_keeps_and_a_replay_writes_the_changes_in_the_task_s_directory(tmp_path):
    repo, own = tree(tmp_path / "repo"), tree(tmp_path / "trees" / "a")
    inside = tree(repo / "inner")
    rec = tmp_path / "rec"

    def flow():
        edit.options(cwd=own)("a")
        edit.options(cwd="inner")("b")

    report = pipeline(tmp_path, StubAgent({"edit": edits}), record=rec).run(flow)
    assert report.ok, report.failed
    undeclared = json.loads((rec / "undeclared.json").read_text())
    # b's tree is inside the run's working directory: its change is declared there; a's is outside it.
    assert undeclared["created"] == []
    for path in (own / "src" / "a.txt", inside / "src" / "b.txt"):
        path.unlink()
    played = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs2", cwd=repo, replay=rec).run(flow)
    assert played.ok, played.failed
    assert (own / "src" / "a.txt").read_text() == "a\n" and (inside / "src" / "b.txt").read_text() == "b\n"


def test_an_imported_recording_takes_the_changes_from_the_task_s_directory(tmp_path):
    repo, own = tree(tmp_path / "repo"), tree(tmp_path / "trees" / "a")
    live = pipeline(tmp_path, StubAgent({"edit": edits})).run(lambda: edit.options(cwd=own)("a"))
    assert live.ok, live.failed
    imported = import_recording(live.run_dir, tmp_path / "rec")
    assert imported.imported == ("edit-a",), imported
    (own / "src" / "a.txt").unlink()
    played = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs2", cwd=repo, replay=tmp_path / "rec").run(
        lambda: edit.options(cwd=own)("a")
    )
    assert played.ok, played.failed
    assert (own / "src" / "a.txt").read_text() == "a\n"


# --- the run's out/ -----------------------------------------------------------------


def launch_in(cwd: Path, out: Path, **fields) -> Launch:
    return Launch(prompt="p", model="m", label="t", cwd=cwd, out_dir=out, **fields)


def test_each_coding_agent_may_write_in_out_when_it_is_outside_the_working_directory(tmp_path):
    cwd, out = tree(tmp_path / "trees" / "a"), tree(tmp_path / "runs" / "r" / "out")
    claude = ClaudeBackend(base_env={"PATH": str(tmp_path)})  # no claude to ask its version
    argv = claude.argv(launch_in(cwd, out))
    assert argv[argv.index("--add-dir") + 1] == str(out.resolve())
    codex = CodexBackend(base_env={})
    roots = next(a for a in codex.tmp_args(launch_in(cwd, out)) if a.startswith("sandbox_workspace_write.writable_roots="))
    assert json.loads(roots.split("=", 1)[1]) == [str(codex.launch_tmp(launch_in(cwd, out))), str(out.resolve())]
    cfg = OpencodeBackend(base_env={}).config(launch_in(cwd, out, tools=("Read", "Write")))
    assert cfg["permission"]["external_directory"] == {"*": "deny", f"{out.resolve().as_posix()}/**": "allow"}


def test_out_inside_the_working_directory_adds_nothing(tmp_path):
    cwd = tree(tmp_path / "repo")
    out = tree(cwd / "runs" / "r" / "out")
    assert "--add-dir" not in ClaudeBackend(base_env={"PATH": str(tmp_path)}).argv(launch_in(cwd, out))
    codex = CodexBackend(base_env={})
    roots = next(a for a in codex.tmp_args(launch_in(cwd, out)) if a.startswith("sandbox_workspace_write.writable_roots="))
    assert json.loads(roots.split("=", 1)[1]) == [str(codex.launch_tmp(launch_in(cwd, out)))]
    assert "external_directory" not in OpencodeBackend(base_env={}).config(launch_in(cwd, out)).get("permission", {})


def test_a_launch_of_a_pipeline_names_the_run_s_out(tmp_path):
    tree(tmp_path / "repo")
    seen = []

    def names(launch):
        seen.append(launch.launch.out_dir)
        return {"text": "ok"}

    report = pipeline(tmp_path, StubAgent({"edit": names})).run(lambda: edit("a"))
    assert report.ok, report.failed
    assert seen == [(report.run_dir / "out").resolve()]
    assert os.path.isdir(seen[0])
