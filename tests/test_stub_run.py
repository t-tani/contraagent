"""A stub run (`Pipeline(stub=)`, `contraagent run --stub`): the stub agent plays every task."""

import json
import sys
from typing import Literal

import pytest
from pydantic import BaseModel, Field, RootModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.cli import main
from contraagent.contracts import smallest
from contraagent.testing import StubAgent, StubTask, fails, writes_nothing, writes_smallest


class Item(BaseModel):
    id: str = Field(min_length=3)
    score: int = Field(gt=0, le=10)


class Found(BaseModel):
    items: list[Item] = Field(min_length=1)
    verdict: Literal["keep", "drop"]
    note: str | None = None


class Tagged(BaseModel):
    tag: str = Field(pattern=r"^T-\d+$")


def test_the_smallest_value_passes_its_schema():
    for model in (Found, RootModel[list[str]], RootModel[dict[str, int]], RootModel[int], RootModel[tuple[int, str]]):
        value, problems = smallest(model.model_json_schema())
        assert problems == []
        model.model_validate(value)
    assert smallest(Found.model_json_schema())[0] == {"items": [{"id": "xxx", "score": 1}], "verdict": "keep"}


def test_a_rule_it_cannot_build_is_named():
    value, problems = smallest(Tagged.model_json_schema())
    assert value == {"tag": ""} and problems == ["<root>.tag: pattern '^T-\\\\d+$'"]


find = agent_task("find", instructions="Find items in params.path.", output=Found, max_turns=5, timeout_s=60, retries=0)
tag = agent_task("tag", instructions="Tag the unit.", output=Tagged, max_turns=5, timeout_s=60, retries=0)
calls: list[str] = []


@python_task
def fetch(unit: str) -> str:
    calls.append(f"fetch {unit}")
    return f"{unit}.md"


@python_task
def publish(found: list[Found]) -> None:
    calls.append("publish")


def flow(units: list[str]):
    paths = yield [fetch(u) for u in units]
    found = yield [find(u, path=p) for u, p in zip(units, paths, strict=True)]
    kept = [f for f in found if f.verdict == "keep"]
    yield publish(found=kept)
    return len(kept)


def test_a_stub_run_plays_every_task_and_runs_no_function(tmp_path):
    calls.clear()
    stub = StubAgent(default=writes_smallest())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.ok, report.failed
    assert report.run_id == "flow-stub" and report.value == 2
    assert calls == []
    assert sorted(t.key for t in stub.played) == ["python:fetch-a", "python:fetch-b", "python:publish"]
    assert sorted(launch.key for launch in stub.launches) == ["find-a", "find-b"]
    assert json.loads((report.run_dir / "run.json").read_text())["stub"] is True


def test_a_stub_run_executes_the_kinds_named_and_scripts_both_executors(tmp_path):
    calls.clear()
    stub = StubAgent(
        {"find-b": {"items": [{"id": "abc", "score": 9}], "verdict": "drop"}, "publish": lambda task: isinstance(task, StubTask) and None},
        default=writes_smallest(),
        execute=["fetch"],
    )
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.ok, report.failed
    assert report.value == 1
    assert sorted(calls) == ["fetch a", "fetch b"]
    assert [t.key for t in stub.played] == ["python:publish"]


def test_a_python_reply_that_fails_raises_in_the_task(tmp_path):
    stub = StubAgent({"python:fetch-b": fails(reason="stub: no network"), "fetch": writes_nothing()}, default=writes_smallest())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.results["python:fetch-b"].reason == "RuntimeError: stub: no network"
    assert report.results["python:fetch-a"].stop == "invalid_output"  # no output where one is declared


def test_an_unbuildable_smallest_output_fails_and_names_the_rule(tmp_path):
    stub = StubAgent(default=writes_smallest())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(lambda: tag("a"), run_id="t")
    assert report.results["tag-a"].stop == "error"
    assert "no smallest output for tag-a: <root>.tag: pattern" in report.results["tag-a"].reason


def test_stub_and_backends_do_not_go_together():
    with pytest.raises(TypeError, match="not both"):
        Pipeline(backends=StubAgent().backends(), stub=StubAgent())


def test_the_cli_lists_the_tasks_a_stub_run_created(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    code = main(["run", f"{__file__}:flow", "--stub", "--execute", "fetch", "--kwargs", '{"units": ["a"]}', "--runs-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "3 tasks created:" in out
    assert "  fetch · a | completed | flow (line " in out
    assert "  find · a | completed | flow (line " in out
    assert (tmp_path / "flow-stub" / "run.json").exists()
    assert main(["run", f"{__file__}:flow", "--execute", "fetch"]) == 2
