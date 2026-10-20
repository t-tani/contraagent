"""A Python task's arguments are checked and converted against its parameters' annotations."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent


class Item(BaseModel):
    name: str
    size: int


class Opaque:
    """A class pydantic has no JSON Schema for."""


seen: dict[str, Any] = {}


@python_task
def take_item(item: Item) -> str:
    seen["item"] = item
    return item.name


@python_task
def take_items(items: list[Item]) -> int:
    seen["items"] = items
    return sum(i.size for i in items)


@python_task
def take_count(count: int, label) -> str:
    seen["count"], seen["label"] = count, label
    return f"{label}{count}"


@python_task
def take_text(text: str, item: Item) -> str:
    seen["text"], seen["from_task"] = text, item
    return text


@python_task
def make_item(unit: str) -> Item:
    return Item(name=unit, size=3)


def run(tmp_path, flow, agent: StubAgent | None = None, **kwargs):
    seen.clear()
    backends = agent.backends() if agent is not None else None
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, backends=backends, log=lambda line: None)
    return pipeline.run(flow, **kwargs)


def test_a_dict_given_to_a_model_parameter_becomes_the_model(tmp_path):
    report = run(tmp_path, lambda: take_item(item={"name": "a", "size": 1}))  # pyright: ignore[reportArgumentType]
    assert report.ok, report.failed
    assert isinstance(seen["item"], Item) and seen["item"] == Item(name="a", size=1)


def test_a_list_of_dicts_given_to_a_list_of_models_becomes_a_list_of_models(tmp_path):
    report = run(tmp_path, lambda: take_items(items=[{"name": "a", "size": 1}, Item(name="b", size=2)]))  # pyright: ignore[reportArgumentType]
    assert report.ok, report.failed
    assert [type(i) for i in seen["items"]] == [Item, Item] and report.results["python:take_items"].ok


def test_an_argument_is_converted_and_an_unannotated_one_passes_as_json(tmp_path):
    label = ("not", "checked")
    report = run(tmp_path, lambda: take_count(count="3", label=label))  # pyright: ignore[reportArgumentType]
    assert report.ok and seen["count"] == 3 and seen["label"] == ["not", "checked"]  # copied as JSON at the call


def test_a_mismatch_refuses_the_task_before_the_function_runs(tmp_path):
    report = run(tmp_path, lambda: take_items(items=[{"zzz": "x"}]))  # pyright: ignore[reportArgumentType]
    assert not report.ok and "items" not in seen
    [failed] = report.failed
    assert failed.stop == "invalid_input" and failed.rounds == 0
    assert failed.reason.startswith("invalid input: parameter items[0].name: Field required; parameter items[0].size: Field required")
    row = json.loads((report.run_dir / "journal.jsonl").read_text().splitlines()[-1])
    assert row["stop"] == "invalid_input" and row["attempt"] == 0  # one attempt: an input is never retried


def test_a_mismatch_names_each_parameter(tmp_path):
    report = run(tmp_path, lambda: take_count(count="many", label=1))  # pyright: ignore[reportArgumentType]
    [failed] = report.failed
    assert failed.reason == "invalid input: parameter count: Input should be a valid integer, unable to parse string as an integer"


def test_a_value_that_is_not_json_is_refused_at_the_call(tmp_path):
    with pytest.raises(TypeError, match="take_count\\(\\): label is a Opaque, which is not JSON"):
        run(tmp_path, lambda: take_count(count=1, label=Opaque()), run_id="instance")


def test_an_annotation_without_a_json_schema_is_refused_where_the_task_is_declared():
    def take_opaque(thing: Opaque) -> str:
        return type(thing).__name__

    with pytest.raises(TypeError, match="parameter thing is annotated .*Opaque.*, which has no JSON Schema"):
        python_task(take_opaque)


def test_outputs_of_other_tasks_count_as_their_values(tmp_path):
    new_plugin(tmp_path / "plugins" / "w")
    write = agent_task("write", plugin=tmp_path / "plugins" / "w", output=str, max_turns=5, timeout_s=60)
    agent = StubAgent({"write": "# text\n"})

    async def flow():
        await take_text(text=await write("u"), item=await make_item("u"))

    report = run(tmp_path, flow, agent)
    assert report.ok, report.failed
    assert seen["text"] == "# text\n" and seen["from_task"] == Item(name="u", size=3)


@python_task
def take_later(later: Later) -> int:
    seen["later"] = later
    return later.v


class Later(BaseModel):
    """Defined after the task that takes it: its annotation resolves at the first call."""

    v: int


def test_a_type_defined_after_the_function_resolves_at_the_first_call(tmp_path):
    assert run(tmp_path, lambda: take_later(later={"v": "2"})).ok  # pyright: ignore[reportArgumentType]
    assert seen["later"] == Later(v=2)


def test_a_stub_run_refuses_what_a_run_refuses(tmp_path):
    seen.clear()
    pipeline = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=StubAgent(), log=lambda line: None)
    report = pipeline.run(lambda: take_item(item={"name": "a"}))  # pyright: ignore[reportArgumentType]
    [failed] = report.failed
    assert failed.stop == "invalid_input" and failed.reason == "invalid input: parameter item.size: Field required"
