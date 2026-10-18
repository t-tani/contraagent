"""A page of the pipeline's own, served by the monitor and shown as a tab of each run.

    contraagent monitor --runs-dir runs --apps path/to/page.py:APPS --panels path/to/page.py:PANELS

The page is an ASGI app with its own routes: the HTML, and the data its script reads.
The monitor serves it under `apps/attempts/`, and a run panel shows it in a frame with
the run's id in its URL. The page names its own routes by relative URLs (`data`), so it
works behind any base path the monitor is served under.
"""

from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from contraagent.monitor import DirectorySource, EmbedBody, Panel, RunRecords

#: Where the runs are: the same directory the monitor reads.
RUNS = DirectorySource(os.environ.get("RUNS_DIR", "runs"))

PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Attempts</title>
<style>
  body { font: 14px system-ui, sans-serif; margin: 12px; }
  body[data-theme="dark"] { background: #111; color: #eee; }
</style>
<ul id="rows"></ul>
<script type="module">
  const q = new URLSearchParams(location.search);
  document.body.dataset.theme = q.get("theme") ?? "light";
  const rows = await (await fetch(`data?run=${encodeURIComponent(q.get("run") ?? "")}`)).json();
  for (const r of rows) {
    const li = document.createElement("li");
    li.textContent = `${r.key}: ${r.stop}`;
    document.querySelector("#rows").append(li);
  }
</script>
</html>"""


async def page(request: Request) -> HTMLResponse:
    return HTMLResponse(PAGE)


async def data(request: Request) -> JSONResponse:
    """The run's attempts: each task's key and how it ended."""
    rows = RunRecords(request.query_params["run"], RUNS).journal()
    return JSONResponse([{"key": r.get("key", ""), "stop": r.get("stop", "")} for r in rows])


def attempts(run: RunRecords) -> EmbedBody:
    """The run panel: the page, for this run, in a frame."""
    return EmbedBody(url=f"apps/attempts/?run={run.id}")


#: What `contraagent monitor --apps page.py:APPS` serves, under apps/attempts/.
APPS = {"attempts": Starlette(routes=[Route("/", page), Route("/data", data)])}

#: What `contraagent monitor --panels page.py:PANELS` loads.
PANELS = {"attempts": Panel(attempts, title="Attempts", description="Each attempt of the run, on a page of its own")}
