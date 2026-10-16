"""The layout of a run directory, `runs/<run-id>/`: the name of each run record.

It is the contract between the process that writes a run (`execution.Run`, the
runners, `contracts.record_contracts`, the call files) and every reader of it (a
`RunSource`, `JournalEstimates`, a relay). They name each record through this module,
so the layout is written down once; a record's name relative to the run directory
(`journal.jsonl`, `streams/<file>.stream.jsonl`) is its layout name.

Logs (one JSON object per line, appended, never rewritten; `files.append_lines`
writes them and `files.read_lines` reads complete lines only): `JOURNAL`, `LAUNCHES`,
`PLAN`, `FLOW_CALLS`, `DEFERRED`, `RESTS`, `SERVICES`, one transcript per task, `stream(key)`, and
the pipeline logs, `pipeline_log(name)`.

Documents (a whole JSON file, replaced atomically by `files.write_document`):
`RUN_INFO`, `CURSOR`, and one file per entry in the folders `CONTRACTS`, `DEFINITIONS`,
`CALLS`, `INFLIGHT` and `PIPELINE` (the pipeline documents, `pipeline_document(name)`).

A file of a task (its transcript, contract record, call file, in-flight marker) is named
by `file_name(key)`, one rule for every folder.

`PIPELINE` (`pipeline/`) holds the pipeline's own files, written by its flow code and
its Python tasks with `contraagent.log` (a pipeline log, `<name>.jsonl`) and
`contraagent.save` (a pipeline document, `<name>.json`); contraagent itself writes
nothing there.

`TRENDS` is the one document a reader writes: the monitor's digest of a finished
run for its trends (`monitor.trends`), made again from the logs whenever they
change (`RunSource.kept`, `RunSource.keep`). Nothing else reads it, and a relay does not
ship it.

`RUN_INFO` (`run.json`) also says which run this is across hosts: `run_uid`, an id
no other run has, kept when the run is resumed, and `host_id`, the host that
drives it (`CONTRAAGENT_HOST_ID`, else the host name). Its `cwd` is the directory a
relative path in a contract record is relative to (`file_path`), and its `format` the run
format of the whole run directory (`FORMAT`, `format_of`).
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterable, Mapping
from pathlib import Path

from contraagent._internal.runs.names import is_plain, safe_chars

#: The run format of a run directory this release writes, as `run.json` records it (`format`):
#: this layout and the schemas of its records (`contraagent/docs/schemas/`). It goes up
#: by one when a record changes in a way a reader of the run format before cannot read.
FORMAT = 1

#: The run formats this release reads; a run directory of another is not resumed.
FORMATS = (1,)

RUN_INFO = "run.json"
JOURNAL = "journal.jsonl"
LAUNCHES = "launches.jsonl"
PLAN = "plan.jsonl"
FLOW_CALLS = "flow_calls.jsonl"
DEFERRED = "deferred.jsonl"
RESTS = "rests.jsonl"
SERVICES = "services.jsonl"
CURSOR = "cursor.json"
TRENDS = "trends.json"
STREAMS = "streams"
CONTRACTS = "contracts"
DEFINITIONS = "definitions"
CALLS = "calls"
INFLIGHT = "inflight"
PIPELINE = "pipeline"

#: The folders whose `*.json` files are documents, one per entry.
FOLDERS = (CONTRACTS, DEFINITIONS, CALLS, INFLIGHT, PIPELINE)

#: The suffix of a task's transcript in `STREAMS`.
STREAM_SUFFIX = ".stream.jsonl"

#: The append-only logs every run has, by name (a task's transcript is `stream(key)`).
LOGS = (JOURNAL, LAUNCHES, PLAN, FLOW_CALLS, DEFERRED, RESTS, SERVICES)

#: Every entry of a run directory contraagent writes, and the pipeline's own folder: all
#: of it but `out/`, the tasks' outputs.
OWN = (RUN_INFO, *LOGS, CURSOR, TRENDS, STREAMS, CONTRACTS, DEFINITIONS, CALLS, INFLIGHT, PIPELINE)

#: Names the host that drives a run in `run.json` (`host_id`); unset, the host name.
HOST_ID_ENV = "CONTRAAGENT_HOST_ID"


def file_name(key: str) -> str:
    """The name task `key`'s files take, without a suffix: `key` with every character
    but a letter, a digit, `-`, `_` and `.` turned into `_`, as are a leading `.` and each
    `..`. Two keys can share a name (`a:b`, `a_b`); a run's keys rarely do."""
    return safe_chars(key)


def stream(key: str) -> str:
    """The transcript log of task `key`, relative to the run directory."""
    return f"{STREAMS}/{file_name(key)}{STREAM_SUFFIX}"


def stream_name(log: str) -> str | None:
    """The `file_name` of the task whose transcript `log` is (a layout name); None for
    any other log."""
    if log.startswith(STREAMS + "/") and log.endswith(STREAM_SUFFIX):
        return log[len(STREAMS) + 1 : -len(STREAM_SUFFIX)]
    return None


def task_entry(folder: str, key: str) -> str:
    """The document of task `key` in `folder` (`contracts/<file_name(key)>.json`), relative
    to the run directory."""
    return entry(folder, file_name(key))


def entry(folder: str, name: str) -> str:
    """The document `name` in `folder` (`contracts/<name>.json`), relative to the run directory."""
    return f"{folder}/{name}.json"


def pipeline_name(name: str) -> str:
    """`name` itself when it names a pipeline log or document: a plain file name (not
    empty, no `/`, `\\` or control character, no leading `.`, no `..`) without the
    `.json` or `.jsonl` its file takes. ValueError naming the fault otherwise."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"a pipeline log or document needs a name, not {name!r}")
    if not is_plain(name):
        raise ValueError(f"{name!r} is not a plain name for a pipeline log or document (no '/', no leading '.', no '..')")
    if name.endswith((".json", ".jsonl")):
        raise ValueError(f"{name!r}: name a pipeline log or document without its suffix ({name.rsplit('.', 1)[0]!r})")
    return name


def pipeline_log(name: str) -> str:
    """The pipeline log `name`, `pipeline/<name>.jsonl`, relative to the run directory."""
    return f"{PIPELINE}/{pipeline_name(name)}.jsonl"


def pipeline_document(name: str) -> str:
    """The pipeline document `name`, `pipeline/<name>.json`, relative to the run directory."""
    return entry(PIPELINE, pipeline_name(name))


def format_of(info: Mapping) -> int | None:
    """The run format of the run whose `run.json` holds `info`: its `format`, 1 when it records
    none; None when `format` is not a positive whole number."""
    value = info.get("format", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def host_id() -> str:
    """This host's id for `run.json`: `CONTRAAGENT_HOST_ID`, else the host name."""
    return os.environ.get(HOST_ID_ENV) or socket.gethostname()


def file_path(path: str, cwd: str | os.PathLike[str] | None) -> Path:
    """Where a file a contract record names (`outputs[].path`, `inputs[].path`) is, on the
    host that drove the run: an absolute path as it is, a relative one under the run's
    working directory `cwd` (`run.json`'s `cwd`; the current directory when unknown)."""
    p = Path(path)
    return p if p.is_absolute() or not cwd else Path(cwd) / p


def contract_paths(records: Iterable[str]) -> list[str]:
    """The paths of the files the contract records (`CONTRACTS`' documents, as text) name,
    outputs and inputs, each once, in order; a record that does not parse is skipped."""
    out: dict[str, None] = {}
    for text in records:
        try:
            rec = json.loads(text)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        for spec in [*rec.get("outputs", []), *rec.get("inputs", [])]:
            if isinstance(spec, dict) and isinstance(spec.get("path"), str) and spec["path"]:
                out[spec["path"]] = None
    return list(out)
