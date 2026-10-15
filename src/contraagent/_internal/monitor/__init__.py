"""Live monitoring of runs: journal, plan, process tree, agent transcripts.

Read-only: it tails what `Run` (`execution/run.py`) writes under `runs/<run>/` and never
touches the pipeline.

* `core`       `Monitor` (every view, as plain data), `Panel`, `RunRecords`, `PeriodRuns`
* `trends`     `Period`, and what the runs of a period add up to
* `aggregate`  token, cost and model sums shared by a run's views and the trends
* `api`        the HTTP contract: one pydantic model per response and live-feed event
* `views`      the view table the routes, the live feed and the export read
* `export`     the views as files a static page reads (`contraagent monitor export`)
* `server`     the web server (`serve`, `create_app`); needs the `monitor` extra
* `static/`    the built web UI (from `web/`); `openapi.json`, the committed contract
"""
