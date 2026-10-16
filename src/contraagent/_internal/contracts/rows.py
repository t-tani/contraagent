"""Rows: an output that grows one line at a time.

A rows output is a JSON Lines file whose every line is one instance of a pydantic
model, a **row**. An agent can add each row to the file as soon as it has it, so the
rows it wrote are there even when its launch is stopped (`agent_task(partial_on=)`).

* `Rows[Row]`      the value: a `list` of rows, what the flow receives and validators see
* `RowsFile[Row]`  the schema of the whole file, a `RootModel`, so a contract holds it
                   where it holds any other model (`OutputContract.schema`)

`contract.parse_rows` checks a file's text line by line, each error naming its line.
"""

from __future__ import annotations

import json
import typing
from typing import Any

from pydantic import BaseModel, GetCoreSchemaHandler, RootModel
from pydantic_core import CoreSchema, core_schema

from contraagent._internal.runs.files import write_document


class Rows[Row: BaseModel](list[Row]):
    """The output of an agent task declared `output=Rows[Finding]`: a JSON Lines file, each
    line one `Finding`. As a value it is a `list` of the models, in the file's order: what
    the flow receives, what validators are given, and what a task it is passed to gets (a
    list of JSON objects in a call file, a list of models in a Python task). A Python task
    that returns one is annotated `-> Rows[Finding]` and returns `Rows([...])`."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        args = typing.get_args(source)
        item = args[0] if args else Any
        return core_schema.no_info_after_validator_function(cls, handler(list[item]))


class RowsFile[Row: BaseModel](RootModel[Rows[Row]]):
    """The schema of a rows output's whole file (`Rows[Row]`): the rows as one value. Its
    text is JSON Lines, read by `parse_rows` and written by `rows_text`."""

    @classmethod
    def row(cls) -> type[BaseModel]:
        """The model of one line."""
        return cls.__pydantic_generic_metadata__["args"][0]


def rows_model(output: Any) -> type[BaseModel] | None:
    """The row model of an `output` declared `Rows[Row]`; None for any other output.
    `TypeError` for `Rows` with no model, or with something else than a pydantic model."""
    if output is Rows:
        raise TypeError("Rows takes the model of one line: Rows[Finding]")
    if typing.get_origin(output) is not Rows:
        return None
    (row,) = typing.get_args(output)
    if not (isinstance(row, type) and issubclass(row, BaseModel)):
        raise TypeError(f"Rows takes a pydantic model, the model of one line, not {row!r}")
    return row


def rows_file(row: type[BaseModel]) -> type[RowsFile[Any]]:
    """The schema of a file of `row`s."""
    return RowsFile[row]  # pyright: ignore[reportInvalidTypeArguments]


def is_rows(schema: Any) -> bool:
    """Whether `schema` is a rows output's (`RowsFile`)."""
    return isinstance(schema, type) and issubclass(schema, RowsFile)


def row_of(schema: type[BaseModel]) -> type[BaseModel]:
    """The model a schema's file is checked by line by line: a rows file's row; else the
    schema itself. It is what the call file names (`SchemaRef`) and the hook imports."""
    return schema.row() if is_rows(schema) else schema  # pyright: ignore[reportAttributeAccessIssue]


def rows_text(rows: Any) -> str:
    """Rows as their file holds them: one JSON object per line, each line ended."""
    out = []
    for r in rows:
        out.append(r.model_dump_json() if isinstance(r, BaseModel) else json.dumps(r, ensure_ascii=False))
    return "".join(line + "\n" for line in out)


def drop_unfinished(path: Any) -> bool:
    """Cut off the last line of a rows file when it is unfinished: it has no newline after
    it and is not valid JSON, so it is the row being written when the launch was stopped.
    True when a line was cut off."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not text or text.endswith("\n"):
        return False
    head, _, last = text.rpartition("\n")
    try:
        json.loads(last)
    except ValueError:
        write_document(path, head + "\n" if head else "")
        return True
    return False
