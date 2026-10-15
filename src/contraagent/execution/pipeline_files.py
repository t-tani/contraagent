"""A pipeline's own files in its run: `contraagent.log` and `contraagent.save`.

Flow code and Python tasks write what the pipeline itself wants to keep of a run into
the run's `pipeline/` folder (`rundir.PIPELINE`): a pipeline log, `<name>.jsonl`, one
JSON line per `log(name, row)`, and a pipeline document, `<name>.json`, the whole value
of the last `save(name, value)`. A relay ships them to a hub with the rest of the run,
and a panel reads them back wherever the monitor reads runs (`RunRecords.log`,
`RunRecords.document`).

They write into the current run: the one a `Run` opened (`Pipeline.run` opens it around
the flow), and, in a Python task, the run its `PythonTaskRunner` runs it for, on
whichever thread the queue runs it. Called outside a run, they raise `NoCurrentRun`.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contraagent import rundir
from contraagent.errors import ContraagentError

_current: ContextVar[Path | None] = ContextVar("contraagent_run_dir", default=None)
_append = threading.Lock()


class NoCurrentRun(ContraagentError):
    """`contraagent.log` or `contraagent.save` was called outside a run: not in flow code
    `Pipeline.run` is running, nor in a Python task of it."""


@contextlib.contextmanager
def writing_into(run_dir: str | Path) -> Iterator[Path]:
    """Make `run_dir` the current run of `log` and `save` in this context, until it exits."""
    path = Path(run_dir)
    token = _current.set(path)
    try:
        yield path
    finally:
        _current.reset(token)


def _run_dir(call: str) -> Path:
    path = _current.get()
    if path is None:
        raise NoCurrentRun(
            f"contraagent.{call} is called outside a run: call it from the flow given to Pipeline.run, or from a Python task of it"
        )
    return path


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
    path = _run_dir("log") / rundir.pipeline_log(name)
    if not isinstance(row, (Mapping, BaseModel)):
        raise TypeError(f"pipeline log {name!r}: a row is a JSON object (a dict or a pydantic model), not {type(row).__name__}")
    line = _json(row if isinstance(row, BaseModel) else dict(row), f"pipeline log {name!r}") + "\n"
    path.parent.mkdir(exist_ok=True)
    with _append, open(path, "a", encoding="utf-8") as f:
        f.write(line)


def save(name: str, value: Any) -> None:
    """Write `value` (any JSON value, or a pydantic model) whole as the pipeline document
    `name` of the current run, `runs/<id>/pipeline/<name>.json`, replacing what it held
    (atomically: a reader sees the old document or the new one).

    `name` is a plain name without a suffix (`"summary"`; ValueError otherwise).
    NoCurrentRun outside a run, TypeError for a value that is not JSON."""
    path = _run_dir("save") / rundir.pipeline_document(name)
    text = _json(value, f"pipeline document {name!r}")
    path.parent.mkdir(exist_ok=True)
    rundir.write_document(path, text)
