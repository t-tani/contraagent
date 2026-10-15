"""The run journal: one `JournalRow` per finished task attempt.

`runs/<id>/journal.jsonl` is what the monitor draws and what a resumed run
reads to skip finished work; `runs/<id>/launches.jsonl` keeps the full
`LaunchResult` of every agent launch beside it.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from contraagent.backends.process import signal_of
from contraagent.dispatch.records import TokenUsage
from contraagent.dispatch.task import Task, TaskResult, kind_name
from contraagent.execution.schemas import JournalRow, QuotaReading


def _usage(o) -> TokenUsage | None:
    """The attempt's tokens; None when the launch reported no API call."""
    if o is None or not (o.usage.calls or o.usage.output_total):
        return None
    u = o.usage
    return TokenUsage(
        input=u.input,
        output=max(u.output, u.output_total),
        cache_read=u.cache_read,
        cache_creation=u.cache_creation,
        calls=u.n_calls,
        resident=u.resident if u.calls else None,
        peak_context=u.peak_context if u.calls else None,
        context_window=o.context_window,
    )


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


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
        row_extras: Callable[[TaskResult], dict] | None = None,
    ) -> None:
        self.path = Path(path)
        self.launches_path = Path(launches_path)
        self.run_id = run_id
        self.run_group = run_group
        self._unit_of = unit_of
        self._row_extras = row_extras
        self._lock = threading.Lock()

    def row(self, result: TaskResult) -> JournalRow:
        """The journal row for one finished attempt."""
        o = result.launch_result
        exit_code = o.exit_code if o is not None else None
        task = result.task
        return JournalRow(
            ts=utcnow_iso(),
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
            rounds=(getattr(o, "rounds", None) if o is not None else result.rounds),
            round_errors=[list(errors[:5]) for errors in (o.round_errors if o is not None else result.round_errors)],
            hook_errors=[list(errors[:5]) for errors in o.hook_errors] if o is not None else [],
            usage=_usage(o),
            cost_usd=(round(o.cost_usd, 6) if o is not None and o.cost_usd is not None else None),
            quota=[
                QuotaReading(**{k: getattr(r, k) for k in QuotaReading.model_fields})
                for r in (o.rate_limits if o is not None else [])
                if r.five_hour_pct is not None or r.seven_day_pct is not None
            ],
            web_queries=list(o.web_queries) if o is not None else [],
            unread_events=dict(o.unread_events) if o is not None else {},
            changes=result.changes,
            context_budget=getattr(o, "context_budget", None),
            context_warned=bool(getattr(o, "context_warned", False)),
            fingerprint=task.fingerprint,
            flow_call=task.origin.flow_call if task.origin is not None else None,
            replayed=result.replayed,
            **(self._row_extras(result) if self._row_extras else {}),
        )

    def append(self, result: TaskResult) -> JournalRow:
        """Append one row, plus the full `LaunchResult` when the attempt was an agent launch.
        Returns the row."""
        row = self.row(result)
        line = row.model_dump_json() + "\n"
        with self._lock, open(self.path, "a") as f:
            f.write(line)
        if result.launch_result is not None:
            result.launch_result.record(self.launches_path)
        return row

    def rows(self) -> list[dict]:
        """Every row on disk, as dicts (a domain's extra columns included)."""
        try:
            lines = self.path.read_text().splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def last_rows(self) -> dict[str, dict]:
        """Each key's last row: what a resume compares a task with."""
        return {r["key"]: r for r in self.rows() if r.get("key")}
