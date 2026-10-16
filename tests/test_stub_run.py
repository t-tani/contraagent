"""A stub run (`Pipeline(stub=)`, `contraagent run --stub`): the stub agent plays every task."""

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, RootModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent._internal.cli import main
from contraagent._internal.contracts.contract import example
from contraagent.testing import StubAgent, StubTask, fails, writes_example, writes_nothing


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
        value, problems = example(model.model_json_schema())
        assert problems == []
        model.model_validate(value)
    assert example(Found.model_json_schema())[0] == {"items": [{"id": "xxx", "score": 1}], "verdict": "keep"}


def test_a_rule_it_cannot_build_is_named():
    value, problems = example(Tagged.model_json_schema())
    assert value == {"tag": ""} and problems == ["<root>.tag: pattern '^T-\\\\d+$'"]


class Pair(BaseModel):
    """A model's own example is the whole value."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"items": [{"id": "abc", "score": 2}] * 2, "verdict": "drop"}]})

    items: list[Item] = Field(min_length=1)
    verdict: Literal["keep", "drop"]


class Labeled(BaseModel):
    """A field's example is that field's value; a field without one is the smallest."""

    tag: str = Field(pattern=r"^T-\d+$", examples=["T-7"])
    item: Item = Field(examples=[{"id": "def", "score": 5}])
    count: int


class Outer(BaseModel):
    """The model's own example comes before its fields'."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"tag": "T-1", "item": {"id": "ghi", "score": 3}, "count": 4}]})

    tag: str = Field(pattern=r"^T-\d+$", examples=["T-7"])
    item: Item
    count: int


def test_the_example_is_the_first_of_examples_at_every_part_of_the_schema():
    assert example(Pair.model_json_schema()) == ({"items": [{"id": "abc", "score": 2}] * 2, "verdict": "drop"}, [])
    assert example(Labeled.model_json_schema()) == ({"tag": "T-7", "item": {"id": "def", "score": 5}, "count": 0}, [])
    assert example(Outer.model_json_schema()) == ({"tag": "T-1", "item": {"id": "ghi", "score": 3}, "count": 4}, [])


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
    stub = StubAgent(default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.ok, report.failed
    assert report.run_id == "flow-stub" and report.value == 2
    assert calls == []
    assert sorted(t.key for t in stub.played) == ["python:fetch-a", "python:fetch-b", "python:publish"]
    assert sorted(launch.key for launch in stub.launches) == ["find-a", "find-b"]
    assert json.loads((report.run_dir / "run.json").read_text(encoding="utf-8"))["stub"] is True


def test_a_stub_run_executes_the_kinds_named_and_scripts_both_executors(tmp_path):
    calls.clear()
    stub = StubAgent(
        {"find-b": {"items": [{"id": "abc", "score": 9}], "verdict": "drop"}, "publish": lambda task: isinstance(task, StubTask) and None},
        default=writes_example(),
        execute=["fetch"],
    )
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.ok, report.failed
    assert report.value == 1
    assert sorted(calls) == ["fetch a", "fetch b"]
    assert [t.key for t in stub.played] == ["python:publish"]


def test_a_python_reply_that_fails_raises_in_the_task(tmp_path):
    stub = StubAgent({"python:fetch-b": fails(reason="stub: no network"), "fetch": writes_nothing()}, default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, units=["a", "b"])
    assert report.results["python:fetch-b"].reason == "RuntimeError: stub: no network"
    assert report.results["python:fetch-a"].stop == "invalid_output"  # no output where one is declared


def test_an_unbuildable_example_fails_and_names_the_rule(tmp_path):
    stub = StubAgent(default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(lambda: tag("a"), run_id="t")
    assert report.results["tag-a"].stop == "error"
    assert "no example for tag-a: <root>.tag: pattern" in report.results["tag-a"].reason


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


def two_items(path, value: Found) -> list[str]:
    return [] if len(value.items) == 2 else [f"items: two expected, got {len(value.items)}"]


strict = agent_task("strict", instructions="Find two items.", output=Found, validators=[two_items], max_turns=5, timeout_s=60, retries=2)


def test_an_example_its_validators_refuse_fails_its_checks_at_once(tmp_path):
    stub = StubAgent(default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(lambda: strict("a"), run_id="s")
    [failed] = report.failed
    assert failed.stop == "invalid_output"
    assert failed.reason.endswith("[two_items] items: two expected, got 1")
    # The same value again cannot pass: no correction round, and no retry for all of `retries=2`.
    assert [launch.resumed for launch in stub.launches] == [False]
    assert len((report.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_a_list_of_replies_corrects_an_example(tmp_path):
    stub = StubAgent({"strict": [writes_example(), {"items": [{"id": "abc", "score": 1}] * 2, "verdict": "keep"}]})
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(lambda: strict("a"), run_id="s")
    assert report.ok, report.failed
    assert [launch.resumed for launch in stub.launches] == [False, True]


DEMO = Path(__file__).resolve().parents[1] / "src/contraagent/docs/examples/demo"


def strict_flow(units: list[str]):
    return [strict(u) for u in units]


def test_the_cli_names_the_checks_the_examples_failed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    code = main(["run", f"{__file__}:strict_flow", "--stub", "--kwargs", '{"units": ["a", "b"]}', "--runs-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "  strict · a | invalid_output | strict_flow (line " in out
    assert "  strict-a: invalid_output out/strict/a.json: [two_items] items: two expected, got 1" in out
    assert out.splitlines()[-1] == (
        "2 tasks failed checks on the examples the stub agent wrote (strict: two_items), so the tasks that "
        "need their outputs did not run. Give each output model an example that passes its validators: "
        "`contraagent docs testing`"
    )


def test_the_demo_stub_run_goes_through_the_whole_flow_on_its_examples(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    argv = ["run", f"{DEMO / 'tasks.py'}:docs", "--stub", "--kwargs", '{"units": ["alpha", "beta"]}', "--runs-dir", str(tmp_path)]
    code = main(argv)
    out = capsys.readouterr().out
    assert code == 0, out
    assert "11 tasks created:" in out and "✓ 11/11 tasks done" in out
    for kind in ("prepare", "summarize", "score", "review", "write_note"):
        assert f"  {kind} · beta | completed | docs > review_loop (line " in out
    assert (tmp_path / "docs-stub" / "out" / "write_note" / "beta.md").read_text(encoding="utf-8").startswith("# alpha")


def test_the_cli_says_nothing_of_checks_when_every_task_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    code = main(["run", f"{__file__}:flow", "--stub", "--kwargs", '{"units": ["a"]}', "--runs-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "examples the stub agent wrote" not in out


class BadExample(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"items": [], "verdict": "maybe"}]})

    items: list[Item] = Field(min_length=1)
    verdict: Literal["keep", "drop"]


bad = agent_task("bad", instructions="Find items.", output=BadExample, max_turns=5, timeout_s=60)
noted = agent_task("noted", instructions="Write a note.", output=Annotated[str, Field(examples=["# a note\n"])], max_turns=5, timeout_s=60)
mislabeled = agent_task("mislabeled", instructions="Write a note.", output=Annotated[str, Field(examples=[7])], max_turns=5, timeout_s=60)


def test_check_reports_an_example_that_fails_its_own_schema():
    report = Pipeline(PipelineConfig({}), backends=StubAgent().backends()).check(lambda: [bad("a"), mislabeled("a"), find("a")])
    assert not report.ok
    assert [e for e in report.errors if "example" in e] == [
        "bad: output BadExample: its example does not pass its own schema: items: List should have at least 1 item after validation, not 0",
        "bad: output BadExample: its example does not pass its own schema: verdict: Input should be 'keep' or 'drop'",
        "mislabeled: output text: its example does not pass its own schema: <root>: Input should be a valid string",
    ]
    assert "contracts" in report.topics


def test_a_text_output_writes_its_example(tmp_path):
    stub = StubAgent(default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(lambda: noted("a"), run_id="n")
    assert report.ok, report.failed
    assert (report.run_dir / "out" / "noted" / "a.md").read_text(encoding="utf-8") == "# a note\n"


class ModuleReview(BaseModel):
    """An example that names the task call's own unit and params."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"module": "{params.module}", "lines": ["{unit}: {params.path}"], "note": "{params.missing} {x}"}]}
    )

    module: str
    lines: list[str]
    note: str


def names_its_module(path, review: ModuleReview, *, params: dict) -> list[str]:
    return [] if review.module == params["module"] else [f"module: {params['module']!r} expected, got {review.module!r}"]


reviewed = agent_task(
    "reviewed", instructions="Review a module.", output=ModuleReview, validators=[names_its_module], max_turns=5, timeout_s=60
)


@python_task
def tally(module: str) -> ModuleReview:
    raise AssertionError("played, not run")


def test_an_example_names_each_task_call_s_unit_and_params(tmp_path):
    def flow(modules: list[str]):
        for m in modules:
            reviewed(m, module=m, path=f"src/{m}.py")
            tally(m, module=m)

    stub = StubAgent(default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(flow, modules=["bank", "retry"])
    assert report.ok, report.failed  # one example passes the validator of every unit
    out = json.loads((report.run_dir / "out" / "reviewed" / "retry.json").read_text(encoding="utf-8"))
    # A field the call does not give, and other text in braces, stay as written.
    assert out == {"module": "retry", "lines": ["retry: src/retry.py"], "note": "{params.missing} {x}"}
    played = json.loads((report.run_dir / "out" / "tally" / "bank.json").read_text(encoding="utf-8"))
    assert played["module"] == "bank"
