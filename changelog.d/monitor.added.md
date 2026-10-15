**The monitor.** `contraagent monitor` (the `monitor` extra) serves a live, read-only
view of every run: the overview (state, problems, outputs, cost, tokens, models,
subscription usage, the pipeline graph by function and loop, the timeline), the scheduled
tasks, the history of attempts, each task's detail with its transcript, inputs, outputs
and checks, and the task definitions. It speaks English and Japanese and has light, dark
and high-contrast themes. Its HTTP and Server-Sent Events API is described by
`openapi.json` (`contraagent.monitor.api`).

- The Trends page sums the runs of a period: cost by day and kind, tasks, models,
  failures, usage, rests and deferrals.
- A pipeline adds views of its own (`contraagent.monitor.Panel`): tiles, tables, charts,
  status grids and notes, per run or over a period (`--panels views.py:PANELS`).
- `contraagent monitor export` writes the views of the newest runs as static files that
  any web server serves.
