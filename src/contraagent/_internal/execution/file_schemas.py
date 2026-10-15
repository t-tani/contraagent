"""The JSON Schemas of the files contraagent reads and writes: the pipeline config file, and
the records of a run directory of format `layout.FORMAT`. They are installed with the
documentation (`contraagent/docs/schemas/`) and written again by

    uv run python -m contraagent._internal.execution.file_schemas

(a test fails while one is stale). A log's schema is that of one of its lines.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from contraagent._internal import docs
from contraagent._internal.dispatch.records import RestEvent
from contraagent._internal.execution.schemas import Cursor, DeferredRow, FlowCallRow, JournalRow, LaunchRow, PlanRow, RunInfo
from contraagent._internal.routing.config_schema import config_schema
from contraagent._internal.runs import layout

#: Where the schemas are installed.
DIR = docs.DIR / "schemas"

DRAFT = "https://json-schema.org/draft/2020-12/schema"

#: Each record of a run directory, by its layout name, and the model of it (of one line, for a log).
RECORDS: dict[str, type[BaseModel]] = {
    layout.RUN_INFO: RunInfo,
    layout.JOURNAL: JournalRow,
    layout.LAUNCHES: LaunchRow,
    layout.PLAN: PlanRow,
    layout.FLOW_CALLS: FlowCallRow,
    layout.DEFERRED: DeferredRow,
    layout.RESTS: RestEvent,
    layout.CURSOR: Cursor,
}


def schema_name(file: str) -> str:
    """The schema file of `file` (`journal.jsonl` -> `journal.schema.json`)."""
    return f"{file.split('.', 1)[0]}.schema.json"


def _record(file: str, model: type[BaseModel]) -> dict:
    what = f"One line of `{file}`" if file.endswith(".jsonl") else f"`{file}`"
    schema = model.model_json_schema(by_alias=True, mode="serialization")
    return {
        "$schema": DRAFT,
        "$comment": f"{what} in a run directory of format {layout.FORMAT}.",
        **schema,
    }


def schemas() -> dict[str, dict]:
    """Every schema, by its file name in `DIR`."""
    out: dict[str, Callable[[], dict]] = {"pipeline.schema.json": config_schema}
    for file, model in RECORDS.items():
        out[schema_name(file)] = lambda file=file, model=model: _record(file, model)
    return {name: make() for name, make in sorted(out.items())}


def render(schema: dict) -> str:
    """A schema as its file holds it."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def write(into: Path = DIR) -> list[Path]:
    """Write every schema into `into`, and remove a `*.schema.json` there that is no longer one."""
    into.mkdir(parents=True, exist_ok=True)
    made = schemas()
    for stale in into.glob("*.schema.json"):
        if stale.name not in made:
            stale.unlink()
    paths = []
    for name, schema in made.items():
        path = into / name
        path.write_text(render(schema))
        paths.append(path)
    return paths


if __name__ == "__main__":
    for path in write(Path(sys.argv[1]) if len(sys.argv) > 1 else DIR):
        sys.stdout.write(f"{path}\n")
