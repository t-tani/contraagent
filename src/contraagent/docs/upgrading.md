# Upgrading from 0.6 to 0.7

This topic lists what a pipeline written for contraagent 0.6 changes to run on 0.7,
each change as the 0.6 form and the 0.7 form. It is the one topic that names the
forms of an earlier release. The other topics state only the forms of this release,
and `CHANGELOG.md` lists every change of 0.7.0, also those that need nothing from a
pipeline.

A flow that runs on 0.6 creates the same tasks with the same outputs on 0.7, once its
code is written in the forms below. The results differ in three places only: a task
whose input's writer failed or was deferred is not created, an exception of flow
code's own is a flow error also when a parent catches it, and a flow that gives each
unit a flow call of its own goes on past a unit that failed.

## Before you upgrade

Do these steps in this order for a pipeline that runs in production.

1. Finish on 0.6 every run that 0.6 started. 0.7 makes a task's fingerprint from
   other parts, so a resume on 0.7 of a run that 0.6 started runs every task once
   again, and spends what the first run spent. 0.7 reads the run directory of 0.6
   (run format 1), and the monitor shows it.
2. When the runs go to a hub, upgrade the hub first and the relays after it. A
   reader of 0.6.1 or earlier fails on the new fields of a 0.7 run
   (`flow_calls.jsonl` `raised_at`, `raised_by`, `unawaited`, and the call file's
   `params_json_schema`); the readers of 0.6.2 and later ignore a field they do not
   know. [Operating a hub](hub-operations.md#upgrade) has the steps.
3. Import again each recording that `contraagent recording import` made from a run
   of 0.6. A replay on 0.7 plays an imported recording only for the same
   fingerprint, so one imported from a run of 0.6 is not played: import it from a
   run of 0.7 ([Checking and testing](testing.md#import-a-run-that-was-not-recorded)).
   A recording that `--record` wrote is still played.
4. Move the waits, clocks, threads and I/O out of the flow's code into Python tasks
   (see [Flow code](#flow-code-no-clock-threads-or-io)).
5. Write each agent task call with an instance of its params model, and give a
   params model to each agent task that is given params (see
   [Agent task calls](#agent-task-calls-an-instance-of-the-params-model)). The
   JSON that the agent reads in the call file's `params` keeps its shape: the fields
   of the model, by name.
6. Give the unit to a Python task through a parameter named `unit`, and name the
   kind with `kind=` (see [Python tasks](#python-tasks)).
7. Give each value that is not JSON as an input file, or as a JSON type (see
   [Values that are not JSON](#values-that-are-not-json-and-large-inputs)).
8. Move `key=`, `after=`, `priority=` and `credential=` from the task call into
   `.options(...)` (see [Call options](#call-options)).
9. Await an output before you give it to another task, in an `async def` flow (see
   [Dependencies are values](#dependencies-are-values)). Add `outside_state=` to a
   task that reads what a task before it (`after=`) changed in the working tree.
10. Give each unit a flow call of its own where a failure of one unit must not stop
    the work on the others (see [Failures](#failures-the-run-keeps-going)).
11. Add `.options(cancellable=True)` only to a task whose answer is not needed once
    no flow call waits for it. A task without it runs to its end, as on 0.6 (see
    [Cancellation](#cancellation)).
12. Check the pipeline (see [Check the upgrade](#check-the-upgrade)).

## Agent task calls: an instance of the params model

An agent task call gives the unit and an instance of the task's params model. The
declaration `agent_task("x", params=XParams, output=Out, ...)` does not change.

| 0.6 | 0.7 |
|---|---|
| `x(unit, a=1, b=2)` | `x(unit, XParams(a=1, b=2))` |
| `x(unit, **params.model_dump())` | `x(unit, params)` |
| `x(a=1)`, a task with no unit | `x(XParams(a=1))` |
| `x(unit, a=1)` for a task declared without `params=` | declare a model, `agent_task("x", params=XParams, ...)`, then `x(unit, XParams(a=1))` |
| `x(unit)` for a task declared without `params=` | `x(unit)`, no change |
| an instance of a subclass of `XParams` | an instance of `XParams` itself |

A task declared without `params=` takes no params on 0.7: a call that gives it
params raises `TypeError`. A call with params as keywords raises `TypeError` that
shows the form to write. The call checks the instance under its model again, so a
value set on the instance after it was made and that does not validate raises
`TypeError` at the call.

A claim `{params.<name>}` is checked where the task is declared: a name that is no
field of the params model raises `ValueError` there, no longer at the first call.

The types of a task carry its params type too:

| 0.6 | 0.7 |
|---|---|
| `AgentTask[Out]` | `AgentTask[XParams, Out]`, and `AgentTask[None, Out]` for a task without a params model |
| `Mapping[str, AgentTask[Out]]`, from `implementations=` | `Implementations[XParams, Out]` |
| `AgentTask[Any]` for `output=Annotated[str, Field(...)]` | `AgentTask[XParams, str]` |
| `PythonTask[Out]` | `PythonTask[P, Out]`, with `P` the function's parameters |
| `TextOutput`, the text output a flow received | `str` |

A helper that takes any task and its params keeps both types:
`async def attempt[P: BaseModel, Out](task: AgentTask[P, Out], unit: str, params: P) -> Out`.
An `Annotated` output around anything but `str` raises `TypeError` where the task is
declared.

## Python tasks

A Python task is called as its function is called, and a type checker checks the
call against the function's parameters.

| 0.6 | 0.7 |
|---|---|
| `@python_task(name="k")` | `@python_task(kind="k")` |
| `PythonTask.name` | `PythonTask.kind` |
| `f(unit, x=1)` for `def f(x)`, the unit given beside the arguments | add the parameter: `def f(unit: str, x)` |
| `def f(unit, *args)`, `def f(unit, **kwargs)`, `def f(unit, x, /)` | a named parameter for each value, or one parameter of type `dict[str, ...]` |
| an annotation that names a type imported under `if TYPE_CHECKING:` only | import the type at run time |

A function without a parameter named `unit` makes tasks with no unit, with the key
`python:<kind>`. A positional-only parameter, `*args`, `**kwargs`, or an annotation
that pydantic has no JSON Schema for raises `TypeError` where the task is declared.

## Values that are not JSON, and large inputs

A task call copies its params as JSON when it is made. On 0.6 a value that was not
JSON was written as its `repr`; on 0.7 it raises `TypeError` at the call, and so does
a Python task's default that is not JSON. Give such a value as a JSON type (a model,
a list, a string), or, for a file, as an input file.

A long text that one task wrote and another reads is given as an input file, not as
its text: `InputFile`, a field of a params model or a parameter of a Python task. The
task is given the path and the SHA-256 of the content, and reads the file itself. For
the output file of a task that the flow awaited, `pending.input_file()` makes one;
`InputFile("in/spec.md")` makes one for a file in the working directory.
[Large inputs](tasks.md#large-inputs-input-files) shows both.

## Call options

The task call takes the task's params only. The key, the order with no output passed
on, the priority, an agent task's credential and the new `cancellable` are call
options, given by `task.options(...)`, which returns the same task with them.

| 0.6 | 0.7 |
|---|---|
| `x(unit, XParams(a=1), key="k", priority=2, credential="c")` | `x.options(key="k", priority=2, credential="c")(unit, XParams(a=1))` |
| `x(unit, after=[p])` | `x.options(after=[p])(unit)` |
| a params field or a Python task's parameter named `key`, `after`, `priority` or `credential`, refused | a param like any other |

A call option given as a keyword of the call raises `TypeError` that names
`.options()`. An option that `.options()` is not given keeps the value it had.
[Call options](tasks.md#call-options) states each option.

## Dependencies are values

A task is given values, not task calls. A flow that gives one task the output of
another awaits the output and passes it on, so it is an `async def` function.

| 0.6 | 0.7 |
|---|---|
| `b(unit, x=a(unit))`, a `Pending` among the params, also in a list, a dict or a model | `b(unit, BParams(x=await a(unit)))` in an `async def` flow |
| a plain `def` flow that gives one task the output of another | an `async def` flow that awaits the output; a plain `def` flow creates tasks that are independent or ordered with `after=` only |
| a task that waits for another with `after=` and reads what it changed in the working tree | the same, with `outside_state=` on the task that reads it |

A `Pending` among the params raises `TypeError` at the call, which says how to write
it. A task given in `after=` is no part of the fingerprint of the task that waits for
it: when that task runs again on a resume, the task after it does not, unless it
declares the state it reads with `outside_state=`. An `outside_state` function is
given the params as JSON, the call file's `params`, not the outputs read from their
files.

When the writer of an input fails or is deferred, the `await` of it raises
`TaskFailed` or `TaskDeferred`, and the task that would read the input is not
created. On 0.6 that task was created and refused (`invalid_input`) or deferred
(`dependency_deferred`). So `RunReport.failed` and `RunReport.deferred` count fewer
tasks, and `deferred.jsonl` has no `dependency_deferred` row.

## Flow code: no clock, threads or I/O

Flow code runs on an event loop of contraagent's own, which has no clock, no threads
and no I/O. An `await` that needs one of them raises `TypeError` at its line, and the
message says what to write instead.

| 0.6 | 0.7 |
|---|---|
| `await asyncio.sleep(5)`, `asyncio.wait_for(..., timeout=5)`, `asyncio.timeout(5)` in the flow | a Python task that waits; for a deadline over part of the flow, `await time_box(sub(unit), deadline_s=600)` |
| `asyncio.to_thread(...)`, `loop.run_in_executor(...)` in the flow | a Python task |
| an async HTTP client, a socket, a subprocess, the async API of another library in the flow | a Python task |
| a future of the event loop that runs the run, awaited in the flow | a Python task |
| a flow call that waits for what nothing will answer, kept until the run's deadline | closed at once when no task is queued or running and every flow call waits, with a `RuntimeError` that names its line |

`asyncio.sleep(0)` and `asyncio.timeout(None)` need no clock, and they work.
`asyncio.wait`, `asyncio.as_completed`, `asyncio.shield`, `asyncio.Queue` and
`asyncio.Event` run as on 0.6, but a flow does not use them: a branch on what finished
first can take another path on a resume. A flow waits with `await`,
`asyncio.gather` and `asyncio.TaskGroup`.
[The flow](tasks.md#the-flow) states the rules.

## Failures: the run keeps going

A failed task stops only the code that awaits its output, and the flow calls that
await that code. Every other flow call and task goes on, as on 0.6. A failure also
stops the rest of its own flow call, the work that does not need the failed output
included. So a loop over units in one flow call stops at the first unit that fails.

| 0.6 | 0.7 |
|---|---|
| a plain `def` flow whose loop over units goes on past a unit whose input's writer failed | a child flow call for each unit, gathered with `asyncio.gather(..., return_exceptions=True)` |
| `asyncio.gather(*units)` without `return_exceptions`, where the work after it must run on the units that got through | `asyncio.gather(*units, return_exceptions=True)`, then the work on the items that are no exception |
| work that is all or nothing | `async with asyncio.TaskGroup()`: the first failure closes the other flow calls of the group |

An exception of flow code's own (a bug, `TooManyPasses`) is a flow error wherever it
is caught, also by `gather(..., return_exceptions=True)` or `try` in a parent: it is
in `RunReport.flow_errors`, and `RunReport.ok` is False. On 0.6 a parent that caught
it could end the run ok. A flow call that raised records the line where it stopped
(`FlowCall.raised_at`) and the key of the failed task (`FlowCall.raised_by`).
[Failures](tasks.md#failures-the-run-keeps-going) shows a flow call for each unit and
a `TaskGroup`.

## Cancellation

By default a task runs to its end whatever happens to the flow call that created it,
as on 0.6. A task called with `.options(cancellable=True)` is cancelled once the flow
call that created it and every flow call that waited for it were closed: a queued one
is not launched, a running agent task has its launch stopped, and a running Python
task runs to its end. It ends with stop `cancelled`, is listed in
`RunReport.cancelled` and not in `RunReport.failed`, and a resume runs it again. Give
the option only to a task whose answer is not needed once no flow call waits for it,
such as one of several probes where the first finding decides.

## Records and the monitor

The run format stays 1: the records of 0.7 add fields and values, and remove none.

- `flow_calls.jsonl`: the end of a flow call that raised has `raised_at` and
  `raised_by`; the end of a top flow call has `unawaited`, the tasks that no flow
  call awaited, gave in `after=` or returned.
- `plan.jsonl`: `given_from`, the tasks whose outputs a task was given, as a value
  or as an input file, and `input_files`, its input files.
- `run.json`: `flow`, the top flow, which the monitor's forecast reads.
- `journal.jsonl`: `fingerprint_parts`, and the stop `cancelled`. `rerun` names the
  parts that changed.
- The call file: `params_json_schema`, the JSON Schema of the params model, beside
  `params`, whose shape does not change.
- `deferred.jsonl`: no `dependency_deferred` row is written.
- The monitor's API is 3.7.0: the plan state `cancelled`, the fields above, and the
  view `forecast`, the tasks a run is expected to create and has not yet.

## Check the upgrade

These steps launch no coding agent and spend nothing.

1. Type check the flow and its tasks with mypy (`--strict` is best) or pyright. They
   find a params model of another task, a misspelled field, a required field left
   out, params given to a task without a model, a call option given to the call, and
   a Python task called with an argument its function does not take.
2. Run `contraagent check <file.py>:<flow> --config pipeline.toml --kwargs '{...}'`
   until it prints ✓. It reports a call that the run refuses at the flow's line, with
   the form to write. Correct it and check again, since the flow stops at the first
   one ([Check](testing.md#check-nothing-launches)).
3. Run the flow as a stub run on 0.6 and on 0.7 (`contraagent run <file.py>:<flow>
   --config pipeline.toml --stub --kwargs '{...}'`), and compare the tasks that each
   lists. They are the same, but where the [first section](#upgrading-from-06-to-07)
   says they differ ([Stub run](testing.md#stub-run-the-whole-flow-on-examples-nothing-called)).
4. Run the tests of the flow on `contraagent.testing.StubAgent`.
