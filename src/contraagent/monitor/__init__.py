"""The monitor: a read-only live view of runs, as a library and a web UI.

    from contraagent.monitor import Monitor, serve
    serve(Monitor("runs"), port=8787)

It reads what a run writes under `runs/<run>/` and never touches the pipeline. A
`Panel` adds a custom view, its body one of the typed bodies below or any JSON object.
The web server (`serve`, `create_app`) needs the `monitor` extra
(`pip install 'contraagent[monitor]'`: fastapi, uvicorn, sse-starlette) and is imported
when first named; the rest of this module, and the HTTP response models in
`contraagent.monitor.api`, do not.
"""

from typing import TYPE_CHECKING, Any

from contraagent._internal.monitor.api import (
    CODE_CHARACTERS,
    CODE_LINES,
    LANGUAGES,
    PANEL_TYPES,
    BlocksBody,
    ChartSeries,
    CodeBody,
    ColumnsBody,
    GridCell,
    HBar,
    HBarsBody,
    HeatmapBody,
    LinesBody,
    NoteBody,
    PanelBody,
    PanelTile,
    StatusGridBody,
    TableBody,
    TableColumn,
    TilesBody,
    TreeBody,
    TreeLink,
    TreeNode,
)
from contraagent._internal.monitor.core import Monitor, Panel, PanelFn, PeriodRuns, RunRecords, TaskDetailFn, TrendsPanelFn
from contraagent._internal.monitor.export import ExportReport, export
from contraagent._internal.monitor.trends import Period, PeriodError
from contraagent._internal.public import publish
from contraagent._internal.runs.liveness import Liveness
from contraagent._internal.runs.source import DirectorySource, LogPosition, RunFile, RunSource, Stat

if TYPE_CHECKING:
    from contraagent._internal.monitor.server import create_app, serve

__all__ = [
    "CODE_CHARACTERS",
    "CODE_LINES",
    "LANGUAGES",
    "PANEL_TYPES",
    "BlocksBody",
    "ChartSeries",
    "CodeBody",
    "ColumnsBody",
    "DirectorySource",
    "ExportReport",
    "GridCell",
    "HBar",
    "HBarsBody",
    "HeatmapBody",
    "LinesBody",
    "Liveness",
    "LogPosition",
    "Monitor",
    "NoteBody",
    "Panel",
    "PanelBody",
    "PanelFn",
    "PanelTile",
    "Period",
    "PeriodError",
    "PeriodRuns",
    "RunFile",
    "RunRecords",
    "RunSource",
    "Stat",
    "StatusGridBody",
    "TableBody",
    "TableColumn",
    "TaskDetailFn",
    "TilesBody",
    "TreeBody",
    "TreeLink",
    "TreeNode",
    "TrendsPanelFn",
    "create_app",
    "export",
    "serve",
]

_SERVER = ("create_app", "serve")

publish(__name__, [name for name in __all__ if name not in _SERVER])


def __getattr__(name: str) -> Any:
    if name in _SERVER:
        from contraagent._internal.monitor import server

        globals().update({n: getattr(server, n) for n in _SERVER})
        publish(__name__, _SERVER)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
