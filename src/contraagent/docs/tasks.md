# Tasks and flows

Every argument is in the docstrings of `agent_task`, `python_task` and `Pipeline`
(`help(contraagent.agent_task)`, `help(contraagent.python_task)`, `help(contraagent.Pipeline)`).

## Agent tasks

An agent task's interface: what it takes (`params`, a pydantic model), what it
must leave behind (`output`: a model, or `str` for a text document), the extra
checks its output must pass, and its default budget. Its implementation is a
role of a plugin, with the skills of any skill plugins it names
([plugins](plugins.md)). The config file may change where and how it runs, never what
it is.

::code{file="examples/demo/tasks.py" from="summarize = agent_task(" to="@python_task"}

`agent_task`'s options, and the topic that explains each (the docstring states
them all):

| Options | For | Topic |
|---|---|---|
| `output`, `params`, `validators` | what it takes and leaves behind (a model, `str`, or `Rows[Row]`), and the checks its output must pass | [Contracts](contracts.md) |
| `partial_on` | keeping what a launch wrote when the runner stopped it for its time | [Contracts](contracts.md#a-launch-stopped-for-its-time) |
| `max_corrections` | how many times an output that fails its checks goes back to the session | [Contracts](contracts.md#checked-twice-by-the-same-rules) |
| `output_from`, `unwrap`, `tools=()` | an output in the final message; a light launch | [Contracts](contracts.md) |
| `preserve`, `output_of` | filling in another task's file, and the parts to keep | [Contracts](contracts.md) |
| `plugin`, `role`, `instructions`, `skills_from`, `implementations` | its implementation | [Plugins](plugins.md) |
| `output_name` | where its output file is | "Flows that depend on results", below |
| `rerun_on_resume` | a step that a resume runs again | "The flow", below |
| `claims` | one task at a time on a name, and the service a name stands for | "Claims" and "Services", below |
| `changes`, `keep_failed_changes` | the files it changes beside its output, and whether the files of a failed attempt stay | "Files a task changes", below |
| `requires` | what its data may be sent under | [Routing](routing.md#credentials) |
| `agent`, `model`, `effort`, `credential`, `model_failover`, `fallbacks` | where it runs, which the config outranks; one task's credential, which its call names (`credential=`), outranks the config | [Routing](routing.md) |
| `max_turns`, `timeout_s`, `max_budget_usd`, `stall_s`, `context_budget`, `context_warn_pct`, `max_denials`, `disallowed_tools`, `max_concurrent`, `retries`, `retry_backoff_base` | its budget, and how its attempts run | [Routing](routing.md#budgets), and each coding agent's in [Coding agents](agents.md) |

## Python tasks

A function becomes a task with the same contract machinery: its return
annotation is its output contract, a function with a `unit` parameter is given
the unit, and a raised exception fails the task. Its parameters' annotations are
its input types: each argument is checked and converted before the call (pydantic,
lax mode), so a dict given to a model parameter arrives as the model, a list of
dicts given to `list[Model]` as a list of models, and an output of another task as
its value. An argument that does not match refuses the task (`invalid_input`, the
parameter named in its reason) and the function is not called; an unannotated
parameter takes its argument as it is. It runs in this process, in its current
directory (a relative path it opens resolves there, not against `Pipeline(cwd=)`), and
has no budget: budgets cap coding-agent launches. A step with a side effect (a
fetch, a write outside the run directory, a push) belongs in a Python task, not
in the flow's own body: a stub run plays Python tasks and runs flow code as it is
(see `testing`).

::code{file="examples/demo/tasks.py" from="@python_task" to="def docs_one_review("}

### Retries

A Python task that talks to a server may fail for a reason a fresh attempt
cures: a dropped connection, a timeout. `retries` is the number of fresh
attempts after the first, and `retry_on` the exception classes that earn one;
any other exception fails the task at once, and so does an off-contract input
or output. Each attempt is a journal row of its own, with its attempt number
and its exception, as for an agent task, and waits `RetryingRunner`'s backoff
first. Declaring one without the other raises at the decorator.

A function that needs a server restores it itself, at its start: a fresh
attempt then finds the server running again. A server that the tasks of a claim
share can instead be a service of the run ("Services", below), which the runner
starts and stops.

::code{file="examples/retries/flow.py" from="@python_task(retries=2" to="summarize = agent_task("}

`retries` and `retry_on` say how a task runs, not what it produces, so they are
not part of its definition's digest: changing them does not run a finished task
again on a resume (as with `claims` and `rerun_on_resume`).

### Partial results

A Python task whose server stays unavailable may still give the run something to
go on with: it returns `Partial(value, reason=...)`. `value` is its output as
usual, checked against its output schema and written to its output file;
`reason` says why it is partial, in one line. The task finishes ok with stop
`partial`, so the flow receives `value` as from any other result and later tasks
run on it. The flow cannot tell the two apart: the result and the journal row
carry the stop and the reason, and `RunReport.partial` lists such results.

A resume runs a task whose last result was `partial` again, and with it every
task that waits for it, directly or through others: their outputs were made from
the placeholder. Every other task a resume skips as usual. Annotate the function
`-> Out | Partial[Out]`; its output is `Out`.

::code{file="examples/partial/flow.py" from="@python_task" to="summarize = agent_task("}

A partial result is not a retry: for a failure a fresh attempt cures, use
`retries`; when the attempts run out, the exception fails the task. To end with a
placeholder instead, catch the exception and return `Partial`.

An agent task is partial when the runner stopped its launch for its time and what
it wrote passes its checks: `agent_task(partial_on=["timeout", "stalled"])`, in
[Contracts](contracts.md#a-launch-stopped-for-its-time).

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
- `priority=` breaks ties in the queue, higher first (see below).
- `credential=` (an agent task's) names the `[credentials.<name>]` that task runs
  as on every route of its kind, in place of the kind's own; how it ranks, fails
  over and rests is in [Routing](routing.md#a-task-calls-credential). A Python task
  runs no coding agent, so it has no credential: its call refuses `credential=`
  unless its function has a parameter of that name.
- A call that the run could not make raises `TypeError` at the call, and
  `contraagent check` reports it at the flow's line: a `key` that is not a
  string, an `after` that is not a list of tasks, a `priority` that is not a
  number, and for a Python task a keyword its function has no parameter for, or a
  required parameter left out.
- After the run, `pending.output` is the checked value.

`contraagent run <file.py>:<flow> --config ... --kwargs '{...}'` runs a flow from
the command line, with the arguments `contraagent check` takes, and exits 1 when
a task or the flow failed. A program calls `Pipeline.run`, which returns a
`RunReport`: `ok`, `failed`, `deferred`, the results by task key, `flow_errors`,
and `value`, whatever the flow returned (a `Pending` in it reads its task's output);
its docstring lists every field.
A deferred task (not launched: past a deadline, or on a resting credential) is in
`deferred`, with its cause, and is no failure: `ok` holds when no task failed and
the flow returned. A `TaskDeferred` the flow does not catch ends the flow without
its value, so it is a flow error and `ok` is False.

A run id is a file name on every operating system, so that a pipeline written on
Linux also runs on Windows. It holds no `/`, `\`, `<`, `>`, `:`, `"`, `|`, `?`, `*`
or control character, no leading `.`, no `..` and no trailing `.` or space, and it
is no Windows device name such as `CON` or `NUL`. Any other run id is refused with
ValueError on every system. The default run id is the flow's name with each
character but a letter, a digit, `-`, `_` and `.` turned into `_`, so a lambda
runs as `_lambda_`.

A run id that already holds a run is refused (`RunExists`) unless it is resumed
(`resume=True`, `--resume`): the flow runs again, and every task whose key's last
journal row is ok with the same fingerprint is skipped, its output read from the
run directory. Another run id starts a new run. A run directory a newer
contraagent wrote, of a run format this one does not read (`run.json` `format`), is
not resumed (`RunFormatError`; [Compatibility](compatibility.md#run-formats-and-schemas)). A task's fingerprint is a digest
of:

- its kind, unit, key and params;
- its definition: for an agent task, its instructions, its role file's content,
  the skills of its plugin and of each plugin of its `skills_from`, its output
  schema, its validators and its params schema; for a Python task, its function's
  source, its output schema and its validators;
- each task it waits for: the content of that task's output file when the flow
  received the output and passed it on (a generator flow), else that task's
  fingerprint (a task call passed before it finished, as in a flow that does not
  yield).

A changed parameter or an edited instruction, role file or function runs its task
again. A task after it runs again when the output it received changed: one that
wrote the same output leaves it skipped. In a flow that does not yield, every task
after it runs again. The functions that call the tasks, their names and lines are
not part of it: renaming a function of the flow runs nothing again.

A final step that reports or publishes the state of the work (a site, statistics,
a commit) often takes nothing from the tasks before it: it reads the working tree.
Its fingerprint does not change when they run again, so a resume would skip it.
`rerun_on_resume=True` on its declaration (`agent_task`, `@python_task`) makes a
resume run it again whatever an earlier attempt did. A task that takes the output
of a task that ran again needs no flag: its fingerprint already changes.

A task can also read state that is not in its params or its inputs: a state file
the pipeline keeps, files another process wrote, a file its instructions tell the
agent to read. A resume does not see that state change, and would skip the task
with an output made from the old state. Its declaration gives `outside_state=`, a
function of the task's unit and params that returns that state as a JSON value,
and the task's fingerprint covers the value. In the example, both tasks read a
backlog file, and the function returns the file's digest:

::code{file="examples/outside/flow.py" from="BACKLOG = " to="class OpenItems"}

::code{file="examples/outside/flow.py" from="@python_task(outside_state" to="def topics("}

- The function is called when the task is about to start, once every task it waits
  for finished, with its params and the outputs it is given. So it sees what those
  tasks wrote, and a resume compares the state as it is then. A relative path is
  relative to the pipeline's process, as in the task itself.
- It returns any JSON value: a digest, a version, a list or a dict of them, a pydantic
  model. A digest stands for a file of any size; `hashlib.file_digest` reads it in
  blocks. A file that is missing is a state too: return a value for it (an empty
  string), so the task runs again once the file appears.
- A function that raises, or that returns what is not JSON, refuses the task
  (`invalid_input`, its reason the exception), and the tasks that wait for it do not
  start. `contraagent check` calls it for every task whose params are known before the
  run and reports the same.
- A task that waits for one with outside state, without receiving its output, runs
  again when that task runs again, as for any change of its fingerprint.
- A file the task itself writes is no outside state: its digest changes with every
  run, so the task would run again on every resume. `rerun_on_resume` and
  `outside_state` do not go together.
- A recording keeps the digest of the outside state, not the state: a replay calls
  the function in its own working directory, and plays a recording made with another
  outside state all the same, its result's reason saying so.

When a resume runs a task again that an earlier attempt finished, its journal row
says why in `rerun` (`its outside state changed`, `its last result was partial`,
...), the start line of the log says so too, and the monitor shows it on the task.

A program gives the run id and the resume to `Pipeline.run`, as
`examples/runner/run.py` does with the `--run-id` and `--resume` it takes:

::code{file="examples/runner/run.py" from="    runs_dir = Path(args.runs_dir)" to="    for key, result"}

`contraagent run` takes the flow's arguments, the config, an agent or model override,
the run id, the resume, the preflight and the stub, record and replay options. A
`Pipeline` argument that is a function or an object (`row_extras`, `quota_rule`,
`scopes`, `enrichers`, `backends`, `log`), and `env`, `max_concurrent`, `cwd`, a
credential override and the queue's options, need a program like this one; its
docstring lists them.

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
- A task's output file is its kind's `output_name` under the run's `out/`: a
  path template with `{kind}`, `{unit}` and `{key}`, `{unit}` being the key for a
  task call given `key=`, so tasks of one kind and one unit with different keys
  write different files. The default is `{kind}/{unit}.json` (`.md` for a text
  output): `out/summarize/alpha.json`. `agent_task(output_name="reports/{unit}.json")`
  writes `out/reports/alpha.json`; `@python_task(output_name=...)` takes the same.
  An absolute path, a `..`, `.` or empty segment, or another field is refused
  where the task is declared.
- One output file has one writer. Two kinds whose templates name one file
  (`reports/{unit}.json` for both) raise `ValueError` when the flow reaches the
  second, and `Pipeline.check` reports it before a run, reachable kinds included;
  two tasks given one file (a template without `{unit}` or `{key}`) raise at the
  second task call. A task that fills in another kind's file names it with
  `output_of` (see [Contracts](contracts.md)).
- The same task created again in one flow call is numbered: `review-beta`,
  `review-beta~2`, ..., with its output file (`out/review/beta~2.json`). One key
  created by two flow calls raises `ValueError` at the second: `key=` tells
  them apart.
- A `while` loop of flow code is bounded by `max_passes`, or by its function's
  `@max_passes(n)` (see below).
- Every kind the flow's code reaches (see [Checking and testing](testing.md)) is
  routed, and probed by the preflight (`preflight="substitute"` or `"stop"`), before the first launch: a config
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
`contraagent.engine.JournalEstimates`): the median, over
tasks of the same kind created by the same functions in the same passes of
their loops (pass 3 and later counted as one), of the longest chain of wall
times that followed them. The samples come from the 10 most recent runs in the
same runs directory and from the run itself as its flow calls return, and only
from chains that ran to their end: a chain cut short by a failure, a deferral or
a flow error would be too short. A task's own duration is the median of its
kind's completed attempts, in this run once one has finished, else in the
recent runs.

A task call's `priority` (`summarize("alpha", priority=2)`, a number, default 0)
orders tasks the queue would otherwise start in the order they were queued:
among ready tasks with equal work after them, the highest priority starts
first. It is a tie-breaker only. A task with longer work after it still starts
first, whatever the priorities; so does a task that has waited past
`overdue_s`, and near a deadline the time box's order (its finishing kinds,
then the shortest remaining work) comes before it too. A priority is not part
of the fingerprint: a resumed run that changes one skips the same tasks.
`plan.jsonl` records it. A params model with a field named `priority` (or
`key`, `after`, and for an agent task `credential`), or a Python task's function
with such a parameter, is refused where the task is declared: the task call takes
these words itself.

Each task records where the flow created it (`plan.jsonl`: `flow`,
`created_from`, `flow_call`), and each flow call its start, with the frames of
its parent where the parent yielded it (`flow`), and its end
(`flow_calls.jsonl`); the docstring of `contraagent.engine.Run` lists the
files and `contraagent.Origin` the fields. A flow that does
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

Loops that converge at different speeds need different bounds. A generator
function decorated with `@max_passes(n)` gives each `while` loop of its own code
the bound `n`, in every call of it, in place of the run's value; every other loop
keeps the run's. The decorator returns the function itself, so the flow is still a
plain function, and `max_passes` is imported from `contraagent`. `analyse_file`, in
the next section, revises a column's reading at most 4 times whatever the run's
`max_passes` is. Two loops that need different bounds go in two
functions: one of them may run in the same flow call through `yield from`, since the
bound belongs to the function's code, not to the flow call. `TooManyPasses` names
the function whose bound the loop passed. `@max_passes` on a function that is not a
generator function, or that has no `while` loop, raises `TypeError` where it is
declared.

Passes are counted from the loops' back edges as the flow runs
(`sys.monitoring`), about 1 µs each time flow
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

::code{file="examples/analysis/flow.py" from="@max_passes(4)" to="def analyse_bundle("}

::code{file="examples/analysis/flow.py" from="def analyse_bundle(" to="def analyse("}

::code{file="examples/analysis/flow.py" from="def analyse("}

The parsers claim `heavy` (`claims=["heavy"]`), so one runs at a time. The monitor draws each flow call as a node that opens its own
layer, and the nodes a loop created in a box (a nested loop is a box inside it).

## A task that finds something missing

A task can find that it lacks something the run could provide: a document, a
setting, the output of another kind. Its output model says so in a field of its
own, and the task still writes what it can. The field's description tells the
agent what to put there, as for any other field:

::code{file="examples/missing/flow.py" from="class Review(" to="class Fetched("}

The flow reads the field at the `yield` and acts on it. Here it runs the task that
provides each missing document and yields the review again with the documents it now
has; the second review of a unit has the key `review-<unit>~2`. The `while` loop ends
when nothing is missing or nothing new was found, and `max_passes` bounds it as any
other loop:

::code{file="examples/missing/flow.py" from="def review_unit(" to="def reviews("}

What stays missing is not a failure: the task ended ok, and its output says what it
lacks. The flow logs each open item as a row of a [pipeline log](#a-pipelines-own-records),
and a run panel shows the rows in the monitor ([panels](monitor.md#your-own-views-panels)):

::code{file="examples/missing/flow.py" from="def missing(" to="#: What"}

When only a person can provide the item, the run ends with the item open. To have a
resume (`--resume`) run the task again once the item is there, declare the place the
task reads it from with `outside_state=` (above): its fingerprint then changes when
the item appears.

## A deadline over part of a flow: time boxes

`Pipeline(deadline_s=)` is a deadline over the whole run. When only one part of a
flow must end in time, and the steps after it must run however it went, put that
part in a **time box**: yield its generator through `time_box(...)`. Its deadline
counts from the moment that flow call starts, and holds over the tasks it and the
flow calls it starts create; nothing outside it is held to it.

::code{file="examples/time_box/flow.py" from="def topic_work("}

Inside, the rules are the run's deadline's: from `deadline_s - slack_s` (default a
quarter of `deadline_s`) its tasks go before the others, its `finishing_kinds`
first, and one whose known remaining work cannot finish in time is deferred at
once; past the deadline only its `finishing_kinds` launch, for `grace_s`; every
other task it creates is deferred, and the flow receives `TaskDeferred` at its
`yield`. A box whose flow does not catch it raises it to the flow call that
yielded the box, which may catch it and go on. The deferred tasks are in
`RunReport.deferred`, not `failed`: a flow that caught the deferral and returned
leaves the run ok, and `contraagent run` exits 0.

A task is held to every time box it is in: the run's and each enclosing box. So
the earliest deadline stops it, and a finishing kind launches past a deadline only
while every box it is in still lets it (that box's grace window, or a later
deadline). `deferred.jsonl` names the box (`cause.flow_call`), and the monitor shows
a function whose flow calls have a deadline of their own, and when each one's falls.

On resume (`resume=True`) a time box counts from its flow call's start in this
run start: the tasks an earlier attempt finished are skipped at once, so the
time goes to the work that is left.

## Claims: one task at a time on a name

Tasks run together unless something keeps them apart: their kind and their
unit lock nothing. A task that must have something to itself while it runs, a
topic's file, a heavy tool, claims it by name: `claims=[...]` on its
declaration. One task at a time holds a name, whatever its kind and wherever
the flow created it; a task that claims nothing runs beside any other.

A claim is a template, filled in when the task is created: `{unit}`, `{kind}`,
`{key}` (the task's key, `~n` included: the second task a flow call creates under
one key claims `<key>~2`), and `{params.<name>}`, a parameter of the task call. A parameter that holds a list gives one name per element, so a task
over several topics claims each of them.

::code{file="examples/claims/flow.py" from="style = agent_task(" to="lookup = agent_task("}

::code{file="examples/claims/flow.py" from="def topics("}

No two of `style`, `terms` and `merge` write one topic at once; `merge` names both
topics and claims both, so it waits while a write of either runs. `triage` claims
nothing and runs beside the writes of its topic. Two topics are two names, so their
writes run together.

`claim_capacity` lets more than one task hold a name: a key is a name or an
`fnmatch` pattern, and a pattern gives each name it matches a capacity of its own
(`{"heavy:*": 2}`: two tasks at a time on each `heavy:` name). A name's own entry
outranks a pattern, and the longest matching pattern outranks the others; a
capacity of 0 starts no task that claims the name. A limit that many tasks share
needs one name that they all claim: a pattern does not share its capacity. The
config holds them as `[defaults.claim_capacity]`, and `Pipeline(claim_capacity=)`
outranks it key by key.

A capacity may instead be what one running task that claims the name needs of the
host, a `PerTask`: `memory_mb`, `cores`, or both. Tasks that each start a local
server of about 1.5 GB claim one name, and the host's free memory sets how many
run at once:

::code{file="examples/claims/flow.py" from="lookup = agent_task(" to="def topics("}

`Pipeline(claim_capacity=CLAIM_CAPACITY)` gives it, or
`index = { memory_mb = 1500, cores = 1 }` in `[defaults.claim_capacity]`. Each
time the queue tries to start such a task, the capacity is the tasks that hold the
name plus as many more as the free memory holds, and at most the usable cores
divided by `cores`. While no task holds the name it is at least 1, so a run always
goes on even on a host short of memory. The free memory is what the OS reports as
available (on Linux `MemAvailable` of `/proc/meminfo`), less `memory_mb` for each
such task started in the last 30 seconds, since a server just started has not taken
its memory yet; where the OS reports none, memory does not limit the name. The capacity grows
as memory frees, and a waiting task starts then, while the others still run.

A claim that names `{unit}` on a task with no unit, or a parameter the call does
not give, raises at the task call; so does a parameter that is an output not
received yet (yield it first), and one that holds an empty list, which would claim
nothing. Claims are not part of the fingerprint: they change
when a task runs, not what it does. The plan records each task's claims, and the
monitor shows them in the task's detail.

## Services: a server that the tasks of a claim share

Some tasks need a long-lived helper while they run: a worker service, a database, a
local server. A **service** is the helper a claim name stands for. `Pipeline(services=)`
names it by the claim name, and its value (`Service`) is a function of the name that
returns a context manager: entering it starts the service and gives its address, a
string its tasks reach it by (None when there is nothing to reach); exiting it stops
the service.

::code{file="examples/services/flow.py" from="@contextlib.contextmanager" to="def topics("}

::code{file="examples/services/flow.py" from="def pipeline("}

A task that claims the name holds the service while it runs. The first such task
starts it, before its first attempt; a task that claims the name while it starts
waits for that start. Every task that claims the name shares the one service, as many
at once as the name's claim capacity lets ("Claims", above), and the service runs
until the run ends. A key may be an `fnmatch` pattern, as in `claim_capacity`: a
service under `db:*` is started once for each name it matches (`db:alpha`, `db:beta`),
and is given that name.

A task reaches the service by its address. A Python task calls
`contraagent.service_address(name)`; an agent task's coding agent finds it in the
variable `CONTRAAGENT_SERVICE_<NAME>`, the name in capitals with each character but a
letter or a digit turned into `_` (`db:alpha` gives `CONTRAAGENT_SERVICE_DB_ALPHA`):

::code{file="examples/services/flow.py" from="@python_task(claims=" to="summarize = agent_task("}

::code{file="examples/services/flow.py" from="review = agent_task(" to="class _Lookup("}

The call file does not name the variable, so the role or the instructions do. For a
service under a pattern, whose variable differs from unit to unit, the flow can pass
the variable's name in the task's params.

The run's end stops every service still running, the last started first: a run that
returns, a run that raises, and a run stopped by Ctrl-C or SIGTERM. A process killed
outright (SIGKILL) runs no stop.

A start that raises fails the task that started it, and every task that claims the
name later in the run, with stop `launch_failed` and the start's exception as the
reason (`service 'index' did not start: OSError: ...`); the other tasks of the run
still run. The start is not tried again in the run: a service whose start can fail
for a moment retries inside its own start. A resumed run starts it again for the
tasks that run again; a task the resume skips starts nothing. A stop that raises is
recorded with its exception, and the service counts as stopped.

`services.jsonl` records each start (the task that started it, its address, how long
it took, or the exception) and each stop (why: `run_end` or `interrupted`),
and the monitor shows each start of a service with its stop (`Plan.services`).
`Pipeline.check` warns about a service that no task of the run claims, and fails
a task that claims two services whose names give one variable.

A service is a function, so it is not an argument of the command line: a pipeline
with services is checked and run from a program, `Pipeline(config, services=...)`
with `.check(...)` and `.run(...)` (the example's `pipeline()`; `examples/runner/run.py`
is such a program). `contraagent check` and `contraagent run` know no service, and a
Python task that calls `service_address` in such a run raises `KeyError`, which says
that the pipeline defines no service of that name.

A stub run and a replay start a service only for a task that really runs: a Python
task whose function runs (a kind that `execute` matches), and an agent task that launches a coding agent (a task with no
recording, under `record_missing`). A task they play holds no service: no service
starts for it, and its launch has no `CONTRAAGENT_SERVICE_<NAME>` variable, so a
stub's reply finds none. A scope ("Around each attempt", below) suits a helper of one
attempt; a service suits one that the tasks of a claim share.

## Concurrency: how many tasks run at once

Every task of a run runs in a thread of the run's process. An agent task's thread
waits on its coding agent's process, which mostly waits on a remote model; a Python
task's thread calls its function. A task whose dependencies are done starts once
three limits all have room, and the queue then starts the first such task in its
order:

- The run's slots: `Pipeline(max_concurrent=)`, 4 by default, is how many tasks run
  at once. Every running task takes a slot, an agent task or a Python task alike.
  Two `rate_limited` ends in a row halve the slots for `throttle_s`.
- Its kind's limit: `max_concurrent` of an agent task kind, in `agent_task(...)` or
  `[tasks.<kind>]`, is how many tasks of that kind run at once. A Python task kind
  has no such limit, and a task table is not read for it.
- Its claims: each name it claims has room under its claim capacity ("Claims",
  above). Claims hold for agent tasks and Python tasks alike.

A task that cannot start does not hold back the tasks after it: while a long
computation waits for room on its claim, an agent task later in the order takes a
free slot.

A long computation in a Python task holds its slot for as long as it computes. With
4 slots and nothing else to stop them, four such tasks keep every agent task
waiting, although the agent tasks need little of this host. Give the computations
a bound of their own with a claim: each of them claims one name, its claim capacity
is how many compute at once, and `max_concurrent` is that number plus the agent
tasks that should run beside them. The agent tasks then always have their slots,
and take the others too while nothing computes.

::code{file="examples/concurrency/flow.py" from="#: Two measurements" to="class Stats("}

::code{file="examples/concurrency/flow.py" from="@python_task" to="summarize = agent_task("}

::code{file="examples/concurrency/flow.py" from="def pipeline("}

The capacity may instead be a share of the host, a `PerTask` (`{"local":
PerTask(cores=1)}`): as many compute at once as the usable cores hold. Choose
`max_concurrent` above the most that capacity gives, so that slots stay for the agent
tasks. To keep the agent tasks themselves at a number (a provider's rate limit), every
agent task kind claims one more name, with that number as its capacity; a kind's
`max_concurrent` bounds one kind only.

A Python task runs in this process, under its interpreter lock: while a function
computes in pure Python, the other threads of the run, the queue's own included, run
only in turns with it. A computation that takes long belongs in a child process
(`subprocess.run`, `concurrent.futures.ProcessPoolExecutor`) or in a library that
releases the lock while it computes; the task's thread then waits, as an agent task's
does. The example's `measure` runs its computation in a child process.

`run.json` records the run's slots (`max_workers`), and the monitor shows them beside
the running tasks; the plan records each task's claims. `Pipeline.check` warns about a
`[tasks.<kind>]` table that names a Python task kind, whose `max_concurrent` would
bound nothing. `contraagent run` does not take `max_concurrent`: a program gives it
("The flow", above), and `[defaults.claim_capacity]` gives the capacities.

## Files a task changes

An agent task whose work is files in the working tree, beside its output,
declares where with `changes`: `Path.glob` patterns relative to the working
directory, filled in like `output_name` (`{unit}`, `{key}`, `{kind}`). A pattern
that matches a directory covers everything under it. Each attempt's journal row
then holds its changes (`created`, `modified`, `deleted`), and the files a
failed attempt created (a timeout, a run of failed checks) are removed, with the
directories it created for them (`removed`). A modified file is not restored.

The files of a failed attempt can show why it failed: the notes of a long analysis
that ran out of time, a draft that did not pass its checks. A kind declared with
`keep_failed_changes=True` (or `keep_failed_changes = true` in its
`[tasks.<kind>]` table, which outranks the declaration) leaves them in place, and
its journal row lists them as `kept` in place of `removed`. The next attempt starts
from the tree with them in it, as a resume does: it sees them as files that exist,
so what it writes over them is `modified`, and a file it does not touch stays.
Nothing tells the agent about them; a role that must start from a clean directory
removes them itself, or the kind does not keep them. A kind that keeps them needs
`changes` patterns: without any, the declaration raises, and `contraagent check`
reports a task table that sets it.

::code{file="examples/changes/flow.py" from="study = agent_task(" to="def pipeline("}

A pattern that starts with `!` leaves out what it matches, and everything under a
directory it matches, whatever the other patterns cover: `["**", "!.git/**",
"!**/__pycache__"]` is every file of the working directory but the version control
directory and the caches. The scan does not enter a directory left out this way, so a
large one costs nothing. A list of `!` patterns alone covers nothing and raises where
the task is declared. `.gitignore` is not read: the files a task writes are often
ones it lists.

A file is counted as the change of the attempt that was running when it changed.
Two tasks that run at once under one pattern cannot be told apart: put `{unit}`
in the pattern, or keep them from running at once (a claim).

## Around each attempt: scopes, enrichers, journal columns

`Pipeline(scopes=, enrichers=, row_extras=)` hooks each attempt of a task, agent or
Python. A scope (`TaskScope`) is a function of the task that returns a context manager,
entered around each attempt: around every hop of an agent task, around the input check,
the call and the output check of a Python task.
A scope that raises fails the task. A Python task's exception is the attempt's result,
so the scope exits without one. An enricher (`ResultEnricher`) sees the task before
and the result after (an agent task's after its changes are recorded), and may return
the result with a `payload` added or `ok` and `stop` changed
(`dataclasses.replace(result, ...)`: a task and a result are frozen);
`row_extras(result)` adds columns to the journal row. The monitor shows each such
column under its own name, in the history and in the task's attempts (the API names
them: `RunSummary.row_extras`). Here an enricher names what each attempt did to its
topic (the files of `changes`, above):

::code{file="examples/changes/flow.py" from="write = agent_task(" to="def topics("}

`row_extras(result)` returns a dict of columns, `{}` for none; it is called once per
attempt. A result carries no output, so a column made from a task's output reads the
task's file, under the run's `out/` at the path its kind's `output_name` gives. Here a
`severity` column comes from each review (`examples/runner/run.py`):

::code{file="examples/runner/run.py" from="def severity_column(" to="def rest_past_80("}

Scopes and enrichers see every task. One for some tasks only tests `task.kind`, or
`task.executor` (`"agent"` or `"python"`), and leaves the others as they are. Here a
scope starts a local index server for each attempt of one Python task kind, and stops
it after; a fresh attempt gets a fresh server:

::code{file="examples/scopes/flow.py" from="@contextlib.contextmanager" to="def topics("}

## A pipeline's own records

Flow code and Python tasks keep what the pipeline wants to see of a run in the run
itself, in its `pipeline/` folder: `contraagent.log(name, row)` appends a row (a dict
or a pydantic model) as one line to the **pipeline log** `pipeline/<name>.jsonl`, and
`contraagent.save(name, value)` writes any JSON value whole as the **pipeline
document** `pipeline/<name>.json`, replacing what it held. `name` is a plain name
without a suffix. They write into the current run: in flow code, the run
`Pipeline.run` is running; in a Python task, the run the task belongs to, on whatever
thread the queue runs it. Anywhere else they raise `NoCurrentRun`. A relay ships them
to a hub with the rest of the run, and a panel reads them back wherever the monitor
reads runs ([the monitor](monitor.md)). In a stub run a Python task the stub agent
plays does not run, so it logs nothing (the kinds that `--execute` matches run and
log); flow code runs as in any run.

In the same places, `contraagent.pipeline_table(name)` reads the pipeline's own
settings: the **pipeline table** `[pipeline.<name>]` of the config file the run was
started with (`contraagent run --config`, `Pipeline(config)`), as parsed. It is an
empty table when the file has none, or the run has no config file
([routing](routing.md)). While `contraagent check` (`Pipeline.check`) builds the
flow, flow code reads the table of the config the check is given, the same table a
run reads, so a flow may read its settings in its body. A check writes no run: what
`log` and `save` write while it builds the flow goes into a temporary directory,
which the check removes.

::code{file="examples/panels/records.py" from="@python_task" to="def words("}

## How a task ends

A result's `stop` says why: `completed`, `partial` (ok, part of the work: a Python
task's placeholder output, or what an agent task wrote before its launch was
stopped, its reason the launch's stop; a resume runs it again), `invalid_output` (still off-contract
after every correction round), `invalid_input` (nothing launched), a budget
(`timeout`, `max_turns`, `budget`), `rate_limited` with no hop left, and the
rest of `contraagent.backends.Stop`, each with its meaning in its docstring.

A run that is stopped stops its agents. Each agent runs in a session of its own, so
a terminal's Ctrl-C does not reach it: `Pipeline.run` (on the main thread) stops the
agents on SIGTERM and SIGINT before the process ends. A process killed outright
(SIGKILL, out of memory) runs nothing, so a watchdog process, started with the
first agent, stops the agents still running once that process is gone.

## The engine underneath

The parts under `Pipeline` work on their own (`contraagent.engine`); their docstrings
describe them.
With its default callbacks, `FlowDriver` drives generators that yield `Task`s
and receive `TaskResult`s.

| Part | What it does |
|---|---|
| `Run` | `runs/<id>/`: run lock, `plan.jsonl`, `journal.jsonl`, `flow_calls.jsonl`, `deferred.jsonl`, in-flight markers, the pipeline's own `pipeline/` (the current run of `contraagent.log` and `save` while it is open), resume by key and fingerprint |
| `AgentRunner` / `RetryingRunner` | one agent task: input check, route, credential (skipping one that rests on its quota), launch, validate, failover; progress-aware retry |
| `PythonTaskRunner` | Python tasks in-process, checked by the same contracts |
| `TaskAdapter` | what a domain says about its tasks (prompt, plugin, contracts, changes, env) |
| `WorkQueue` | claims and their capacities, caps, retry, throttle; a greedy schedule by bottom level, then priority, overdue tasks first with the starvation guard (`overdue_s`), and past `deadline_s - slack_s` the shortest remaining work first, deferring what cannot finish; every queued task finishes once through `follow_up` (run, skipped, refused or deferred) |
| `FlowDriver` | generator flows over a `WorkQueue`, for flows that depend on results: each `yield` waits for tasks or child flow calls, and a failure raises `TaskFailed` there |
| `RoutingPlan`, `Router`, `QuotaRests` | per-kind routing and budgets, the failover chain, and the credentials that rest on their quota |
| `run_until_valid`, `OutputContract`, `InputContract` | files checked by schema and validators; resume until they pass |
| `CursorStore` | resume cursor: stage, per-unit step, in-flight work, markers |
