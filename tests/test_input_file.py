"""Input files (`InputFile`): a file a task is given by its path and the SHA-256 of its content,
taken at the task call. The params hold `{"path", "sha256"}`, so the fingerprint holds both; the
task is refused (`invalid_input`) when the file no longer has that content as it starts; a path
outside the working directory is refused at the call. What a type checker finds is in
`tests/typing/public_types.py`."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, ValidationError

from contraagent import InputFile, Pipeline, agent_task, python_task
from contraagent.backends import CallFile
from contraagent.testing import StubAgent


class Review(BaseModel):
    approved: bool


class ReviewParams(BaseModel):
    note: InputFile = Field(description="the note to review")


review = agent_task("review", params=ReviewParams, output=Review, instructions="Review the note.", max_turns=3, timeout_s=30)


def pipeline(tmp_path: Path, agent: StubAgent | None = None) -> Pipeline:
    agent = agent or StubAgent({"review": {"approved": True}})
    return Pipeline(None, runs_dir=tmp_path / "runs", backends=agent.backends(), cwd=tmp_path, log=lambda line: None)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def reviewing(path: str):
    async def flow():
        return await review("a", ReviewParams(note=InputFile(path)))

    return flow


def refused_at_the_call(tmp_path: Path, path: str | Path) -> str:
    with pytest.raises(ValueError) as caught:
        pipeline(tmp_path).run(reviewing(str(path)), run_id="refused")
    return str(caught.value)


def test_the_call_file_holds_the_path_and_hash_and_the_schema_says_to_read_the_file(tmp_path):
    write(tmp_path, "in/spec.md", "the spec")
    report = pipeline(tmp_path).run(reviewing("in/spec.md"), run_id="r")
    assert report.ok
    call = CallFile.read(report.run_dir / "calls" / "review-a.json")
    assert call.params == {"note": {"path": "in/spec.md", "sha256": sha256("the spec")}}
    note = call.params_json_schema["properties"]["note"]
    assert note["description"] == "the note to review"
    assert note["required"] == ["path", "sha256"] and note["additionalProperties"] is False
    assert "Read the file with your tools" in note["properties"]["path"]["description"]
    assert "SHA-256" in note["properties"]["sha256"]["description"]


def test_a_text_output_passed_on_by_its_path_is_given_from_its_writer(tmp_path):
    note = agent_task("note", output=str, instructions="Write a note.", max_turns=3, timeout_s=30)
    agent = StubAgent({"note": "line\n" * 2000, "review": {"approved": True}})

    async def flow():
        written = note("a")
        await written
        return await review("a", ReviewParams(note=written.input_file()))

    report = pipeline(tmp_path, agent).run(flow, run_id="r")
    assert report.ok
    call = CallFile.read(report.run_dir / "calls" / "review-a.json")
    assert call.params["note"] == {"path": "runs/r/out/note/a.md", "sha256": sha256("line\n" * 2000)}
    plan = [json.loads(line) for line in (report.run_dir / "plan.jsonl").read_text().splitlines()]
    assert next(row for row in plan if row["key"] == "review-a")["given_from"] == ["note-a"]


def test_a_python_task_is_given_the_file_with_an_absolute_path_and_reads_it(tmp_path, monkeypatch):
    write(tmp_path, "in/spec.md", "four words in it")
    monkeypatch.chdir(tmp_path.parent)  # a relative path would not resolve here

    @python_task
    def words(unit: str, note: InputFile) -> int:
        assert note.path.is_absolute() and note.sha256 == sha256("four words in it")
        return len(note.read_text().split())

    async def flow():
        return await words("a", note=InputFile("in/spec.md"))

    report = pipeline(tmp_path).run(flow, run_id="r")
    assert report.ok
    assert json.loads((report.run_dir / "out" / "words" / "a.json").read_text()) == 4


def test_a_file_changed_after_the_call_refuses_the_task_as_it_starts(tmp_path):
    spec = write(tmp_path, "in/spec.md", "the spec")

    @python_task
    def rewrite(unit: str) -> None:
        spec.write_text("another spec", encoding="utf-8")

    def flow():
        changed = rewrite("a")
        review.options(after=[changed])("a", ReviewParams(note=InputFile("in/spec.md")))

    report = pipeline(tmp_path).run(flow, run_id="r")
    result = report.results["review-a"]
    assert not report.ok and result.stop == "invalid_input"
    assert result.reason == (
        f"input file in/spec.md changed after the task call: sha256 {sha256('the spec')[:12]} at the call, "
        f"{sha256('another spec')[:12]} now; the task is given the content the file had at its call"
    )
    row = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()][-1]
    assert row["key"] == "review-a" and row["stop"] == "invalid_input"


def test_a_file_removed_after_the_call_refuses_a_python_task_as_it_starts(tmp_path):
    spec = write(tmp_path, "in/spec.md", "the spec")
    read: list[str] = []

    @python_task
    def remove(unit: str) -> None:
        spec.unlink()

    @python_task
    def words(unit: str, note: InputFile) -> int:
        read.append(unit)
        return len(note.read_text().split())

    def flow():
        words.options(after=[remove("a")])("a", note=InputFile("in/spec.md"))

    report = pipeline(tmp_path).run(flow, run_id="r")
    result = report.results["python:words-a"]
    assert result.stop == "invalid_input" and read == []
    assert result.reason.startswith("input file in/spec.md is gone; it was given to the task call with sha256 ")


def test_a_file_a_python_task_reads_after_it_changed_refuses_the_task(tmp_path):
    spec = write(tmp_path, "in/spec.md", "the spec")

    @python_task
    def words(unit: str, note: InputFile) -> int:
        spec.write_text("another spec", encoding="utf-8")
        return len(note.read_text().split())

    report = pipeline(tmp_path).run(lambda: words("a", note=InputFile("in/spec.md")), run_id="r")
    result = report.results["python:words-a"]
    assert result.stop == "invalid_input"
    assert result.reason.startswith("invalid input: input file ") and "changed after the task call" in result.reason


def test_the_hash_is_in_the_fingerprint_and_so_is_the_path(tmp_path):
    write(tmp_path, "in/spec.md", "the spec")
    agent = StubAgent({"review": {"approved": True}})

    def run(path: str):
        agent.launches.clear()
        return pipeline(tmp_path, agent).run(reviewing(path), run_id="r", resume=(tmp_path / "runs" / "r").exists())

    assert run("in/spec.md").ok and len(agent.launches) == 1
    same = run("in/spec.md")
    assert same.results["review-a"].stop == "skipped" and agent.launches == []

    write(tmp_path, "in/spec.md", "another spec")
    changed = run("in/spec.md")
    assert changed.results["review-a"].stop == "completed" and len(agent.launches) == 1

    write(tmp_path, "in/moved.md", "another spec")  # the same content at another path
    moved = run("in/moved.md")
    assert moved.results["review-a"].stop == "completed" and len(agent.launches) == 1
    rows = [json.loads(line) for line in (moved.run_dir / "journal.jsonl").read_text().splitlines()]
    reruns = [r["rerun"] for r in rows if r["key"] == "review-a"][1:]
    assert reruns == ["its fingerprint changed: its params, its input files"] * 2  # no divergence


def test_a_path_that_climbs_out_is_refused_where_it_is_made():
    with pytest.raises(ValueError, match=r"input file \.\./x\.md climbs out of the working directory"):
        InputFile("../x.md")
    with pytest.raises(ValueError, match="climbs out"):
        InputFile("in/../../x.md")
    with pytest.raises(ValueError, match="not an empty string"):
        InputFile("")
    assert InputFile("in/../x.md").path == Path("in/../x.md")


def test_a_path_outside_the_working_directory_is_refused_at_the_call(tmp_path):
    work, outside = tmp_path / "work", tmp_path / "outside.md"
    outside.write_text("secret")
    work.mkdir()
    message = refused_at_the_call(work, outside)
    assert message == (
        f"review(): input file {outside.as_posix()} is outside the working directory {work.as_posix()}; give a file inside it"
    )


@pytest.mark.skipif(os.name == "nt", reason="a symbolic link needs a privilege on Windows")
def test_a_symbolic_link_out_of_the_working_directory_is_refused_at_the_call(tmp_path):
    work, outside = tmp_path / "work", tmp_path / "outside.md"
    outside.write_text("secret")
    (work / "in").mkdir(parents=True)
    (work / "in" / "link.md").symlink_to(outside)
    message = refused_at_the_call(work, "in/link.md")
    assert message.startswith(f"review(): input file in/link.md is a symbolic link to {outside.resolve().as_posix()}, outside")


def test_a_missing_file_or_a_directory_is_refused_at_the_call(tmp_path):
    assert refused_at_the_call(tmp_path, "in/none.md") == (
        "review(): input file in/none.md does not exist; a task is given a file that is there at its call"
    )
    (tmp_path / "in").mkdir()
    assert refused_at_the_call(tmp_path, "in") == "review(): input file in is not a file"


def test_its_json_validates_back_and_another_value_does_not():
    file = ReviewParams.model_validate({"note": {"path": "in/a.md", "sha256": "0" * 64}}).note
    assert file == InputFile._recorded("in/a.md", "0" * 64) and file.sha256 == "0" * 64
    assert ReviewParams(note=file).model_dump(mode="json") == {"note": {"path": "in/a.md", "sha256": "0" * 64}}
    for wrong in ("in/a.md", {"path": "in/a.md"}, {"path": "in/a.md", "sha256": "xyz"}):
        with pytest.raises(ValidationError, match="an input file is InputFile"):
            ReviewParams.model_validate({"note": wrong})
    assert repr(file) == "InputFile('in/a.md', sha256=000000000000...)"


def test_the_example_gives_the_reviewer_the_draft_s_file_and_resumes_with_nothing_launched(tmp_path):
    from contraagent.docs.examples.input_file import flow

    text = "word " * 5000
    agent = StubAgent({"draft": text, "review": {"approved": True, "note": ""}})

    def run(**kw):
        return pipeline(tmp_path, agent).run(flow.reports, topics=["caching"], run_id="reports", **kw)

    first = run()
    assert first.ok and first.value == [[flow.Verdict(approved=True, note=""), 5000]]  # gather gives a list
    call = CallFile.read(first.run_dir / "calls" / "review-caching.json")
    assert call.params == {
        "report": {"path": "runs/reports/out/draft/caching.md", "sha256": sha256(text)},
        "audience": "new team members",
    }
    agent.launches.clear()
    again = run(resume=True)
    assert again.ok and agent.launches == [] and {r.stop for r in again.results.values()} == {"skipped"}


def test_a_task_s_output_file_is_an_input_file_only_once_it_succeeded(tmp_path):
    from contraagent.testing import fails

    tidy = agent_task("tidy", instructions="Tidy.", max_turns=3, timeout_s=30)
    note = agent_task("note", output=str, instructions="Write a note.", max_turns=3, timeout_s=30)
    agent = StubAgent({"note": fails(), "tidy": None, "review": {"approved": True}})
    raised: list[str] = []

    async def flow():
        for make in (lambda: tidy("a"), lambda: note("a")):
            pending = make()
            try:
                pending.input_file()
            except ValueError as exc:
                raised.append(str(exc))
            try:
                await pending
            except Exception:
                pass
            try:
                pending.input_file()
            except ValueError as exc:
                raised.append(str(exc))

    pipeline(tmp_path, agent).run(flow, run_id="r")
    assert raised == [
        "tidy-a has no output file to give as an input file",
        "tidy-a has no output file to give as an input file",
        "note-a has not finished: await it before you give its output file as an input file",
        "note-a ended error: its output file is not given as an input file",
    ]
