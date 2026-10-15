"""The layout of a run directory, `runs/<run-id>/`.

It is the contract between the process that writes a run (`execution.Run`, the
runners, `contracts.write_contract_record`, the call files) and every reader of
it (the monitor's `DirectorySource`, `JournalEstimates`). They name each file
through this module, so the layout is written down once.

Append-only logs (one JSON object per line, never rewritten; a reader keeps a
line offset): `JOURNAL`, `LAUNCHES`, `PLAN`, `FLOW_CALLS`, `DEFERRED`, `RESTS`, one transcript
per task, `stream(key)`, and the pipeline logs, `pipeline_log(name)`.

Documents (a whole JSON file, replaced atomically): `RUN_INFO`, `CURSOR`, and
one file per entry in the folders `CONTRACTS`, `DEFINITIONS`, `CALLS`,
`INFLIGHT` and `PIPELINE` (the pipeline documents, `pipeline_document(name)`).
Every writer of a document goes through `write_document`.

`PIPELINE` (`pipeline/`) holds the pipeline's own files, written by its flow code and
its Python tasks with `contraagent.log` (a pipeline log, `<name>.jsonl`) and
`contraagent.save` (a pipeline document, `<name>.json`); contraagent itself writes
nothing there.

`TRENDS` is the one document a reader writes: the monitor's digest of a finished
run for its trends (`monitor.trends`), made again from the logs whenever they
change. Nothing else reads it, and a relay does not ship it.

`RUN_INFO` (`run.json`) also says which run this is across hosts: `run_uid`, an id
no other run has, kept when the run is resumed, and `host_id`, the host that
drives it (`CONTRAAGENT_HOST_ID`, else the host name).
"""

from __future__ import annotations

import os
import secrets
import socket
from pathlib import Path

RUN_INFO = "run.json"
JOURNAL = "journal.jsonl"
LAUNCHES = "launches.jsonl"
PLAN = "plan.jsonl"
FLOW_CALLS = "flow_calls.jsonl"
DEFERRED = "deferred.jsonl"
RESTS = "rests.jsonl"
CURSOR = "cursor.json"
TRENDS = "trends.json"
STREAMS = "streams"
CONTRACTS = "contracts"
DEFINITIONS = "definitions"
CALLS = "calls"
INFLIGHT = "inflight"
PIPELINE = "pipeline"

#: The append-only logs every run has, by name (a task's transcript is `stream(key)`).
LOGS = (JOURNAL, LAUNCHES, PLAN, FLOW_CALLS, DEFERRED, RESTS)

#: Names the host that drives a run in `run.json` (`host_id`); unset, the host name.
HOST_ID_ENV = "CONTRAAGENT_HOST_ID"


def stream(key: str) -> str:
    """The transcript log of task `key`, relative to the run directory."""
    return f"{STREAMS}/{key}.stream.jsonl"


def entry(folder: str, name: str) -> str:
    """The document `name` in `folder` (`contracts/<name>.json`), relative to the run directory."""
    return f"{folder}/{name}.json"


def pipeline_name(name: str) -> str:
    """`name` itself when it names a pipeline log or document: a plain file name (not
    empty, no `/`, `\\` or control character, no leading `.`, no `..`) without the
    `.json` or `.jsonl` its file takes. ValueError naming the fault otherwise."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"a pipeline log or document needs a name, not {name!r}")
    if name.startswith(".") or ".." in name or any(c in name for c in "/\\\0") or any(ord(c) < 32 or ord(c) == 127 for c in name):
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


def host_id() -> str:
    """This host's id for `run.json`: `CONTRAAGENT_HOST_ID`, else the host name."""
    return os.environ.get(HOST_ID_ENV) or socket.gethostname()


def write_document(path: str | os.PathLike[str], text: str) -> Path:
    """Write the document `path` whole: `text` goes to a temporary file in the same
    folder, `.<name>.<pid>.<random>.tmp` (not matched by `*.json`), which then
    replaces `path`. A reader sees the old document or the new one, never a part;
    of writers racing on one document, the last replace wins. Returns `path`."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path
