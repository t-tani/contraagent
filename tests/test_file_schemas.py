"""The JSON Schemas of the files contraagent reads and writes (`contraagent/docs/schemas/`):
current, and true of what a run writes and of the reference config."""

from __future__ import annotations

import asyncio
import json
import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

from contraagent import Pipeline, PipelineConfig, agent_task, python_task
from contraagent._internal import docs
from contraagent._internal.execution import file_schemas
from contraagent._internal.execution.schemas import RunInfo
from contraagent._internal.routing import config as config_module
from contraagent._internal.routing.config_schema import DefaultsTable, PipelineFile, TaskTable
from contraagent._internal.runs import layout
from contraagent.testing import StubAgent, fails, writes_example

FIXTURE = Path(__file__).parent / "fixtures" / "runs" / "v1" / "review"
REGENERATE = "uv run python -m contraagent._internal.execution.file_schemas"


def test_the_committed_schemas_are_current():
    made = {name: file_schemas.render(schema) for name, schema in file_schemas.schemas().items()}
    committed = {p.name: p.read_text() for p in file_schemas.DIR.glob("*.schema.json")}
    assert committed == made, f"the file schemas are stale: run `{REGENERATE}`"


def test_every_log_and_the_run_documents_have_a_schema():
    assert set(file_schemas.RECORDS) == {*layout.LOGS, layout.RUN_INFO, layout.CURSOR}


def _aliases(model: type[BaseModel]) -> set[str]:
    return {f.alias or name for name, f in model.model_fields.items()}


def test_the_config_schema_names_the_keys_the_loader_accepts():
    assert _aliases(PipelineFile) == set(config_module.TABLES)
    assert _aliases(DefaultsTable) == {*config_module.DEFAULTS_KEYS, "_comment"}
    assert _aliases(TaskTable) == {*config_module.TASK_KEYS, "_comment"}


def test_the_reference_config_matches_its_schema():
    path = docs.DIR / "examples" / "reference" / "pipeline.toml"
    PipelineFile.model_validate(tomllib.loads(path.read_text()))
    assert path.read_text().startswith("#:schema ../../schemas/pipeline.schema.json\n")


@pytest.mark.parametrize("bad", [{"defaults": {"max_passes": 0}}, {"tasks": {"k": {"timeout_s": True}}}, {"default": {}}])
def test_the_config_schema_refuses_what_the_loader_refuses(bad):
    with pytest.raises(ValueError):
        PipelineFile.model_validate(bad)


def _check_run(run_dir: Path) -> None:
    """Every record of `run_dir` holds to its model; run.json names only fields it knows."""
    for name, model in file_schemas.RECORDS.items():
        path = run_dir / name
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines()] if name.endswith(".jsonl") else [json.loads(path.read_text())]
        for row in rows:
            model.model_validate(row)
    info = json.loads((run_dir / layout.RUN_INFO).read_text())
    assert set(info) <= _aliases(RunInfo)


def test_the_format_fixture_holds_to_the_schemas():
    _check_run(FIXTURE)


class Verdict(BaseModel):
    ok: bool


review = agent_task("check", instructions="Check the unit.", output=Verdict, max_turns=5, timeout_s=60, retries=0)


@python_task
def double(unit: str) -> str:
    return unit * 2


async def _flow(units: list[str]):
    await asyncio.gather(*[double(u) for u in units])
    for unit in units:
        try:
            await review(unit)
        except Exception:
            pass


def test_what_a_run_writes_holds_to_the_schemas(tmp_path):
    stub = StubAgent({"check-b": fails()}, default=writes_example())
    report = Pipeline(PipelineConfig({}), runs_dir=tmp_path / "runs", cwd=tmp_path, stub=stub).run(_flow, units=["a", "b"])
    assert (report.run_dir / layout.LAUNCHES).read_text()
    _check_run(report.run_dir)
