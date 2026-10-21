"""Input roots (`Pipeline(input_roots=)`, `--input-root`): a file a task is given as
`InputFile(path, root=name)` is held by the root's name and its path under the root, so the
params, the plan and the fingerprint do not depend on where the root is; the call file and
a Python task get the absolute path. The run's `out/` is the input root `out`."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from contraagent import InputFile, Pipeline, PipelineConfig, agent_task, python_task
from contraagent.backends import CallFile, ClaudeBackend, CodexBackend, Launch, OpencodeBackend
from contraagent.testing import StubAgent


class Verdict(BaseModel):
    approved: bool


class ReviewParams(BaseModel):
    data: InputFile = Field(description="the data to review")


review = agent_task("review", params=ReviewParams, output=Verdict, instructions="Review the data.", max_turns=3, timeout_s=30)
note = agent_task("note", output=str, instructions="Write a note.", max_turns=3, timeout_s=30)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def corpus(path: Path, text: str = "a,b\n1,2\n") -> Path:
    (path / "2026").mkdir(parents=True)
    (path / "2026" / "x.csv").write_text(text, encoding="utf-8")
    return path


def pipeline(tmp_path: Path, agent: StubAgent | None = None, **options) -> Pipeline:
    agent = agent or StubAgent({"review": {"approved": True}, "note": "a note"})
    (tmp_path / "work").mkdir(exist_ok=True)
    options.setdefault("backends", agent.backends())
    return Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path / "work", log=lambda line: None, **options)


def reviewing(path: str = "2026/x.csv", root: str | None = "data"):
    async def flow():
        return await review("a", ReviewParams(data=InputFile(path, root=root)))

    return flow


def rows(run_dir: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (run_dir / name).read_text().splitlines()]


def test_the_records_hold_the_root_and_the_call_file_the_absolute_path(tmp_path):
    data = corpus(tmp_path / "srv" / "corpus")
    report = pipeline(tmp_path, input_roots={"data": data}).run(reviewing(), run_id="r")
    assert report.ok, report.failed
    held = {"root": "data", "path": "2026/x.csv", "sha256": sha256("a,b\n1,2\n")}
    [row] = [r for r in rows(report.run_dir, "plan.jsonl") if r["key"] == "review-a"]
    assert row["input_files"] == [{"param": "data", **held}]
    assert json.loads((report.run_dir / "run.json").read_text())["input_roots"] == {"data": data.as_posix()}
    call = CallFile.read(report.run_dir / "calls" / "review-a.json")
    assert call.params == {"data": {"path": (data / "2026/x.csv").as_posix(), "sha256": held["sha256"]}}


def test_a_run_with_no_root_records_none(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "in.csv").write_text("x")
    report = pipeline(tmp_path).run(reviewing("in.csv", None), run_id="r")
    assert report.ok, report.failed
    assert "input_roots" not in json.loads((report.run_dir / "run.json").read_text())


def test_a_python_task_gets_the_absolute_path_and_the_root(tmp_path, monkeypatch):
    data = corpus(tmp_path / "corpus")
    monkeypatch.chdir(tmp_path)

    @python_task
    def count(unit: str, data: InputFile) -> int:
        assert data.path == data_dir / "2026" / "x.csv" and data.root == "data"
        return len(data.read_text().splitlines())

    data_dir = data

    async def flow():
        return await count("a", data=InputFile("2026/x.csv", root="data"))

    report = pipeline(tmp_path, input_roots={"data": "../corpus"}).run(flow, run_id="r")  # relative to the working directory
    assert report.ok, report.failed
    assert report.value == 2


def test_a_python_task_passes_on_the_file_it_was_given(tmp_path):
    corpus(tmp_path / "corpus")

    @python_task
    def pick(unit: str, data: InputFile) -> InputFile:
        return data

    async def flow():
        picked = await pick("a", data=InputFile("2026/x.csv", root="data"))
        return await review("a", ReviewParams(data=picked))

    report = pipeline(tmp_path, input_roots={"data": tmp_path / "corpus"}).run(flow, run_id="r")
    assert report.ok, report.failed
    [row] = [r for r in rows(report.run_dir, "plan.jsonl") if r["key"] == "review-a"]
    assert row["input_files"][0]["root"] == "data" and row["input_files"][0]["path"] == "2026/x.csv"


def test_an_absolute_path_under_a_root_is_given_with_the_root(tmp_path):
    data = corpus(tmp_path / "corpus")
    with pytest.raises(ValueError) as caught:
        pipeline(tmp_path, input_roots={"data": data}).run(reviewing(str(data / "2026/x.csv"), None), run_id="r")
    assert str(caught.value) == (
        f"review(): input file {(data / '2026/x.csv').as_posix()} is under input root data ({data.as_posix()}); "
        "give it as InputFile('2026/x.csv', root='data')"
    )


def test_a_root_the_run_does_not_have_is_refused_at_the_call_and_by_the_check(tmp_path):
    corpus(tmp_path / "corpus")
    with pytest.raises(ValueError, match=r"names input root 'data', which this run does not have \(its input roots: out\)"):
        pipeline(tmp_path).run(reviewing(), run_id="r")
    report = pipeline(tmp_path).check(reviewing())
    assert not report.ok
    assert any("names input root 'data', which this run does not have" in e for e in report.errors)


def test_a_root_s_name_and_its_directory_are_checked(tmp_path):
    for name in ("Data", "1st", "", "a b"):
        with pytest.raises(ValueError, match="is not lowercase letters"):
            pipeline(tmp_path, input_roots={name: tmp_path})
    with pytest.raises(ValueError, match="input root name 'out' is the run's own out/ directory"):
        pipeline(tmp_path, input_roots={"out": tmp_path})
    with pytest.raises(ValueError, match="is not an input root's name"):
        InputFile("x.csv", root="Data")
    with pytest.raises(ValueError, match="of input root data is absolute"):
        InputFile(tmp_path / "x.csv", root="data")
    with pytest.raises(ValueError, match="climbs out of input root data"):
        InputFile("../x.csv", root="data")
    missing = pipeline(tmp_path, input_roots={"data": tmp_path / "none"})
    with pytest.raises(ValueError, match="input root data is .*/none, which is not a directory"):
        missing.run(reviewing(), run_id="r")
    assert not (tmp_path / "runs" / "r").exists()  # refused before anything is written
    assert any("input root data is" in e for e in missing.check(reviewing()).errors)


@pytest.mark.skipif(os.name == "nt", reason="a symbolic link needs a privilege on Windows")
def test_a_symbolic_link_out_of_the_root_is_refused(tmp_path):
    data = corpus(tmp_path / "corpus")
    (tmp_path / "secret.csv").write_text("secret")
    (data / "link.csv").symlink_to(tmp_path / "secret.csv")
    with pytest.raises(ValueError, match=r"input file link\.csv is a symbolic link to .*secret\.csv, outside input root data"):
        pipeline(tmp_path, input_roots={"data": data}).run(reviewing("link.csv"), run_id="r")


def test_a_file_changed_after_the_call_is_refused_naming_its_root(tmp_path):
    data = corpus(tmp_path / "corpus")

    @python_task
    def rewrite(unit: str) -> None:
        (data / "2026" / "x.csv").write_text("other")

    async def flow():
        changed = rewrite("a")
        await review.options(after=[changed])("a", ReviewParams(data=InputFile("2026/x.csv", root="data")))

    report = pipeline(tmp_path, input_roots={"data": data}).run(flow, run_id="r")
    result = report.results["review-a"]
    assert result.stop == "invalid_input"
    assert "input file 2026/x.csv of input root data changed after the task call" in result.reason


def test_a_root_moved_between_a_run_and_its_resume_skips_the_task(tmp_path):
    agent = StubAgent({"review": {"approved": True}})
    first = corpus(tmp_path / "first")
    assert pipeline(tmp_path, agent, input_roots={"data": first}).run(reviewing(), run_id="r").ok
    moved = tmp_path / "moved"
    shutil.move(first, moved)
    agent.launches.clear()
    again = pipeline(tmp_path, agent, input_roots={"data": moved}).run(reviewing(), run_id="r", resume=True)
    assert again.ok and again.results["review-a"].stop == "skipped" and agent.launches == []
    journal = rows(again.run_dir, "journal.jsonl")
    assert journal[0]["fingerprint"] == journal[-1]["fingerprint"]


def test_a_replay_takes_a_root_moved_since_the_recording(tmp_path):
    first = corpus(tmp_path / "first")
    rec = tmp_path / "rec"
    assert pipeline(tmp_path, input_roots={"data": first}, record=rec).run(reviewing(), run_id="r").ok
    moved = tmp_path / "moved"
    shutil.move(first, moved)
    played = pipeline(tmp_path, input_roots={"data": moved}, replay=rec, backends=None).run(reviewing())
    assert played.ok, played.failed
    assert "another fingerprint" not in played.results["review-a"].reason


def test_an_agent_task_with_its_own_working_directory_takes_a_root_s_file(tmp_path):
    data = corpus(tmp_path / "corpus")
    own = tmp_path / "trees" / "a"
    own.mkdir(parents=True)
    seen = []

    def reads(launch):
        seen.append((Path(launch.call.params["data"]["path"]).read_text(), launch.launch.input_roots))
        return {"approved": True}

    async def flow():
        await review.options(cwd=own)("a", ReviewParams(data=InputFile("2026/x.csv", root="data")))

    report = pipeline(tmp_path, StubAgent({"review": reads}), input_roots={"data": data}).run(flow, run_id="r")
    assert report.ok, report.failed
    assert seen == [("a,b\n1,2\n", (data,))]


# --- out/, the built-in root --------------------------------------------------------


def test_an_output_file_is_of_the_root_out_wherever_the_run_directory_is(tmp_path):
    agent = StubAgent({"note": "a note", "review": {"approved": True}})

    async def flow():
        written = note("a")
        await written
        given = written.input_file()
        assert (given.root, given.path) == ("out", Path("note/a.md"))
        await review("a", ReviewParams(data=given))

    prints = []
    for runs in ("runs", "elsewhere/deeper"):
        (tmp_path / "work").mkdir(exist_ok=True)
        p = Pipeline(PipelineConfig({}), runs_dir=tmp_path / runs, backends=agent.backends(), cwd=tmp_path / "work", log=lambda line: None)
        report = p.run(flow, run_id="r")
        assert report.ok, report.failed
        [row] = [r for r in rows(report.run_dir, "journal.jsonl") if r["key"] == "review-a"]
        prints.append(row["fingerprint"])
    assert prints[0] == prints[1]


def test_an_output_file_given_by_its_path_or_its_root_is_one_file(tmp_path):
    agent = StubAgent({"note": "a note", "review": {"approved": True}})

    async def flow():
        written = note("a")
        await written
        assert written.path is not None
        await review.options(key="by-path")("a", ReviewParams(data=InputFile(written.path)))
        await review.options(key="by-root")("a", ReviewParams(data=InputFile("note/a.md", root="out")))

    report = pipeline(tmp_path, agent).run(flow, run_id="r")
    assert report.ok, report.failed
    plan = {r["key"]: r for r in rows(report.run_dir, "plan.jsonl")}
    assert (
        plan["by-path"]["input_files"]
        == plan["by-root"]["input_files"]
        == [{"param": "data", "root": "out", "path": "note/a.md", "sha256": sha256("a note")}]
    )


# --- the coding agents --------------------------------------------------------------


def launch_reading(cwd: Path, *roots: Path, **fields) -> Launch:
    return Launch(prompt="p", model="m", label="t", cwd=cwd, input_roots=roots, **fields)


def test_each_coding_agent_may_read_a_root_outside_its_working_directory(tmp_path):
    cwd, data = tmp_path / "work", corpus(tmp_path / "corpus")
    inside = corpus(cwd / "inner")
    claude = ClaudeBackend(base_env={"PATH": str(tmp_path)})  # no claude to ask its version
    argv = claude.argv(launch_reading(cwd, data, inside))
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--add-dir"] == [str(data.resolve())]
    cfg = OpencodeBackend(base_env={}).config(launch_reading(cwd, data, inside, tools=("Read",)))
    assert cfg["permission"]["external_directory"] == {"*": "deny", f"{data.resolve().as_posix()}/**": "allow"}
    codex = CodexBackend(base_env={})  # its sandbox reads every directory: nothing is added
    assert str(data.resolve()) not in " ".join(codex.tmp_args(launch_reading(cwd, data)))


# --- the command line ---------------------------------------------------------------


FLOW = """
from pydantic import BaseModel, Field
from contraagent import InputFile, agent_task


class Verdict(BaseModel):
    approved: bool = Field(examples=[True])


class Given(BaseModel):
    data: InputFile = Field(description="the data")


review = agent_task("review", params=Given, output=Verdict, instructions="Review.", max_turns=1, timeout_s=10)


def flow():
    review("a", Given(data=InputFile("2026/x.csv", root="data")))
"""


def cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "contraagent", *args], cwd=tmp_path, capture_output=True, text=True, env={**os.environ, "NO_COLOR": "1"}
    )


def test_the_command_line_names_the_roots(tmp_path):
    corpus(tmp_path / "corpus")
    (tmp_path / "tasks.py").write_text(FLOW)
    done = cli(tmp_path, "run", "tasks.py:flow", "--stub", "--input-root", "data=corpus")
    assert done.returncode == 0, done.stdout + done.stderr
    info = json.loads((tmp_path / "runs" / "flow-stub" / "run.json").read_text())
    assert info["input_roots"] == {"data": (tmp_path / "corpus").as_posix()}
    bad = cli(tmp_path, "run", "tasks.py:flow", "--stub", "--input-root", "data")
    assert bad.returncode == 2 and "--input-root 'data': give NAME=DIR" in bad.stderr
    gone = cli(tmp_path, "run", "tasks.py:flow", "--stub", "--run-id", "g", "--input-root", "data=none")
    assert gone.returncode == 1 and "--input-root: input root data is" in gone.stdout
    unnamed = cli(tmp_path, "check", "tasks.py:flow", "--stub")
    assert unnamed.returncode == 1 and "names input root 'data', which this run does not have" in unnamed.stdout
