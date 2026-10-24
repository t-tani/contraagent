"""A run that resumes from another run: `EarlierRun`, for `Pipeline.run(resume_from=)` and
`contraagent run --resume-from RUN_ID`.

A resume skips what an earlier attempt of the same run id finished. A run that resumes
from another run is a new run id, which skips by the same rule what the other run (the
earlier run) finished: a task whose key's last journal row there is ok with the same
fingerprint (`run.resume_skip`), its output still reading under its output schema. Every
other task runs, and one the earlier run finished says why it runs again (journal
`rerun`), as on a resume.

`EarlierRun` reads the earlier run once, as the new run starts: each key's last journal
row and its place in the journal (the order a resume gives the flow the results of the
tasks it skips), with the earlier run's lock held, so no process changes it meanwhile;
one that holds the lock refuses the new run (`RunLocked`). It then copies into the new
run directory what a resume would find in its own: `out/` (the tasks' output files, and
each file a task fills in as the earlier run left it), `pipeline/` (the pipeline logs and
documents) and `definitions/`. As the flow is given the result of a task it skips
(`take_over`), the task's contract record and call file are copied too, their paths into
the earlier run directory made paths into the new one, and the new journal gets a row
for it: stop `skipped`, the fingerprint and its parts of the earlier run's row, and
`resumed_from`, the earlier run's id. So the new run holds every record of the work it
took over, and a resume of it, or a run that resumes from it, skips that work again.

What the tasks left in the working directory is not copied: a run that resumes from
another works in the working directory as it is, as a resume does. Transcripts and
launches stay in the earlier run directory.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contraagent._internal.errors import ContraagentError
from contraagent._internal.platform.locks import locks
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import read_document, read_rows, write_document

#: The folders copied into the new run directory as it starts.
COPIED = (layout.OUT, layout.PIPELINE, layout.DEFINITIONS)
#: The folders of a task's own documents, copied as the flow is given its result.
TAKEN_OVER = (layout.CONTRACTS, layout.CALLS)


class EarlierRunError(ContraagentError):
    """The run to resume from cannot be: it does not exist, it is of a run format this
    release does not read, or another process drives it."""


class EarlierRun:
    """The run a new run resumes from (see the module docstring), read once."""

    def __init__(self, runs_dir: str | Path, run_id: str) -> None:
        self.run_id = run_id
        self.dir = Path(runs_dir) / run_id
        info = self._info()
        self.run_uid = str(info.get("run_uid") or "")
        self._lock_fd = self._hold(Path(runs_dir) / f"{run_id}.lock")
        try:
            rows = read_rows(self.dir / layout.JOURNAL)
        except BaseException:
            self.release()
            raise
        #: Each key's last journal row: what the new run compares a task with.
        self.last_rows: dict[str, dict[str, Any]] = {r["key"]: r for r in rows if r.get("key")}
        #: Each key's place in the journal: the order the flow is given the skipped tasks' results.
        self.places: dict[str, int] = {r["key"]: i for i, r in enumerate(rows) if r.get("key")}

    def _info(self) -> Mapping[str, Any]:
        try:
            info = json.loads(read_document(self.dir / layout.RUN_INFO))
        except FileNotFoundError:
            raise EarlierRunError(f"no run {self.run_id!r} to resume from: {self.dir} holds none") from None
        except ValueError as exc:
            raise EarlierRunError(f"{self.dir / layout.RUN_INFO} does not read: {exc}") from None
        if not isinstance(info, dict) or layout.format_of(info) not in layout.FORMATS:
            found = info.get("format") if isinstance(info, dict) else None
            raise EarlierRunError(
                f"{self.dir} is of run format {found!r}; this contraagent reads run format "
                f"{', '.join(map(str, layout.FORMATS))}: resume from it with the contraagent that wrote it"
            )
        return info

    def _hold(self, path: Path) -> int:
        """Hold the earlier run's lock until `release`: no process drives it while it is read."""
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            taken = locks.try_lock(fd)
        except OSError:
            os.close(fd)
            raise
        if not taken:
            os.close(fd)
            raise EarlierRunError(f"another process drives run {self.run_id!r} ({path}); resume from it when it has ended")
        return fd

    def release(self) -> None:
        """Let go of the earlier run's lock."""
        if self._lock_fd is not None:
            try:
                locks.unlock(self._lock_fd)
            finally:
                os.close(self._lock_fd)
                self._lock_fd = None

    @property
    def info(self) -> dict[str, str]:
        """What the new run's `run.json` says of the earlier run (`resumed_from`)."""
        return {"run_id": self.run_id, "run_uid": self.run_uid}

    def copy_into(self, run_dir: Path) -> None:
        """Copy the earlier run's `COPIED` folders into `run_dir`, then let go of its lock.
        A document that names a path in the earlier run directory names it in `run_dir`."""
        try:
            for folder in COPIED:
                source = self.dir / folder
                if source.is_dir():
                    shutil.copytree(source, run_dir / folder, dirs_exist_ok=True)
            for path in (run_dir / layout.DEFINITIONS).glob("*.json"):
                self._moved(path, path, run_dir)
        finally:
            self.release()

    def take_over(self, key: str, run_dir: Path) -> dict[str, Any] | None:
        """Copy the contract record and the call file of task `key` into `run_dir`; its
        last journal row in the earlier run, or None for a key the earlier run has none of."""
        for folder in TAKEN_OVER:
            name = layout.task_entry(folder, key)
            if (self.dir / name).is_file():
                self._moved(self.dir / name, run_dir / name, run_dir)
        return self.last_rows.get(key)

    def _moved(self, source: Path, target: Path, run_dir: Path) -> None:
        """Write the JSON document `source` to `target` with each path into the earlier run
        directory made the same path into `run_dir`; one that does not read is copied as it is."""
        text = read_document(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            doc = json.loads(text)
        except ValueError:
            write_document(target, text)
            return
        prefixes = _prefixes(self.dir, run_dir)
        write_document(target, json.dumps(_repath(doc, prefixes), ensure_ascii=False))


def _prefixes(old: Path, new: Path) -> list[tuple[str, str]]:
    """The forms a path into run directory `old` takes in a record (absolute, and relative
    to this process's directory), each with its form for `new`; the longest first."""
    pairs = {(str(old.resolve()), str(new.resolve())), (old.resolve().as_posix(), new.resolve().as_posix())}
    if not old.is_absolute():
        pairs |= {(str(old), str(new)), (old.as_posix(), new.as_posix())}
    return sorted(pairs, key=lambda p: -len(p[0]))


def _repath(value: Any, prefixes: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {k: _repath(v, prefixes) for k, v in value.items()}
    if isinstance(value, list):
        return [_repath(v, prefixes) for v in value]
    if isinstance(value, str):
        for old, new in prefixes:
            if value == old or value.startswith((old + "/", old + os.sep)):
                return new + value[len(old) :]
    return value
