"""One run of a pipeline: its directory, journal, lock, and queue wiring (the `Run`
docstring lists its files).

It builds `WorkQueue`s that journal every result, record the plan and mark
running tasks, and reads its own journal back (`Journal`) so a resumed
run skips the work a previous attempt finished: a key whose last journal row
is ok and carries the task's `fingerprint`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import threading
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contraagent._internal.backends.base import Backend
from contraagent._internal.backends.credentials import Credential
from contraagent._internal.backends.launch import Stop
from contraagent._internal.contracts.input_file import input_files_of
from contraagent._internal.dispatch.flow import FlowState
from contraagent._internal.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent._internal.dispatch.python_task import make_python_task
from contraagent._internal.dispatch.queue import (
    GRACE_S,
    MAX_CONCURRENT,
    OVERDUE_S,
    RETRY_WAIT_S,
    THROTTLE_S,
    FinishChance,
    FollowUp,
    TaskRunner,
    WorkQueue,
)
from contraagent._internal.dispatch.records import DeferralCause, Frame, QuotaReading, Rest, RestEvent, TimeBoxRecord
from contraagent._internal.dispatch.task import STOP_PARTIAL, Task, TaskResult, TimeBox, fingerprint_of, kind_name
from contraagent._internal.errors import ContraagentError
from contraagent._internal.execution import teardown as _teardown
from contraagent._internal.execution.adapter import TaskAdapter
from contraagent._internal.execution.cursor import CursorStore
from contraagent._internal.execution.estimates import JournalEstimates, recent_runs
from contraagent._internal.execution.journal import Journal
from contraagent._internal.execution.pipeline_files import writing_into
from contraagent._internal.execution.python_tasks import PythonTaskRunner
from contraagent._internal.execution.runner import AgentRunner
from contraagent._internal.execution.schemas import DeferredRow, FlowCallRow, PlanRow
from contraagent._internal.platform import processes
from contraagent._internal.platform.locks import locks
from contraagent._internal.routing.capacity import sized
from contraagent._internal.routing.config import PerTask, PipelineConfig
from contraagent._internal.routing.kind_config import KindConfig
from contraagent._internal.routing.quota import CredentialRests, QuotaRule, caps_of
from contraagent._internal.routing.router import Router
from contraagent._internal.runs import layout
from contraagent._internal.runs.files import append_lines, parse_rows, read_document, read_rows, write_document
from contraagent._internal.runs.names import check_portable
from contraagent._internal.runs.source import DirectorySource, parse_info
from contraagent._internal.runs.times import iso_of, now_iso

_logger = logging.getLogger(__name__)

#: A launch that never ran is retried once by the queue, unless its result is not
#: retryable (a command the operating system refused to start); a rate limit counts
#: toward its throttle. These are the stop values naming those cases.
RETRY_ON = frozenset({Stop.API_ERROR.value, Stop.NO_OUTPUT.value, Stop.LAUNCH_FAILED.value})
THROTTLE_ON = frozenset({Stop.RATE_LIMITED.value})


#: Why a resume runs a task again whose journal row matches it (`resume_skip`).
UNREAD = "its output no longer reads under its output schema"

#: Why a resume runs a task again that fills in another task's file (`output_of`) when the
#: file is not as the task, or a task after it that fills it in, left it.
REFILL = "the file it fills in (output_of) is not as the earlier attempts left it"

#: How the rerun reason of a divergence starts (`rerun_reason`).
DIVERGENCE = "divergence"


def finished_before(row: dict[str, Any] | None, task: Task, fingerprint: str | None = None) -> bool:
    """Whether `row`, its key's last journal row, shows `task` finished: ok and not
    `partial`, with the task's fingerprint (`fingerprint`, when given, in its place). What a
    resume skips; never a task that reruns on resume (`Task.rerun_on_resume`)."""
    if task.rerun_on_resume or row is None or row.get("stop") == STOP_PARTIAL:
        return False
    return bool(row.get("ok")) and row.get("fingerprint", "") == (task.fingerprint if fingerprint is None else fingerprint)


def _left_by(rows: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    """For the tasks that fill in another task's file (`output_of`): each digest a file had
    before such a task started, with the digests the task left it with."""
    out: dict[str, set[str]] = {}
    for row in rows:
        parts = row.get("fingerprint_parts") or {}
        if "output_of" in parts and row.get("output_of_after"):
            out.setdefault(str(parts["output_of"]), set()).add(str(row["output_of_after"]))
    return out


def _as_left(row: Mapping[str, Any], now: str, left_by: Mapping[str, set[str]]) -> bool:
    """Whether a file that a task fills in (`output_of`), whose digest is `now`, is as the
    task's last attempt (`row`) left it, or as a task after it that fills it in left it."""
    first = str(row.get("output_of_after") or "")
    seen: set[str] = set()
    todo = [first] if first else []
    while todo:
        digest = todo.pop()
        if digest in seen:
            continue
        if digest == now:
            return True
        seen.add(digest)
        todo.extend(left_by.get(digest, ()))
    return False


def resume_skip(
    last: Mapping[str, dict[str, Any]],
    reruns: dict[str, str] | None = None,
    reads: Callable[[Task], bool] | None = None,
    warn: Callable[[str], None] | None = None,
) -> Callable[[Task], bool]:
    """What a resume skips, given each key's last journal row: a task `finished_before`.
    A task given the output of a task whose last result was `partial` is skipped only when
    that task, run again, gives it the same output: the output is part of its params.
    `reads(task)`: whether the task's output still reads under its output schema; one that
    does not runs again. Asked once per task, as it is queued (a task whose fingerprint is
    complete only when it starts, once the tasks it waits for are done). A task an earlier
    attempt finished (its last row ok) that is not skipped goes into `reruns`, with why it
    runs again (`rerun_reason`); `warn(line)` is told of each divergence.

    A task that fills in another task's file (`output_of`) holds the file's digest as it
    is about to start in its fingerprint (`output_of` of `Task.fingerprint_parts`). The
    file then holds what the earlier attempts left in it, not what the task found there:
    when it is as the task's last attempt left it, or as a task after it that fills it in
    left it (journal `output_of_after`), the part is the one its journal row recorded,
    the digest of the file before the task started. A file that is not (changed by hand,
    or written again by a task before it) runs the task again (`REFILL`)."""
    skipped: set[str] = set()
    left_by = _left_by(last.values())

    def skip(task: Task) -> bool:
        row = last.get(task.key)
        fingerprint = None
        refill = False
        if row is not None and "output_of" in task.fingerprint_parts:
            recorded = (row.get("fingerprint_parts") or {}).get("output_of")
            if recorded is not None and _as_left(row, task.fingerprint_parts["output_of"], left_by):
                parts = {**task.fingerprint_parts, "output_of": str(recorded)}
                fingerprint = fingerprint_of(task.kind, task.unit, task.key, parts)
            else:
                refill = True
        finished = not refill and finished_before(row, task, fingerprint)
        unread = finished and reads is not None and not reads(task)
        if finished and not unread:
            skipped.add(task.key)
            return True
        if row is not None and row.get("ok") and reruns is not None:
            if unread:
                why = UNREAD
            elif refill and not task.rerun_on_resume and row.get("stop") != STOP_PARTIAL:
                why = REFILL
            else:
                why = rerun_reason(row, task, skipped)
            reruns[task.key] = why
            if warn is not None and why.startswith(DIVERGENCE):
                warn(f"[resume] {task.key}: {why}")
        return False

    return skip


def rerun_reason(row: Mapping[str, Any], task: Task, skipped: Iterable[str] | None = None) -> str:
    """Why a resume runs `task` again although its last journal row, `row`, is ok: it is
    declared `rerun_on_resume`; its last result was `partial`; its outside state changed;
    or other parts of its fingerprint did, each named (from the row's `fingerprint_parts`).

    A divergence: its params changed although every task it was given from
    (`Origin.given_from`) or created from (`Origin.created_from`) is in `skipped`, the keys
    this resume skipped, and its input files did not: a file on disk with other content is
    no divergence. The flow gave other params for the same outputs: its code takes
    another path on a clock, randomness or outside state, or the code itself changed."""
    if task.rerun_on_resume:
        return "its kind is declared rerun_on_resume"
    if row.get("stop") == STOP_PARTIAL:
        return "its last result was partial"
    if task.outside and row.get("outside") and task.outside != row["outside"] and _changed(row, task) in ([], ["outside"]):
        return "its outside state changed"
    if task.fingerprint_at_start and not task.outside and row.get("outside"):
        return "its outside state could not be worked out"
    if not row.get("fingerprint_parts") or not task.fingerprint_parts:
        return "its fingerprint changed: its params or its definition"
    changed = _changed(row, task)
    if not changed:
        return "its fingerprint changed: its kind or its unit"
    named = ", ".join(_part_name(part) for part in changed)
    if "params" in changed and skipped is not None:
        done = set(skipped)
        given = task.origin.given_from if task.origin is not None else ()
        created = task.origin.created_from if task.origin is not None else ()
        if "input_files" not in changed and all(k in done for k in (*given, *created)):
            return (
                f"{DIVERGENCE}: the flow gave it other params for the same outputs, every task it was given "
                f"or created from skipped (a clock, randomness, outside state or changed flow code); changed: {named}"
            )
    return f"its fingerprint changed: {named}"


def _changed(row: Mapping[str, Any], task: Task) -> list[str]:
    """The names of the parts of `task`'s fingerprint whose digest differs from `row`'s, a
    part either of them lacks included, in a stable order."""
    before: Mapping[str, Any] = row.get("fingerprint_parts") or {}
    now = task.fingerprint_parts
    order = {"definition": 0, "params": 1, "input_files": 2, "outside": 3, "output_of": 4}
    names = [n for n in {**before, **now} if before.get(n) != now.get(n)]
    return sorted(names, key=lambda n: (order.get(n, len(order)), n))


def _part_name(part: str) -> str:
    """A part of a fingerprint (`Task.fingerprint_parts`) as a rerun reason names it; a part
    of another name, as a journal row of another writer may hold, by its name."""
    return {
        "definition": "its definition",
        "params": "its params",
        "input_files": "its input files",
        "outside": "its outside state",
        "output_of": "the file it fills in (output_of)",
    }.get(part, part)


def _name_of(fn: Callable[..., Any]) -> str:
    """A callable's `module.qualname`, as `run.json` names a quota rule."""
    fn = getattr(fn, "__func__", fn)
    qualname = getattr(fn, "__qualname__", "") or type(fn).__qualname__
    return f"{getattr(fn, '__module__', '') or ''}.{qualname}".lstrip(".")


class RunLocked(ContraagentError):
    """Another process already holds this run id."""


class RunExists(ContraagentError):
    """The run id already holds a run, and the caller did not ask to resume it.
    `run_dir` is the run's directory and `rows` the number of its journal rows."""

    run_dir: Path
    rows: int

    def __init__(self, run_dir: Path, rows: int):
        self.run_dir, self.rows = run_dir, rows
        super().__init__(
            f"{run_dir} already holds a run ({rows} journal rows): continue it with resume=True, or start a new one with another run_id"
        )


class RunFormatError(ContraagentError):
    """The run directory is of a run format this release does not read (`run.json` `format`):
    a newer contraagent wrote it."""


class Run:
    """One run of a pipeline: `runs/<run-id>/`, its journal, its lock, and its queues.

    A `Run` owns `runs/<run-id>/`:

        run.json                who is running it (pid, start time, working directory) and
                                which run it is across hosts (`run_uid`, `host_id`) — how a
                                monitor knows it is live
        journal.jsonl           one `JournalRow` per finished task
        launches.jsonl          the full `LaunchResult` of each agent launch
        streams/<key>.stream.jsonl  the raw agent transcript, when `keep_transcripts`
        plan.jsonl              every task a queue accepted, with its `after`, its `claims`, its
                                `priority` and its origin (`flow`, `created_from`, `flow_call`)
        flow_calls.jsonl        each flow call's start (`parent`, `function`, `flow`) and end
                                (`state`, `error`)
        deferred.jsonl          one row per deferred task: its key and why it was not launched
                                (`reason`, and `cause` as data: `Deferral`)
        rests.jsonl             each start and end of a credential's quota rest (`CredentialRests`)
        services.jsonl          each start and stop of a service (`execution.services`)
        inflight/<key>.json     one marker per running task
        contracts/, definitions/  what each task declared, for the monitor
        pipeline/<name>.jsonl   a pipeline log: the rows of `contraagent.log(name, row)`
        pipeline/<name>.json    a pipeline document: the last `contraagent.save(name, value)`

    and the run lock `runs/<run-id>.lock`, which refuses a second process
    driving the same run id: two drivers would launch the same work twice and
    bill for it twice.
    """

    def __init__(
        self,
        run_id: str,
        runs_dir: str | Path = "runs",
        *,
        run_group: str = "",
        lock: bool = True,
        fresh: bool = False,
        row_extras: Callable[[TaskResult], dict[str, Any]] | None = None,
        unit_of: Callable[[Task], str] | None = None,
        log: Callable[[str], None] | None = None,
        cwd: str | Path | None = None,
        config: PipelineConfig | None = None,
    ):
        """`run_group` is a label grouping runs (default: the run id).
        `row_extras(result)` adds a domain's own columns to a journal row;
        `unit_of(task)` names the row's `unit` (default `task.unit`).
        `log` receives the run's progress lines (duplicates, retries, failed
        `follow_up()`); without it they go to this module's logger, so a library
        caller decides through `logging` whether and where they appear.
        `cwd` is the run's working directory, where its agents run (default: this
        process's); `run.json` records it, and the monitor shows the flow code
        files under it relative to it.
        `config` is the config file the run was started with; its pipeline tables are what
        `contraagent.pipeline_table` reads in the run (none without it).
        `fresh` refuses a run id whose journal already has rows (`RunExists`), before
        anything is written: not its `run.json`, nor its lock file.
        A `run_id` that is not a file name on every operating system (`<lambda>`, `a:b`,
        `CON`, a trailing `.`) is refused with ValueError, on every system alike."""
        self.run_id: str = check_portable(run_id, "run id")
        self.run_group: str = run_group or run_id
        self.runs_dir: Path = Path(runs_dir)
        self.dir: Path = self.runs_dir / run_id
        self.config = config
        if fresh:
            self._refuse_existing()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / layout.STREAMS).mkdir(exist_ok=True)
        # A task given no unit has it defaulted to its own key, which names
        # no unit; the journal row then carries an empty unit.
        self._unit_of = unit_of or (lambda t: t.declared_unit)
        self.journal: Journal = Journal(
            self.dir / layout.JOURNAL,
            self.dir / layout.LAUNCHES,
            run_id=run_id,
            run_group=self.run_group,
            unit_of=self._unit_of,
            row_extras=row_extras,
        )
        self._log_to = log
        self._lock_fd: int | None = None
        self._estimates: JournalEstimates | None = None
        self._torn_down = False
        self._teardown_lock = threading.Lock()
        self._teardown_callbacks: list[Callable[[], None]] = []
        self._restore_signals: Callable[[], None] | None = None
        self._writing: contextlib.AbstractContextManager | None = None
        self._failures_lock = threading.Lock()
        # The run's records that could not be written, counted by file name, and the first
        # error of a journal row that could not be written (`_record_failed`).
        self._failures: dict[str, int] = {}
        self._journal_error: Exception | None = None
        if lock:
            self._acquire()
        if fresh:  # rows another process wrote before this one held the lock
            try:
                self._refuse_existing()
            except RunExists:
                self.close()
                raise
        self._check_format()
        if lock:
            self._clear_inflight()
        write_document(
            self.dir / layout.RUN_INFO,
            json.dumps(
                {
                    "format": layout.FORMAT,
                    "run_id": run_id,
                    "run_uid": self._previous_uid() or uuid.uuid4().hex,
                    "host_id": layout.host_id(),
                    "run_group": self.run_group,
                    "pid": os.getpid(),
                    "start_ticks": processes.start_ticks(os.getpid()),
                    "argv": list(sys.argv),
                    "cwd": str(Path(cwd or os.getcwd()).resolve()),
                    "started_at": now_iso(),
                }
            ),
        )

    def _check_format(self) -> None:
        """Refuse a run directory an earlier attempt left in a run format this release does not
        read (`RunFormatError`), before its `run.json` is replaced."""
        info = self._info()
        if info is None:
            return
        found = layout.format_of(info)
        if found in layout.FORMATS:
            return
        self.close()
        raise RunFormatError(
            f"{self.dir} is of run format {info.get('format')!r}; this contraagent reads run format "
            f"{', '.join(map(str, layout.FORMATS))}: resume it with the contraagent that wrote it, or start a new run id"
        )

    def _clear_inflight(self) -> None:
        """Remove the in-flight markers an earlier attempt of this run left: with the run
        lock held, no other process runs a task of it."""
        for path in (self.dir / layout.INFLIGHT).glob("*.json"):
            path.unlink(missing_ok=True)

    def _refuse_existing(self) -> None:
        rows = len(read_rows(self.dir / layout.JOURNAL))
        if rows:
            raise RunExists(self.dir, rows)

    def _previous_uid(self) -> str | None:
        """The `run_uid` of an earlier attempt of this run id: a resumed run keeps it."""
        uid = (self._info() or {}).get("run_uid")
        return uid if isinstance(uid, str) and uid else None

    # --- lock and lifecycle ------------------------------------------------

    def _acquire(self) -> None:
        """Hold the run's lock (`locks`) until `close()` or process exit. Process exit, normal
        or killed, always releases it, which is what makes this safe under SIGKILL."""
        path = self.runs_dir / f"{self.run_id}.lock"
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            taken = locks.try_lock(fd)
        except OSError as exc:  # no lock on this file system (ENOLCK on some NFS mounts)
            os.close(fd)
            raise OSError(exc.errno, f"cannot lock {path}: {exc.strerror}; the runs directory needs a file system with file locks") from exc
        if not taken:
            os.close(fd)
            raise RunLocked(
                f"another process already holds run id {self.run_id!r} ({path}); wait for it or pick a different run id"
            ) from None
        self._lock_fd = fd

    def close(self) -> None:
        """Release the run lock (process exit releases it too), and put back the signal
        handlers `stop_on_signals` replaced, after the teardown a signal started has ended."""
        if self._restore_signals is not None:
            self._restore_signals()
            self._restore_signals = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None

    def __enter__(self) -> Run:
        """The run, as the current run of `contraagent.log`, `save` and `pipeline_table`
        until the `with` ends."""
        self._writing = writing_into(self.dir.resolve(), self.config)
        self._writing.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        writing, self._writing = self._writing, None
        try:
            self.close()
        finally:
            if writing is not None:
                writing.__exit__(None, None, None)

    def cursor(
        self, *, stages: Iterable[object] | None = None, steps: Iterable[object] | None = None, skip_when_completed: Iterable[object] = ()
    ) -> CursorStore:
        """This run's resume cursor, at `runs/<id>/cursor.json` where the monitor
        looks for it. `stages` / `steps` are the legal vocabulary (see `CursorStore`)."""
        return CursorStore(self.dir / layout.CURSOR, self.run_id, stages=stages, steps=steps, skip_when_completed=skip_when_completed)

    def finish(self) -> None:
        """Mark the run finished in run.json. The monitor then shows it as no
        longer live even while this process stays up (to serve a monitor, say)."""
        self.update_info(finished_at=now_iso())

    def update_info(self, **fields: Any) -> None:
        """Merge `fields` into run.json (what the monitor shows about this run)."""
        info = self._info() or {}
        info.update(fields)
        write_document(self.dir / layout.RUN_INFO, json.dumps(info))

    def _info(self) -> dict[str, Any] | None:
        """`run.json` as this run directory holds it; None before the first write."""
        try:
            return parse_info(read_document(self.dir / layout.RUN_INFO))
        except OSError:
            return None

    def on_teardown(self, callback: Callable[[], None]) -> None:
        """Register a stop callback (a server, a VM lease) for `teardown`."""
        self._teardown_callbacks.append(callback)

    def teardown(self) -> None:
        """Stop the live agents and every registered callback. Idempotent, never raises.

        Reached from the main thread, the thread a signal wakes (`stop_on_signals`) and
        atexit, possibly overlapping, so the flag is claimed under a lock; a call that
        finds a teardown already under way returns at once.
        """
        if not self._teardown_lock.acquire(blocking=False):
            return
        try:
            if self._torn_down:
                return
            self._torn_down = True
        finally:
            self._teardown_lock.release()
        _teardown.run(*self._teardown_callbacks)

    def stop_on_signals(self) -> None:
        """Run `teardown` on SIGTERM and SIGINT until `close()`: an interrupted run stops its
        agents, whose sessions of their own a terminal's Ctrl-C does not reach. The teardown
        runs on a thread of its own, never in the signal handler, so it cannot wait for a
        lock the interrupted main thread holds; `close()` waits for it to end. SIGTERM then
        ends the process by its default action. Only on the main thread (Python's signal
        handlers live there); elsewhere it does nothing."""
        if threading.current_thread() is threading.main_thread() and self._restore_signals is None:
            self._restore_signals = _teardown.install_signal_handlers(self.teardown)

    def install_signal_handlers(self) -> None:
        """Run `teardown` on SIGTERM/SIGINT and at interpreter exit."""
        import atexit

        _teardown.install_signal_handlers(self.teardown)
        atexit.register(self.teardown)

    # --- journal -----------------------------------------------------------

    def record_attempt(self, result: TaskResult) -> None:
        """Journal one finished attempt, and say so in one progress line.
        Pass as `RetryingRunner(on_attempt=run.record_attempt)`.

        A row that cannot be written does not raise: a warning line names the file and the
        error, and `Pipeline.run` raises at the end of the run, since a resume would run the
        task again. A `LaunchResult` that cannot be written to `launches.jsonl` gets the
        warning line only."""
        key = result.task.key
        try:
            row = self.journal.append(result, on_launch_error=lambda exc: self._record_failed(layout.LAUNCHES, exc, key))
        except Exception as exc:  # the task's result stands; the run fails at its end
            self._record_failed(layout.JOURNAL, exc, key)
            return
        if self._estimates is not None:
            self._estimates.observe_attempt(row.model_dump())
        launched = result.launch_result
        rounds = launched.rounds if launched is not None else None
        line = f"[end] {result.task.key}: {result.stop} in {result.wall_s:.1f}s"
        if rounds and rounds > 1 and launched is not None and launched.round_errors and launched.round_errors[0]:
            # Why the first round went back: the correction is otherwise only a count here.
            first = " ".join(launched.round_errors[0][0].split())
            # A path in the run's directory as the run names it, so the cause fits in the line.
            for root in (self.dir.resolve().as_posix() + "/", self.dir.as_posix() + "/", str(self.dir.resolve()) + os.sep):
                first = first.replace(root, "")
            line += f", {rounds} rounds (round 1: {first[:160]}{'…' if len(first) > 160 else ''})"
        elif rounds and rounds > 1:
            line += f", {rounds} rounds"
        line += ", output unwrapped from the final message" if launched is not None and launched.unwrapped else ""
        line += f", on {result.route}" if len(result.hops) > 1 else ""
        self._log(logging.INFO, line)

    def rows(self) -> list[dict[str, Any]]:
        return self.journal.rows()

    def _record_failed(self, name: str, error: Exception, about: str = "") -> None:
        """A record of the run, its file `name` in the run directory, that could not be
        written: count it, keep the first error of a journal row, and say so in a warning
        progress line with the file, the task or flow call it is `about`, and the error.
        Called from the queue's threads too."""
        with self._failures_lock:
            self._failures[name] = self._failures.get(name, 0) + 1
            if name == layout.JOURNAL and self._journal_error is None:
                self._journal_error = error
        what = f" for {about}" if about else ""
        after = "; a resume runs the task again, and the run fails at its end" if name == layout.JOURNAL else ""
        self._log(logging.WARNING, f"[error] {(self.dir / name).as_posix()} not written{what}: {type(error).__name__}: {error}{after}")

    def _record_failures(self) -> dict[str, int]:
        """How many writes of each record file failed so far, by file name; empty: none."""
        with self._failures_lock:
            return dict(self._failures)

    def _journal_failure(self) -> ContraagentError | None:
        """The error that ends a run some of whose journal rows could not be written; None
        when every row was written."""
        with self._failures_lock:
            error, count = self._journal_error, self._failures.get(layout.JOURNAL, 0)
        if error is None:
            return None
        rows = "1 journal row" if count == 1 else f"{count} journal rows"
        failure = ContraagentError(
            f"{rows} of run {self.run_id} could not be written to {(self.dir / layout.JOURNAL).as_posix()} "
            f"(first: {type(error).__name__}: {error}); those tasks finished, but a resume runs them again"
        )
        failure.__cause__ = error
        return failure

    # --- running tasks -----------------------------------------------------

    def agent_runner(
        self,
        backends: Backend | Mapping[str, Backend],
        configs: Mapping[str, KindConfig],
        *,
        adapter: TaskAdapter | None = None,
        routers: Mapping[str, Router] | None = None,
        model: str = "",
        model_failover: bool = False,
        credentials: Mapping[str, Credential] | None = None,
        env: Mapping[str, str] | None = None,
        keep_transcripts: bool = False,
        cwd: Path | str | None = None,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
        rests: CredentialRests | None = None,
    ) -> AgentRunner:
        """An `AgentRunner` whose launches are attributed to this run and recorded under it;
        every argument is the `AgentRunner`'s."""
        return AgentRunner(
            backends,
            configs,
            run_dir=self.dir,
            run_id=self.run_id,
            adapter=adapter,
            routers=routers,
            model=model,
            model_failover=model_failover,
            credentials=credentials,
            env=env,
            keep_transcripts=keep_transcripts,
            cwd=cwd,
            scopes=scopes,
            enrichers=enrichers,
            rests=rests,
        )

    def python_runner(
        self,
        inner: TaskRunner | None = None,
        adapter: TaskAdapter | None = None,
        cwd: str | Path | None = None,
        *,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
    ) -> PythonTaskRunner:
        """The runner for a queue that mixes Python tasks with agent tasks: Python
        tasks run in-process with their declared contracts checked, agent tasks go
        to `inner` (`RetryingRunner(...)`). Each attempt of a Python task is journaled:
        a retried one here, the last by the queue. `scopes` / `enrichers` wrap each
        attempt of a Python task (`PythonTaskRunner`)."""
        return PythonTaskRunner(
            inner,
            adapter=adapter,
            run_dir=self.dir,
            cwd=cwd,
            on_failed_attempt=self.record_attempt,
            scopes=scopes,
            enrichers=enrichers,
            config=self.config,
        )

    def estimator(self) -> JournalEstimates:
        """The estimates of durations and tails (`JournalEstimates`): read from the recent
        runs when first asked for, then told of this run's plan rows, attempts and flow
        call ends as they are recorded."""
        if self._estimates is None:
            self._estimates = JournalEstimates(self.runs_dir)
        return self._estimates

    def credential_rests(
        self,
        credentials: Mapping[str, Credential],
        rule: QuotaRule | None = None,
        *,
        finishing_kinds: Iterable[str] = (),
        grace_s: float = GRACE_S,
    ) -> CredentialRests:
        """The run's quota rests (`CredentialRests`) over `credentials`, told the utilization
        readings of the recent runs' journals (this run's included, when resumed): an
        account's windows outlast a run. `finishing_kinds`, `grace_s`: the `CredentialRests`'.
        `run.json` records the caps (`quota_caps`, by credential) and the rule's name
        (`quota_rule`, '' for none); `rests.jsonl` each start and end of a rest."""
        rests = CredentialRests(credentials, rule, finishing_kinds=finishing_kinds, grace_s=grace_s, on_change=self._record_rest)
        caps = {c.credential: c.model_dump(exclude={"credential"}, exclude_none=True) for c in caps_of(credentials)}
        self.update_info(quota_caps=caps, quota_rule=_name_of(rule) if rule is not None else "")
        source = DirectorySource(self.runs_dir)
        for run in recent_runs(source):
            for row in parse_rows(source.lines(run, layout.JOURNAL)[0]):
                for reading in row.get("quota") or ():
                    try:
                        rests.observe(QuotaReading.model_validate(reading))
                    except ValidationError:
                        continue
        return rests

    def queue(
        self,
        runner: TaskRunner,
        *,
        follow_up: FollowUp | None = None,
        resume: bool = False,
        max_concurrent: int = MAX_CONCURRENT,
        deadline_s: float | None = None,
        retry_wait_s: float = RETRY_WAIT_S,
        throttle_s: float = THROTTLE_S,
        skip: Callable[[Task], bool] | None = None,
        grace_s: float = GRACE_S,
        retry_on: frozenset[str] = RETRY_ON,
        throttle_on: frozenset[str] = THROTTLE_ON,
        finishing_kinds: Iterable[str] = (),
        claim_capacity: Mapping[str, int | PerTask] | None = None,
        estimate: Callable[[Task], float | None] | None = None,
        overdue_s: float = OVERDUE_S,
        slack_s: float | None = None,
        finish_chance: FinishChance | None = None,
    ) -> WorkQueue:
        """A `WorkQueue` over `runner` that records the plan and journals Python tasks; every
        other argument is the `WorkQueue`'s.

        Agent tasks are journaled per attempt by `RetryingRunner(on_attempt=
        run.record_attempt)`, so nothing is written twice; a task the queue cancels before it
        launches is journaled here, as a Python task's attempts are. `resume=True` skips every
        task an earlier attempt finished, unless `skip` is given. `retry_on` and `throttle_on`
        default to the stops of a coding agent's failure (`api_error`, `no_output`,
        `launch_failed`) and of its rate limit (`rate_limited`); `estimate`, to what the
        recent runs' journals say (`Run.estimator`), and then `finish_chance` to the same
        estimates' (`JournalEstimates.finish_chance`). A `PerTask` entry of `claim_capacity`
        is sized by this host and the memory its tasks' agents hold.
        """
        if skip is None and resume:
            skip = resume_skip(self.journal.last_rows(), self.journal.reruns, warn=lambda line: self._log(logging.WARNING, line))
        q = WorkQueue(
            runner,
            follow_up=follow_up,
            on_event=self._on_event,
            on_result=self._journal_queue_result,
            max_concurrent=max_concurrent,
            deadline_s=deadline_s,
            retry_wait_s=retry_wait_s,
            throttle_s=throttle_s,
            skip=skip,
            grace_s=grace_s,
            retry_on=retry_on,
            throttle_on=throttle_on,
            finishing_kinds=tuple(finishing_kinds),
            claim_capacity=sized(claim_capacity) if claim_capacity else None,
            estimate=estimate if estimate is not None else self.estimator().estimate,
            overdue_s=overdue_s,
            slack_s=slack_s,
            finish_chance=finish_chance if finish_chance is not None or estimate is not None else self.estimator().finish_chance,
        )
        self.update_info(max_workers=q.max_concurrent)
        return q

    def run_python_steps(self, steps: list[tuple[str, Callable[[], None]]]) -> None:
        """Run `(name, fn)` steps as Python tasks, in order, through a queue, each
        queued by the previous one's success. The first failure is re-raised and
        queues nothing further."""
        if not steps:
            return
        failure: list[BaseException] = []

        def make(i: int) -> Task:
            name, fn = steps[i]

            def call():
                try:
                    fn()
                except Exception as exc:
                    failure.append(exc)
                    raise

            return make_python_task(name, call)

        index = {make_python_task(name, fn).key: i for i, (name, fn) in enumerate(steps)}

        def follow_up(res: TaskResult) -> list[Task]:
            i = index[res.task.key]
            return [make(i + 1)] if res.ok and i + 1 < len(steps) else []

        q = self.queue(self.python_runner(), follow_up=follow_up, max_concurrent=1)
        q.add(make(0))
        q.run()
        if failure:
            raise failure[0]

    # --- queue callbacks ---------------------------------------------------

    def _journal_queue_result(self, res: TaskResult, attempt: int) -> None:
        """Journal what no runner journals: a Python task's attempts, and a task the queue
        cancelled before it launched (attempt 0)."""
        if res.task.fn is not None or attempt == 0:
            self.record_attempt(res)

    def _on_event(self, event: str, task: Task | None, **fields) -> None:
        if event == "queued" and task is not None:
            self._record_plan(task)
        elif event in ("start", "end") and task is not None:
            self._mark_inflight(task, running=event == "start")
            if event == "start":
                why = self.journal.reruns.get(task.key, "") if fields.get("attempt") == 1 else ""
                # The credential its task call names, when that is in effect (the kind's is in `[route]`).
                cred = f" credential={task.credential}" if task.credential else ""
                self._log(logging.INFO, f"[start] {task.key}{cred}" + (f": runs again, {why}" if why else ""))
            elif fields.get("stop") == "skipped":
                self._log(logging.INFO, f"[skip] {task.key}: finished in an earlier attempt of this run")
        if event == "deferred" and task is not None:
            cause = fields.get("cause")
            self._record_deferral(task, str(fields.get("reason") or ""), cause if isinstance(cause, DeferralCause) else None)
        if event == "duplicate_key_refused":
            self._log(logging.WARNING, f"[refused] {fields.get('key')}: already in flight")
        elif event == "retry" and task is not None:
            wait = f" in {fields['wait_s']:.0f}s" if isinstance(fields.get("wait_s"), (int, float)) else ""
            self._log(logging.INFO, f"[retry] {task.key}: {fields.get('stop') or 'no progress'}; again{wait}")
        elif event == "note" and "follow_up_failed" in fields:
            self._log(logging.WARNING, f"[error] {task.key if task is not None else '?'}: follow_up() raised {fields['follow_up_failed']}")
        elif event == "note" and (failed := _hook_failure(fields)):
            self._log(logging.WARNING, f"[error] {task.key if task is not None else '?'}: {failed}")
        elif event == "note" and isinstance(fields.get("context_warned"), dict) and task is not None:
            w = fields["context_warned"]
            peak, budget = w.get("peak_context") or 0, w.get("context_budget") or 0
            share = f" ({100 * peak // budget}% of context_budget {budget})" if budget else ""
            self._log(
                logging.WARNING,
                f"[context] {task.key}: peak context {peak} tokens{share}, past context_warn_pct {w.get('context_warn_pct')}%",
            )

    def progress(self, line: str, *, warning: bool = False) -> None:
        """A progress line of the run's (a recording's file kept by hash, its summary): to
        the caller's `log`, else to this module's logger, at WARNING with `warning`."""
        self._log(logging.WARNING if warning else logging.INFO, line)

    def _log(self, level: int, line: str) -> None:
        """A progress line to the caller's `log`, else to this module's logger at `level`:
        a refused duplicate or a flow callback that raised is a warning, a retry is routine."""
        if self._log_to is not None:
            self._log_to(line)
        else:
            _logger.log(level, "%s", line)

    def _record_plan(self, task: Task) -> None:
        """Record every task a queue accepts, with its dependencies and its origin, in
        `plan.jsonl`: the monitor draws the pipeline from it, including the
        work that has not started yet (the journal only knows what finished).
        A task with no origin (built by hand) has an empty `flow` and `created_from`, and
        `flow_call` null. `base_kind` is there only for an implementation kind, `credential`
        only for a task whose call names one (`Task.credential`), `input_files` only for a task
        whose params (its payload's, as JSON) hold input files."""
        origin = task.origin
        row = PlanRow(
            ts=now_iso(),
            key=task.key,
            kind=kind_name(task.kind),
            unit=self._unit_of(task),
            claims=list(task.claims),
            after=list(task.after),
            priority=task.priority,
            executor=task.executor,
            flow=list(origin.flow) if origin is not None else [],
            created_from=list(origin.created_from) if origin is not None else [],
            given_from=list(origin.given_from) if origin is not None else [],
            flow_call=origin.flow_call if origin is not None else None,
            base_kind=task.base_kind,
            credential=task.credential,
            input_files=input_files_of(getattr(task.payload, "params", None)),
        ).to_dict()
        self._append(layout.PLAN, row)
        if self._estimates is not None:
            self._estimates.observe_plan(row)

    def _record_deferral(self, task: Task, reason: str, cause: DeferralCause | None) -> None:
        """Record a task the queue deferred in `deferred.jsonl` (a `DeferredRow`): the
        monitor names why it did not run. A task deferred after it started (its runner found
        no way to launch it) loses its running marker too."""
        self._mark_inflight(task, running=False)
        row = DeferredRow(ts=now_iso(), key=task.key, kind=kind_name(task.kind), unit=self._unit_of(task), reason=reason, cause=cause)
        self._append(layout.DEFERRED, row.to_dict())
        self._log(logging.INFO, f"[deferred] {task.key}: {reason}")

    def _record_rest(self, event: str, rest: Rest) -> None:
        """One line of `rests.jsonl` (a `RestEvent`): `event` `start` when the credential
        began resting, `end` when it was found not resting again (with the rest that ended)."""
        row = RestEvent.model_validate({"ts": now_iso(), "event": event, **rest.to_dict()})
        try:
            self._append(layout.RESTS, row.model_dump(mode="json", exclude_unset=True))
        except Exception as exc:  # the monitor's record only: the rest itself holds
            self._record_failed(layout.RESTS, exc, f"credential {rest.credential}")
        self._log(logging.INFO, f"[rest] {rest.text()}" if event == "start" else f"[rest] {rest.credential} rests no more")

    def record_flow_call(
        self,
        event: str,
        call_id: str,
        *,
        parent: str | None = None,
        function: str = "",
        flow: Sequence[Frame] = (),
        state: FlowState | None = None,
        error: BaseException | None = None,
        time_box: TimeBox | None = None,
        started_at: float | None = None,
        raised_at: Frame | None = None,
        raised_by: str | None = None,
        unawaited: Sequence[str] = (),
        ended_at: float | None = None,
    ) -> None:
        """One line of `flow_calls.jsonl` (a `FlowCallRow`). `event` "start": its `parent`,
        `function` and `flow`, the flow path where the parent created it (the parent's frames,
        with their loops' passes, as in `plan.jsonl`; empty for a top flow call), and for a
        flow call started through `time_box`, its `time_box` (a `TimeBoxRecord`). `started_at`
        (`time.time()`): when the flow call started, where a time box's deadline counts from,
        and the start row's `ts`; a flow call may go on record after it started (`FlowDriver`).
        "end": its `state` and `error`, `raised_at` and `raised_by` when given, and for a top
        flow call the keys of its `unawaited` tasks when there are any; `ended_at`
        (`time.time()`): when it ended, the end row's `ts` (a top flow call's end may be
        recorded once the flow calls it started have ended)."""
        ts = now_iso()
        if event == "start":
            ts = iso_of(started_at) if started_at is not None else ts
            box = {"time_box": _time_box_record(time_box, started_at)} if time_box is not None else {}
            start = {"ts": ts, "id": call_id, "event": "start", "parent": parent, "function": function, "flow": list(flow)}
            row = FlowCallRow.model_validate(start | box)
        else:
            ts = iso_of(ended_at) if ended_at is not None else ts
            error_text = f"{type(error).__name__}: {error}" if error is not None else None
            end: dict[str, Any] = {"ts": ts, "id": call_id, "event": "end", "state": state, "error": error_text}
            if raised_at is not None:
                end["raised_at"] = raised_at
            if raised_by is not None:
                end["raised_by"] = raised_by
            if unawaited:
                end["unawaited"] = list(unawaited)
            row = FlowCallRow.model_validate(end)
        self._append(layout.FLOW_CALLS, row.to_dict())
        if event == "end" and self._estimates is not None:
            self._estimates.flow_call_ended(call_id, state or "")

    def _append(self, name: str, row: dict[str, Any]) -> None:
        append_lines(self.dir / name, [json.dumps(row)])

    def _mark_inflight(self, task: Task, *, running: bool) -> None:
        """One marker per running task, so the monitor can show it even when
        nothing is a child process (a Python task, a backend that is a
        library call). It holds the process's pid and start (`processes.start_ticks`):
        a marker whose process is gone, or whose pid another process now has, is ignored
        by the monitor, so a crash leaves nothing that looks live, and a resume removes
        the markers an earlier attempt left (`_clear_inflight`)."""
        (self.dir / layout.INFLIGHT).mkdir(exist_ok=True)
        path = self.dir / layout.task_entry(layout.INFLIGHT, task.key)
        if not running:
            path.unlink(missing_ok=True)
            return
        write_document(
            path,
            json.dumps(
                {
                    "key": task.key,
                    "kind": kind_name(task.kind),
                    "unit": self._unit_of(task),
                    "claims": list(task.claims),
                    "executor": task.executor,
                    "started_at": now_iso(),
                    "pid": os.getpid(),
                    "start_ticks": processes.start_ticks(os.getpid()),
                }
            ),
        )


def _hook_failure(fields: Mapping[str, Any]) -> str:
    """What a queue's note says of a callback that raised around a task (`WorkQueue`: its
    result's recording, its deferral check, the completion of its fingerprint); "" for
    another note."""
    if "record_failed" in fields:
        return f"recording its result raised {fields['record_failed']}"
    if "deferral_failed" in fields:
        return f"its deferral check raised {fields['deferral_failed']}; launched"
    if "starting_failed" in fields:
        return f"completing its fingerprint raised {fields['starting_failed']}; launched without it, so a resume runs it again"
    return ""


def _time_box_record(box: TimeBox, started_at: float | None) -> TimeBoxRecord:
    """`box` as `flow_calls.jsonl` records it; `started_at`: when its flow call started
    (`time.time()`), now when None."""
    return TimeBoxRecord(
        started_at=iso_of(started_at) if started_at is not None else now_iso(),
        deadline_s=box.deadline_s,
        grace_s=box.grace_s,
        slack_s=box.slack_s,
        finishing_kinds=tuple(sorted(box.finishing_kinds)),
    )
