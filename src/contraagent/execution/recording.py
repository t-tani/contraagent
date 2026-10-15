"""Recordings: what each task attempt left behind, kept to be played again.

A **recording** (`Pipeline(record="recordings/")`, `contraagent run --record DIR`) keeps,
per task attempt (agent tasks and Python tasks), what a later run needs to play it again
without a launch or a call of the function:

    recordings/<kind>/<key>.json         the task's recording: one entry per attempt, in order
    recordings/<kind>/<key>/<id>/        the files of one attempt:
        output-<n>                       the final contents of its n-th output file
        output-<n>.message.txt           the whole final message beside an unwrapped output
        files/<path>                     what its `changes=` patterns saw created or modified
        stream.jsonl                     its part of the transcript, when transcripts are kept
        pipeline/<name>.jsonl            a Python task's rows of `contraagent.log(name, ...)`, in order
        pipeline/<name>.json             a Python task's last `contraagent.save(name, ...)`

A file over the recording's cap (`max_file_mb`, default 4 MB, `Pipeline(record_max_file_mb=)`,
`--record-max-file-mb`) is kept by its SHA-256 and size only (the entry's `by_hash`), so a
recording stays small enough to commit; the task's recording cannot be played then.

An agent task attempt's entry holds the facts of its last launch (stop, ok, final message,
structured output, turns, agent, model, ...), the task's fingerprint, and the paths its
patterns saw deleted. A Python task attempt's entry holds how its call ended (stop, ok,
reason, and `retry_on`: whether it raised an exception of its task's `retry_on`) and the
output file its return value was written to, which is what the flow receives, and what
its call wrote with `contraagent.log` and `contraagent.save` (`pipeline_files.capturing`):
a replay writes those rows and documents into the run's `pipeline/` as it plays the
attempt, so a panel reads the same. An agent task cannot call them (its coding agent runs
in another process), so it has none. Only what
the task declares is kept: its outputs and its `changes=`, never the rest of the working
directory. A task's first attempt in a run replaces its recording;
each later attempt adds to it. The entry file is replaced whole after the files it names
are written, so a reader sees the old recording or the new one.

A recording run compares the working directory at its start and its end (`Recorder.start`,
`Recorder.finish`), leaving out `.git`, `__pycache__`, the recordings and the run's own
files (`rundir.OWN`; its `out/` is compared like any other folder). A path created,
modified or deleted that no task's outputs, nor its `changes=` patterns, cover is an
**undeclared change**: a replay cannot make it again, since no recording holds it. They are
written to `recordings/undeclared.json` (`run`, `created`, `modified`, `deleted`), replaced
by each recording run. Tasks run at once, so they are the run's, not a task's.

A **replay** (`Pipeline(replay="recordings/")`, `contraagent run --replay DIR`) plays a
task's recording in place of a launch, or of a Python task's function: attempt 1 the first
entry, attempt 2 the second, past the last the last again. It writes the recorded outputs
and changed files into place, deletes the recorded deletions, appends the recorded
transcript, and returns the recorded result with no cost and no tokens: nothing was spent
in this run. A Python task of a kind in `execute` runs its function instead. A played
attempt's result says `replayed` (`TaskResult.replayed`, the journal row's `replayed`).

With `record_missing` (`Pipeline(replay=, record_missing=True)`, `--record-missing`), a
task with no recording launches, or runs its function, as in any run, and the `Recorder`
on the same directory records it there; the tasks with one are played. A key
minted with `~n` that has no recording of its own plays the first recording of its base
key after it (`summarize-alpha~3`, `summarize-alpha~4`, ... for `summarize-alpha~2`)
that no task of this run has played. A task
with no recording ends `error` after one attempt: `no recording for <key>`; so does a task
whose recording holds a file by hash only, its reason naming the file. With `record_missing`
such a recording counts as missing. A recording made with another
fingerprint is played all the same; the result's reason says so.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contraagent import envvars, rundir
from contraagent.backends import backend_class, known_agents
from contraagent.backends.base import Backend, ModelChains
from contraagent.backends.credentials import CredentialBase, CredentialBinding
from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.contracts import OutputContract
from contraagent.dispatch.task import STOP_DEFERRED, STOP_ERROR, STOP_INVALID_INPUT, Task, TaskResult, kind_name
from contraagent.errors import ContraagentError
from contraagent.execution.changes import compare, scan, scan_tree
from contraagent.execution.pipeline_files import Written, restore

VERSION = 1

#: The facts of an attempt's last launch a replay gives back (`LaunchResult` fields).
LAUNCH_FIELDS = (
    "agent",
    "stop",
    "ok",
    "model",
    "credential",
    "session_id",
    "num_turns",
    "result_text",
    "structured_output",
    "hollow",
    "stderr_tail",
    "hook_errors",
    "web_queries",
    "tool_uses",
)

_TILDE = re.compile(r"^(?P<base>.+)~(?P<n>[0-9]+)$")

#: The file in a recordings directory that names the last recording run's undeclared changes.
UNDECLARED = "undeclared.json"

#: The size above which a recorded file is kept by hash only, in MB (MiB).
MAX_FILE_MB = 4.0
_MB = 1024 * 1024


def megabytes(size: int) -> str:
    """A file size in MB, for a line: `120 MB`, `4.5 MB`, `<0.1 MB`."""
    mb = size / _MB
    return f"{mb:,.0f} MB" if mb >= 10 else f"{mb:.1f} MB" if mb >= 0.05 else "<0.1 MB"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class RecordingError(ContraagentError):
    """A recording directory that cannot be replayed: missing, or holding no recording."""


def safe_name(name: str) -> str:
    """`name` as one file name: letters, digits, `-`, `_` and `.` kept, anything else `_`."""
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)


def base_key(key: str) -> tuple[str, int]:
    """A key's base and its `~n` (1 for a key with none): `summarize-alpha~2` is `("summarize-alpha", 2)`."""
    m = _TILDE.match(key)
    return (m["base"], int(m["n"])) if m else (key, 1)


def _outputs(contracts: Sequence[OutputContract], cwd: Path) -> list[tuple[Path, Path]]:
    """Each output's file and the file beside it that keeps an unwrapped output's final message."""
    return [(c.resolve(cwd), c.message_path(cwd)) for c in contracts]


def _written(files: Path, pipeline: dict) -> Written:
    """What a recorded attempt wrote with `contraagent.log` and `save`, read back from its files."""
    written = Written()
    for name in pipeline.get("logs") or ():
        try:
            written.logs[name] = (files / rundir.pipeline_log(name)).read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            continue
    for name in pipeline.get("documents") or ():
        try:
            written.documents[name] = (files / rundir.pipeline_document(name)).read_text(encoding="utf-8")
        except OSError:
            continue
    return written


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _copy(src: Path, dst: Path) -> bool:
    try:
        data = src.read_bytes()
    except OSError:
        return False
    _write(dst, data)
    return True


@dataclass
class _Mark:
    """What `Recorder.snapshot` saw before the dispatch: where the task's transcript ended."""

    stream_at: int


class Recorder:
    """The `ResultEnricher` that writes each agent task attempt's recording under `directory`,
    and the recorder of each Python task attempt (`record_python`, by `PythonTaskRunner`).

    `outputs(task)`: an agent task's output contracts (`TaskAdapter.output_contracts`); `cwd`:
    where its changes and outputs are resolved; `run_dir`: the run whose transcripts are
    copied. It runs after the enricher that records the task's changes, so it sees them.
    `max_file_mb`: an output or changed file larger is kept by hash only, and `log` is given
    a line naming it; `summary()` is the line that sums up what this run recorded.
    `patterns(task)`: an agent task's `changes=` patterns, which declare what it may change
    (`start` and `finish` find the changes nothing declared).
    """

    def __init__(
        self,
        directory: str | Path,
        outputs: Callable[[Task], Sequence[OutputContract]],
        *,
        cwd: Path,
        run_dir: Path,
        run_id: str = "",
        max_file_mb: float = MAX_FILE_MB,
        log: Callable[[str], None] | None = None,
        patterns: Callable[[Task], Sequence[str]] = lambda task: (),
    ) -> None:
        self.directory = Path(directory)
        self._patterns = patterns
        self._tree: dict[str, tuple[int, int]] | None = None
        self._declared: set[str] = set()  # paths relative to cwd: outputs, and what changes= saw
        self._declared_patterns: set[str] = set()
        self.max_file_mb = max_file_mb
        self._log = log or (lambda line: None)
        self._files = 0
        self._bytes = 0
        self._hashed = 0
        self._unplayable: dict[str, str] = {}  # key -> kind, of the tasks with a file kept by hash
        self._outputs = outputs
        self._cwd = Path(cwd)
        self._run_dir = Path(run_dir)
        self._run_id = run_id
        self._lock = threading.Lock()

    def snapshot(self, task: Task) -> _Mark:
        stream = self._run_dir / rundir.stream(task.key)
        try:
            at = stream.stat().st_size
        except OSError:
            at = 0
        return _Mark(stream_at=at)

    def enrich(self, task: Task, before: _Mark, result: TaskResult) -> None:
        self.declare(self._outputs(task), self._patterns(task), result)
        # Nothing was launched: a deferral, or an input refused before launch; or it was played.
        if result.stop in (STOP_DEFERRED, STOP_INVALID_INPUT) or result.launch_result is None or result.replayed:
            return
        token, files = self._attempt_dir(task)
        by_hash: list[dict[str, Any]] = []

        outputs: list[dict[str, Any]] = []
        for n, (out, message) in enumerate(_outputs(self._outputs(task), self._cwd)):
            name = f"output-{n}"
            kept = self._store(task, out, files / name, by_hash)
            beside = self._store(task, message, files / f"{name}.message.txt", by_hash)
            outputs.append({"file": name if kept else None, "message": f"{name}.message.txt" if beside else None})

        changes = result.changes
        written: list[str] = []
        deleted: list[str] = []
        if changes is not None:
            removed = set(changes.removed)
            for rel in (*changes.created, *changes.modified):
                if rel not in removed and self._store(task, self._cwd / rel, files / "files" / rel, by_hash):
                    written.append(rel)
            deleted = list(changes.deleted)

        stream = None
        source = self._run_dir / rundir.stream(task.key)
        try:
            with open(source, "rb") as f:
                f.seek(before.stream_at)
                part = f.read()
        except OSError:
            part = b""
        if part:
            _write(files / "stream.jsonl", part)
            stream = "stream.jsonl"
            self._count(len(part))

        o: LaunchResult = result.launch_result
        launch = {name: getattr(o, name) for name in LAUNCH_FIELDS}
        launch["stop"] = o.stop.value
        attempt = {
            **self._facts(task, token, result),
            "route": result.route,
            "launch": launch,
            "outputs": outputs,
            "written": written,
            "deleted": deleted,
            "stream": stream,
            "by_hash": by_hash,
        }
        self._keep(task, "agent", attempt)

    def record_python(
        self, task: Task, result: TaskResult, outputs: Sequence[OutputContract], retry: bool, written: Written | None = None
    ) -> None:
        """Keep one call of a Python task's function: how it ended, `retry` (it raised an
        exception of its task's `retry_on`), when it finished ok (a `Partial` too) its output
        files, and `written`, what it wrote with `contraagent.log` and `save`, whatever its end."""
        token, files = self._attempt_dir(task)
        by_hash: list[dict[str, Any]] = []
        kept: list[dict[str, Any]] = []
        for n, (out, message) in enumerate(_outputs(outputs, self._cwd)):
            name = f"output-{n}"
            stored = result.ok and self._store(task, out, files / name, by_hash)
            beside = result.ok and self._store(task, message, files / f"{name}.message.txt", by_hash)
            kept.append({"file": name if stored else None, "message": f"{name}.message.txt" if beside else None})
        pipeline: dict[str, list[str]] = {"logs": [], "documents": []}
        for name, lines in (written.logs if written is not None else {}).items():
            data = "".join(lines).encode()
            if self._store_bytes(task, data, files / rundir.pipeline_log(name), rundir.pipeline_log(name), by_hash):
                pipeline["logs"].append(name)
        for name, text in (written.documents if written is not None else {}).items():
            data = text.encode()
            if self._store_bytes(task, data, files / rundir.pipeline_document(name), rundir.pipeline_document(name), by_hash):
                pipeline["documents"].append(name)
        facts = {**self._facts(task, token, result), "retry_on": retry, "outputs": kept, "pipeline": pipeline, "by_hash": by_hash}
        self._keep(task, "python", facts)

    def _store_bytes(self, task: Task, data: bytes, dst: Path, shown: str, by_hash: list[dict[str, Any]]) -> bool:
        """`_store` for content held in memory, shown in a line as `shown`."""
        if len(data) <= self.max_file_mb * _MB:
            _write(dst, data)
            self._count(len(data))
            return True
        by_hash.append({"path": shown, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        self._hashed_by(task, shown, len(data))
        return False

    def _hashed_by(self, task: Task, shown: str, size: int) -> None:
        with self._lock:
            self._hashed += 1
            self._unplayable[task.key] = kind_name(task.kind)
        self._log(f"[record] {task.key}: {shown} ({megabytes(size)}) stored by hash only, over {self.max_file_mb:g} MB")

    def declare(self, outputs: Sequence[OutputContract], patterns: Sequence[str] = (), result: TaskResult | None = None) -> None:
        """What a task attempt declares it changes: its output files, its `changes=` patterns,
        and the paths those saw change (`result.changes`). Played attempts count too."""
        paths = [p for pair in _outputs(outputs, self._cwd) for p in pair]
        changes = result.changes if result is not None else None
        seen = [*changes.created, *changes.modified, *changes.deleted] if changes is not None else []
        with self._lock:
            for p in paths:
                rel = self._relative(p)
                if rel is not None:
                    self._declared.add(rel)
            self._declared.update(seen)
            self._declared_patterns.update(patterns)

    def _relative(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self._cwd.resolve()).as_posix()
        except ValueError:
            return None

    def _skip(self) -> Callable[[Path], bool]:
        """What the working directory's comparison leaves out: `.git`, `__pycache__`, the
        recordings, and the run's own files (`rundir.OWN`) and lock, wherever they are."""
        own = {(self._run_dir / name).resolve() for name in rundir.OWN}
        own |= {self.directory.resolve(), self._run_dir.parent.resolve() / f"{self._run_dir.name}.lock"}
        names = {".git", "__pycache__"}
        return lambda path: path.name in names or path in own

    def start(self) -> None:
        """Stamp every file of the working directory, before the run's flow runs."""
        self._tree = scan_tree(self._cwd.resolve(), self._skip())

    def finish(self) -> list[str]:
        """The undeclared changes since `start`, in path order: written to `undeclared.json`
        in the recordings directory (replacing an earlier run's), and returned."""
        if self._tree is None:
            return []
        cwd = self._cwd.resolve()
        found = compare(self._tree, scan_tree(cwd, self._skip()))
        covered, dirs = scan(cwd, sorted(self._declared_patterns))

        def declared(rel: str) -> bool:
            parents = [p.as_posix() for p in Path(rel).parents][:-1]
            return rel in self._declared or rel in covered or any(p in dirs for p in parents)

        body = {
            "run": self._run_id,
            "created": [p for p in found.created if not declared(p)],
            "modified": [p for p in found.modified if not declared(p)],
            "deleted": [p for p in found.deleted if not declared(p)],
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        rundir.write_document(self.directory / UNDECLARED, json.dumps(body, ensure_ascii=False, indent=2) + "\n")
        return sorted([*body["created"], *body["modified"], *body["deleted"]])

    def _store(self, task: Task, src: Path, dst: Path, by_hash: list[dict[str, Any]]) -> bool:
        """Copy `src` into the recording; one over the cap goes to `by_hash` (its path, SHA-256
        and size) instead. Whether its content was kept."""
        try:
            size = src.stat().st_size
        except OSError:
            return False
        if size <= self.max_file_mb * _MB:
            kept = _copy(src, dst)
            if kept:
                self._count(size)
            return kept
        shown = self._shown(src)
        try:
            by_hash.append({"path": shown, "sha256": _sha256(src), "bytes": size})
        except OSError:
            return False
        self._hashed_by(task, shown, size)
        return False

    def _count(self, size: int) -> None:
        with self._lock:
            self._files += 1
            self._bytes += size

    def _shown(self, path: Path) -> str:
        """A recorded file's path for a line: relative to the working directory, or else to the run."""
        for root in (self._cwd, self._run_dir):
            try:
                return path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
        return str(path)

    def summary(self) -> str:
        """What this run recorded, in one line: files and size, the files kept by hash only,
        and the tasks those make unplayable, with their kinds."""
        with self._lock:
            facts = [f"{self._files:,} file{'s' if self._files != 1 else ''}, {megabytes(self._bytes)}"]
            if self._hashed:
                facts.append(f"{self._hashed:,} file{'s' if self._hashed != 1 else ''} stored by hash")
                n, kinds = len(self._unplayable), sorted(set(self._unplayable.values()))
                facts.append(f"{n} task{'s' if n != 1 else ''} cannot be replayed: kind{'s' if len(kinds) != 1 else ''} {', '.join(kinds)}")
        return f"[record] {self.directory}: " + " | ".join(facts)

    def _attempt_dir(self, task: Task) -> tuple[str, Path]:
        """A fresh folder for one attempt's files: its name and its path."""
        token = f"{task.attempt + 1}-{secrets.token_hex(4)}"
        files = self.directory / safe_name(kind_name(task.kind)) / safe_name(task.key) / token
        files.mkdir(parents=True, exist_ok=True)
        return token, files

    def _facts(self, task: Task, token: str, result: TaskResult) -> dict[str, Any]:
        return {
            "attempt": task.attempt + 1,
            "files": token,
            "run": self._run_id,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "fingerprint": task.fingerprint,
            "ok": result.ok,
            "stop": result.stop,
            "reason": result.reason,
        }

    def _keep(self, task: Task, executor: str, attempt: dict[str, Any]) -> None:
        """Add `attempt` to the task's recording (its first attempt in this run replaces it)."""
        kind = kind_name(task.kind)
        home = self.directory / safe_name(kind)
        entry_file = home / f"{safe_name(task.key)}.json"
        folder = home / safe_name(task.key)
        with self._lock:
            earlier: list[dict] = []
            if task.attempt > 0:
                try:
                    earlier = json.loads(entry_file.read_text(encoding="utf-8")).get("attempts", [])
                except (OSError, ValueError):
                    earlier = []
            body = {
                "version": VERSION,
                "key": task.key,
                "kind": kind,
                "executor": executor,
                "unit": task.declared_unit,
                "attempts": [*earlier, attempt],
            }
            rundir.write_document(entry_file, json.dumps(body, ensure_ascii=False, indent=2, default=str) + "\n")
            # The attempts the entry no longer names: an earlier run's recording of this key.
            named = {a.get("files") for a in body["attempts"]}
            for old in folder.iterdir():
                if old.is_dir() and old.name not in named:
                    shutil.rmtree(old, ignore_errors=True)


@dataclass
class _Playing:
    """The recording one task plays in this run, and what its result says about it."""

    task: Task
    key: str | None  # the recorded key played; None when there is none
    attempts: list[dict] = field(default_factory=list)
    folder: Path | None = None
    #: Why the recording cannot be played (a file kept by hash only); empty when it can.
    blocked: str = ""


class Replay:
    """A recording directory, played in place of the coding agents (`backends()`) and of
    the Python tasks' functions (`play_python`, by `PythonTaskRunner`).

    It is the `ResultEnricher` that tells its agents which task each launch is: give it
    to the runner's enrichers, and its `backends()` as the runner's backends. Bind it to a
    run's output contracts and working directory with `start` before the run.
    `execute`: the Python task kinds whose functions run instead of being played.
    `record_missing`: a task with no recording launches on the coding agents given to
    `backends(real=)`, or runs its function, instead of ending `error`; the directory may
    be empty, or not exist yet.
    """

    def __init__(self, directory: str | Path, *, execute: Iterable[str] = (), record_missing: bool = False) -> None:
        self.directory = Path(directory)
        self.execute: frozenset[str] = frozenset(execute)
        self.record_missing = record_missing
        if record_missing:
            self.directory.mkdir(parents=True, exist_ok=True)
        if not self.directory.is_dir():
            raise RecordingError(f"replay: {self.directory} is not a directory of recordings")
        #: Recorded key -> (its entry, the folder of its attempts' files).
        self.recordings: dict[str, tuple[dict, Path]] = {}
        for entry_file in sorted(self.directory.glob("*/*.json")):
            try:
                body = json.loads(entry_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RecordingError(f"replay: {entry_file} is not a recording: {exc}") from exc
            if not isinstance(body, dict) or not body.get("key") or not body.get("attempts"):
                raise RecordingError(f"replay: {entry_file} is not a recording (no key, or no attempt)")
            self.recordings[str(body["key"])] = (body, entry_file.with_suffix(""))
        if not self.recordings and not record_missing:
            raise RecordingError(f"replay: {self.directory} holds no recording (<kind>/<key>.json)")
        self._outputs: Callable[[Task], Sequence[OutputContract]] = lambda task: ()
        self._cwd = Path.cwd()
        self._playing: dict[str, _Playing] = {}
        self._played: set[str] = set()
        self._lock = threading.Lock()

    def start(self, outputs: Callable[[Task], Sequence[OutputContract]], cwd: Path) -> None:
        """Bind to a run: `outputs(task)`, the task's output contracts, and `cwd`, where its
        changes are written. No recording counts as played yet."""
        self._outputs = outputs
        self._cwd = Path(cwd)
        with self._lock:
            self._playing.clear()
            self._played.clear()

    def backends(self, names: Iterable[str] | None = None, *, real: Mapping[str, Backend] | None = None) -> dict[str, Backend]:
        """A player under every coding-agent name (default: every registered one, or those of
        `real`), for the runner: a config's routes all land on it. `real`: the coding agents
        a task with no recording launches on (`record_missing`)."""
        if names is None:
            names = list(real) if real is not None else known_agents()
        return {n: ReplayAgent(self, n, real=(real or {}).get(n)) for n in names}

    def plays(self, key: str) -> bool:
        """Whether the task `key` plays a recording in this run (False: it launches; only with
        `record_missing`)."""
        with self._lock:
            playing = self._playing.get(key)
        return not self.record_missing or (playing is not None and playing.key is not None)

    # --- ResultEnricher ------------------------------------------------------

    def snapshot(self, task: Task) -> None:
        """Choose the recording `task` plays, on its first attempt in this run."""
        self._take(task)

    def _take(self, task: Task) -> _Playing:
        """The recording `task` plays: chosen on its first attempt in this run."""
        with self._lock:
            if task.key in self._playing:
                self._playing[task.key].task = task
                return self._playing[task.key]
            key = self._choose(task.key)
            blocked = self._blocked(task, key) if key is not None else ""
            if blocked and self.record_missing:  # recorded again in full
                key, blocked = None, ""
            playing = _Playing(task=task, key=key, blocked=blocked)
            if key is not None:
                self._played.add(key)
                body, folder = self.recordings[key]
                playing.attempts, playing.folder = list(body["attempts"]), folder
            self._playing[task.key] = playing
            return playing

    def _blocked(self, task: Task, key: str) -> str:
        """Why the recording `key` cannot be played for `task`: a file it keeps by hash only."""
        body, _ = self.recordings[key]
        for attempt in body.get("attempts") or ():
            for kept in attempt.get("by_hash") or ():
                kind = kind_name(task.kind)
                fix = f"run kind {kind} with --execute" if task.fn is not None else "record it again with a larger --record-max-file-mb"
                return (
                    f"the recording of {key} holds {kept.get('path')} ({megabytes(int(kept.get('bytes') or 0))}) "
                    f"by hash only: {fix}, or use --record-missing"
                )
        return ""

    def enrich(self, task: Task, before: None, result: TaskResult) -> None:
        """A played attempt is `replayed`; a task with no recording is not retried (no attempt
        finds one), unless it launched (`record_missing`)."""
        with self._lock:
            playing = self._playing.get(task.key)
        if playing is None:
            return
        if playing.blocked:
            result.retryable = False
        elif playing.key is not None and result.launch_result is not None:
            result.replayed = True
        elif playing.key is None and not self.record_missing:
            result.retryable = False

    def _choose(self, key: str) -> str | None:
        """The key's own recording; for a `~n` key with none, the first recording of its base
        after `~n` that no task has played."""
        if key in self.recordings:
            return key
        base, n = base_key(key)
        if n == 1:
            return None
        later = sorted((k for k in self.recordings if base_key(k)[0] == base and base_key(k)[1] > n), key=lambda k: base_key(k)[1])
        return next((k for k in later if k not in self._played), None)

    # --- playing ---------------------------------------------------------------

    def play_python(
        self, task: Task, outputs: Sequence[OutputContract], cwd: Path, run_dir: Path | None = None
    ) -> tuple[TaskResult, bool] | None:
        """A Python task's recorded call for its attempt, its output files written into place
        and its pipeline log rows and documents into `run_dir`'s `pipeline/`, and whether that
        call raised an exception of its `retry_on`; None for a kind in `execute`, whose function
        runs, and for a task with no recording with `record_missing`. A task with no recording
        ends `error` otherwise, not retried."""
        if kind_name(task.kind) in self.execute:
            return None
        started = time.monotonic()
        playing = self._take(task)
        if playing.key is None or playing.folder is None:
            if self.record_missing:
                return None
            return TaskResult(task=task, ok=False, stop=STOP_ERROR, reason=f"no recording for {task.key}", retryable=False), False
        if playing.blocked:
            return TaskResult(task=task, ok=False, stop=STOP_ERROR, reason=playing.blocked, retryable=False), False
        attempt = playing.attempts[min(task.attempt, len(playing.attempts) - 1)]
        files = playing.folder / str(attempt.get("files", ""))
        self._place(files, attempt, outputs, cwd)
        if run_dir is not None:
            restore(run_dir, _written(files, attempt.get("pipeline") or {}))
        reason = "; ".join([*self._notes(playing, task, attempt), *([attempt["reason"]] if attempt.get("reason") else [])])
        result = TaskResult(
            task=task,
            ok=bool(attempt.get("ok")),
            stop=str(attempt.get("stop") or STOP_ERROR),
            wall_s=time.monotonic() - started,
            reason=reason,
            replayed=True,
        )
        return result, bool(attempt.get("retry_on"))

    @staticmethod
    def _place(files: Path, attempt: dict, outputs: Sequence[OutputContract], cwd: Path) -> None:
        """Write an attempt's recorded outputs and changed files into place, and delete its deletions."""
        for (out, message), recorded in zip(_outputs(outputs, cwd), attempt.get("outputs") or (), strict=False):
            if recorded.get("file"):
                _copy(files / recorded["file"], out)
            if recorded.get("message"):
                _copy(files / recorded["message"], message)
        for rel in attempt.get("written") or ():
            _copy(files / "files" / rel, cwd / rel)
        for rel in attempt.get("deleted") or ():
            (cwd / rel).unlink(missing_ok=True)

    @staticmethod
    def _notes(playing: _Playing, task: Task, attempt: dict) -> list[str]:
        """What the result says about the recording played: another key's, another fingerprint."""
        notes = []
        if playing.key != task.key:
            notes.append(f"played the recording of {playing.key}")
        if attempt.get("fingerprint") and task.fingerprint and attempt["fingerprint"] != task.fingerprint:
            notes.append(f"the recording has another fingerprint ({attempt['fingerprint'][:12]}, task {task.fingerprint[:12]})")
        return notes

    def play(self, launch: Launch, agent: str) -> LaunchResult:
        """The recorded result of the launch's task for its attempt, its files written."""
        started = time.monotonic()
        key = launch.env.get(envvars.TASK, launch.label)
        with self._lock:
            playing = self._playing.get(key)
        if playing is None or playing.key is None or playing.folder is None or playing.blocked:
            return LaunchResult(
                label=launch.label,
                agent=agent,
                stop=Stop.ERROR,
                ok=False,
                model=launch.model,
                credential=launch.credential.label,
                stderr_tail=playing.blocked if playing is not None and playing.blocked else f"no recording for {key}",
                cost_usd=0.0,
            )
        task = playing.task
        attempt = playing.attempts[min(task.attempt, len(playing.attempts) - 1)]
        files = playing.folder / str(attempt.get("files", ""))
        self._place(files, attempt, self._outputs(task), launch.cwd)
        if attempt.get("stream") and launch.stream_path is not None:
            try:
                part = (files / attempt["stream"]).read_bytes()
            except OSError:
                part = b""
            launch.stream_path.parent.mkdir(parents=True, exist_ok=True)
            with open(launch.stream_path, "ab") as f:
                f.write(part)
        recorded = dict(attempt.get("launch") or {})
        notes = self._notes(playing, task, attempt)
        tail = str(recorded.get("stderr_tail") or "")
        return LaunchResult(
            label=launch.label,
            agent=str(recorded.get("agent") or agent),
            stop=Stop(recorded.get("stop", Stop.ERROR.value)),
            ok=bool(recorded.get("ok")),
            model=str(recorded.get("model") or launch.model),
            credential=str(recorded.get("credential") or launch.credential.label),
            wall_s=round(time.monotonic() - started, 3),
            session_id=str(recorded.get("session_id") or ""),
            num_turns=recorded.get("num_turns"),
            result_text=str(recorded.get("result_text") or ""),
            structured_output=recorded.get("structured_output"),
            hollow=bool(recorded.get("hollow")),
            stderr_tail="; ".join([*notes, tail] if tail else notes),
            hook_errors=list(recorded.get("hook_errors") or []),
            web_queries=list(recorded.get("web_queries") or []),
            tool_uses=dict(recorded.get("tool_uses") or {}),
            cost_usd=0.0,
        )


class ReplayAgent(Backend):
    """A coding agent that plays a `Replay`'s recordings under one coding agent's name.

    With `real` (`record_missing`), a launch of a task with no recording, and a preflight's
    probe, go to that coding agent; it answers for credentials, models and sessions."""

    binary = ""

    def __init__(self, replay: Replay, name: str, *, real: Backend | None = None) -> None:
        super().__init__(base_env={})
        self.replay = replay
        self.name = name
        self.real = real
        cls = type(real) if real is not None else backend_class(name)
        if cls is not None:
            self.light_launch = cls.light_launch
            self.tool_deny_problem = cls.tool_deny_problem  # type: ignore[method-assign]
        if real is not None:
            for flag in ("native_model_chain", "drivable_model_chain", "needs_inline_role_file", "cost_is_session_total", "effort_levels"):
                setattr(self, flag, getattr(real, flag))

    def _launches(self, launch: Launch) -> Backend | None:
        """The coding agent this launch goes to; None when it plays a recording."""
        if self.real is None or self.replay.plays(launch.env.get(envvars.TASK, launch.label)):
            return None
        return self.real

    def argv(self, launch: Launch) -> list[str]:
        real = self._launches(launch)
        return real.argv(launch) if real is not None else ["replay", "--model", launch.model or "-"]

    def env(self, launch: Launch) -> dict[str, str]:
        real = self._launches(launch)
        return real.env(launch) if real is not None else {}

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """Any credential: a replay makes no API call. With `real`, that agent's binding."""
        if self.real is not None:
            return self.real.bind_credential(credential, model, env=env, label=label)
        return CredentialBinding(isolated=True, isolation="replay: no API calls")

    def account(self, credential: CredentialBase, model: str = "") -> str:
        return self.real.account(credential, model) if self.real is not None else ""

    def catalogue(self) -> set[str] | None:
        return self.real.catalogue() if self.real is not None else None

    def model_chains(self, cwd: Path | None = None) -> ModelChains | None:
        return self.real.model_chains(cwd) if self.real is not None else None

    def attest(self, launch_result: LaunchResult, credential: CredentialBase) -> str | None:
        return self.real.attest(launch_result, credential) if self.real is not None else None

    def resumable(self, launch: Launch) -> Launch:
        real = self._launches(launch)
        return real.resumable(launch) if real is not None else launch

    def resumed(self, launch: Launch, prior: LaunchResult, prompt: str) -> Launch | None:
        real = self._launches(launch)
        return real.resumed(launch, prior, prompt) if real is not None else super().resumed(launch, prior, prompt)

    def discard_session(self, launch: Launch, session_id: str) -> None:
        real = self._launches(launch)
        if real is not None:
            real.discard_session(launch, session_id)

    def run(self, launch: Launch) -> LaunchResult:
        real = self._launches(launch)
        return real.run(launch) if real is not None else self.replay.play(launch, self.name)


__all__ = ["MAX_FILE_MB", "Recorder", "RecordingError", "Replay", "ReplayAgent", "base_key", "megabytes", "safe_name"]
