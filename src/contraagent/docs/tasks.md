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

A task's params model is a pydantic model of its own: each field is one param, and
its `Field(description=...)` tells the agent what the param is. The call file carries
the fields' values as JSON (`params`) and the model's JSON Schema beside them
(`params_json_schema`), so a description and a constraint (`ge=1`, a `Literal`) reach
the agent. Tasks that share fields share a base model, which each task's model
extends; a check across fields is a `model_validator` of the model.

::code{file="examples/demo/tasks.py" from="class SummarizeParams" to="def three_points"}

A task call passes the unit and an instance of the model:
`summarize(unit, SummarizeParams(prepared=prepared))`, or
`summarize(SummarizeParams(...))` for a task with no unit. The declaration is typed
`AgentTask[SummarizeParams, Summary]`, so a type checker (mypy, pyright) finds a
misspelled field, a value of another type, a required field left out and the model
of another task before anything runs, and a function that takes any task with its
params (`async def attempt[P: BaseModel, Out](task: AgentTask[P, Out], unit: str, params: P) -> Out`)
keeps both types. The instance is of the model itself: one of a subclass carries
fields the model's JSON Schema does not describe, and raises `TypeError` at the call.
A task declared without `params=` takes no params: it is typed `AgentTask[None, Out]`,
called `tidy(unit)` or `tidy()`, and its params are `{}`; a call that gives it params
raises `TypeError`. A text output with an example,
`output=Annotated[str, Field(examples=[...])]`, is typed as `str`; an `Annotated`
around anything else raises `TypeError` where the task is declared.

`agent_task`'s arguments, and the topic that explains each (the docstring states
them all):

| Arguments | For | Topic |
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
| `agent`, `model`, `effort`, `credential`, `model_failover`, `fallbacks`, `safety_stop_failover` | where it runs, which the config outranks; one task's credential, which its call options give (`.options(credential=)`), outranks the config | [Routing](routing.md) |
| `max_turns`, `timeout_s`, `max_budget_usd`, `stall_s`, `context_budget`, `context_warn_pct`, `max_denials`, `disallowed_tools`, `max_concurrent`, `retries`, `retry_backoff_base` | its budget, and how its attempts run | [Routing](routing.md#budgets), and each coding agent's in [Coding agents](agents.md) |

## Python tasks

A function becomes a task with the same contract machinery: its return
annotation is its output contract, and a raised exception fails the task. A task
call calls it as the function is called, and a type checker checks the call
against the function's parameters (`PythonTask[P, Out]`). Its parameter named
`unit`, a string, takes the task's unit; a function without one makes tasks with
no unit (key `python:<kind>`). Every other parameter is a param, by its name, so
the function's parameters are named: a positional-only parameter, `*args` and
`**kwargs` raise `TypeError` where the task is declared, and so does an annotation
pydantic has no JSON Schema for. Its kind is the function's name, or the one
`@python_task(kind=...)` gives. Its arguments are JSON values,
copied at the task call, and its parameters' annotations are its input types: each
argument is checked and converted before the call (pydantic, lax mode), so a model
given to a model parameter arrives as the model, a list of dicts given to
`list[Model]` as a list of models, and `"3"` given to `int` as 3. An argument that
does not match refuses the task (`invalid_input`, the parameter named in its reason)
and the function is not called; an unannotated parameter takes the JSON as it is (a
model as a dict, a tuple as a list). It runs in this process, in its current
directory (a relative path it opens resolves there, not against `Pipeline(cwd=)`), and
has no budget: budgets cap coding-agent launches. A step with a side effect (a
fetch, a write outside the run directory, a push) belongs in a Python task, not
in the flow's own body: a stub run plays Python tasks and runs flow code as it is
(see `testing`).

::code{file="examples/demo/tasks.py" from="@python_task" to="async def one_review("}

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

A flow is a function, with no decorator. A flow that gives a task another task's
output is an `async def` function: it awaits the output and passes the value on (see
[Flows that depend on results](#flows-that-depend-on-results)). A plain `def`
function is a flow too, for tasks that are independent of each other or ordered with
`after=` only. `Pipeline` tells one from the other by itself.

The demo's `docs_one_review` reviews each unit in a flow call of its own, then
writes one report over the units that got through:

::code{file="examples/demo/tasks.py" from="async def one_review(" to="async def review_loop("}

Calling a task inside a flow does not run it. It returns a `Pending`, a
reference to the task's future output:

- Awaited in an async flow, it gives the task's checked output. A task is given
  values: its params are copied as JSON at the call, so what the flow does with a
  value afterwards does not reach the task. An output the flow received is a value
  like any other, and so is a copy of it or a field of it.
- A `Pending` among the params of another task call, at any depth (in a list, a
  dict or a model), raises `TypeError` at that call, which says how to write it:
  await the task call and pass its output, or give the task call in
  `.options(after=[...])` for an order with no output passed on. A value that is
  not JSON (an object pydantic cannot turn into JSON, a NaN) raises `TypeError`
  there too. A field of a params model whose type is not `Any` refuses a `Pending`
  when the model is built, with pydantic's `ValidationError`; `contraagent run` and
  `contraagent check` add the same advice to its report.
- A task called and never awaited, never given in `after=` and never returned runs
  all the same, for its output file and its changes: it is an unawaited task, which
  the end of its top flow call lists (`flow_calls.jsonl` `unawaited`). That is
  information, not an error.
- A task's key, an order without data, a priority, a credential and cancellation
  are its call options, given by `task.options(...)` (see below).
- A call that the run could not make raises `TypeError` at the call, and
  `contraagent check` reports it at the flow's line: for a Python task a keyword
  its function has no parameter for, or a required parameter left out; for an agent
  task params that are no instance of its params model itself, params given to a
  task without a model or as keywords, and an instance whose fields no longer
  validate under the model (a value set after it was made); and for any task a
  call option given as a keyword of the call. A type checker finds most of them
  before the run.
- After the run, `pending.output` is the checked value.

### Call options

A task call takes the task's params, and nothing else. The words that say how the
task is run are its call options: `task.options(...)` returns the same task with
them, and calling what it returns is the task call, as in
`summarize.options(key="summary-short", priority=2)("alpha", params)`.

`options` takes each option as a keyword, and an option it is not given keeps the
value it had, so `summarize.options(priority=2).options(key="k")` has both. None
given as `key` or `credential` clears it: the key is `<kind>-<unit>` again, and the
credential is the kind's. The task
it returns has the same declaration: one kind, one digest, one `[tasks.<kind>]`
table. Its type is the task's own (`AgentTask[SummarizeParams, Summary]` stays
`AgentTask[SummarizeParams, Summary]`), so a function that takes a task and calls it
with a key keeps the params and output types too.
Each option is checked where `options` is given; one that is wrong raises
`TypeError` there.

- `key` names the task in place of `<kind>-<unit>`, and its output file in place of
  the unit (see below). Two tasks of one kind on one unit with different keys are
  two tasks with two files.
- `after` is a list of tasks, each a task call's `Pending` or a task's key: the task
  starts after them, with no output passed on. They are not part of its fingerprint:
  a task that reads what they changed in the working tree declares that state with
  `outside_state=` (see below).
- `priority` breaks ties in the queue, higher first (see below).
- `credential` (an agent task's) names the `[credentials.<name>]` that task runs as
  on every route of its kind, in place of the kind's own; how it ranks, fails over
  and rests is in [Routing](routing.md#a-task-calls-credential). A Python task runs
  no coding agent, so it has no credential, and its `options` does not take one.
- `cancellable=True` lets the task be cancelled when no flow call waits for it any
  longer (see below).

A params field or a Python task's parameter may have the name of an option
(`key`, `priority`): it is a param like any other. A call option given as a keyword
of an agent task's call, or of a Python task's call to a function without such a
parameter, raises `TypeError` that names `options`. Only `key` is part of the
fingerprint.

By default a task runs to its end whatever happens to the flow call that created
it, as a task nothing awaits does: its result is in the run and in the journal, and a
resume uses its output. A flow call is closed when a sibling in its
`asyncio.TaskGroup` fails, when its time box is past its grace window, when it
waits for what nothing will answer, when flow code cancels its asyncio Task, or when
the run ends before it returns. A task called with `.options(cancellable=True)` is cancelled once the flow call that
created it and every flow call that waited for it were closed and no flow call
waits for it. A queued one is not launched. A running agent task has its launch
stopped within a second, and no other hop, correction round or attempt of it
launches; a backend that does not run its process through contraagent's
`run_process` cannot be stopped, and its result is kept when it returns. A running
Python task runs to its end and keeps its result: its function runs on a thread,
which cannot be stopped. A cancelled task ends with stop `cancelled`: not ok, not
retried, and not a failure (`RunReport.cancelled`, never `RunReport.failed`). The
files it created under its `changes` patterns are removed as those of a failed
attempt are, and a resume runs it again when the flow creates it.

Cancellation is for work whose answer is no longer needed when nobody waits for
it: several probes of one change, of which the first blocking finding settles the
review.

::code{file="examples/cancel/flow.py" from="async def ask("}

`contraagent run <file.py>:<flow> --config ... --kwargs '{...}'` runs a flow from
the command line, with the arguments `contraagent check` takes, and exits 1 when a
task or the flow failed. A program calls `Pipeline.run`, which returns a
`RunReport`. Async code (an `async def` function, a notebook) calls
`await Pipeline.run_async(...)` instead: it schedules the run's tasks on the running
event loop, runs the flow from there, and returns the same report, and `Pipeline.run`
raises `RuntimeError` there. One event loop runs one run at a time: a second
`run_async` on a loop that runs one raises an error. The `RunReport` holds `ok`, `failed`, `deferred`, the results by task key,
`flow_errors`, and `value`, whatever the flow returned (a `Pending` in it reads its
task's output); its docstring lists every field. A deferred task (not launched: past
a deadline, or on a resting credential) is in `deferred`, with its cause, and is no
failure: `ok` holds when no task failed and there is no flow error (see
[Failures](#failures-the-run-keeps-going)). A `TaskDeferred` the
flow does not catch ends the flow without its value, so it is a flow error and `ok`
is False.

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
of what it is given and what it observes:

- its kind, unit and key;
- its params, as the JSON the task call copied: an output it was given is part of
  them, by its content; an agent task's params model fills in its defaults, and a
  Python task's function's defaults are filled in, so a call that gives a default
  and one that leaves it out have one fingerprint;
- its definition: for an agent task, its instructions, its role file's content,
  the skills of its plugin and of each plugin of its `skills_from`, its output
  schema, its validators and its params schema; for a Python task, its function's
  source, its output schema and its validators;
- for a task that fills in another task's file (`output_of`), the content of
  that file as it was when the task was about to start;
- its outside state, when it declares one (below).

The journal row of each attempt keeps a digest of each of these parts beside the
fingerprint (`fingerprint_parts`): `definition`, `params`, `outside` and
`output_of`.

A changed parameter or an edited instruction, role file or function runs its task
again. A task given another task's output runs again only when that output
changed: a task that ran again and wrote the same output leaves the tasks given it
skipped, and one that wrote another output runs them again, since the flow receives
the new output and passes it on. A task it waits for with `after=` is not part of
the fingerprint, and neither is where its params came from: a task that reads what
another task changed in the working tree declares that state with `outside_state=`
(below), and then runs again when the state changed. The functions that call the
tasks, their names and lines are not part of it: renaming a function of the flow
runs nothing again.

Where a task's params came from is recorded beside the fingerprint, and never
changes what a resume skips. A task is given from the tasks whose outputs had reached
the flow call that created it and are among its params: `plan.jsonl` `given_from`. The
outputs that reached a flow call are those it awaited, those its parent had received
when it created the flow call, and those that had reached the flow calls whose end it
awaited (directly, through `asyncio.gather` or an `asyncio.TaskGroup`); so a value passed
down as an argument or returned by a child counts, and an equal output of another
unit's flow call, or of a child it never awaited, does not. Several equal outputs that reached it
are all named. A value of the params, at any depth, counts when its JSON is that of a
whole output, or of one whole row of an output that is a list (a Rows). A copy of an
output counts as the output. A field or a text taken out of an output, or a value built
from it, does not: the task's created from still shows which results it came after.

A resume skips a task only when its output still reads under its output schema.
An output file that no longer does (one edited by hand into another shape) runs
its task again, and its journal row's `rerun` says so.

A task that fills in another task's file (`output_of`) left its own output in the
file, so a resume cannot see in the file what the task found there. The journal
row keeps both digests: the file as the task found it (`fingerprint_parts`
`output_of`) and as the task left it (`output_of_after`). A resume skips the task
when the file is as the task left it, or as a task after it that fills it in left
it. A file changed by hand, or written again by a task before it that ran again,
runs again every task after its writer that fills it in.

A resume gives the flow the results of the tasks it skips one at a time, in the
order the journal recorded them, so flow code that depends on the order in which
its tasks finish takes the path it took. A task that runs again finishes when it
finishes, and its result comes after them.

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
  for finished, with its unit and its params as JSON (the call file's `params`). So
  it sees what those tasks wrote, and a resume compares the state as it is then. A
  relative path is relative to the pipeline's process, as in the task itself.
- It returns any JSON value: a digest, a version, a list or a dict of them, a pydantic
  model. A digest stands for a file of any size; `hashlib.file_digest` reads it in
  blocks. A file that is missing is a state too: return a value for it (an empty
  string), so the task runs again once the file appears.
- A function that raises, or that returns what is not JSON, refuses the task
  (`invalid_input`, its reason the exception), and the tasks that wait for it do not
  start. `contraagent check` calls it for every task whose params are known before the
  run and reports the same.
- A task given the output of one with outside state runs again when that output
  changed, as for any output it is given. A task that only waits for it (`after=`)
  does not run again with it, unless it declares outside state of its own.
- A file the task itself writes is no outside state: its digest changes with every
  run, so the task would run again on every resume. `rerun_on_resume` and
  `outside_state` do not go together.
- A recording keeps the digest of the outside state, not the state: a replay calls
  the function in its own working directory, and plays a recording made with another
  outside state all the same, its result's reason saying so.

When a resume runs a task again that an earlier attempt finished, its journal row
says why in `rerun` (`its outside state changed`, `its last result was partial`,
...), the start line of the log says so too, and the monitor shows it on the task.
A changed fingerprint names each part that changed: `its fingerprint changed: its
definition`, `its fingerprint changed: its params`.

A task whose params changed although every task it was given from or was created
from was skipped, and whose input files did not change, is a **divergence**: the
flow gave other params for the same outputs. The flow's code reads a clock, randomness or outside state, or the
code itself changed. The task runs again with `rerun` `divergence: ...`, and the
run logs a warning, `[resume] <key>: divergence: ...`. Its fingerprint keeps a
wrong output from being used: a divergence costs a run of the task, not a wrong
result.

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

A flow that waits for outputs is an `async def` function. It awaits a task call and
receives the task's checked output at the `await`, so what it creates next can
depend on it. The demo's `docs` reviews each unit's summary and revises it until the
review approves it, every unit at once, then one report joins them. A unit whose
summary could not be made (`zeta`) stops its own flow call there; the other units go
on, and the report joins the units that got through (see
[Failures](#failures-the-run-keeps-going)).

::code{file="examples/demo/tasks.py" from="def review_loop("}

- `await task(...)` receives the output: the model instance, the text (a `str`),
  the Python task's return value, or None for a task with no output. A task call
  returns `Pending[Out]`, and the `await` gives an `Out`, so a type checker knows
  the output's type.
- A task call does not wait. It queues the task and returns its `Pending` at once,
  so a helper function that only creates tasks can be a plain `def`. A task called
  and never awaited still runs; the flow call does not wait for it, and its top flow
  call lists it as unawaited once every flow call it started has ended.
- `await sub(...)`, for an `async def` function `sub` of flow code, runs `sub` in
  the same flow call, as any function call does. A coroutine that is never awaited
  (`sub(u)` without `await`) never runs: the run logs a warning line for it, and
  `contraagent check` reports it as an error.
- Work at the same time is plain asyncio; contraagent adds no functions of its
  own for it. `await asyncio.gather(a, b)` waits for every item and receives the
  outputs in order, each with its own type. An item may be a task call or a child
  flow, `sub(...)`: every asyncio Task that flow code starts is a flow call of its
  own, beside the others, and what it returns is its item.
  `asyncio.TaskGroup` and `asyncio.create_task` start flow calls in the same way.
- A received output is a value: the flow passes it on to another task as it passes
  any value, and the task is given a copy, made at the call. The second review is
  given the revision the flow received. A task call itself is never passed: its
  `Pending` among the params of another task call raises `TypeError`.
- A task that did not succeed raises `TaskFailed` at the `await` (`.stop`,
  `.key`, `.result`, and `.item`, the task call); a refused task too
  (`invalid_input`), and an output that no longer passes its checks
  (`invalid_output`). A task not launched by the deadline, or unlikely to finish
  before it while other tasks take every slot, raises `TaskDeferred`, which a flow may answer
  with a task of a `finishing_kinds` kind. An exception that ends a child flow
  call is raised again at its parent's `await`. What a failure stops, and what
  goes on, is in [Failures](#failures-the-run-keeps-going).
- One failure is tolerated with `try`/`except` around its `await`. Without more
  arguments, `gather` raises the first failure as soon as it comes, and the other
  items go on running. To tolerate failures in a group, give
  `return_exceptions=True`: `gather` then waits for every item, and an item that
  failed is its exception. Inspect the items by position, as `analyse_bundle`
  does in [Flow calls, loops and layers](#flow-calls-loops-and-layers).
- Flow code does not depend on the order in which tasks finish. A resume gives
  the flow the results of the tasks it skips in the order the first run recorded
  them, but a task that runs again finishes in its own time. A branch on
  `asyncio.as_completed`, on `asyncio.wait(..., return_when=FIRST_COMPLETED)` or on
  which exception `gather` raises first can then create other tasks, and a task
  given other params is a [divergence](#the-flow). `gather(..., return_exceptions=True)`,
  inspected by position, gives the same answer in every order.
- Cancelling a flow call does not cancel the tasks it created: they run to
  their end, and their results are in the run, unless their call options give
  `cancellable=True` ([Call options](#call-options)). A flow call is cancelled when a
  sibling in its `asyncio.TaskGroup` fails, when its time box is past its grace
  window, when it waits for what nothing will answer (see below), or when the run
  ends before it returns; `flow_calls.jsonl` records it `closed`.
- A task's output file is its kind's `output_name` under the run's `out/`: a
  path template with `{kind}`, `{unit}` and `{key}`, `{unit}` being the key for a
  task whose call options give one, so tasks of one kind and one unit with different keys
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
  created by two flow calls raises `ValueError` at the second:
  `.options(key=...)` tells them apart.
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
  `Pipeline.run`; `contraagent run` prints it in one line, as `contraagent check`
  does, with the flow's file and line, and exits 1. After it, the tasks already queued still run, and the
  exception is in `RunReport.flow_errors`: `ok` is False and `contraagent run`
  exits 1. A top flow call closed because it waited for what nothing would
  answer is there too, and so is any flow call that raised an exception of its
  own, even one that its parent caught.

Flow code runs on an event loop of contraagent's own, on the thread of the event loop
that schedules every task. This loop has no clock, no threads and no I/O, so an
`await` that needs one of them raises `TypeError` at that line, and the message says
what to write instead. `asyncio.sleep(5)`, `asyncio.wait_for(..., timeout=5)` and
`asyncio.timeout(5)` need a clock. `asyncio.to_thread` and `run_in_executor` need a
thread. A socket, a subprocess, a file read through an async client and the async API
of another library need I/O. A future of another event loop raises asyncio's
`RuntimeError`. Waiting, polling and I/O belong in a Python task: the run records its
output, and a resume skips it. A deadline over part of a flow is a time box (see
[A deadline over part of a flow](#a-deadline-over-part-of-a-flow-time-boxes)).
`asyncio.sleep(0)` and `asyncio.timeout(None)` need no clock, and they work.

A flow waits for task calls and for flow calls, with `await`, `asyncio.gather` and
`asyncio.TaskGroup`. It does not use `asyncio.wait`, `asyncio.as_completed`,
`asyncio.shield`, `asyncio.Queue` or `asyncio.Event`. They run, but a branch on what
finished first can take another path on a resume that runs a task again, and an `Event` that no flow code sets
waits forever. A branch that tolerates failures uses `gather(...,
return_exceptions=True)`, or a child flow call for each item. When a flow call still
waits while no task is queued or running and every other flow call waits too, nothing
will answer it. The run then closes it at once: `flow_calls.jsonl` records it
`closed`, its error names the line where it waits, and a top flow call closed this
way is in `RunReport.flow_errors`.

A step of flow code between two `await`s that takes more than a second is logged:
heavy work belongs in a Python task. The second counts flow code only, not what
contraagent does for a task call. Flow code does not start another run or event
loop: `Pipeline.run` and `asyncio.run` raise inside a flow. A resumed run runs the flow again from the
start and answers each skipped task with its output, so the flow must create the
same tasks for the same outputs: a random choice or the clock belongs in a Python
task too.

The queue starts first the ready tasks with the longest work after them. In an
async flow that work is not queued yet, so it is estimated (a task's tail,
`contraagent.engine.JournalEstimates`): the median, over
tasks of the same kind created by the same functions in the same passes of
their loops (pass 3 and later counted as one), of the longest chain of wall
times that followed them. The samples come from the 10 most recent runs in the
same runs directory and from the run itself as its flow calls return, and only
from chains that ran to their end: a chain cut short by a failure, a deferral or
a flow error would be too short. A task's own duration is the median of its
kind's completed attempts, in this run once one has finished, else in the
recent runs. The order uses the median because a rare long launch does not move
it. The samples themselves are kept, the 100 most recent of each kind and of each
tail key, for the deadline below.

A task's `priority` (`summarize.options(priority=2)("alpha", params)`, a number, default 0)
orders tasks the queue would otherwise start in the order they were queued:
among ready tasks with equal work after them, the highest priority starts
first. It is a tie-breaker only. A task with longer work after it still starts
first, whatever the priorities; so does a task that has waited past
`overdue_s`, and near a deadline the time box's order (its finishing kinds,
then the shortest remaining work) comes before it too. A priority is not part
of the fingerprint: a resumed run that changes one skips the same tasks.
`plan.jsonl` records it.

Each task records where the flow created it (`plan.jsonl`: `flow`,
`created_from`, `flow_call`), and each flow call its start, with the frames of
its parent where the parent created it (`flow`), and its end
(`flow_calls.jsonl`); the docstring of `contraagent.engine.Run` lists the
files and `contraagent.Origin` the fields. A flow that does
not wait is flow call `0`, and its tasks have no `created_from`.
`contraagent check` runs an async flow to its first wait and checks the kinds
its code reaches (see [Checking and testing](testing.md)).

### Loops and passes

A loop is a `for` or `while` statement in flow code, named by its
first line. A pass is one iteration of one loop: 1 when the loop is entered, and
one more each time it goes back to its start (the end of its body, or
`continue`), whether or not that iteration created a task. Each frame of a
task's flow path lists the loops around its call site, outermost first, each
with its pass (`flow[].loops`: `{"line": 122, "pass": 1}, {"line": 125, "pass":
2}` is pass 2 of the inner loop in pass 1 of the outer one). A loop entered again
starts again at pass 1: an inner loop counts from 1 in each pass of the outer
one. Each flow call counts its own: two flow calls of one function do not share
passes. A loop in code outside the flow (the standard library, contraagent) is
not listed.

These are not passes:

- an attempt: a retry of one task;
- the `~n` of a key: the n-th task under one key in a flow call (`refine-u~3`
  may be pass 2 of an inner loop in pass 2 of the outer one);
- a comprehension: `await asyncio.gather(*[step(u) for u in units])` is a
  fan-out, its tasks in the passes of the loops around it, with no pass of their
  own.

`max_passes` (`Pipeline(max_passes=)` or `[defaults] max_passes`, 10 by default)
bounds every `while` loop: a task call, or the start of a child flow call, in a
later pass raises `TooManyPasses`, which names the loop (`file:line`) and the
pass; for a child flow call the parent receives it at the `await`. A `for` loop
has no limit: it ends with its iterable. A comprehension has none either.

Loops that converge at different speeds need different bounds. An `async def`
function decorated with `@max_passes(n)` gives each `while` loop of its own code
the bound `n`, in every call of it, in place of the run's value; every other loop
keeps the run's. The decorator returns the function itself, so the flow is still a
plain function, and `max_passes` is imported from `contraagent`. `analyse_file`, in
the next section, revises a column's reading at most 4 times whatever the run's
`max_passes` is. Two loops that need different bounds go in two
functions: one of them may run in the same flow call through `await`, since the
bound belongs to the function's code, not to the flow call. `TooManyPasses` names
the function whose bound the loop passed. `@max_passes` on a function that is not
an `async def` function, or that has no `while` loop, raises `TypeError` where it is
declared.

Passes are counted from the loops' back edges as the flow runs
(`sys.monitoring`), about 1 µs each time flow
code goes back to the start of a loop. When the two monitoring tool ids it can
use (3 and 4) are both taken, `pass` is null and no loop is bounded.

### A loop that stops when it stops improving

A loop that revises a draft until a critique finds nothing may never get there. Each
pass costs tasks, and after a few passes the draft often stays as good as it is. Such
a loop needs three ends: a measure that has not changed for a few passes, a largest
number of passes, and a deadline. Each one is plain flow code over what contraagent
already has, and the loop returns the last draft whichever end it reaches.

::code{file="examples/converge/flow.py" from="async def refine("}

The measure is a value the flow computes from the outputs it receives, here the
critique's `open_issues`, compared with `==` to the values of the passes before.
`refine` stops when it has not changed for `flat` passes in a row. A resume gives the flow
the recorded outputs of the skipped tasks in the same order, so the loop computes the
same values and stops at the same pass.

The largest number of passes is the range of a `for` loop. When `range(passes)`
ends, the loop ends as any `for` loop does, and the flow goes on with the last draft.
A `while` loop under `max_passes` does not end that way: `max_passes` guards against a
loop that never ends by mistake, and the pass after it raises `TooManyPasses`, a flow
error that leaves the run not ok. A loop whose bound is part of its design takes a
range, and `max_passes` stays the guard.

The deadline is a time box: `improve` runs each `refine` in `time_box(...,
deadline_s=)`, since flow code has no clock to read. Past the deadline, the next
critique or revision is deferred, and `refine` receives `TaskDeferred` at its `await`,
catches it and returns the draft it has. The box counts from its flow call's start in
each run, so a resume gives the loop the whole `deadline_s` again: the passes an earlier
run finished are skipped at once, and the time goes to the passes that are left. A
loop that stopped on its time box may therefore go further on a resume.

The measures and why the loop stopped are kept with `contraagent.save` in the
pipeline document `refine-<unit>` ([A pipeline's own records](#a-pipelines-own-records)), not with
`contraagent.log`. A resume runs the flow again from its start, so a row logged after
the loop would be appended once more on each resume, while `save` writes the same
value in place of the old one. After a run in which alpha's critiques find 5 open
issues, then 2 three times, `pipeline/refine-alpha.json` holds the following, and a
resume leaves it the same:

```json
{"open_issues": [5, 2, 2, 2], "why": "flat"}
```

`why` is `flat`, `ceiling` when the range ended, or `time box`.

## Large inputs: input files

A task call copies its params into the call file. A long text that one task wrote and
another reads would be copied too: the call file grows, and a coding agent cannot read
a very long file in one step. A large input goes to a task as an input file instead,
`InputFile(path)`, which is a field of a params model or a parameter of a Python task.
The task is given the file's path and the SHA-256 of its content, taken at the task
call, and reads the file itself.

::code{file="examples/input_file/flow.py" from="class ReviewParams" to="draft = agent_task("}

::code{file="examples/input_file/flow.py" from="@python_task" to="async def reports("}

- The params hold `{"path": ..., "sha256": ...}`, the path relative to the working
  directory (`Pipeline(cwd=)`). The JSON Schema of the params model in the call file
  (`params_json_schema`) tells the agent to read the file with its tools. A light
  launch (`tools=()`) has no tool to read a file, so give it the text as a `str` field.
- A task's output goes by its output file: `pending.input_file()`, once the flow has
  awaited the task. It raises `ValueError` for a task that has no output, has not
  finished or did not succeed. A file that is there before the run goes by its path,
  `InputFile("in/spec.md")`.
- The file is in the working directory, or it is an output file of the run. A
  relative path that climbs out with `..` raises `ValueError` where the `InputFile` is
  made. An absolute path outside both directories, a symbolic link to a file outside
  them, and a path that names no file raise `ValueError` at the task call.
- The fingerprint holds the path and the hash. A resume runs the task again when the
  file has other content, and also when the same content is at another path; while
  both are the same, it skips the task. The journal keeps the digest of the input
  files as a part of their own (`input_files` of `fingerprint_parts`), so a file with
  other content is not a [divergence](#the-flow).
- When the task is about to start, the file must still have the content it had at the
  call. A file that changed or is gone refuses the task (`invalid_input`), and the
  reason names the file. So a task that writes the file finishes before the task call
  that gives it: the flow awaits it first.
- A Python task is given an `InputFile` whose `path` is absolute and whose `sha256` is
  the hash taken at the call. `read_text()` and `read_bytes()` check the content
  against it: a file that changed while the task ran refuses the task (`invalid_input`).
- When the path is the output file of a task whose result had reached the flow call
  that gives the file, that task is in the given from of the task the file is given
  to, by the same rule as an output given as a value.

The declaration decides whether a param is a value or a file, never the size of a
value or where it came from: a field typed `str` always holds the text, and a field
typed `InputFile` always holds a path and a hash. A path given as a plain `str` puts
only the path in the fingerprint, so a file with other content at the same path would
not run the task again.

## Flow calls, loops and layers

A child flow that a flow gives to `asyncio.gather`, `asyncio.TaskGroup` or
`asyncio.create_task` runs as its own flow call, so flows nest to any depth, with
loops inside loops. A flow call's id is its parent's and a number: `0.1`, `0.1.2`,
the n-th asyncio Task its parent created, counted from 1. The numbers follow the order
of creation, not the order of finishing, so the same flow code gives the same ids in
every run. Every Task takes a number, also the one asyncio makes around each task
call given to `asyncio.gather`, but `flow_calls.jsonl` and the monitor show a flow
call only once it creates a task or a flow call, or ends with an error of its own. A
task's `TaskFailed` or `TaskDeferred` that only passes through a flow call is no
error of its own: the task's record already says it. A Task that only waits for a
task already created leaves no record, so the ids on record may skip numbers:
`analyse_bundle` gathers two `classify` task calls first, and its `analyse_file`
flow calls are then `0.1.3` and `0.1.4`.

`examples/analysis/flow.py` has three layers: `analyse` gathers one
`analyse_bundle` per bundle; each `analyse_bundle` fans out a `classify` per file (a
group sized by what `unpack` returned), leaves out a file whose `classify` failed,
and gathers one `analyse_file` per data file; each `analyse_file` picks its parser
by the file's format (a kind chosen on a result, both reachable), then loops over
the top columns and, inside that, revises each until `verify` accepts it.

::code{file="examples/analysis/flow.py" from="@max_passes(4)" to="def analyse_bundle("}

::code{file="examples/analysis/flow.py" from="def analyse_bundle(" to="def analyse("}

::code{file="examples/analysis/flow.py" from="def analyse("}

The parsers claim `heavy` (`claims=["heavy"]`), so one runs at a time. The monitor draws each flow call as a node that opens its own
layer, and the nodes a loop created in a box (a nested loop is a box inside it).

## Failures: the run keeps going

A run does not stop at a failure. A task that did not succeed, after its retries,
failover hops, correction rounds and `partial_on`, raises `TaskFailed` at each
`await` of it, and that stops only the code that needs its output:

- the flow call that awaits it, from that `await` on, unless its code catches the
  exception;
- each parent that awaits that flow call, with `await`, with `asyncio.gather`
  without `return_exceptions`, or through `asyncio.TaskGroup`, from that `await` on,
  and the parents above it by the same rule.

Nothing else stops. Every other flow call goes on and creates its tasks; `gather`
does not cancel its other items when it raises. A task already queued or running
runs to its end, and its result is in the run. A flow call goes on when its parent
ends, whether the parent returned or raised, and the run waits for every flow call.
The run ends when no task is queued or running and every flow call has ended. Its
`RunReport.ok` is False when a task failed or there is a flow error. A resume then
skips every task that succeeded and runs the failed tasks again, and the code that
waited for them goes on from there.

A failure stops the rest of its own flow call, also the work that does not need the
failed output. So a flow gives each unit a flow call of its own, an `async def`
function for one unit, and gathers them with `return_exceptions=True`: a unit that
failed stops there, and its item is the exception. The demo's `docs` above does this,
and so does the review example:

::code{file="examples/review/flow.py" from="def docs(" to="def publish("}

`return_exceptions=True` makes every exception an item, an exception of flow
code's own too (`TooManyPasses`, a bug). A task's failure is an outcome to tolerate:
the run is not ok only because the task failed. An exception of flow code's own is
not: it is a flow error wherever it is caught, listed in `RunReport.flow_errors` for
the flow call it started in, and the run is not ok. The other units still go on.

When the work is all or nothing, the flow says so with `asyncio.TaskGroup`. The first
failure in the group cancels its other flow calls (recorded `closed`), and the group
raises an `ExceptionGroup` at the end of its `async with`. The tasks those flow calls
created still run to their end, and a resume skips them.

::code{file="examples/review/flow.py" from="def publish("}

A flow call that raised records where and why it stopped, in `FlowCall.raised_at` and
`FlowCall.raised_by`, at the end of its `flow_calls.jsonl` record and in the monitor.
`raised_at` is the frame where the exception left the flow call's own code: mostly
the line of the `await` that failed, or for a parent, the line where it awaits the
child. An exception raised in a function that is not `async def`, such as a helper
or a library, is at the line of the flow code that called the function. `raised_by` is the key of the failed task the exception is (`TaskFailed.key`,
the first one in an exception group), the same in every flow call it passes through;
it is null for an exception of flow code's own. `contraagent run` prints the place of
each flow error.

## A task that finds something missing

A task can find that it lacks something the run could provide: a document, a
setting, the output of another kind. Its output model says so in a field of its
own, and the task still writes what it can. The field's description tells the
agent what to put there, as for any other field:

::code{file="examples/missing/flow.py" from="class Review(" to="class Fetched("}

The flow reads the field at the `await` and acts on it. Here it runs the task that
provides each missing document and runs the review again with the documents it now
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
part in a **time box**: give its coroutine to `time_box(...)` and await what it
returns. The part runs as a flow call of its own; `time_box(...)` can also be an
item of `asyncio.gather`. Its deadline counts from the moment that flow call
starts, and holds over the tasks it and the flow calls it starts create; nothing
outside it is held to it.

::code{file="examples/time_box/flow.py" from="def topic_work("}

Inside, the rules are the run's deadline's: from `deadline_s - slack_s` (default a
quarter of `deadline_s`) its tasks go before the others, its `finishing_kinds`
first, then the shortest remaining work. A task that is not of a finishing kind is
late when its finish chance is below 0.35: the share of the past tasks with
the same kind, flow path and loop passes whose own time and the work after them
fit in the time left (`JournalEstimates.finish_chance`), asked again as tasks
finish. A late task goes last. It still starts when a slot is free, since an idle
slot finishes nothing; it is deferred only when other tasks take every slot. A
task with no history and no `estimate_s` is never late. Past the deadline only
its `finishing_kinds` launch, for `grace_s`; every other task it creates is
deferred, and the flow receives `TaskDeferred` at its `await`. A box whose flow does not catch it raises it to the flow call that
awaits the box, which may catch it and go on. A box past its grace window is
cancelled: its flow call is `closed`, and the agent tasks it created still run to
their end. The deferred tasks are in
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
`index = { memory_mb = 1500, cores = 1 }` in `[defaults.claim_capacity]`. Give as
`memory_mb` the most memory one task takes, its coding agent and every process it
starts included.

Each running task with a `PerTask` claim holds its `memory_mb` from its start until
it ends, or what its processes take when that is more. A server that takes its
memory late is held all the same, and one that took its memory is counted once.
Each time the queue tries to start such a task, it reads the free memory and what
the running tasks' processes take, and checks two conditions. The holds, the new
task's `memory_mb` and the memory that other programs took must fit in the
baseline: the free memory read while no such task runs. The free memory now must
also hold the new task's `memory_mb` and what the running tasks hold but have not
taken yet. Tasks that start on one reading count each other's `memory_mb`, so a
burst of starts does not take more than the memory holds.

The free memory is what the OS reports as available (on Linux `MemAvailable` of
`/proc/meminfo`); where the OS reports none, memory does not limit the name. What a
task's processes take is the memory that the processes in its coding agents'
process groups do not share with other processes. A Python task runs inside the
run's own process, and a process can leave its agent's group, so what they take
counts as other programs' memory while the task's `memory_mb` stays held. The cores allow at most the
usable cores divided by `cores`. While no task holds the name, one starts anyway,
so a run always goes on even on a host short of memory. A larger `memory_mb` than a
task takes holds back other tasks. A waiting task starts as soon as a task ends or
the memory frees, while the others still run.

A claim that names `{params.<name>}`, where `<name>` is no field of the task's params
model (for a Python task, no parameter of its function), raises where the task is
declared. A claim that names `{unit}` on a task with no unit, or a parameter the call
does not give, raises at the task call; so does a parameter that holds an empty list,
which would claim nothing. Claims are not part of the fingerprint: they change
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
still run. By default the start is not tried again in the run. With
`Pipeline(service_cooloff_s=)`, the failure holds only for that many seconds: the
first task that claims the name after them tries the start again, and the tasks
before it still fail at once. A task that failed this way gets its one retry of a
`launch_failed` within `retry_wait_s`, so a cool-off shorter than `retry_wait_s` lets
some retries find the service started again. A service whose start fails only for
a moment can instead retry inside its own start. A resumed run starts it again for
the tasks that run again; a task the resume skips starts nothing. A stop that raises
is recorded with its exception, and the service counts as stopped.

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
(`timeout`, `max_turns`, `budget`), `rate_limited` with no hop left,
`cancelled` (called with `.options(cancellable=True)` and waited for by no flow call
any longer; see [Call options](#call-options)), and the rest of
`contraagent.backends.Stop`, each with its meaning in its docstring.

A run that is stopped stops its agents. Each agent runs in a session of its own, so
a terminal's Ctrl-C does not reach it: `Pipeline.run` (on the main thread) stops the
agents on SIGTERM and SIGINT before the process ends. A process killed outright
(SIGKILL, out of memory) runs nothing, so a watchdog process, started with the
first agent, stops the agents still running once that process is gone.

## The engine underneath

The parts under `Pipeline` work on their own (`contraagent.engine`); their docstrings
describe them.

| Part | What it does |
|---|---|
| `Run` | `runs/<id>/`: run lock, `plan.jsonl`, `journal.jsonl`, `flow_calls.jsonl`, `deferred.jsonl`, in-flight markers, the pipeline's own `pipeline/` (the current run of `contraagent.log` and `save` while it is open), resume by key and fingerprint |
| `AgentRunner` / `RetryingRunner` | one agent task: input check, route, credential (skipping one that rests on its quota), launch, validate, failover; progress-aware retry |
| `PythonTaskRunner` | Python tasks in-process, checked by the same contracts |
| `TaskAdapter` | what a domain says about its tasks (prompt, plugin, contracts, changes, env) |
| `WorkQueue` | claims and their capacities, caps, retry, throttle; a greedy schedule by bottom level, then priority, overdue tasks first with the starvation guard (`overdue_s`), and past `deadline_s - slack_s` the shortest remaining work first and late tasks last, deferred only when other tasks take every slot; every queued task finishes once through `follow_up` (run, skipped, refused or deferred) |
| `FlowDriver` | async flows over a `WorkQueue`, for flows that depend on results: each `await` waits for a task or a child flow call, and a failure raises `TaskFailed` there |
| `RoutingPlan`, `Router`, `CredentialRests` | per-kind routing and budgets, the failover chain, and the credentials that rest on their quota or after a refused launch |
| `run_until_valid`, `OutputContract`, `InputContract` | files checked by schema and validators; resume until they pass |
| `CursorStore` | resume cursor: stage, per-unit step, in-flight work, markers |
