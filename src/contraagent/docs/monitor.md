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
while a layer holds a single node, the graph opens it, and stops at a node whose
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
correction, a failover a model switch, the `ambient` credential "default (this
machine's login)". A colour means a status, and only where it applies: red
failed, amber not started (or a limit near), green done (in marks and small
chips), cyan running; totals, cost, tokens and time are in the text colour, and
a count of a problem is coloured only above 0. A status also has a shape (✓ ✕ ◌,
a round or a square mark) and its word, so it reads without colour. Times show the month as a word (`Oct 12, 10:38:40`), so they
read the same in every locale.

Live processes are found through the `CONTRAAGENT_*` environment each launch
carries. Where the reader is lives in the URL, so Back, Forward and a reload
return to it. The monitor speaks English and Japanese.

The monitor is local and read-only, but it serves agent transcripts: it sends no
CORS headers unless origins are opted in (`--cors-origin`), and answers only
requests whose `Host` names this machine.

It reads a run's records only through a run source and liveness
(`contraagent/monitor/source.py`): by default the runs directory and this host's
`/proc`. `Monitor(source=..., liveness=...)` serves the same views from another
store; the layout of a run's records is `contraagent/rundir.py`.

## Your own views: panels

A pipeline adds views of its own with `monitor.Panel`: a function that returns
the view's body, sent live whenever it changes. A typed body is drawn with the
monitor's own elements: `tiles` (figures), a `table` (columns, each with a
format: `usd`, `pct` (a fraction), `duration` (seconds), `tokens`, `datetime`,
`number`; `bar` draws a bar in its cells, and a row's `_tone` is its status),
`columns` (vertical bars, `stacked` or side by side), `lines`, a `heatmap`,
`hbars` (horizontal bars), and `blocks` of them one under another, each with an
optional `title` and folded when `collapsed`. The models are in
`contraagent.monitor.api` (`PanelBody`); a panel returns one, or a dict with its
`type`. Any other dict is shown as a JSON tree. A typed body that does not
validate is an error, never a JSON tree.

::code{file="examples/panels/views.py" from="def spend(" to="def cost_by_day("}

A panel's `scope` says what it is computed over: `run` (the default), `fn(run)`,
a tab of each run; `trends`, `fn(runs, period)`, over the run ids of a period
(`Period`: its `start`, `end` and the time zone `tz` its days are counted in),
for a view of many runs.

::code{file="examples/panels/views.py" from="def cost_by_day(" to="#: What"}

`contraagent monitor --panels views.py:PANELS` loads them from a file or a
module (`package.module:PANELS`), a dict of name to `Panel`; `--groups`
(the plan's columns) and `--task-detail` (`fn(run, key, rows)`, merged into a
task's detail) take the same form. From Python, `Monitor(panels=...)`:

::code{file="examples/demo/run.py" from="        from contraagent.monitor import" to="        threading.Thread("}

## Over many runs: trends

A run's page says what one run did. The trends say what the runs of a
**period** did together (`/api/trends?from=2026-10-01&to=2026-10-14&tz=Asia/Tokyo`;
by default the last 14 days in UTC): the cost of each day by kind, or by group
when the monitor has groups (`Monitor(groups=)`); each kind's tasks, how many
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
takes the period's run ids and the `Period`, and it is served at
`/api/trends/panels/<name>`.

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
`app.js`, `ja.js`) and `data/`, the JSON each route of the API would answer
(`/api/info`, `/api/runs`, and for each run its journal, plan, outputs, definitions,
cursor, each task and each panel), and the trends of a period over every run with
its trend panels (`--days 14`, or `--from` and `--to`; `--tz`, default UTC). The
export's Trends page shows that period and offers no other.

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
`contraagent.monitor.export` writes one from Python.

## Its API and its page

The monitor publishes its contract as OpenAPI at `/api/openapi.json`
(`contraagent/monitor/openapi.json`), browsable at `/api/docs` when started with
`--docs`; every response is checked against its pydantic model before it is
sent. `curl http://127.0.0.1:8787/api/runs` lists the runs, and every route
under `/api/runs/<run>/` (the journal, the plan, outputs, one task by its key,
a task's transcript) is in that document. The plan (`/api/runs/<run>/plan`)
carries each task's origin (`flow`, each frame with its loops and their passes; `created_from`, `flow_call`)
and the run's `flow_calls` (each with `flow`, its parent's frames where it was
yielded), and `models`: what the agent sessions spent on each model (`ModelUsage`,
summed from each journal row's hops, which record their own tokens, cost and time);
a run whose tasks no flow created (queued through `Run.queue` by hand) has
none. A file of flow code under the run's working directory (`run.json`
`cwd`) is given relative to it. Its page is built from two npm packages that
work in any page or framework: `@contraagent/api` (the typed client, live feeds
and store) and `@contraagent/ui` (the monitor and each of its views as web
components). Their documentation is in those packages.
