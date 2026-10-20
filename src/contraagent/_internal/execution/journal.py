"""The run journal: one `JournalRow` per finished task attempt.

`runs/<id>/journal.jsonl` is what the monitor draws and what a resumed run
reads to skip finished work; `runs/<id>/launches.jsonl` keeps the full
`LaunchResult` of every agent launch beside it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from contraagent._internal.backends.process import signal_of
from contraagent._internal.dispatch.task import Task, TaskResult, kind_name
from contraagent._internal.execution.schemas import JournalRow
from contraagent._internal.runs.files import append_lines, read_rows
from contraagent._internal.runs.times import now_iso


class Journal:
    """Appends journal rows and reads them back. Safe from worker threads."""

    def __init__(
        self,
        path: Path,
        launches_path: Path,
        *,
        run_id: str,
        run_group: str,
        unit_of: Callable[[Task], str],
        row_extras: Callable[[TaskResult], dict[str, Any]] | None = None,
    ) -> None:
        self.path: Path = Path(path)
        self.launches_path: Path = Path(launches_path)
        self.run_id = run_id
        self.run_group = run_group
        self._unit_of = unit_of
        self._row_extras = row_extras
        #: Why a resume runs each task again that an earlier attempt finished, by key
        #: (`resume_skip`): the `rerun` of each of its rows.
        self.reruns: dict[str, str] = {}

    def row(self, result: TaskResult) -> JournalRow:
        """The journal row for one finished attempt."""
        o = result.launch_result
        exit_code = o.exit_code if o is not None else None
        task = result.task
        return JournalRow(
            ts=now_iso(),
            run_id=self.run_id,
            run_group=self.run_group,
            key=task.key,
            attempt=task.attempt,
            kind=kind_name(task.kind),
            executor=task.executor,
            unit=self._unit_of(task),
            agent=o.agent if o is not None else "",
            model=o.model if o is not None else "",
            credential=o.credential if o is not None else "",
            route=result.route,
            hops=list(result.hops),
            skipped_hops=list(result.skipped_hops),
            stop=result.stop,
            ok=result.ok,
            wall_s=round(result.wall_s, 1),
            exit_code=exit_code,
            signal=signal_of(exit_code),
            reason=result.reason,
            rounds=result.rounds,
            round_errors=[list(errors[:5]) for errors in result.round_errors],
            max_corrections=result.max_corrections,
            hook_errors=[list(errors[:5]) for errors in o.hook_errors] if o is not None else [],
            usage=o.usage.totals(o.context_window) if o is not None else None,
            cost_usd=(round(o.cost_usd, 6) if o is not None and o.cost_usd is not None else None),
            quota=[r for r in (o.quota if o is not None else []) if r.five_hour_pct is not None or r.seven_day_pct is not None],
            web_queries=list(o.web_queries) if o is not None else [],
            safety_stops=list(o.safety_stops) if o is not None else [],
            unread_events=dict(o.unread_events) if o is not None else {},
            changes=result.changes,
            context_budget=getattr(o, "context_budget", None),
            context_warned=bool(getattr(o, "context_warned", False)),
            fingerprint=task.fingerprint,
            outside=task.outside,
            rerun=self.reruns.get(task.key, ""),
            flow_call=task.origin.flow_call if task.origin is not None else None,
            replayed=result.replayed,
            **(self._row_extras(result) if self._row_extras else {}),
        )

    def append(self, result: TaskResult, on_launch_error: Callable[[Exception], None] | None = None) -> JournalRow:
        """Append one row, plus the full `LaunchResult` when the attempt was an agent launch.
        Returns the row. `on_launch_error(error)`: the `LaunchResult` could not be written
        (the row was); without it, the error is raised."""
        row = self.row(result)
        append_lines(self.path, [row.model_dump_json()])
        if result.launch_result is not None:
            try:
                result.launch_result.record(self.launches_path)
            except Exception as exc:
                if on_launch_error is None:
                    raise
                on_launch_error(exc)
        return row

    def rows(self) -> list[dict[str, Any]]:
        """Every row on disk, as dicts (a domain's extra columns included)."""
        return read_rows(self.path)

    def last_rows(self) -> dict[str, dict[str, Any]]:
        """Each key's last row: what a resume compares a task with."""
        return {r["key"]: r for r in self.rows() if r.get("key")}
