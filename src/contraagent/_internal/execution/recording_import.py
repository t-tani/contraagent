"""Recordings made from a run that was not recorded: `import_recording`.

A run with no `--record` still leaves, in its run directory, most of what a recording
holds: its journal (how each attempt ended, its fingerprint, the files its `changes=`
patterns saw change), its contract records (the paths of each task's outputs), its
launches (the facts of each launch), its transcripts and, under `out/` or wherever the
outputs were written, the outputs themselves. `import_recording` writes a recording from
them, in the layout `Recorder` writes (`recording`), so a replay plays it as it plays a
recorded one.

What it imports, per task, from the task's last journal row (a resumed run's `skipped`
rows left out):

* a task whose last attempt finished ok, or `partial`, is imported as one attempt: a
  replay plays it on the task's first attempt. The attempts that failed before it are not
  imported, since a run keeps none of their outputs; a replay does not wait or retry for
  them.
* an agent task: its output files as they are now, the whole final message of an
  unwrapped output (`<output>.message.txt`), and the files its `changes=` patterns saw
  created or modified, as they are now in the task's working directory (its `plan.jsonl`
  row's `cwd`, else the run's: `run.json` `cwd`), and the paths they saw deleted. The facts of the launch come from the journal row and
  the task's last row of `launches.jsonl`; the final message of a task whose output is
  its message (`output_from="message"`) is read back from its output file, since the
  runner writes the message there. Its transcript is imported when the journal holds one
  attempt of the task (the transcript is then that attempt's); a replay needs none.
* a Python task: how its call ended and its output file, which is its return value as the
  flow received it (a task that returns None has none). What its call wrote with
  `contraagent.log` and `contraagent.save` is not imported: the run's `pipeline/` holds every
  writer's rows together, not one call's. A replay that needs them runs the kind with
  `--execute`.

What it does not import, and why (`RecordingImport.unfinished`, `RecordingImport.not_imported`): a task
whose last attempt did not finish ok (a replay of it, with no recording, ends `error` too,
or launches with `--record-missing`); a task whose journal row holds no fingerprint; one
whose output file, or a file its patterns saw change, is missing now; a task the run took
over from the run it resumes from (`resumed_from`), whose attempt is that run's; one whose output was
written again by a later task of the run (what the file holds now is that task's, not
this one's); and one with a file over the cap (`record_max_file_mb`, as a recording's), which a
replay could not play. A run of a run format this release does not read is refused whole
(`RecordingError`).

An imported recording's entry names the run it came from (`imported`: `run`, `run_uid`,
`imported_at`), and each attempt the fingerprint its journal row recorded. A replay
plays an imported recording only for a task of that fingerprint, and only for its own key:
a task whose definition, params or inputs changed since that run ends `error`, its
reason naming the recording, or, with `record_missing`, launches and is recorded again.
(A recorded recording of another fingerprint is played all the same, its reason saying
so.) The import writes no `undeclared.json`: it never saw the working directory change.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contraagent._internal.backends.launch import Stop
from contraagent._internal.dispatch.task import STOP_COMPLETED, STOP_PARTIAL, STOP_SKIPPED
from contraagent._internal.execution.recording import (
    LAUNCH_FIELDS,
    MAX_FILE_MB,
    RecordingError,
    attempt_folder,
    megabytes,
    write_entry,
)
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import read_document, read_rows
from contraagent._internal.runs.source import parse_info
from contraagent._internal.runs.times import now_iso

_MB = 1024 * 1024


@dataclass(frozen=True)
class RecordingImport:
    """What `import_recording` made of a run: the keys it `imported`, in journal order;
    the tasks whose last attempt did not finish ok, with how it ended (`unfinished`); and
    the tasks that finished but could not be imported, with why (`not_imported`)."""

    run_dir: Path
    directory: Path
    imported: tuple[str, ...] = ()
    unfinished: Mapping[str, str] = field(default_factory=dict)
    not_imported: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Some task was imported, and every task that finished was."""
        return bool(self.imported) and not self.not_imported

    def __str__(self) -> str:
        n = len(self.imported)
        tasks = f"{n} task{'s' if n != 1 else ''}"
        head = f"{'✓' if self.ok else '✗'} {tasks} imported from {self.run_dir.as_posix()} into {self.directory.as_posix()}"
        later = [f"{len(self.not_imported)} not imported"] if self.not_imported else []
        later += [f"{len(self.unfinished)} not finished"] if self.unfinished else []
        lines = [head + (f"; {', '.join(later)}" if later else "")]
        lines += [f"  not imported {key}: {why}" for key, why in self.not_imported.items()]
        lines += [f"  not finished {key}: {why}" for key, why in self.unfinished.items()]
        return "\n".join(lines)


def _document(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(read_document(path))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


def _copy(src: Path, dst: Path) -> int:
    data = src.read_bytes()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return len(data)


def _shown(path: Path, cwd: str, run_dir: Path) -> str:
    """A file's path for a line: relative to the run's directory or its working directory
    when under one of them, else as it is."""
    for root in (run_dir, Path(cwd) if cwd else None):
        if root is None:
            continue
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def _changes(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """The paths an attempt's `changes=` patterns saw written (created or modified, and not
    removed after) and deleted, from its journal row."""
    changes = row.get("changes") or {}
    removed = set(changes.get("removed") or ())
    written = [p for p in (*(changes.get("created") or ()), *(changes.get("modified") or ())) if p not in removed]
    return written, list(changes.get("deleted") or ())


def import_recording(run_dir: str | Path, directory: str | Path, *, record_max_file_mb: float = MAX_FILE_MB) -> RecordingImport:
    """Write a recording of each task of the run in `run_dir` that finished ok (or
    `partial`) into the recordings directory `directory`, as if the run had recorded it
    (`Pipeline(record=)`), so a replay of the same flow plays it with nothing launched.

    The recording of each key it imports replaces the one `directory` held; the other
    recordings stay. A task with a file over `record_max_file_mb` (default 4 MB) is not
    imported. A task is imported as one attempt, its output files and changed files as they
    are now; a replay plays it only for a task of the fingerprint the run recorded.
    `contraagent docs testing` lists what is imported and what is not.

    `RecordingError` when `run_dir` holds no run (no `run.json` or no journal row) or a run
    of a run format this release does not read.
    """
    run_dir, directory = Path(run_dir), Path(directory)
    try:
        info = parse_info(read_document(run_dir / layout.RUN_INFO))
    except OSError:
        info = None
    if info is None:
        raise RecordingError(f"import: {run_dir} is not a run directory (no {layout.RUN_INFO})")
    run_format = layout.format_of(info)
    if run_format not in layout.FORMATS:
        reads = ", ".join(map(str, layout.FORMATS))
        raise RecordingError(f"import: {run_dir} is a run of run format {info.get('format')!r}; this release reads run format {reads}")
    every = read_rows(run_dir / layout.JOURNAL)
    rows = [r for r in every if r.get("key") and r.get("stop") != STOP_SKIPPED]
    # The tasks the run took over from the run it resumes from: their attempts are that run's.
    taken = {
        str(r["key"]): str(r["resumed_from"]) for r in every if r.get("key") and r.get("stop") == STOP_SKIPPED and r.get("resumed_from")
    }
    if not rows and not taken:
        raise RecordingError(f"import: {run_dir} has no journal row ({layout.JOURNAL}): nothing finished")
    cwd = str(info.get("cwd") or "")
    # A task whose call options named a working directory: its changes are relative to it.
    own_cwd = {str(r["key"]): str(r["cwd"]) for r in read_rows(run_dir / layout.PLAN) if r.get("key") and r.get("cwd")}
    run_id = str(info.get("run_id") or run_dir.name)
    imported_from = {"run": run_id, "run_uid": str(info.get("run_uid") or ""), "imported_at": now_iso()}
    launches = {str(r.get("label")): r for r in read_rows(run_dir / layout.LAUNCHES)}
    cap = record_max_file_mb * _MB

    attempts: dict[str, int] = {}
    last: dict[str, tuple[int, dict[str, Any]]] = {}
    for i, row in enumerate(rows):
        key = str(row["key"])
        attempts[key] = attempts.get(key, 0) + 1
        last[key] = (i, row)

    def outputs_of(key: str) -> list[tuple[Path, Path]]:
        record = _document(run_dir / layout.task_entry(layout.CONTRACTS, key)) or {}
        paths = [layout.file_path(o["path"], cwd) for o in record.get("outputs") or () if isinstance(o, dict) and o.get("path")]
        return [(p, p.with_name(p.name + ".message.txt")) for p in paths]

    outputs = {key: outputs_of(key) for key in last}

    # Each file an attempt that finished wrote, with the journal index of its row: what a later task wrote again.
    writers: dict[Path, list[tuple[int, str]]] = {}
    for i, row in enumerate(rows):
        key = str(row["key"])
        paths = [p for pair in outputs[key] for p in pair] if row.get("ok") else []
        written, deleted = _changes(row)
        paths += [layout.file_path(p, own_cwd.get(key) or cwd) for p in (*written, *deleted)]
        for p in paths:
            writers.setdefault(p, []).append((i, key))

    imported: list[str] = []
    unfinished: dict[str, str] = {}
    not_imported: dict[str, str] = {
        key: f"the run took it over from run {run} (resumed_from), whose journal holds its attempt: import that run too"
        for key, run in taken.items()
        if key not in last
    }
    for key, (index, row) in last.items():
        stop = str(row.get("stop") or "")
        if not row.get("ok"):
            unfinished[key] = f"{stop}: {row.get('reason')}" if row.get("reason") else stop
            continue
        fingerprint = str(row.get("fingerprint") or "")
        if not fingerprint:
            not_imported[key] = "its journal row records no fingerprint, so a replay could not tell a changed task from it"
            continue
        written, deleted = _changes(row)
        files = [(p, f"output-{n}") for n, (p, _) in enumerate(outputs[key])]
        files += [(m, f"output-{n}.message.txt") for n, (_, m) in enumerate(outputs[key]) if _size(m) is not None]
        files += [(layout.file_path(rel, own_cwd.get(key) or cwd), f"files/{rel}") for rel in written]
        why = ""
        for path, _ in files:
            size = _size(path)
            again = [k for j, k in writers.get(path, ()) if j > index and k != key]
            shown = _shown(path, cwd, run_dir)
            if size is None:
                why = f"{shown} is missing"
            elif again:
                why = f"{shown} was written again by {again[0]} after it"
            elif size > cap:
                why = f"{shown} ({megabytes(size)}) is over the {record_max_file_mb:g} MB cap of a recording"
            if why:
                break
        if why:
            not_imported[key] = why
            continue
        executor = str(row.get("executor") or "agent")
        kind = str(row.get("kind") or "")
        unit = str(row.get("unit") or "")
        token, folder = attempt_folder(directory, kind, key, 1)
        for path, name in files:
            _copy(path, folder / name)
        kept = [
            {"file": f"output-{n}", "message": f"output-{n}.message.txt" if _size(m) is not None else None}
            for n, (_, m) in enumerate(outputs[key])
        ]
        attempt: dict[str, Any] = {
            "attempt": 1,
            "files": token,
            "run": run_id,
            "recorded_at": str(row.get("ts") or ""),
            "fingerprint": fingerprint,
            "ok": True,
            "stop": stop,
            "reason": str(row.get("reason") or ""),
        }
        if executor == "python":
            attempt |= {"retry_on": False, "outputs": kept, "pipeline": {"logs": [], "documents": []}, "by_hash": []}
        else:
            stream = None
            transcript = run_dir / layout.stream(key)
            if attempts[key] == 1 and _size(transcript):
                _copy(transcript, folder / "stream.jsonl")
                stream = "stream.jsonl"
            launch = _launch(run_dir, kind, row, launches.get(key) or {}, outputs[key])
            attempt |= {
                "route": str(row.get("route") or ""),
                "launch": launch,
                "outputs": kept,
                "written": written,
                "deleted": deleted,
                "stream": stream,
                "by_hash": [],
            }
        write_entry(directory, kind, key, executor, "" if unit == key else unit, [attempt], imported=imported_from)
        imported.append(key)
    return RecordingImport(run_dir=run_dir, directory=directory, imported=tuple(imported), unfinished=unfinished, not_imported=not_imported)


def _launch(
    run_dir: Path, kind: str, row: Mapping[str, Any], launched: Mapping[str, Any], outputs: list[tuple[Path, Path]]
) -> dict[str, Any]:
    """The facts of an agent task's last launch a replay gives back (`LAUNCH_FIELDS`), from
    its journal row and its row of `launches.jsonl`. A partial attempt's launch stopped as
    its last hop did (`timeout`, `stalled`); the replay finds it partial again."""
    stop = Stop.COMPLETED.value
    if row.get("stop") == STOP_PARTIAL:
        hops = row.get("hops") or []
        stop = str((hops[-1].get("stop") if hops and isinstance(hops[-1], dict) else "") or row.get("reason") or "")
        if stop not in {s.value for s in Stop}:
            stop = Stop.TIMEOUT.value
    definition = _document(run_dir / layout.entry(layout.DEFINITIONS, layout.file_name(kind))) or {}
    message = ""
    if definition.get("output_from") == "message" and outputs:
        path, beside = outputs[0]
        message = (beside if _size(beside) is not None else path).read_text(encoding="utf-8", errors="replace")
    launch = {name: launched.get(name) for name in LAUNCH_FIELDS}
    return launch | {
        "agent": str(row.get("agent") or launched.get("agent") or ""),
        "stop": stop,
        "ok": stop == STOP_COMPLETED,
        "model": str(row.get("model") or launched.get("model") or ""),
        "credential": str(row.get("credential") or ""),
        "result_text": message,
        "structured_output": None,
        "hollow": False,
        "stderr_tail": "",
        "hook_errors": list(row.get("hook_errors") or []),
        "web_queries": list(row.get("web_queries") or []),
        "safety_stops": list(row.get("safety_stops") or []),
        "tool_uses": dict(launched.get("tool_uses") or {}),
    }


__all__ = ["RecordingImport", "import_recording"]
