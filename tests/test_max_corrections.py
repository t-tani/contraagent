"""A kind's correction rounds (`max_corrections`): declared, set in `[tasks.<kind>]` or
`[defaults]`, checked, and recorded beside the rounds a task took."""

import json

import pytest
from pydantic import BaseModel

from contraagent import ConfigError, Pipeline, PipelineConfig, agent_task
from contraagent.testing import StubAgent


class Count(BaseModel):
    n: int


def count(max_corrections: int | None = None):
    return agent_task("count", instructions="Count.", output=Count, max_corrections=max_corrections, max_turns=5, timeout_s=60, retries=0)


def run(tmp_path, task, config: dict | None = None):
    stub = StubAgent({"count": lambda launch: {"n": "many"}})  # never passes its checks
    pipeline = Pipeline(PipelineConfig(config or {}), backends=stub.backends(), runs_dir=tmp_path / "runs", cwd=tmp_path)
    report = pipeline.run(lambda: task("a"), run_id="r")
    (row,) = [json.loads(line) for line in (report.run_dir / "journal.jsonl").read_text().splitlines()]
    (launch,) = [json.loads(line) for line in (report.run_dir / "launches.jsonl").read_text().splitlines()]
    assert row["stop"] == "invalid_output"
    assert len([s for s in stub.launches if s.resumed]) == row["rounds"] - 1
    assert launch["max_corrections"] == row["max_corrections"]
    return row["rounds"], row["max_corrections"]


def test_three_correction_rounds_by_default(tmp_path):
    assert run(tmp_path, count()) == (4, 3)


def test_the_declaration_sets_them_and_the_task_table_outranks_it(tmp_path):
    assert run(tmp_path / "a", count(max_corrections=1)) == (2, 1)
    assert run(tmp_path / "b", count(max_corrections=1), {"tasks": {"count": {"max_corrections": 0}}}) == (1, 0)


def test_defaults_give_them_to_a_kind_that_gives_none(tmp_path):
    assert run(tmp_path / "a", count(), {"defaults": {"max_corrections": 2}}) == (3, 2)
    assert run(tmp_path / "b", count(max_corrections=1), {"defaults": {"max_corrections": 2}}) == (2, 1)


@pytest.mark.parametrize("value", [-1, 21, True, 1.5])
def test_a_value_out_of_range_is_refused(value):
    with pytest.raises(ConfigError, match="max_corrections"):
        count(max_corrections=value)
    errors: list[str] = []
    PipelineConfig({"tasks": {"count": {"max_corrections": value}}}).task_tables(errors)
    PipelineConfig({"defaults": {"max_corrections": value}}).defaults(errors)
    assert len(errors) == 2 and all("max_corrections" in e for e in errors)


def test_check_reports_a_value_out_of_range(tmp_path):
    config = PipelineConfig({"tasks": {"count": {"max_corrections": 50}}})
    report = Pipeline(config, backends=StubAgent().backends(), runs_dir=tmp_path, cwd=tmp_path).check(lambda: count()("a"))
    assert not report.ok
    assert any("[tasks.count].max_corrections = 50 is not a whole number from 0 to 20" in e for e in report.errors)
    assert "routing" in report.topics
