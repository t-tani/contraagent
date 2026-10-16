`contraagent monitor` (the `monitor` extra) serves a live, read-only view of every run:
its state, problems, outputs, cost, tokens and subscription usage, the pipeline graph,
the timeline, and each task with its transcript, inputs, outputs and checks. A Trends
page sums the runs of a period, and a pipeline adds views of its own
(`contraagent.monitor.Panel`). The monitor speaks English and Japanese, with light, dark
and high-contrast themes, and `openapi.json` describes its HTTP API.
`contraagent monitor export` writes the views of the newest runs as static files that any
web server serves.
