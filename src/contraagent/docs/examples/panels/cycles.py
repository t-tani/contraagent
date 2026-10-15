"""A pipeline run once an hour, as a trends panel: how each hour's run ended, day by day.

    contraagent monitor --runs-dir runs --panels path/to/cycles.py:PANELS

A status grid (a state per hour and day, each coloured by its tone and named in
words), a note on how to read it, and the runs as a table whose ids lead to each
run in the monitor (a `link` column).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from contraagent.monitor import Panel, Period, PeriodRuns, RunRecords
from contraagent.monitor.api import BlocksBody, GridCell, NoteBody, StatusGridBody, TableBody, TableColumn

HOURS = [f"{h:02d}" for h in range(24)]


def ended(run: RunRecords) -> GridCell:
    """How a run ended: failed when an attempt did, else done; still running without an end."""
    if not run.info().get("finished_at"):
        return GridCell(label="running", tone="running", tip=run.id)
    failed = sum(1 for r in run.journal() if not r.get("ok"))
    if failed:
        return GridCell(label="failed", tone="failed", tip=f"{run.id} | {failed} failed")
    return GridCell(label="done", tone="done", tip=run.id)


def cycles(monitor_url: str = "http://127.0.0.1:8787"):
    """Each hour's run of the period: a grid of how it ended, and the runs by start."""

    def view(runs: PeriodRuns, period: Period) -> BlocksBody:
        tz = ZoneInfo(period.tz)
        days = [(period.start + timedelta(days=i)).strftime("%m-%d") for i in range((period.end - period.start).days + 1)]
        cells: list[list[GridCell | None]] = [[None] * len(HOURS) for _ in days]
        table: list[dict] = []
        for run in runs:
            records = runs.run(run)
            start = datetime.fromisoformat(records.info()["started_at"].replace("Z", "+00:00")).astimezone(tz)
            cell = ended(records)
            day = start.strftime("%m-%d")
            if day in days:
                cells[days.index(day)][start.hour] = cell  # the hour's last run, if it ran twice
            table.append(
                {"run": run, "url": f"{monitor_url}/?run={run}", "started": start.isoformat(), "state": cell.label, "_tone": cell.tone}
            )
        return BlocksBody(
            blocks=[
                NoteBody(text="A cell is the run that started in that hour. **failed**: an attempt of it failed."),
                StatusGridBody(title="Runs by hour", x=HOURS, y=days, cells=cells),
                TableBody(
                    title="Runs",
                    collapsed=True,
                    columns=[
                        TableColumn(id="run", label="Run", link="url"),
                        TableColumn(id="started", label="Started", format="datetime"),
                        TableColumn(id="state", label="State"),
                    ],
                    rows=sorted(table, key=lambda r: r["started"], reverse=True),
                ),
            ],
        )

    return view


#: What `contraagent monitor --panels cycles.py:PANELS` loads.
PANELS = {"cycles": Panel(cycles(), title="Hourly runs", icon="▦", scope="trends")}
