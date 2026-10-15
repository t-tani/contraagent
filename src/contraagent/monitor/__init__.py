"""Live monitoring of a pipeline run: journal, plan, process tree, agent transcripts.

    from contraagent.monitor import Monitor, serve
    serve(Monitor("runs"), port=8787)

Read-only: it tails what `contraagent.execution.run.Run` writes under `runs/<run>/`
and never touches the pipeline. The web server (`serve`, `create_app`, from
`contraagent.monitor.server`, imported when first named) needs the `monitor` extra
(`pip install contraagent[monitor]`: fastapi, uvicorn, sse-starlette); `Monitor`
itself and the response models in `contraagent.monitor.api` do not.
"""

from typing import TYPE_CHECKING, Any

from contraagent.monitor.core import Monitor, Panel, Period, PeriodRuns, RunRecords

if TYPE_CHECKING:
    from contraagent.monitor.server import create_app, serve

__all__ = ["Monitor", "Panel", "Period", "PeriodRuns", "RunRecords", "create_app", "serve"]


def __getattr__(name: str) -> Any:
    if name in ("create_app", "serve"):
        from contraagent.monitor import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
