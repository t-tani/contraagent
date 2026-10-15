"""One run of a pipeline: its directory, journal, lock, and queue wiring.

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
    rests.jsonl             each start and end of a credential's quota rest (`routing.quota`)
    inflight/<key>.json     one marker per running task
    contracts/, definitions/  what each task declared, for the monitor

and the run lock `runs/<run-id>.lock`, which refuses a second process
driving the same run id: two drivers would launch the same work twice and
bill for it twice.

It builds `WorkQueue`s that journal every result, record the plan and mark
running tasks, and reads its own journal back (`Journal`) so a resumed
run skips the work a previous attempt finished: a key whose last journal row
is ok and carries the task's `fingerprint`.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import logging
import os
import sys
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from contraagent import procfs
from contraagent.backends.base import Backend
from contraagent.backends.launch import RateLimit, Stop
from contraagent.dispatch.flow import FlowState
from contraagent.dispatch.interceptors import ResultEnricher, TaskScope
from contraagent.dispatch.python_task import make_python_task
from contraagent.dispatch.queue import WorkQueue
from contraagent.dispatch.records import DeferralCause, Frame, Rest, RestEvent
from contraagent.dispatch.task import STOP_PARTIAL, Task, TaskResult, TimeBox, kind_name
from contraagent.errors import ContraagentError
from contraagent.execution import teardown as _teardown
from contraagent.execution.cursor import CursorStore
from contraagent.execution.estimates import JournalEstimates, recent_runs
from contraagent.execution.journal import Journal
from contraagent.execution.pipeline_files import writing_into
from contraagent.execution.python_tasks import PythonTaskRunner
from contraagent.execution.runner import AgentRunner
from contraagent.execution.schemas import DeferredRow, FlowCallRow, PlanRow
from contraagent.routing.capacity import sized
from contraagent.routing.config import PipelineConfig
from contraagent.routing.quota import QuotaRests, QuotaRule, caps_of
from contraagent.runs import layout
from contraagent.runs.files import append_lines, parse_rows, write_document
from contraagent.runs.source import DirectorySource, parse_info
from contraagent.runs.times import now_iso

_logger = logging.getLogger(__name__)

#: A launch that never ran is retried once by the queue; a rate limit counts
#: toward its throttle. These are the stop values naming those cases.
RETRY_ON = frozenset({Stop.API_ERROR.value, Stop.NO_OUTPUT.value, Stop.LAUNCH_FAILED.value})
THROTTLE_ON = frozenset({Stop.RATE_LIMITED.value})


def finished_before(row: dict | None, task: Task) -> bool:
    """Whether `row`, its key's last journal row, shows `task` finished: ok and not
    `partial`, with the task's fingerprint. What a resume skips; never a task that reruns
    on resume (`Task.rerun_on_resume`)."""
    if task.rerun_on_resume or row is None or row.get("stop") == STOP_PARTIAL:
        return False
    return bool(row.get("ok")) and row.get("fingerprint", "") == task.fingerprint


def resume_skip(last: Mapping[str, dict]) -> Callable[[Task], bool]:
    """What a resume skips, given each key's last journal row: a task `finished_before`,
    unless it waits for a task that runs again because its last result was `partial`, or
    for one that runs again for that reason in turn. Its output was made from a
    placeholder, which a fingerprint does not show when the flow passed the output on
    without receiving it. Asked once per task, as it is queued."""
    again: set[str] = set()

    def skip(task: Task) -> bool:
        row = last.get(task.key)
        stale = not again.isdisjoint(task.after)
        if stale or (row is not None and row.get("stop") == STOP_PARTIAL):
            again.add(task.key)
        return not stale and finished_before(row, task)

    return skip


def _name_of(fn: Callable) -> str:
    """A callable's `module.qualname`, as `run.json` names a quota rule."""
    fn = getattr(fn, "__func__", fn)
    qualname = getattr(fn, "__qualname__", "") or type(fn).__qualname__
    return f"{getattr(fn, '__module__', '') or ''}.{qualname}".lstrip(".")


class RunLocked(ContraagentError):
    """Another process already holds this run id."""


class RunExists(ContraagentError):
    """The run id already holds a run, and the caller did not ask to resume it."""


class Run:
    """One run of a pipeline: `runs/<run-id>/`, its journal, its lock, and its queues."""

    def __init__(
        self,
        run_id: str,
        runs_dir: str | Path = "runs",
        *,
        run_group: str = "",
        lock: bool = True,
        row_extras: Callable[[TaskResult], dict] | None = None,
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
        `contraagent.pipeline_table` reads in the run (none without it)."""
        self.run_id = run_id
        self.run_group = run_group or run_id
        self.runs_dir = Path(runs_dir)
        self.dir = self.runs_dir / run_id
        self.config = config
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / layout.STREAMS).mkdir(exist_ok=True)
        # A task given no unit has it defaulted to its own key, which names
        # no unit; the journal row then carries an empty unit.
        self._unit_of = unit_of or (lambda t: t.declared_unit)
        self.journal = Journal(
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
        if lock:
            self._acquire()
        write_document(
            self.dir / layout.RUN_INFO,
            json.dumps(
                {
                    "run_id": run_id,
                    "run_uid": self._previous_uid() or uuid.uuid4().hex,
                    "host_id": layout.host_id(),
                    "run_group": self.run_group,
                    "pid": os.getpid(),
                    "start_ticks": procfs.pid_start_ticks(os.getpid()),
                    "argv": list(sys.argv),
                    "cwd": str(Path(cwd or os.getcwd()).resolve()),
                    "started_at": now_iso(),
                }
            ),
        )

    def _previous_uid(self) -> str | None:
        """The `run_uid` of an earlier attempt of this run id: a resumed run keeps it."""
        uid = (self._info() or {}).get("run_uid")
        return uid if isinstance(uid, str) and uid else None

    # --- lock and lifecycle ------------------------------------------------

    def _acquire(self) -> None:
        """Hold an flock until `close()` or process exit. Process exit, normal or
        killed, always releases it, which is what makes this safe under SIGKILL."""
        path = self.runs_dir / f"{self.run_id}.lock"
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise RunLocked(
                f"another process already holds run id {self.run_id!r} ({path}); wait for it or pick a different run id"
            ) from None
        self._lock_fd = fd

    def close(self) -> None:
        """Release the run lock (process exit releases it too), and put back the signal
        handlers `stop_on_signals` replaced."""
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

    def __exit__(self, *exc) -> None:
        writing, self._writing = self._writing, None
        try:
            self.close()
        finally:
            if writing is not None:
                writing.__exit__(None, None, None)

    def cursor(self, *, stages=None, steps=None, skip_when_completed=()) -> CursorStore:
        """This run's resume cursor, at `runs/<id>/cursor.json` where the monitor
        looks for it. `stages` / `steps` are the legal vocabulary (see `CursorStore`)."""
        return CursorStore(self.dir / layout.CURSOR, self.run_id, stages=stages, steps=steps, skip_when_completed=skip_when_completed)

    def finish(self) -> None:
        """Mark the run finished in run.json. The monitor then shows it as no
        longer live even while this process stays up (to serve a monitor, say)."""
        self.update_info(finished_at=now_iso())

    def update_info(self, **fields) -> None:
        """Merge `fields` into run.json (what the monitor shows about this run)."""
        info = self._info() or {}
        info.update(fields)
        write_document(self.dir / layout.RUN_INFO, json.dumps(info))

    def _info(self) -> dict | None:
        """`run.json` as this run directory holds it; None before the first write."""
        try:
            return parse_info((self.dir / layout.RUN_INFO).read_text())
        except OSError:
            return None

    def on_teardown(self, callback: Callable[[], None]) -> None:
        """Register a stop callback (a server, a VM lease) for `teardown`."""
        self._teardown_callbacks.append(callback)

    def teardown(self) -> None:
        """Stop the live agents and every registered callback. Idempotent, never raises.

        Reached from the main thread, a signal handler and atexit, possibly
        overlapping (a SIGTERM landing mid-teardown), so the flag is claimed
        under a lock. Non-blocking: a signal handler that finds a teardown
        already under way on its own thread must return, not wait on itself.
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
        agents, whose sessions of their own a terminal's Ctrl-C does not reach. Only on the
        main thread (Python's signal handlers live there); elsewhere it does nothing."""
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
        Pass as `RetryingRunner(on_attempt=run.record_attempt)`."""
        row = self.journal.append(result)
        if self._estimates is not None:
            self._estimates.observe_attempt(row.model_dump())
        launched = result.launch_result
        rounds = launched.rounds if launched is not None else None
        line = f"[end] {result.task.key}: {result.stop} in {result.wall_s:.1f}s"
        if rounds and rounds > 1 and launched is not None and launched.round_errors and launched.round_errors[0]:
            # Why the first round went back: the fix-up is otherwise only a count here.
            first = " ".join(launched.round_errors[0][0].split())
            # A path in the run's directory as the run names it, so the cause fits in the line.
            for root in (str(self.dir.resolve()) + os.sep, str(self.dir) + os.sep):
                first = first.replace(root, "")
            line += f", {rounds} rounds (round 1: {first[:160]}{'…' if len(first) > 160 else ''})"
        elif rounds and rounds > 1:
            line += f", {rounds} rounds"
        line += ", output unwrapped from the final message" if launched is not None and launched.unwrapped else ""
        line += f", on {result.route}" if len(result.hops) > 1 else ""
        self._log(logging.INFO, line)

    def rows(self) -> list[dict]:
        return self.journal.rows()

    # --- running tasks -----------------------------------------------------

    def agent_runner(self, backends: Backend | Mapping[str, Backend], configs: Mapping, **kwargs) -> AgentRunner:
        """An `AgentRunner` whose launches are attributed to this run and recorded under it."""
        return AgentRunner(backends, configs, run_dir=self.dir, run_id=self.run_id, **kwargs)

    def python_runner(
        self,
        inner=None,
        adapter=None,
        cwd: str | Path | None = None,
        *,
        scopes: Sequence[TaskScope] = (),
        enrichers: Sequence[ResultEnricher] = (),
        recorder=None,
        replay=None,
    ) -> PythonTaskRunner:
        """The runner for a queue that mixes Python tasks with agent tasks: Python
        tasks run in-process with their declared contracts checked, agent tasks go
        to `inner` (`RetryingRunner(...)`). Each attempt of a Python task is journaled:
        a retried one here, the last by the queue. `scopes` / `enrichers` wrap each
        attempt of a Python task, `recorder` keeps each attempt's recording and `replay` plays
        it (`PythonTaskRunner`)."""
        return PythonTaskRunner(
            inner,
            adapter=adapter,
            run_dir=self.dir,
            cwd=cwd,
            on_failed_attempt=self.record_attempt,
            scopes=scopes,
            enrichers=enrichers,
            config=self.config,
            recorder=recorder,
            replay=replay,
        )

    def estimator(self) -> JournalEstimates:
        """The estimates of durations and tails (`JournalEstimates`): read from the recent
        runs when first asked for, then told of this run's plan rows, attempts and flow
        call ends as they are recorded."""
        if self._estimates is None:
            self._estimates = JournalEstimates(self.runs_dir)
        return self._estimates

    def quota_rests(self, credentials: Mapping, rule: QuotaRule | None = None, **kwargs) -> QuotaRests:
        """The run's quota rests (`routing.quota`) over `credentials`, told the utilization
        readings of the recent runs' journals (this run's included, when resumed): an
        account's windows outlast a run. `kwargs`: `finishing_kinds`, `grace_s`.
        `run.json` records the caps (`quota_caps`, by credential) and the rule's name
        (`quota_rule`, '' for none); `rests.jsonl` each start and end of a rest."""
        rests = QuotaRests(credentials, rule, on_change=self._record_rest, **kwargs)
        caps = {c.credential: c.model_dump(exclude={"credential"}, exclude_none=True) for c in caps_of(credentials)}
        self.update_info(quota_caps=caps, quota_rule=_name_of(rule) if rule is not None else "")
        fields = {f.name for f in dataclasses.fields(RateLimit)}
        source = DirectorySource(self.runs_dir)
        for run in recent_runs(source):
            for row in parse_rows(source.lines(run, layout.JOURNAL)[0]):
                for reading in row.get("quota") or ():
                    if isinstance(reading, dict):
                        rests.observe(RateLimit(**{k: v for k, v in reading.items() if k in fields}))
        return rests

    def queue(self, runner, *, follow_up: Callable[[TaskResult], list[Task]] | None = None, resume: bool = False, **kwargs) -> WorkQueue:
        """A `WorkQueue` over `runner` that records the plan and journals Python tasks.

        Agent tasks are journaled per attempt by `RetryingRunner(on_attempt=
        run.record_attempt)`, so nothing is written twice. `resume=True` skips every
        task an earlier attempt finished (`resume_skip`). `kwargs` pass through
        (`max_concurrent`, `claim_capacity`, `finishing_kinds`, `deadline_s`...);
        `retry_on`/`throttle_on` default to the stop sets above; a `PerTask` entry of
        `claim_capacity` is sized by this host (`routing.capacity`).
        """
        if kwargs.get("claim_capacity"):
            kwargs["claim_capacity"] = sized(kwargs["claim_capacity"])
        kwargs.setdefault("retry_on", RETRY_ON)
        kwargs.setdefault("throttle_on", THROTTLE_ON)
        kwargs.setdefault("estimate", self.estimator().estimate)
        if resume:
            kwargs.setdefault("skip", resume_skip(self.journal.last_rows()))
        q = WorkQueue(runner, follow_up=follow_up, on_event=self._on_event, on_result=self._journal_python_task, **kwargs)
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

    def _journal_python_task(self, res: TaskResult, attempt: int) -> None:
        if res.task.fn is not None:
            self.record_attempt(res)

    def _on_event(self, event: str, task: Task | None, **fields) -> None:
        if event == "queued" and task is not None:
            self._record_plan(task)
        elif event in ("start", "end") and task is not None:
            self._mark_inflight(task, running=event == "start")
            if event == "start":
                self._log(logging.INFO, f"[start] {task.key}")
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
        `flow_call` null. `base_kind` is there only for an implementation kind."""
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
            flow_call=origin.flow_call if origin is not None else None,
            base_kind=task.base_kind,
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
        self._append(layout.RESTS, row.model_dump(mode="json", exclude_unset=True))
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
    ) -> None:
        """One line of `flow_calls.jsonl` (a `FlowCallRow`). `event` "start": its `parent`,
        `function` and `flow`, the flow path where the parent yielded it (the parent's frames,
        with their loops' passes, as in `plan.jsonl`; empty for a top flow call), and for a
        flow call yielded through `time_box`, its `time_box` (`TimeBox.record`; `started_at`:
        when the flow call started, where its deadline counts from); "end": its `state` and
        `error`."""
        ts = now_iso()
        if event == "start":
            box = {"time_box": time_box.record(started_at)} if time_box is not None else {}
            start = {"ts": ts, "id": call_id, "event": "start", "parent": parent, "function": function, "flow": list(flow)}
            row = FlowCallRow.model_validate(start | box)
        else:
            error_text = f"{type(error).__name__}: {error}" if error is not None else None
            row = FlowCallRow(ts=ts, id=call_id, event="end", state=state, error=error_text)
        self._append(layout.FLOW_CALLS, row.to_dict())
        if event == "end" and self._estimates is not None:
            self._estimates.flow_call_ended(call_id, state or "")

    def _append(self, name: str, row: dict) -> None:
        append_lines(self.dir / name, [json.dumps(row)])

    def _mark_inflight(self, task: Task, *, running: bool) -> None:
        """One marker per running task, so the monitor can show it even when
        nothing is a child process (a Python task, a backend that is a
        library call). A marker whose process is gone is ignored by the monitor,
        so a crash leaves nothing that looks live."""
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
                }
            ),
        )
