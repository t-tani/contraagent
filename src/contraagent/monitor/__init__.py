"""Live monitoring of a pipeline run: journal, plan, process tree, agent transcripts.

    from contraagent.monitor import Monitor, serve
    serve(Monitor("runs"), port=8787)

Read-only: it tails what `contraagent.execution.run.Run` writes under `runs/<run>/`
and never touches the pipeline. The web server needs the `monitor` extra
(`pip install contraagent[monitor]`: fastapi, uvicorn, sse-starlette); `Monitor`
itself and the response models in `contraagent.monitor.api` do not.
"""

from contraagent.monitor.core import Monitor, Panel, Period, PeriodRuns, RunRecords

__all__ = ["Monitor", "Panel", "Period", "PeriodRuns", "RunRecords", "create_app", "serve"]


def create_app(monitor: Monitor, **kwargs):
    """See `contraagent.monitor.server.create_app`."""
    from contraagent.monitor.server import create_app as _create_app

    return _create_app(monitor, **kwargs)


def serve(monitor: Monitor, host: str = "127.0.0.1", port: int = 8787, **kwargs) -> None:
    """See `contraagent.monitor.server.serve`."""
    from contraagent.monitor.server import serve as _serve

    _serve(monitor, host, port, **kwargs)
