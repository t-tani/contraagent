"""A pipeline's own views in the monitor: a run's spend by kind, and the cost by day over a period.

    contraagent monitor --runs-dir runs --panels path/to/views.py:PANELS

Each panel returns a typed body (`contraagent.monitor.api`): tiles, a table and
charts, which the monitor draws with its own elements; any other dict would be shown
as a JSON tree. A run panel reads its run through the `RunRecords` it is given, a
trends panel the runs of its period through the `PeriodRuns` it is given, wherever the
monitor reads them (a runs directory or a hub).
"""

from __future__ import annotations

from collections import defaultdict

from contraagent.monitor import Panel, Period, PeriodRuns, RunRecords
from contraagent.monitor.api import (
    BlocksBody,
    ChartSeries,
    ColumnsBody,
    HBar,
    HBarsBody,
    PanelTile,
    TableBody,
    TableColumn,
    TilesBody,
)


def spend(run: RunRecords) -> BlocksBody:
    """A run's attempts by kind: what they cost, how many ended well, how long they took."""
    rows = run.journal()
    kinds: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        kinds[r["kind"]].append(r)
    cost = sum(r.get("cost_usd") or 0 for r in rows)
    return BlocksBody(
        blocks=[
            TilesBody(
                tiles=[
                    PanelTile(id="attempts", label="Attempts", value=len(rows)),
                    PanelTile(id="cost", label="Cost", value=f"${cost:.3f}", sub=[[f"{len(kinds)} kinds"]]),
                ],
            ),
            TableBody(
                title="By kind",
                columns=[
                    TableColumn(id="kind", label="Kind"),
                    TableColumn(id="attempts", label="Attempts", format="number"),
                    TableColumn(id="done", label="Done", format="pct", bar=True),
                    TableColumn(id="cost", label="Cost", format="usd"),
                    TableColumn(id="wall", label="Time", format="duration"),
                ],
                rows=[
                    {
                        "kind": kind,
                        "attempts": len(rs),
                        "done": sum(1 for r in rs if r["ok"]) / len(rs),
                        "cost": sum(r.get("cost_usd") or 0 for r in rs),
                        "wall": sum(r.get("wall_s") or 0 for r in rs),
                        # A kind with a failed attempt: its row takes the failed status.
                        "_tone": "failed" if any(not r["ok"] for r in rs) else None,
                    }
                    for kind, rs in sorted(kinds.items())
                ],
            ),
            HBarsBody(
                title="Time by kind",
                unit="duration",
                bars=[HBar(label=kind, value=sum(r.get("wall_s") or 0 for r in rs)) for kind, rs in sorted(kinds.items())],
            ),
        ],
    )


def cost_by_day(runs: PeriodRuns, period: Period) -> ColumnsBody:
    """The cost of the period's runs by day and kind, stacked: a trends panel. A run may
    begin before the period or end after it: only its attempts that ended inside it count."""
    by: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for run in runs:
        for r in runs.journal(run):
            day = period.day_of(r.get("ts"))  # None outside the period
            if day is not None:
                by[r["kind"]][day.strftime("%m-%d")] += r.get("cost_usd") or 0
    days = [d.strftime("%m-%d") for d in period.days]
    return ColumnsBody(
        title="Cost by day",
        unit="usd",
        stacked=True,
        x=days,
        series=[ChartSeries(name=kind, values=[by[kind].get(d) for d in days]) for kind in sorted(by)],
    )


#: What `contraagent monitor --panels views.py:PANELS` loads, in the order the monitor shows them.
PANELS = {
    "spend": Panel(spend, title="Spend", description="Attempts, cost and time by kind", icon="$"),
    "cost": Panel(cost_by_day, title="Cost by day", icon="▥", scope="trends"),
}
