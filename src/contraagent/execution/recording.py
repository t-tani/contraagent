"""Recordings: what each attempt of an agent task left behind, kept to be played again.

A **recording** (`Pipeline(record="recordings/")`, `contraagent run --record DIR`) keeps,
per agent task attempt, what a later run needs to play it again without a launch:

    recordings/<kind>/<key>.json         the task's recording: one entry per attempt, in order
    recordings/<kind>/<key>/<id>/        the files of one attempt:
        output-<n>                       the final contents of its n-th output file
        output-<n>.message.txt           the whole final message beside an unwrapped output
        files/<path>                     what its `changes=` patterns saw created or modified
        stream.jsonl                     its part of the transcript, when transcripts are kept

An attempt's entry holds the facts of its last launch (stop, ok, final message, structured
output, turns, agent, model, ...), the task's fingerprint, and the paths its patterns saw
deleted. Only what the task declares is kept: its outputs and its `changes=`, never the
rest of the working directory. A task's first attempt in a run replaces its recording;
each later attempt adds to it. The entry file is replaced whole after the files it names
are written, so a reader sees the old recording or the new one.

A **replay** (`Pipeline(replay="recordings/")`, `contraagent run --replay DIR`) plays an
agent task's recording in place of a launch: attempt 1 the first entry, attempt 2 the
second, past the last the last again. It writes the recorded outputs and changed files
into place, deletes the recorded deletions, appends the recorded transcript, and returns
the recorded result with no cost and no tokens: nothing was spent in this run. A key
minted with `~n` that has no recording of its own plays the first recording of its base
key after it (`summarize-alpha~3`, `summarize-alpha~4`, ... for `summarize-alpha~2`)
that no task of this run has played. A task
with no recording ends `error` after one attempt: `no recording for <key>`. A recording made with another
fingerprint is played all the same; the result's reason says so.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contraagent import envvars, rundir
from contraagent.backends import backend_class, known_agents
from contraagent.backends.base import Backend
from contraagent.backends.credentials import CredentialBase, CredentialBinding
from contraagent.backends.launch import Launch, LaunchResult, Stop
from contraagent.contracts import OutputContract
from contraagent.dispatch.task import STOP_DEFERRED, STOP_INVALID_INPUT, Task, TaskResult, kind_name
from contraagent.errors import ContraagentError

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
    """The `ResultEnricher` that writes each agent task attempt's recording under `directory`.

    `outputs(task)`: the task's output contracts (`TaskAdapter.output_contracts`); `cwd`:
    where its changes and outputs are resolved; `run_dir`: the run whose transcripts are
    copied. It runs after the enricher that records the task's changes, so it sees them.
    """

    def __init__(
        self,
        directory: str | Path,
        outputs: Callable[[Task], Sequence[OutputContract]],
        *,
        cwd: Path,
        run_dir: Path,
        run_id: str = "",
    ) -> None:
        self.directory = Path(directory)
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
        # Nothing was launched: a deferral, or an input refused before launch.
        if result.stop in (STOP_DEFERRED, STOP_INVALID_INPUT) or result.launch_result is None:
            return
        kind = kind_name(task.kind)
        home = self.directory / safe_name(kind)
        entry_file = home / f"{safe_name(task.key)}.json"
        folder = home / safe_name(task.key)
        token = f"{task.attempt + 1}-{secrets.token_hex(4)}"
        files = folder / token
        files.mkdir(parents=True, exist_ok=True)

        outputs: list[dict[str, Any]] = []
        for n, (out, message) in enumerate(_outputs(self._outputs(task), self._cwd)):
            name = f"output-{n}"
            kept = _copy(out, files / name)
            beside = _copy(message, files / f"{name}.message.txt")
            outputs.append({"file": name if kept else None, "message": f"{name}.message.txt" if beside else None})

        changes = result.changes
        written: list[str] = []
        deleted: list[str] = []
        if changes is not None:
            removed = set(changes.removed)
            for rel in (*changes.created, *changes.modified):
                if rel not in removed and _copy(self._cwd / rel, files / "files" / rel):
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

        o: LaunchResult = result.launch_result
        launch = {name: getattr(o, name) for name in LAUNCH_FIELDS}
        launch["stop"] = o.stop.value
        attempt = {
            "attempt": task.attempt + 1,
            "files": token,
            "run": self._run_id,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "fingerprint": task.fingerprint,
            "ok": result.ok,
            "stop": result.stop,
            "reason": result.reason,
            "route": result.route,
            "launch": launch,
            "outputs": outputs,
            "written": written,
            "deleted": deleted,
            "stream": stream,
        }
        with self._lock:
            earlier: list[dict] = []
            if task.attempt > 0:
                try:
                    earlier = json.loads(entry_file.read_text(encoding="utf-8")).get("attempts", [])
                except (OSError, ValueError):
                    earlier = []
            body = {"version": VERSION, "key": task.key, "kind": kind, "unit": task.declared_unit, "attempts": [*earlier, attempt]}
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


class Replay:
    """A recording directory, played in place of the coding agents (`backends()`).

    It is the `ResultEnricher` that tells its agents which task each launch is: give it
    to the runner's enrichers, and its `backends()` as the runner's backends. Bind it to a
    run's output contracts and working directory with `start` before the run.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
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
        if not self.recordings:
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

    def backends(self, names: Iterable[str] | None = None) -> dict[str, Backend]:
        """A player under every coding-agent name (default: every registered one), for the
        runner: a config's routes all land on it."""
        return {n: ReplayAgent(self, n) for n in (names if names is not None else known_agents())}

    # --- ResultEnricher ------------------------------------------------------

    def snapshot(self, task: Task) -> None:
        """Choose the recording `task` plays, on its first attempt in this run."""
        with self._lock:
            if task.key in self._playing:
                self._playing[task.key].task = task
                return
            key = self._choose(task.key)
            playing = _Playing(task=task, key=key)
            if key is not None:
                self._played.add(key)
                body, folder = self.recordings[key]
                playing.attempts, playing.folder = list(body["attempts"]), folder
            self._playing[task.key] = playing

    def enrich(self, task: Task, before: None, result: TaskResult) -> None:
        """A task with no recording is not retried: no attempt finds one."""
        with self._lock:
            playing = self._playing.get(task.key)
        if playing is not None and playing.key is None:
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

    def play(self, launch: Launch, agent: str) -> LaunchResult:
        """The recorded result of the launch's task for its attempt, its files written."""
        started = time.monotonic()
        key = launch.env.get(envvars.TASK, launch.label)
        with self._lock:
            playing = self._playing.get(key)
        if playing is None or playing.key is None or playing.folder is None:
            return LaunchResult(
                label=launch.label,
                agent=agent,
                stop=Stop.ERROR,
                ok=False,
                model=launch.model,
                credential=launch.credential.label,
                stderr_tail=f"no recording for {key}",
                cost_usd=0.0,
            )
        task = playing.task
        attempt = playing.attempts[min(task.attempt, len(playing.attempts) - 1)]
        files = playing.folder / str(attempt.get("files", ""))
        for (out, message), recorded in zip(_outputs(self._outputs(task), launch.cwd), attempt.get("outputs") or (), strict=False):
            if recorded.get("file"):
                _copy(files / recorded["file"], out)
            if recorded.get("message"):
                _copy(files / recorded["message"], message)
        for rel in attempt.get("written") or ():
            _copy(files / "files" / rel, launch.cwd / rel)
        for rel in attempt.get("deleted") or ():
            (launch.cwd / rel).unlink(missing_ok=True)
        if attempt.get("stream") and launch.stream_path is not None:
            try:
                part = (files / attempt["stream"]).read_bytes()
            except OSError:
                part = b""
            launch.stream_path.parent.mkdir(parents=True, exist_ok=True)
            with open(launch.stream_path, "ab") as f:
                f.write(part)
        recorded = dict(attempt.get("launch") or {})
        notes = []
        if playing.key != key:
            notes.append(f"played the recording of {playing.key}")
        if attempt.get("fingerprint") and task.fingerprint and attempt["fingerprint"] != task.fingerprint:
            notes.append(f"the recording has another fingerprint ({attempt['fingerprint'][:12]}, task {task.fingerprint[:12]})")
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
    """A coding agent that plays a `Replay`'s recordings under one coding agent's name."""

    binary = ""

    def __init__(self, replay: Replay, name: str) -> None:
        super().__init__(base_env={})
        self.replay = replay
        self.name = name
        cls = backend_class(name)
        if cls is not None:
            self.light_launch = cls.light_launch
            self.tool_deny_problem = cls.tool_deny_problem  # type: ignore[method-assign]

    def argv(self, launch: Launch) -> list[str]:
        return ["replay", "--model", launch.model or "-"]

    def env(self, launch: Launch) -> dict[str, str]:
        return {}

    def bind_credential(
        self, credential: CredentialBase, model: str = "", *, env: dict[str, str] | None = None, label: str = ""
    ) -> CredentialBinding:
        """Any credential: a replay makes no API call."""
        return CredentialBinding(isolated=True, isolation="replay: no API calls")

    def resumable(self, launch: Launch) -> Launch:
        return launch

    def run(self, launch: Launch) -> LaunchResult:
        return self.replay.play(launch, self.name)


__all__ = ["Recorder", "RecordingError", "Replay", "ReplayAgent", "base_key", "safe_name"]
