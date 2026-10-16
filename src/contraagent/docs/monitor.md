# The monitor

A live, read-only view of every run, from the `monitor` extra:

```
contraagent monitor --runs-dir runs          # http://127.0.0.1:8787; --help for every option
```

It reads `runs/<id>/` and shows, live, one tab each:

- **Overview**: in the order a reader checks a run: its state, problems with
  their causes and outputs side by side, the tasks running at once (while it
  runs), the scheduled tasks as a layered graph, totals, then where the tokens,
  the cost and the subscription went (by kind, and each model's share of the
  agent sessions by cost, tokens, time or sessions; a failover's hops count on
  their own models), and a timeline. Each card is as wide as its content needs;
  the graph, the totals and the timeline take the whole width;
- **Tasks** and **History**: every task (`kind · unit`) with its status, and
  every finished attempt with its outcome (`journal.jsonl`). A task is one task
  key: each task of the plan (`plan.jsonl`) joined with its journal rows, so
  the passes of a loop over one unit (`review-gamma`, `review-gamma~2`) are two
  tasks, and a task that never ran is one too. The journal columns a pipeline
  adds (`row_extras`) are columns of the history under their own names;
- **Outputs**: every checked file (`OutputContract`, `InputContract`), field
  by field against the file;
- **Definitions**: each kind's interface and its plugin's files;
- **Processes**: the agent sessions and Python tasks running, and the process tree;
- **Task detail**: one task's transcript, one button per agent session
  (attempt, correction, model switch), tailed live, next to its input, output
  and definition. Its input is file by file: each file the task reads, with the
  earlier task whose output it is (or that it was there before the run), then
  the earlier tasks it waits for, each with its other output files. A resumed
  run numbers a task's attempts from 1 again, so an attempt of a later run start
  reads "Attempt 1 | resumed run".

With the keyboard, the tabs are one tab stop: the arrow keys,
Home and End move between them and Enter opens one; the keys 1 to 9 open a tab
from anywhere. `r` opens the run picker, which holds the focus in its search
field until Escape or a pick returns it, and `/` goes to the filter. A row of
Problems, Processes and Definitions opens with Tab and Enter, as do the rows of
Tasks and History.

The graph is drawn from `plan.jsonl` and `flow_calls.jsonl`, so tasks that have
not started are in it too. A layer holds a node per kind (or per group,
`Monitor(groups=)`) for the tasks its flow function created itself, and a node
per function it called as a flow call, which holds that function's own layer;
while a layer holds a single node, the graph goes into it, and stops at a node whose
flow call raised, where that failure shows. Each node has one mark per unit: a
task in a kind node, a flow call in a function node; above 200 marks, a bar of
its counts and its failed units by name. A mark that stands for several tasks
shows the most severe state among them (failed, running, not started, waiting,
skipped, done): a flow call's mark covers its own tasks and those of every flow
call it started, and counts as failed when the call raised or was closed, so a
call that caught a task's failure and returned still shows it failed. A node's
count ("12/13") is its tasks done out of its tasks, those of its flow calls
included, and the tasks not done follow by state ("1 failed | 1 not started");
a function node also names its flow calls that stopped with an error. A kind node
shows who runs its tasks: ✦ and a violet edge for an agent task, ⚙ for a Python
task. A breadcrumb names the layer
(Pipeline › function › loop at flow.py:122), each loop by the file and first line
it is at, so a loop and the loop inside it are told apart. A solid edge is a dependency (`after`); a dashed
one joins a task to a result its flow call had received when it created the task
(`created_from`), drawn only where the task does not also wait for that output.
A flow that does not yield is one layer: its kinds.

The layer shown is drawn with some of its functions open: a function drawn open
is a box that holds its own layer (its kinds, its loops, the functions it called,
drawn open or closed in turn), joined by the same edges to what is outside it, so
the whole flow reads in one drawing. A chain of functions, each the only function
in the layer of the one before (outside any loop), is one box named by its path
(`topic_work › write_batches › write_batch`), each part of the name a link into
that function's layer. Which functions open is chosen by interest: one that holds
agent tasks, a failure, running work, work that did not run, or the selection,
the more of these and the more tasks the sooner, and the nearer the layer shown
the sooner; a function of finished Python steps stays a node, whose count says it
all. They open while the drawing holds about 40 nodes (fewer in a narrower frame)
and spans about one screen of layers; what would make it longer stays closed. A
function's control opens or closes it (Show inside, Hide inside), and "Show all
inside" and "Hide all inside" set every one; the reader's choices outrank the
graph's and are kept for the page, a reload included. A drawing too long to read
left to right in its frame is drawn top to bottom, where the frame grows with it.

Beside the graph (above it, in a part that opens, on a frame narrower than 1500
px) the outline lists every function of the flow and the loops they are in, a
chain as one item, each with a bar of its tasks done and what is not done, the
layer shown marked and the selection's item highlighted. A click shows its item
in the graph, selected, opening the functions around it; a double click or Enter
goes into its layer (a loop's: its passes).

The nodes created inside one loop are drawn in a box, a nested loop's box inside
it. A pass is one iteration of one loop (`flow[].loops[].pass`, see
[Tasks](tasks.md)), and each box counts its own loop's passes, never a nested
one's: its label gives the loop's last pass ("up to 3 passes") and, when its
units ran different numbers of passes, how many ran each ("1 pass: 4 | 2
passes: 1"). In a box, a unit's mark shows its latest pass, with the number of
passes it ran there when more than 1. Opening a box shows its passes: a row per
unit, a column per node and pass, and a nested loop's passes as a group of
columns inside each pass of the outer loop, so an inner loop's passes are
counted within each outer pass. Its units sort by number of passes or by status.

Each layer has two views in one frame, switched by "Graph | Table" at the right
end of the row under it: the graph, and its table, a row per node with the
node's status ("28/30 | 1 failed | 1 not started") and the nodes it waits for,
was created after and feeds. A loop's passes are its layer's table: there,
"Graph" shows the layer the loop is in, its box selected. The frame keeps its
height across the switch; a table taller than it scrolls inside it, and a loop's
passes narrower than it sit in its middle. A row of the table is selected as a
node is, with the same card.

The layout is layered: a layer of the flow per column (per row on a narrow
screen), an edge bending only in the gaps between them, never over a node or a
box's label; in each box, a dotted edge from its last layer back to its first,
in a band past its nodes, is the return to its next pass. It follows the flow's
structure, not the tasks' states, so it stays still while a run progresses; a
node that appears later goes at the end of its column.

A click selects a mark, a node or a loop box, and a card next to it in the
frame, joined to it by a pointer, shows its facts and where it leads (on a
narrow screen, a sheet under the frame that names the item): a mark's
status, pass, attempts, time and cost, and its task detail; a kind node's tasks
by status and the tasks before and after it, and its row in Tasks; a function
node's flow calls, and its layer; a loop's place in the code and its passes. A
function node and a loop box carry a mark of their inner view. A double click
follows the first link. With the keyboard, Tab moves between nodes, the arrow
keys between a node's marks, Shift and an arrow key along an edge to an earlier
or a later node (on the same unit); what has the focus is selected, Enter
follows its first link, Tab goes on from the selected item to the card's links,
and Escape clears the selection, then goes up a level. The card stays with the
item as the graph pans and zooms, and hides while the item is out of the frame.
The layer and the selection are in the URL; a link to a layer the run does not
have opens the graph's first layer and says so, and a function named by its
qualified name alone opens its layer when the run reaches it one way only.

The words on screen are the reader's, not the code's: a task's `Outcome` is its
status, an attempt's `stop` its outcome, a round after failed checks a
correction, a failover a model switch, the `ambient` credential
"default" (its tooltip: local credentials), a route the preflight dropped an unavailable model and a kind it
substituted a model replaced, an attempt's `peak_context` its peak context. A colour means a status, and only where it applies: red
failed, amber not started (or a limit near), green done (in marks and small
chips), cyan running; totals, cost, tokens and time are in the text colour, and
a count of a problem is coloured only above 0. A status also has a shape (✓ ✕ ◌,
a round or a square mark) and its word, so it reads without colour; in a status grid,
the states that share a tone differ by a texture as well. Times show the month as a word (`Oct 12, 10:38:40`), so they
read the same in every locale.

Live processes are found through the `CONTRAAGENT_*` environment each launch
carries. Where the reader is lives in the URL, so Back, Forward and a reload
return to it. The monitor speaks English and Japanese.

The monitor is local and read-only, but it serves agent transcripts: it sends no
CORS headers unless origins are opted in (`--cors-origin`), and answers only
requests whose `Host` names this machine.

It reads a run's records only through a run source and liveness
(`contraagent.monitor.RunSource`, `contraagent.monitor.Liveness`): by default the runs
directory (`DirectorySource`) and this host's processes. `Monitor(source=..., liveness=...)`
serves the same views from another store; the records of a run and their JSON Schemas
are in [Compatibility](compatibility.md#run-formats-and-schemas), and the files of a run
directory in the docstring of `contraagent.engine.Run`.

## Your own views: panels

A pipeline adds views of its own with `monitor.Panel`: a function that returns
the view's body, sent live whenever it changes. A typed body is drawn with the
monitor's own elements: `tiles` (figures), a `table` (columns, each with a
format: `usd`, `pct` (a fraction), `duration` (seconds), `tokens`, `datetime`,
`number`; `bar` draws a bar in its cells, `link` names the key of each row that
holds the URL its cell leads to (http or https), and a row's `_tone` is its
status), `columns` (vertical bars, `stacked` or side by side), `lines`, a
`heatmap` (a number per row and column, in shades of one colour), a
`status_grid` (a state per row and column, each coloured by its tone and named
by its label), `hbars` (horizontal bars), a `note` (markdown beside the figures:
what a part shows, how to read a number; any markup in it is shown as text), and
`blocks` of them one under another, each with an optional `title` and folded
when `collapsed`. A tone is one of `failed`, `attention`, `done`, `running`,
`muted` and `neutral`. The models are in `contraagent.monitor`
(`PanelBody`); a panel returns one, or a dict with its `type`. Any other dict is
shown as a JSON tree. A typed body that does not validate (an unknown tone
included) is an error, never a JSON tree.

::code{file="examples/panels/views.py" from="def spend(" to="def cost_by_day("}

A panel's `scope` says what it is computed over: `run` (the default), `fn(run)`,
a tab of each run; `trends`, `fn(runs, period)`, over the runs of a period, for a
view of many runs. A panel reads runs only through what it is given, never through a
path of its own, so it shows the same on one host and on a hub. `run`
(`RunRecords`) is one run's records: its `id`, `info()` (its `run.json`),
`journal()`, `records(log)` for another log contraagent writes (`deferred.jsonl`,
...), `log(name)` and `document(name)` for the pipeline's own logs and documents
(what `contraagent.log` and `contraagent.save` wrote; see
[tasks and flows](tasks.md)), `output(key)` for a task's output file, and `dir()`, the
run's directory on this host, for a file that is none of these (None on a hub). `runs` (`PeriodRuns`) is the period's run ids, newest
activity first, with the same methods taking the run id first (`journal(run)`,
`log(run, name)`, ...) and `run(run)`, its `RunRecords`. `Period` holds its `start`, `end` and the time zone
`tz` its days are counted in; `period.day_of(ts)` is the day of a time inside the
period and None outside it, for a run that began before the period or ended after
it. The monitor offers the panels in the order of the dict it is given.
A test calls a panel as the monitor does, over a runs directory:
`fn(RunRecords(run_id, DirectorySource(runs_dir)))` for a run panel,
`fn(PeriodRuns(run_ids, DirectorySource(runs_dir)), Period.parse(start, end))` for a
trends panel (all in `contraagent.monitor`).

::code{file="examples/panels/views.py" from="def cost_by_day(" to="#: What"}

A run panel over the pipeline's own records: the counts a Python task logged, and the
total the flow saved (both in `examples/panels/records.py`):

::code{file="examples/panels/records.py" from="def words(" to="#: What"}

A pipeline run once an hour, as a trends panel: how each hour's run ended, day
by day, in a status grid, with a note on how to read it and the runs as a table
whose ids lead to each run in the monitor:

::code{file="examples/panels/cycles.py" from="def cycles(" to="#: What"}

`contraagent monitor --panels views.py:PANELS` loads them from a file or a
module (`package.module:PANELS`), a dict of name to `Panel`; `--groups`
(the plan's columns) and `--task-detail` (`fn(run, key, rows)`, merged into a
task's detail) take the same form. The demo's panel shows each unit's note, the
output of its `write_note` task, read with `output(key)`:

::code{file="examples/demo/run.py" from="def notes(" to="def main("}

From Python, `Monitor(panels=...)`:

::code{file="examples/demo/run.py" from="        from contraagent.monitor import" to="        threading.Thread("}

## Over many runs: trends

A run's page says what one run did. The trends say what the runs of a
**period** did together (`/api/trends?from=2026-10-01&to=2026-10-14&tz=Asia/Tokyo`;
by default the last 14 days in UTC): the cost of each day by kind, or by group
when the monitor has groups (`Monitor(groups=)`; the implementation kinds of a base kind are one group); each kind's tasks, how many
passed, its attempts and their median time, tokens and cost; what each model was
spent on; the outcomes that were not `completed`; the tool calls the coding
agent's permissions refused; each account's utilization, by its highest reading
of each day and of each hour; the rests and deferrals; the runs; and when runs start, by weekday
and hour. An attempt counts on the day it ended, in the period's time zone; a
stub run counts only with `stub=true`, and `run_group=` keeps one group's runs.

The page shows them as **Trends**, the first entry of the run picker
(`?page=trends`): the last 7, 14 or 30 days or two dates, counted in the browser's
time zone unless the page names another (`&tz=`), and one run group or all. It draws
each fact in its own form: the totals as figures, the cost of each day as stacked
columns by kind, each kind's and each model's numbers as tables, the subscription
usage as a line per identity and window, when runs start as a weekday by hour grid;
then the pipeline's own trend panels.

`Trends.bodies` holds the same numbers as panel bodies (`{"type": "blocks", ...}`),
in English, for a page that draws them without words of its own. A pipeline adds
its own numbers over a period as a panel whose `scope` is `"trends"`: its function
takes the period's runs (`PeriodRuns`) and the `Period`, and it is served at
`/api/trends/panels/<name>`, checked as a run panel is. A trend panel is made once
for the same period over the same runs, as they were, and kept: a page asks for it
again every few seconds and gets it back, and one that asks while it is being made
waits for that one. Panels, a pipeline's own code, run on threads of their own, so a
panel that takes a minute holds no other endpoint back.

Many trend panels make a long page. A trend panel's `tab` (`Panel(scope="trends",
tab="Reliability")`) puts it on a tab of the Trends page with the other panels of the
same `tab`; the tabs follow the order of the first panel of each, after a first tab
that holds the trends and the trend panels of no `tab`. The page's address names the
open tab (`?page=trends&tab=Reliability`), and an export's Trends page has the same
tabs. With no `tab` on any panel, the page has no tabs.

The monitor reads only the runs that started before the period ends and did not
finish before it begins, and of each, only a digest of its logs: what it did per
15 minutes of UTC and per kind (attempts, passes, time, cost, tokens, outcomes, each
model's spend, each account's highest reading), with every wall time, so a median
is exact. Every time zone's offset is a multiple of 15 minutes, so a digest answers
any period in any time zone exactly. The monitor keeps a digest in memory while the
logs stay the same and, for a finished run that is not live, as `trends.json` in the
run's directory, so a restarted monitor reads that instead of the logs
(`Monitor(keep_digests=False)` keeps none on disk); a `trends.json` made from other
logs or by another version is made again. The same period over unchanged runs gives
back the trends it gave before. Thirty days of hourly runs (720 runs, 300,000
attempts) are summed in about 0.2 s from memory and 1 s from their `trends.json`;
reading their logs the first time takes about half a minute
(`uv run pytest -m perf` measures it).

## Without a server: an export

`contraagent monitor export` writes the monitor's views of the newest runs as files a
static server or a site serves, with no monitor running: the page (`index.html`,
`app.js`, `ja.js`, and its icons) and `data/`, the JSON each endpoint of the API would answer
(`/api/info`, `/api/runs`, and for each run its journal, plan, outputs, definitions,
cursor, each task and each panel), and the trends of a period over every run with
its trend panels (`--days 14`, or `--from` and `--to`; `--tz`, default UTC). The
export's Trends page shows that period and offers no other. `--panels`, `--groups`
and `--task-detail` take what `contraagent monitor` takes (`path/to/views.py:PANELS`
or `package.module:PANELS`). A run still running is left out, its views would stop
half way (the run that writes the export, as its last step, is one); `--include-live`
writes it too.

```
contraagent monitor export --runs-dir runs --out site/stats --runs 14 --days 30 --tz Asia/Tokyo --panels mypipeline.panels:PANELS
python -m http.server --directory site/stats    # or put site/stats on any static site
```

An export holds no transcripts and no process trees, and none of the launches running
when it was written; its page says so where those views would be, and its header
shows when it was written. It takes out what says where it ran: a path under the
run's directory, the run's working directory or the runs directory is made relative
to it and one under the home directory starts with `~`, everywhere; outside a
document's contents, any other path of a person's or a temporary directory is
`<path>` (a system path such as `/etc/hosts` stays), and the host's name is left
blank. `--keep paths` or `--keep host` puts either back, `--exclude <key>` takes a key
out wherever it appears (`--exclude params`), and `Info.export.redacted` lists what was
taken out. Written again, the export holds only the runs chosen then.

In another page, `<ca-monitor export="data/">` reads an export, and
`createExportClient` with `openExportFeed` (in `@contraagent/api`) give a
`MonitorStore` the same data; `export(monitor, out, ...)` in
`contraagent.monitor` writes one from Python.

## Its API and its page

The monitor publishes its contract as OpenAPI at `/api/openapi.json`
(`contraagent monitor --openapi PATH` writes it), browsable at `/api/docs` when started with
`--docs`; every response is checked against its pydantic model before it is
sent. `curl http://127.0.0.1:8787/api/runs` lists the runs, and every endpoint
under `/api/runs/<run>/` (the journal, the plan, outputs, one task by its key,
a task's transcript) is in that document. The plan (`/api/runs/<run>/plan`)
carries each task's origin (`flow`, each frame with its loops and their passes; `created_from`, `flow_call`)
and the run's `flow_calls` (each with `flow`, its parent's frames where it was
yielded), and `models`: what the agent sessions spent on each model (`ModelUsage`,
summed from each journal row's hops, which record their own tokens, cost and time;
a hop's spend on other models, such as Claude Code's summary of a fetched page on a
smaller model, counts on each of them, `Hop.other_models`);
a run whose tasks no flow created (queued through `Run.queue` by hand) has
none. A file of flow code under the run's working directory (`run.json`
`cwd`) is given relative to it. Its page is built from two npm packages that
work in any page or framework: `@contraagent/api` (the typed client, live feeds
and store) and `@contraagent/ui` (the monitor and each of its views as web
components). Their documentation is in those packages.
