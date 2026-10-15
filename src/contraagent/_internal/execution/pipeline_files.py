"""A pipeline's own files in its run, `contraagent.log` and `contraagent.save`, and its
own tables in the config the run was started with, `contraagent.pipeline_table`.

Flow code and Python tasks write what the pipeline itself wants to keep of a run into
the run's `pipeline/` folder (`layout.PIPELINE`): a pipeline log, `<name>.jsonl`, one
JSON line per `log(name, row)`, and a pipeline document, `<name>.json`, the whole value
of the last `save(name, value)`. A relay ships them to a hub with the rest of the run,
and a panel reads them back wherever the monitor reads runs (`RunRecords.log`,
`RunRecords.document`).

They act on the current run: the one a `Run` opened (`Pipeline.run` opens it around
the flow), and, in a Python task, the run its `PythonTaskRunner` runs it for, on
whichever thread the queue runs it. Called outside a run, they raise `NoCurrentRun`.
An agent task cannot call them: its coding agent runs in another process, which has no
current run.

`capturing()` keeps, beside the files, what `log` and `save` write in its context (a
recording keeps a Python task attempt's writes with it), and `write_captured` writes them
into a run again (a replay plays them back), as `log` and `save` write.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import BaseModel

from contraagent._internal.errors import ContraagentError
from contraagent._internal.routing.config import PipelineConfig
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import append_lines, write_document


class _Current(NamedTuple):
    """The current run: its directory, and the config it was started with (None: no file)."""

    dir: Path
    config: PipelineConfig | None


_current: ContextVar[_Current | None] = ContextVar("contraagent_current_run", default=None)


@dataclass
class Written:
    """What `log` and `save` wrote in a `capturing()` context: each log's lines (JSON text,
    one row each, in order) and each document's last text, by name."""

    logs: dict[str, list[str]] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)


_capture: ContextVar[Written | None] = ContextVar("contraagent_capture", default=None)


@contextlib.contextmanager
def capturing() -> Iterator[Written]:
    """Keep what `log` and `save` write in this context (they still write their files)."""
    written = Written()
    token = _capture.set(written)
    try:
        yield written
    finally:
        _capture.reset(token)


def write_captured(run_dir: str | Path, written: Written) -> None:
    """Write what `capturing()` kept into the run `run_dir`: each log's lines appended,
    each document replaced, as `log` and `save` write them."""
    for name, lines in written.logs.items():
        _append_log(Path(run_dir), name, lines)
    for name, text in written.documents.items():
        _save_document(Path(run_dir), name, text)


def _append_log(run_dir: Path, name: str, lines: list[str]) -> None:
    path = run_dir / layout.pipeline_log(name)
    path.parent.mkdir(exist_ok=True)
    append_lines(path, lines)


def _save_document(run_dir: Path, name: str, text: str) -> None:
    path = run_dir / layout.pipeline_document(name)
    path.parent.mkdir(exist_ok=True)
    write_document(path, text)


class NoCurrentRun(ContraagentError):
    """`contraagent.log`, `contraagent.save` or `contraagent.pipeline_table` was called
    outside a run: not in flow code `Pipeline.run` is running, nor in a Python task of it."""


@contextlib.contextmanager
def writing_into(run_dir: str | Path, config: PipelineConfig | None = None) -> Iterator[Path]:
    """Make `run_dir`, started with `config`, the current run of `log`, `save` and
    `pipeline_table` in this context, until it exits."""
    path = Path(run_dir)
    token = _current.set(_Current(path, config))
    try:
        yield path
    finally:
        _current.reset(token)


def _current_run(call: str) -> _Current:
    current = _current.get()
    if current is None:
        raise NoCurrentRun(
            f"contraagent.{call} is called outside a run: call it from the flow given to Pipeline.run, or from a Python task of it"
        )
    return current


def _run_dir(call: str) -> Path:
    return _current_run(call).dir


def pipeline_table(name: str) -> dict:
    """`[pipeline.<name>]` of the config the current run was started with: a pipeline
    table, the pipeline's own settings, as parsed (`PipelineConfig.table`). Empty when the
    file has none, or the run has no config file. NoCurrentRun outside a run."""
    config = _current_run("pipeline_table").config
    return config.table(name) if config is not None else {}


def _json(value: Any, what: str) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{what}: not a JSON value ({exc})") from exc


def log(name: str, row: Mapping[str, Any] | BaseModel) -> None:
    """Append `row`, a JSON object (a dict, or a pydantic model), as one line to the
    pipeline log `name` of the current run, `runs/<id>/pipeline/<name>.jsonl`.

    `name` is a plain name without a suffix (`"notes"`; ValueError otherwise). Lines are
    never rewritten; a resumed run appends to the same log. NoCurrentRun outside a run,
    TypeError for a row that is not a JSON object."""
    run_dir = _run_dir("log")
    layout.pipeline_log(name)
    if not isinstance(row, (Mapping, BaseModel)):
        raise TypeError(f"pipeline log {name!r}: a row is a JSON object (a dict or a pydantic model), not {type(row).__name__}")
    line = _json(row if isinstance(row, BaseModel) else dict(row), f"pipeline log {name!r}") + "\n"
    _append_log(run_dir, name, [line])
    captured = _capture.get()
    if captured is not None:
        captured.logs.setdefault(name, []).append(line)


def save(name: str, value: Any) -> None:
    """Write `value` (any JSON value, or a pydantic model) whole as the pipeline document
    `name` of the current run, `runs/<id>/pipeline/<name>.json`, replacing what it held
    (atomically: a reader sees the old document or the new one).

    `name` is a plain name without a suffix (`"summary"`; ValueError otherwise).
    NoCurrentRun outside a run, TypeError for a value that is not JSON."""
    run_dir = _run_dir("save")
    layout.pipeline_document(name)
    text = _json(value, f"pipeline document {name!r}")
    _save_document(run_dir, name, text)
    captured = _capture.get()
    if captured is not None:
        captured.documents[name] = text
