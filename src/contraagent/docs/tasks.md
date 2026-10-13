# Tasks and flows

Every argument is in the docstrings of `agent_task`, `python_task`
(`contraagent/pipeline/spec.py`) and `Pipeline` (`contraagent/pipeline/pipeline.py`).

## Agent tasks

An agent task's interface: what it takes (`params`, a pydantic model), what it
must leave behind (`output`: a model, or `str` for a text document), the extra
checks its output must pass, and its default budget. Its implementation is a
role of a plugin. The config file may change where and how it runs, never what
it is.

::code{file="examples/demo/tasks.py" from="summarize = agent_task(" to="@python_task"}

## Python tasks

A function becomes a task with the same contract machinery: its return
annotation is its output contract, a function with a `unit` parameter is given
the unit, and a raised exception fails the task. It runs in this process and
has no budget: budgets cap coding-agent launches.

::code{file="examples/demo/tasks.py" from="@python_task" to="def docs_one_review("}

## The flow

A flow is a plain function, with no decorator. `Pipeline` tells a generator flow
(one that yields) from one that does not by itself.

A flow that does not yield creates every task at once:

::code{file="examples/demo/tasks.py" from="def docs_one_review(" to="def review_loop("}

Calling a task inside a flow does not run it. It returns a `Pending`, a
reference to the task's future output:

- Passed to another task (also inside a list or a dict), it makes that task
  wait. Its file becomes the consumer's checked input, and its value is what
  the consumer receives.
- A task whose input failed is refused before launch (`invalid_input`), not run
  on nothing. In `docs_one_review` `prepare` raises for `zeta`, so `zeta`'s
  summary, score, review and note are refused, and so is the report, which
  needs every summary.
- `after=` orders tasks without passing data.
- After the run, `pending.output` is the checked value.

`contraagent run <file.py>:<flow> --config ... --kwargs '{...}'` runs a flow from
the command line, with the arguments `contraagent check` takes, and exits 1 when
a task or the flow failed. A program calls `Pipeline.run`, which returns a
`RunReport`: `ok`, `failed`, the results by task key, `flow_errors`, and `value`,
whatever the flow returned (a `Pending` in it reads its task's output).

A run id that already holds a run is refused (`RunExists`) unless it is resumed
(`resume=True`, `--resume`): the flow runs again, and every task whose key's last
journal row is ok with the same fingerprint is skipped, its output read from the
run directory. Another run id starts a new run. A task's fingerprint is a digest
of:

- its kind, unit, key and params;
- its definition: for an agent task, its instructions, its role file's content,
  its output schema, its validators and its params schema; for a Python task, its
  function's source, its output schema and its validators;
- each task it waits for: the content of that task's output file when the flow
  received the output and passed it on (a generator flow), else that task's
  fingerprint (a task call passed before it finished, as in a flow that does not
  yield).

A changed parameter or an edited instruction, role file or function runs its task
again. A task after it runs again when the output it received changed: one that
wrote the same output leaves it skipped. In a flow that does not yield, every task
after it runs again. The functions that call the tasks, their names and lines are
not part of it: renaming a function of the flow runs nothing again.

::code{file="examples/demo/run.py" from="    if args.real:" to="    if not args.no_serve:"}

## Flows that depend on results

A flow that is a generator yields a task call and receives the task's checked
output at the `yield`, so what it creates next can depend on it. The demo's
`docs` reviews each unit's summary and revises it until the review approves it,
every unit at once, then one report joins them. A unit whose summary could not
be made (`zeta`) ends its loop there.

::code{file="examples/demo/tasks.py" from="def review_loop("}

- `yield task(...)` receives the output: the model instance, the text (a `str`),
  the Python task's return value, or None for a task with no output.
- `yield [a, b]` (a list or a tuple) waits for every item and receives the
  outputs in order. An item may be a generator: it runs as its own flow call,
  beside the others, and what it returns is its item. `yield from sub(...)` runs
  `sub` in the same flow call.
- Passing a received output on to another task is the dependency, as passing
  the task call is: the second review waits for the revision and reads its file.
  A number, a bool, None or a `str` the flow built is a value.
- A task that did not succeed raises `TaskFailed` at the `yield` (`.stop`,
  `.key`, `.result`, and `.item`, the task call); a refused task too
  (`invalid_input`), and an output that no longer passes its checks
  (`invalid_output`). A task not launched by the deadline, or whose remaining
  work cannot finish before it, raises `TaskDeferred`, which a flow may answer
  with a task of a `finishing_kinds` kind. A batch settles every item, then raises the first failure by position.
  Tolerating a failure is `try`/`except`.
- A task called and never yielded still runs; the flow call does not wait for it.
- A task's output file is `out/<kind>/<unit>.json` (`.md` for a text output),
  and `out/<kind>/<key>.json` for a task call given `key=`: tasks of one kind
  and one unit with different keys write different files.
- The same task created again in one flow call is numbered: `review-beta`,
  `review-beta~2`, ..., with its output file (`out/review/beta~2.json`). One key
  created by two flow calls raises `ValueError` at the second: `key=` tells
  them apart.
- A `while` loop of flow code is bounded by `max_passes` (see below).
- Every kind the flow's code reaches (see [Checking and testing](testing.md)) is
  routed, and probed by `preflight=True`, before the first launch: a config
  problem refuses the run. A kind declared inside the flow's body is routed when
  its first task is created: a config problem raises at that task call.
- A kind is one definition and one `[tasks.<kind>]` table. The flow's code may
  reach two declarations of one kind (a function's default argument, replaced by
  its caller): only the one whose tasks are created is the kind's, and it is
  routed again as its first task is created when its `config` or `requires`
  differ from the one routed. Creating tasks of two declarations of one kind
  that differ (`AgentTask.differences`) raises `ValueError` at the second task
  call; two `agent_task` calls that declare it the same way are one kind.
- An exception in a flow before its first task is queued is raised by
  `Pipeline.run`. After it, the tasks already queued still run, and the
  exception is in `RunReport.flow_errors`: `ok` is False and `contraagent run`
  exits 1.

Flow code runs between two `yield`s on the thread that schedules every task: a
step that takes more than a second is logged, and heavy work belongs in a Python
task. A resumed run runs the flow again from the start and answers each skipped
task with its output, so the flow must create the same tasks for the same
outputs: a random choice or the clock belongs in a Python task too.

The queue starts first the ready tasks with the longest work after them. In a
generator flow that work is not queued yet, so it is estimated (a task's tail,
`JournalEstimates` in `contraagent/execution/estimates.py`): the median, over
tasks of the same kind created by the same functions in the same passes of
their loops (pass 3 and later counted as one), of the longest chain of wall
times that followed them. The samples come from the 10 most recent runs in the
same runs directory and from the run itself as its flow calls return, and only
from chains that ran to their end: a chain cut short by a failure, a deferral or
a flow error would be too short. A task's own duration is the median of its
kind's completed attempts, in this run once one has finished, else in the
recent runs.

Each task records where the flow created it (`plan.jsonl`: `flow`,
`created_from`, `flow_call`), and each flow call its start, with the frames of
its parent where the parent yielded it (`flow`), and its end
(`flow_calls.jsonl`); the docstring of `contraagent/execution/run.py` lists the
files and `Origin` (`contraagent/dispatch/task.py`) the fields. A flow that does
not yield is flow call `0`, and its tasks have no `created_from`.
`contraagent check` runs a generator flow to its first wait and checks the kinds
its code reaches (see [Checking and testing](testing.md)).

### Loops and passes

A loop is a `for` or `while` statement of a generator in flow code, named by its
first line. A pass is one iteration of one loop: 1 when the loop is entered, and
one more each time it goes back to its start (the end of its body, or
`continue`), whether or not that iteration created a task. Each frame of a
task's flow path lists the loops around its call site, outermost first, each
with its pass (`flow[].loops`: `{"line": 122, "pass": 1}, {"line": 125, "pass":
2}` is pass 2 of the inner loop in pass 1 of the outer one). A loop entered again
starts again at pass 1: an inner loop counts from 1 in each pass of the outer
one. Each flow call counts its own: two flow calls of one function do not share
passes. A loop in a function that is not a generator, or in code outside the flow
(the standard library, contraagent), is not listed.

These are not passes:

- an attempt: a retry of one task;
- the `~n` of a key: the n-th task under one key in a flow call (`refine-u~3`
  may be pass 2 of an inner loop in pass 2 of the outer one);
- a comprehension: `yield [step(u) for u in units]` is a fan-out, its tasks in
  the passes of the loops around it, with no pass of their own.

`max_passes` (`Pipeline(max_passes=)` or `[defaults] max_passes`, 10 by default)
bounds every `while` loop: a task call, or a `yield` of a child flow call, in a
later pass raises `TooManyPasses`, which names the loop (`file:line`) and the
pass; for a child flow call the parent receives it at the `yield`. A `for` loop
has no limit: it ends with its iterable. A comprehension has none either.

Passes are counted from the loops' back edges as the flow runs
(`sys.monitoring`, `contraagent/pipeline/loops.py`), about 1 µs each time flow
code goes back to the start of a loop. When the two monitoring tool ids it can
use (3 and 4) are both taken, `pass` is null and no loop is bounded.

## Flow calls, loops and layers

A generator a flow yields runs as its own flow call, so flows nest to any depth,
with loops inside loops. `examples/analysis/flow.py` has three layers:
`analyse` yields one `analyse_bundle` per bundle; each `analyse_bundle` fans out
a `classify` per file (a batch sized by what `unpack` returned) and yields one
`analyse_file` per data file; each `analyse_file` picks its parser by the file's
format (a kind chosen on a result, both reachable), then loops over the top
columns and, inside that, revises each until `verify` accepts it.

::code{file="examples/analysis/flow.py" from="def analyse_file(" to="def analyse_bundle("}

::code{file="examples/analysis/flow.py" from="def analyse_bundle(" to="def analyse("}

::code{file="examples/analysis/flow.py" from="def analyse("}

The parsers carry `tags=["heavy"]`; `Pipeline(tag_capacity={"heavy": 1})` runs
one at a time. The monitor draws each flow call as a node that opens its own
layer, and the nodes a loop created in a box (a nested loop is a box inside it).

## Units and locks

A task's unit is also its lock: tasks of different kinds on one unit never run at
the same time, and tasks of one kind on one unit may. A task that reads or changes
more than its own unit names the others at its call, `extra_units=[...]`. It locks
them as it locks its unit; its key, its output file and its place in the monitor
stay its own unit's.

::code{file="examples/units/flow.py" from="def topics("}

A `compare` of `alpha` and `beta` waits while a `write` of either runs, and no
`write` of them starts while it runs. Two `compare` tasks may share a topic: they are
one kind. `extra_units` is not part of the fingerprint, since it changes when a task
runs, not what it does. An extra unit that is the task's own unit, or one named
twice, raises at the task call.

## How a task ends

A result's `stop` says why: `completed`, `invalid_output` (still off-contract
after every fix-up round), `invalid_input` (nothing launched), a budget
(`timeout`, `max_turns`, `budget`), `rate_limited` with no hop left, and the
rest of `contraagent.Stop`, each with its meaning in `contraagent/backends/launch.py`.

## The engine underneath

The parts under `Pipeline` work on their own; their docstrings describe them.
With its default callbacks, `FlowDriver` drives generators that yield `Task`s
and receive `TaskResult`s.

| Part | What it does |
|---|---|
| `Run` | `runs/<id>/`: run lock, `plan.jsonl`, `journal.jsonl`, `flow_calls.jsonl`, in-flight markers, resume by key and fingerprint |
| `AgentRunner` / `RetryingRunner` | one agent task: input check, route, credential, launch, validate, failover; progress-aware retry |
| `PythonTaskRunner` | Python tasks in-process, checked by the same contracts |
| `TaskAdapter` | what a domain says about its tasks (prompt, plugin, contracts, env) |
| `WorkQueue` | per-unit locks (a task's unit and its extra units), caps, tags, retry, throttle; a greedy schedule by bottom level, overdue tasks first with the starvation guard (`overdue_s`), and past `deadline_s - slack_s` the shortest remaining work first, deferring what cannot finish; every queued task finishes once through `follow_up` (run, skipped, refused or deferred) |
| `FlowDriver` | generator flows over a `WorkQueue`, for flows that depend on results: each `yield` waits for tasks or child flow calls, and a failure raises `TaskFailed` there |
| `RoutingPlan`, `Router` | per-kind routing and budgets, and the failover chain |
| `OutputContract` / `InputContract`, `run_until_valid` | files checked by schema and validators; resume until they pass |
| `CursorStore` | resume cursor: stage, per-unit step, in-flight work, markers |
