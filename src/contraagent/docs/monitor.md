# The monitor

A live, read-only view of every run, from the `monitor` extra:

```
contraagent monitor --runs-dir runs          # http://127.0.0.1:8787; --help for every option
```

It reads `runs/<id>/` and shows, live, one tab each:

- **Overview**: the run's state, the tasks running at once, progress by kind,
  the scheduled tasks as a layered graph, totals, problems with their causes,
  outputs, and a timeline;
- **Tasks** and **History**: every task (`kind · unit`) with its status, and
  every finished attempt with its outcome (`journal.jsonl`);
- **Outputs**: every checked file (`OutputContract`, `InputContract`), field
  by field against the file;
- **Definitions**: each kind's interface and its plugin's files;
- **Processes**: the agent sessions and Python tasks running, and the process tree;
- **Task detail**: one task's transcript, one button per agent session
  (attempt, correction, model switch), tailed live, next to its input, output
  and definition.

The graph is drawn from `plan.jsonl` and `flow_calls.jsonl`, so tasks that have
not started are in it too. A layer holds a node per kind (or per group,
`Monitor(groups=)`) for the tasks its flow function created itself, and a node
per function it called as a flow call, which opens that function's own layer;
while a layer holds a single node, the graph opens it, and stops at a node whose
flow call raised, where that failure shows. Each node has one mark per unit: a
task in a kind node, a flow call in a function node; above 200 marks, a bar of
its counts and its failed units by name. A breadcrumb names the layer
(Pipeline › function › loop). A solid edge is a dependency (`after`); a dashed
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

The layout is layered: a layer of the flow per column (per row on a narrow
screen), an edge bending only in the gaps between them, never over a node or a
box's label, and a mark on each box for the return to its next pass, which is
not drawn as an edge. It follows the flow's structure, not the tasks' states, so
it stays still while a run progresses; a node that appears later goes at the end
of its column. With the keyboard, Tab moves between nodes, the arrow keys between
a node's marks, Shift and an arrow key along an edge to an earlier or a later
node (on the same unit), Enter opens, and Escape goes up a level.

The words on screen are the reader's, not the code's: a task's `Outcome` is its
status, an attempt's `stop` its outcome, a round after failed checks a
correction, a failover a model switch, the `ambient` credential "default (this
machine's login)". Times show the month as a word (`Oct 12, 10:38:40`), so they
read the same in every locale.

Live processes are found through the `CONTRAAGENT_*` environment each launch
carries. Where the reader is lives in the URL, so Back, Forward and a reload
return to it. The monitor speaks English and Japanese.

The monitor is local and read-only, but it serves agent transcripts: it sends no
CORS headers unless origins are opted in (`--cors-origin`), and answers only
requests whose `Host` names this machine.

## Your own views: panels

A pipeline adds tabs of its own with `monitor.Panel`: a function of the run id
that returns any JSON object, sent live whenever it changes.

::code{file="examples/demo/run.py" from="        from contraagent.monitor import" to="        threading.Thread("}

## Its API and its page

The monitor publishes its contract as OpenAPI at `/api/openapi.json`
(`contraagent/monitor/openapi.json`), browsable at `/api/docs` when started with
`--docs`; every response is checked against its pydantic model before it is
sent. `curl http://127.0.0.1:8787/api/runs` lists the runs, and every route
under `/api/runs/<run>/` (the journal, tasks, outputs, a task's transcript) is
in that document. The plan (`/api/runs/<run>/plan`) carries each task's origin
(`flow`, each frame with its loops and their passes; `created_from`, `flow_call`)
and the run's `flow_calls` (each with `flow`, its parent's frames where it was
yielded);
a run whose tasks no flow created (queued through `Run.queue` by hand) has
none. A file of flow code under the run's working directory (`run.json`
`cwd`) is given relative to it. Its page is built from two npm packages that
work in any page or framework: `@contraagent/api` (the typed client, live feeds
and store) and `@contraagent/ui` (the monitor and each of its views as web
components). Their documentation is in those packages.
