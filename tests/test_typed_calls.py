"""Typed task calls: an agent task is called with an instance of its params model, a
Python task as its function. What a type checker finds is in `tests/typing/public_types.py`;
here, what the run refuses and what the agent is given."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

import pytest
from pydantic import BaseModel, Field

from contraagent import Pipeline, agent_task, python_task
from contraagent.backends import CallFile
from contraagent.plugins import new_plugin
from contraagent.testing import StubAgent, writes_example

if TYPE_CHECKING:
    from decimal import Decimal


class Triage(BaseModel):
    severity: int


class FindingsParams(BaseModel):
    triage: Triage
    depth: int = Field(default=1, ge=1, description="how far to follow a call")
    topics: list[str] = Field(default=[], description="the topics the findings are about")


class LaneParams(FindingsParams):
    lane: str


class Other(BaseModel):
    depth: int


class Findings(BaseModel):
    count: int


class Opaque:
    """A class pydantic has no JSON Schema for."""


findings = agent_task("findings", params=FindingsParams, output=Findings, instructions="List the findings.", max_turns=5, timeout_s=60)
tidy = agent_task("tidy", instructions="Remove the trailing spaces.", max_turns=5, timeout_s=60)


def run(tmp_path, flow, *, run_id: str | None = None):
    stub = StubAgent(default=writes_example())
    pipeline = Pipeline(None, runs_dir=tmp_path / "runs", backends=stub.backends(), cwd=tmp_path, log=lambda line: None)
    report = pipeline.run(flow, run_id=run_id)
    return report, stub


def call_file(report, key: str) -> CallFile:
    return CallFile.read(report.run_dir / "calls" / f"{key}.json")


def raised(flow, tmp_path) -> str:
    """The message of the TypeError the flow raised at its task call."""
    with pytest.raises(TypeError) as caught:
        run(tmp_path, flow, run_id="refused")
    return str(caught.value)


def test_the_call_file_holds_the_fields_by_name_and_the_models_json_schema(tmp_path):
    report, _ = run(tmp_path, lambda: findings("alpha", FindingsParams(triage=Triage(severity=2), topics=["auth"])))
    assert report.ok, report.failed
    call = call_file(report, "findings-alpha")
    assert call.params == {"triage": {"severity": 2}, "depth": 1, "topics": ["auth"]}  # flat, the defaults filled in
    schema = call.params_json_schema
    assert schema == FindingsParams.model_json_schema()
    assert schema["properties"]["depth"] == {
        "default": 1,
        "description": "how far to follow a call",
        "minimum": 1,
        "title": "Depth",
        "type": "integer",
    }
    assert schema["required"] == ["triage"]
    raw = json.loads((report.run_dir / "calls" / "findings-alpha.json").read_text(encoding="utf-8"))
    assert list(raw)[:7] == ["version", "run", "key", "kind", "unit", "params", "params_json_schema"]


def test_a_task_without_a_params_model_takes_none_and_its_schema_has_no_properties(tmp_path):
    report, _ = run(tmp_path, lambda: [tidy("alpha"), tidy()])
    assert report.ok, report.failed
    call = call_file(report, "tidy-alpha")
    assert call.params == {}
    assert call.params_json_schema == {"type": "object", "properties": {}}
    assert call_file(report, "tidy").unit == ""


def test_the_call_prompt_says_where_each_parameter_is_described(tmp_path):
    _, stub = run(tmp_path, lambda: findings("alpha", FindingsParams(triage=Triage(severity=2))))
    [launch] = stub.launches
    assert "`params_json_schema` says what each parameter is" in launch.launch.prompt


def test_a_light_launch_has_the_params_json_schema_in_its_prompt(tmp_path):
    judge = agent_task(
        "judge", params=FindingsParams, output=Findings, instructions="Judge.", output_from="message", tools=(), max_turns=2, timeout_s=60
    )
    _, stub = run(tmp_path, lambda: judge("alpha", FindingsParams(triage=Triage(severity=2))))
    [launch] = stub.launches
    assert "What each parameter is, as a JSON Schema:" in launch.launch.prompt
    assert '"description": "how far to follow a call"' in launch.launch.prompt


def test_an_instance_of_a_subclass_or_of_another_model_is_refused(tmp_path):
    message = raised(lambda: findings("a", LaneParams(triage=Triage(severity=1), lane="py")), tmp_path)
    assert "params is a LaneParams, a subclass of FindingsParams; give a FindingsParams itself" in message
    message = raised(lambda: findings("a", Other(depth=1)), tmp_path)
    assert "params is Other, and this task takes a FindingsParams: findings(unit, FindingsParams(...))" in message


def test_keyword_params_are_refused_with_the_form_to_write(tmp_path):
    message = raised(lambda: findings("a", triage={"severity": 1}), tmp_path)
    assert "triage=: an agent task takes its params as one instance of its params model" in message
    assert "findings(unit, FindingsParams(...))" in message
    message = raised(lambda: tidy("a", path="x"), tmp_path)
    assert "path=: this task declares no params model, so it takes no params" in message
    message = raised(lambda: findings("a", FindingsParams(triage=Triage(severity=1)), key="k"), tmp_path)
    assert "key= is a call option" in message and "findings.options(key=...)" in message


def test_params_left_out_or_given_to_a_task_without_a_model_are_refused(tmp_path):
    assert "findings(...) takes its params, an instance of FindingsParams" in raised(lambda: findings("a"), tmp_path)
    assert "this task declares no params model" in raised(lambda: tidy("a", FindingsParams(triage=Triage(severity=1))), tmp_path)
    assert "the unit is a string, not 3" in raised(lambda: tidy(3), tmp_path)


def test_a_value_set_after_the_instance_was_made_is_checked_again(tmp_path):
    params = FindingsParams(triage=Triage(severity=1))
    params.depth = 0  # pydantic does not check an assignment unless the model asks it to
    assert "params do not validate under FindingsParams: depth: Input should be greater than or equal to 1" in raised(
        lambda: findings("a", params), tmp_path
    )
    params = FindingsParams(triage=Triage(severity=1))
    params.triage.severity = "high"  # type: ignore[assignment]
    assert "params hold a value that is not JSON or not of its field's type" in raised(lambda: findings("a", params), tmp_path)


def test_an_annotated_output_is_a_text_output_only():
    note = agent_task("note", output=Annotated[str, Field(examples=["# a\n"])], instructions="Write.", max_turns=2, timeout_s=60)
    assert note.output_format == "text"
    with pytest.raises(TypeError, match=r"an Annotated output is a text output with an example, Annotated\[str"):
        agent_task("count", output=Annotated[int, Field(examples=[3])], instructions="Count.", max_turns=2, timeout_s=60)


def test_a_claim_names_a_field_of_the_params_model_or_a_parameter_of_the_function():
    agent_task("merge", params=FindingsParams, claims=["topic:{params.topics}"], instructions="Merge.")
    with pytest.raises(ValueError, match=r"names params.topic, and its params are depth, topics, triage"):
        agent_task("merge", params=FindingsParams, claims=["topic:{params.topic}"], instructions="Merge.")
    with pytest.raises(ValueError, match=r"names params.topic, and it takes no params"):
        agent_task("merge", claims=["topic:{params.topic}"], instructions="Merge.")
    with pytest.raises(ValueError, match=r"names params.unit, and its params are text"):

        @python_task(claims=["{params.unit}"])
        def count(unit: str, text: str) -> int:
            return len(text)


def test_a_python_tasks_unit_is_its_parameter_named_unit(tmp_path):
    @python_task(kind="measure")
    def measure(unit: str, *, text: str, scale: int = 1) -> int:
        return len(text) * scale + len(unit)

    @python_task
    def total(counts: list[int]) -> int:
        return sum(counts)

    async def flow():
        one = await measure("ab", text="xyz")
        two = await measure(unit="c", text="x", scale=2)
        return await total([one, two])

    report, _ = run(tmp_path, flow)
    assert report.ok, report.failed
    assert report.value == 5 + 3
    assert measure.kind == "measure"
    assert sorted(report.results) == ["python:measure-ab", "python:measure-c", "python:total"]


def test_a_unit_given_to_a_function_without_a_unit_parameter_says_how_to_take_it(tmp_path):
    @python_task
    def count(text: str) -> int:
        return len(text)

    message = raised(lambda: count("alpha", text="x"), tmp_path)  # type: ignore[call-arg]
    assert "a Python task is given its unit through a parameter named unit (def f(unit: str, ...))" in message


def test_a_python_tasks_parameters_are_named_and_json():
    with pytest.raises(TypeError, match="parameter text is positional-only"):

        @python_task
        def positional(text: str, /) -> int:
            return 0

    with pytest.raises(TypeError, match=r"\*texts: a Python task's params are named"):

        @python_task
        def many(*texts: str) -> int:
            return 0

    with pytest.raises(TypeError, match=r"\*\*fields: a Python task's params are named"):

        @python_task
        def keywords(**fields: str) -> int:
            return 0

    with pytest.raises(TypeError, match="parameter thing is annotated .*Opaque.*, which has no JSON Schema"):

        @python_task
        def opaque(thing: Opaque) -> int:
            return 0


def test_an_annotation_imported_for_the_type_checker_only_is_named_at_the_first_call(tmp_path):
    @python_task
    def price(unit: str, amount: Decimal) -> str:
        return str(amount)

    message = raised(lambda: price("a", amount=1), tmp_path)  # type: ignore[arg-type]
    assert "names Decimal, which is not defined when the task is called" in message
    assert "not under `if TYPE_CHECKING:` only" in message


def test_each_implementation_takes_the_steps_params_model(tmp_path):
    root = tmp_path / "plugins"

    for name in ("fast", "deep"):
        new_plugin(root / name)
    review = agent_task(
        "review",
        params=FindingsParams,
        output=Findings,
        implementations={"fast": root / "fast", "deep": root / "deep"},
        max_turns=2,
        timeout_s=60,
    )
    report, _ = run(tmp_path, lambda: review["deep"]("alpha", FindingsParams(triage=Triage(severity=3))))
    assert report.ok, report.failed
    assert call_file(report, "review-deep-alpha").params == {"triage": {"severity": 3}, "depth": 1, "topics": []}
    assert "params is Other" in raised(lambda: review["fast"]("alpha", Other(depth=1)), tmp_path)
