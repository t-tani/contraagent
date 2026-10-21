# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The changes not released yet are the fragments in [`changelog.d/`](changelog.d/);
`towncrier build --draft` shows them as the next release's section.

<!-- towncrier release notes start -->

## [0.7.1] - 2026-10-21

### Fixed

- A light launch whose instructions hold a long param, and a launch with a long `preamble` param, now start on every coding agent. The system prompt went on the command line of Claude Code, omp and pi and into `OPENCODE_CONFIG_CONTENT` for opencode, and the preamble went on the command line of omp and pi; past 131072 bytes on Linux the launch failed with `[Errno 7] Argument list too long`. Each system prompt is now a file in the launch's scratch directory that only the user can read (`--system-prompt-file` for Claude Code, a file path for omp's and pi's `--system-prompt`, `{file:...}` in opencode's config). The preamble is now the head of the prompt, which goes over stdin when it is long, so omp and pi get the preamble and the prompt as one first message instead of two turns. Codex gets `append_system_prompt` at the head of the prompt instead of as `developer_instructions` on its command line. A prompt goes over stdin by its size as the operating system counts it, not by its characters: past 60,000 bytes in UTF-8 (on Windows, 16,000 UTF-16 code units), so a prompt of 50,000 Japanese characters (150,000 bytes) no longer goes on the command line.
- A task whose params hold a long text launches. Every scalar param was also copied, as JSON, into one variable of the launch's environment, and a variable longer than the operating system allows (131072 bytes on Linux) made the launch fail with `[Errno 7] Argument list too long`. The params now reach an agent only through its call file (old → new): an agent read its scalar params from `CONTRAAGENT_PARAMS` → from its call file (`CONTRAAGENT_CALL`), which holds every param.
- A launch that the operating system refuses for its own command is not launched again: arguments and environment too long (`E2BIG`), an executable it cannot run (`ENOEXEC`) or may not run (`EACCES`). The launch fails with `launch_failed`, its reason says that the command is refused on every launch, and its result is not retryable (`LaunchResult.retryable`, `TaskResult.retryable`): neither the kind's `retries` nor the queue's retry of a launch that never ran tries it again. The task still fails over to the next route, which has its own command. A missing executable (`ENOENT`) and every other launch failure are retried as before.
## [0.7.0] - 2026-10-21

### Added

- `contraagent check` reports a task call that the run refuses at the flow's line, with the form to write: a `Pending` among the params, params given to a task without a params model or as keywords, an instance of another model, a call option given to the call, a Python task called with an argument its function does not take, or flow code that needs a clock, a thread or I/O.
- A resume names what changed when it runs a task again: the journal row keeps a digest of each part of the fingerprint (`JournalRow.fingerprint_parts`, `Task.fingerprint_parts`: `definition`, `params`, `input_files`, `outside`, `output_of`), and `rerun` names the parts that differ, as in `its fingerprint changed: its definition` or `its fingerprint changed: its params`. A task whose params changed although every task it was given an output of or created from was skipped is a divergence: the flow's code gave other params for the same outputs (a clock, randomness, outside state, or changed code). Its `rerun` starts with `divergence:`, and the run logs the warning `[resume] <key>: divergence: ...`. The task runs again, as before.
- A flow call that raised records where it stopped and because of which failed task: `FlowCall.raised_at` (a `Frame`: the line where the exception left the flow call's own code, mostly the `await` that failed) and `FlowCall.raised_by` (the failed task's key, the first one in an exception group; null for an exception of flow code's own), in `RunReport.flow_errors`, at the end of its `flow_calls.jsonl` record (`raised_at`, `raised_by`), and in the monitor's `FlowCallNode` (API 3.7.0). `contraagent run` prints the place of each flow error. A reader of 0.6.1 or earlier fails on the new fields: upgrade a hub before its relays.
- `plan.jsonl` records where each task's params came from: `given_from`, the keys of the tasks whose outputs had reached the flow call that created the task, its causal past (every result that reached it or its ancestors before they created it, and what the flow calls whose end it awaited had received: `FlowDriver.received`), and are among the task's params: an output whose JSON is a value of its params at any depth, whole, or one whole row of which is (an output that is a list), and an output whose file is an input file among its params (`Origin.given_from`, monitor `PlanNode.given_from`). A copy of an output counts as the output; a field or a text taken out of it, or a value built from it, does not, and created from still shows that the task came after it. An equal output of another unit's flow call is not named, and when several equal outputs are in the causal past, each is named, in the order their tasks were created. It is shown only, never part of the fingerprint or of what a resume skips; a resume's divergence is judged by it. The monitor draws a task after the tasks it was given from, and counts them among its earlier tasks (`TaskIO.upstream`) and their later ones (`downstream`).
- `InputFile`, a file a task is given as a param by its path and the SHA-256 of its content, taken at the task call: a field of an agent task's params model or a parameter of a Python task (`pending.input_file()` for the output file of a task the flow awaited, `InputFile("in/spec.md")` for a file on disk). The params hold `{"path", "sha256"}`, with a JSON Schema that tells the agent to read the file; the fingerprint holds both (journal `fingerprint_parts` `input_files`); a task whose file no longer has that content as it starts is refused (`invalid_input`); and a path outside the working directory and the run's `out/` raises `ValueError` at the call. A Python task is given it with an absolute path, and `read_text` and `read_bytes` check the content. `PythonTask.arguments` and `PythonTask.invoke` take `cwd=`, the directory a relative path is under. See "Large inputs" in `contraagent docs tasks`.
- The monitor has a forecast: the tasks a run is expected to create and has not yet, with their wall time and cost, read from the run of the same flow that finished last before it started (`run.json` records the top flow as `flow`). It is the view `forecast` (`/api/runs/<run>/forecast`, `Forecast`, `ForecastEntry`; the run feed's `forecast` event, an export's `forecast.json`), above the pipeline graph ("Forecast: 7 more tasks | 4m 10s of task time | $0.62") and on each kind node as the tasks it is expected to have beyond its own. A display only: the schedule never reads it (`Monitor.forecast`, API 3.7.0).
- The monitor tells data from order and from creation: an edge of the pipeline graph is solid for `given_from` (the later tasks were given the earlier ones' output), dotted for `after` alone (order only) and dashed for `created_from`; a highlighted unit rings the tasks joined to it in the style of their link; a task's earlier and later tasks carry their lineage (`UpstreamTask.lineage`, `DownstreamTask.lineage`), and its earlier tasks now include those it was created from. A task's input files are its `InputFile` params, which `plan.jsonl` now records (`input_files`), shown with the task whose output file each is and the check at the start (`TaskIO.input_files`, `TaskInputFile`); the files of an input contract are "Checked files it reads". The monitor also shows where a failure stopped a flow call (on the failed task and on the flow call's mark), the tasks no flow awaited, a rerun's changed fingerprint parts and a divergence, and counts cancelled tasks as finished everywhere, never among failed attempts (API 3.7.0).
- The call file carries the JSON Schema of the task's params model beside its params: `params_json_schema`, with each field's `Field(description=...)` and constraints (`AgentTask.params_json_schema`; an object with no properties for a task without a model). The prompt tells the agent that it says what each parameter is, and a light launch's prompt holds it. The call file's `version` stays 1; a reader of an earlier release does not know the field, so a hub is upgraded before its relays.
- The end of a top flow call in `flow_calls.jsonl` lists its unawaited tasks: `unawaited`, the keys of the tasks created in it or in the flow calls it started that no flow call awaited, gave in `after=` or returned (`FlowCall.unawaited`, monitor `FlowCallNode.unawaited`; for a flow that does not wait, the end of flow call `0`). They ran all the same: this is information, never an error. A top flow call's end is recorded once every flow call it started has ended, with the time it ended itself. `FlowDriver(holds=)` tells the driver which tasks a returned value holds.
- The documentation topic `upgrading` (`contraagent docs upgrading`) lists each change that a pipeline written for 0.6 makes to run on 0.7, as the 0.6 form and the 0.7 form, with the steps for a pipeline in production (finish the runs that 0.6 started on 0.6, upgrade a hub before its relays) and how to check the upgrade.

### Changed

- A task call takes the task's params only. Its key, its order without data, its priority and an agent task's credential are its call options, given by the new `AgentTask.options(key=, after=, priority=, credential=, cancellable=)` and `PythonTask.options(key=, after=, priority=, cancellable=)`. `options` returns the same task with them, typed as the task is, and an option it is not given keeps the value it had (old → new):

  - `task(u, key="k", priority=2, credential="c", a=1)` → `task.options(key="k", priority=2, credential="c")(u, TaskParams(a=1))`.
  - `task(u, after=[p])` → `task.options(after=[p])(u)`.
  - A call that still gives `key=`, `after=`, `priority=`, `credential=` or `cancellable=` to a task with no param of that name raises `TypeError`, which names `.options()`; a Python task given `credential=` raises as before.
  - A params field or a Python task's parameter named `key`, `after`, `priority` or `credential` was refused where the task was declared → it is a param like any other, and the call gives it.
  - `key=None` and `credential=None` on a call meant "none" → `options(key=None, credential=None)` clears the key and the credential the task had; an option not given keeps its value.
- A task called with `.options(cancellable=True)` is cancelled once the flow call that created it and every flow call that waited for it were closed (a failed sibling in an `asyncio.TaskGroup`, a time box past its grace window) and no flow call waits for it: a queued one is not launched, a running agent task has its launch stopped within a second, and a running Python task runs to its end. It ends with the new stop `cancelled` (in `journal.jsonl`, `TaskResult.cancelled`): not ok, not retried, not a failure (the new `RunReport.cancelled`, never `RunReport.failed`), and a resume runs it again. The files it created under its `changes` patterns are removed as those of a failed attempt are. A task called without the option runs to its end whatever happens to its flow calls, as before. New in the engine: `Task.cancellable`, `WorkQueue.cancel(key)`, and a runner's `cancel(task)`, which the queue calls when the runner has one (`AgentRunner`, `RetryingRunner`, `PythonTaskRunner`). The monitor shows such a task as cancelled: plan state `cancelled`, `TaskCounts.cancelled` and `PlanGroup.cancelled` (API 3.7.0).
- Near a deadline, the queue no longer leaves a slot idle to defer a task that cannot finish in time. Such a late task goes after every other task and starts when a slot is still free; it is deferred (`cannot_finish`) only when other tasks take every slot. A task alone, or with free slots around it, now runs instead of being deferred: it may still finish, and an idle slot finishes nothing.
- A task's fingerprint is what it is given and what it observes: its kind, unit, key, the JSON of its params (an output it was given among them, by its content; a Python task's defaults filled in), its definition, the path and hash of each input file, the file an `output_of` task fills in and its outside state (old → new):

  - A task it waits for with `after=` stood in its fingerprint by that task's fingerprint → it is no part of it: a task that only waits for another no longer runs again on a resume when the other does. A task that reads what an `after=` task changed in the working tree declares it with `outside_state=`.
  - An output it was given stood by the content of its output file → it is part of `params`, as the JSON of the value the flow passed. A task that runs again and writes the same output still leaves the tasks given it skipped.
  - A resume ran again every task that waited for a task whose last result was `partial` → the tasks given its output run again when it now writes another output.
  - A call that gives a Python task's default and one that leaves it out had two fingerprints → one.
  - A run started on 0.6 that 0.7 resumes runs every task once more, since each fingerprint is made from the digests of its parts. Finish a running run on 0.6 before upgrading.
- Flow code runs on an event loop of contraagent's own, with no clock, no threads and no I/O, and the run lets the flow calls run until every one of them waits before it starts what they queued. What changes for a flow (old → new):

  - `asyncio.sleep(5)`, `asyncio.wait_for(..., timeout=5)`, `asyncio.timeout(5)`, `asyncio.wait(..., timeout=5)` and `call_later` in flow code: they waited on the run's event loop → they raise `TypeError` at their `await`, which says to give a deadline with `time_box()` and to wait in a Python task. `asyncio.sleep(0)` and `asyncio.timeout(None)` still work.
  - `asyncio.to_thread`, `run_in_executor` and `call_soon_threadsafe` in flow code: they ran on a thread → `TypeError` at the `await`. Sockets, pipes, subprocesses (`asyncio.open_connection`, `asyncio.create_subprocess_exec`) and signal handlers: they ran → `TypeError` at the `await`. Each message says to put the work in a Python task.
  - Awaiting a future of another event loop in flow code, the caller's own included: it worked for the event loop that ran the run → asyncio's `RuntimeError` at the `await`. `asyncio.get_running_loop()` in flow code is the flow's own event loop.
  - A flow call that waits for what nothing will answer (an `asyncio.Event` that no flow code sets): the run waited for it until its deadline and grace window, or forever with no deadline, then closed it with no error → once no task is queued or running and every flow call waits, the run closes it at once (`closed`), with a `RuntimeError` that names the line where it waits; a top flow call closed this way is in `RunReport.flow_errors`, so the run is not ok. So is a top flow call that the run closed and that raised an exception of its own while it ended.
  - Flow call ids and records: a Task whose coroutine was flow code took the next number in its parent, any other Task none → every asyncio Task created while a flow call's code runs takes the next number, the one asyncio makes around a task call given to `asyncio.gather` included, so the ids of later flow calls move up (in the analysis example, `analyse_file` is `0.1.3` after two gathered `classify` calls, not `0.1.1`). Every flow call was in `flow_calls.jsonl` and the monitor from its start → a flow call is on record only once it creates a task or a flow call, or ends with an error of its own, a top flow call from its start (a task's `TaskFailed` or `TaskDeferred` that only passes through a flow call does not put it on record: the task's own record says it); a Task that only waits for a task already created leaves no record, so the ids on record may skip numbers. A start row's `ts` is still when the flow call started.
  - Flow code ran whenever the event loop turned, also while the queue waited for a task → it runs only between the queue's passes, after the results that came in since, so the steps of the flow calls follow the order in which the results came, whatever else runs on the event loop.
  - A coroutine never awaited that was dropped in a reference cycle was reported after a garbage collection at the run's end → only a coroutine dropped at once is reported; mypy (`unused-coroutine`) and pyright (`reportUnusedCoroutine`) find both.
  - A step of flow code longer than `slow_step_s` was logged per step of a flow call → per callback of the flow's event loop, naming its flow call, and once for a run of flow code that has gone on that long in all without waiting for a task.
  - An asynchronous generator that flow code left open was closed by the caller's event loop → by the flow's own event loop when the run ends.
  - `contraagent check` ran an async flow on a new event loop → on the calling thread with no event loop.
  - `FlowDriver`: `async def wait(item) -> Any` → `def wait(item) -> Coroutine[Any, Any, Any]`, a coroutine that is awaited once; `on_flow_call` events `"start"` (at creation) and `"end"` → `"create"` at creation, `"start"` when the flow call goes on record, `"end"` for every flow call, with the new `FlowCall.recorded`; `settle_here()` and `finish_here()` drive the flows where no event loop runs; `driving()` puts no task factory on the event loop and works where none runs; `finish()` waited up to 5 seconds for the flow calls it cancelled → it lets them end at once.
- The documentation states the failure rule that runs already follow (keep going): a failed task stops only the code that awaits its output and the flow calls that await that code; every other flow call and every queued or running task goes on, a parent that ends leaves its children running, and `asyncio.TaskGroup` is the choice for all or nothing. The examples that fan out give each unit a flow call of its own and gather them with `return_exceptions=True`: the demo's and the review example's `docs`, the analysis example's `analyse` and `analyse_bundle`, the tutorial's `triage_and_plan`, and the `missing` and `rows` examples' `reviews` report on the units that got through; `implementations`' `review_all` reviews every unit at once and leaves a failed one out of its counts. The review example adds `publish`, all or nothing with a `TaskGroup`. A flow waits with `await`, `asyncio.gather` and `asyncio.TaskGroup`; the documentation says that it does not use `asyncio.wait`, `asyncio.as_completed`, `asyncio.shield`, `asyncio.Queue` or `asyncio.Event`. They still run, but a branch on what finished first can take another path on a resume.
- An exception of flow code's own in a flow call that is not a top flow call (a bug, `TooManyPasses`; not a task's `TaskFailed` or `TaskDeferred` passing through) was not a flow error when a parent caught it, with `asyncio.gather(..., return_exceptions=True)` or `try`, and the run could end ok → it is a flow error wherever it is caught: `RunReport.flow_errors` lists it once, for the flow call it started in, and `RunReport.ok` is False. An exception of its own that reached a top flow call is listed for the flow call it started in, no longer for the top flow call. A failed task that a parent tolerates still makes the run not ok only as a failed task. New: `FlowDriver.flow_errors()`.
- A Python task's kind is named as an agent task's is (old → new): `@python_task(name="k")` → `@python_task(kind="k")`, and `PythonTask.name` → `PythonTask.kind`, now a field.
- Whether a task can finish before a deadline is decided from the samples of its kind and tail key, no longer from their median: a task is late when fewer than 35% of its samples (its own wall time and the work after it) fit in the time left, and each queue pass asks again as tasks finish. `JournalEstimates` keeps the 100 most recent samples of each kind and tail key and gives the share that fits (`JournalEstimates.finish_chance`); `WorkQueue(finish_chance=)` and `Run.queue(finish_chance=)` take it, a `FinishChance`; `Run.queue` gives the run's own when it also uses the run's own estimates. The queue's order still uses the median.
- A task call is typed: a type checker (mypy, pyright) checks an agent task's params against its params model and a Python task's arguments against its function, before anything runs. The params JSON the agent, the plugins, the claims, the validators and the monitor read stays as it was: the fields of the model, by name (old → new):

  - `x = agent_task("x", params=P, output=Out)` called `x(u, a=1, b=2)` → `x(u, P(a=1, b=2))`; `x(u, **p.model_dump())` → `x(u, p)`; a task with no unit, `x(a=1)` → `x(P(a=1))`. Keyword params raise `TypeError`, which shows the form to write.
  - An agent task declared without `params=` took any JSON params → it takes none: `x(u)` or `x()`, its params `{}`; a call that gives it params raises `TypeError`. A task that is given params declares a params model (`agent_task("x", params=XParams, ...)`), called `x(u, XParams(a=1))`.
  - An instance of a subclass of the params model was taken → `TypeError` at the call: the instance is of the declared model itself, whose JSON Schema describes every field. A value set on the instance after it was made is checked again under the model at the call.
  - `AgentTask[Out]` → `AgentTask[ParamsT, Out]` (`AgentTask[None, Out]` for a task without a params model); `implementations=` returned a `Mapping[str, AgentTask[Out]]` → `Implementations[ParamsT, Out]`, now public, whose `task[name]` is typed `AgentTask[ParamsT, Out]`. A helper over any task keeps both types: `async def attempt[P: BaseModel, Out](task: AgentTask[P, Out], unit: str, params: P) -> Out`.
  - `agent_task("x", output=Annotated[str, Field(examples=[...])])` was typed `AgentTask[Any]` → `AgentTask[ParamsT, str]`; an `Annotated` output around anything but `str` raises `TypeError` where the task is declared.
  - `PythonTask[Out]` → `PythonTask[**P, Out]`: a Python task is called as its function is. Its parameter named `unit` takes the task's unit; `f(u, x=1)` for a function `def f(x)` without one gave the unit beside its arguments → `TypeError`: add `unit: str` to the function (`def f(unit: str, x)`). A function with no `unit` parameter makes tasks with no unit.
  - A Python task's function with a positional-only parameter, `*args` or `**kwargs`, or a parameter annotated with a class pydantic has no JSON Schema for (checked with `isinstance`), was taken → `TypeError` where the task is declared: name each parameter, and annotate it with a JSON type or a pydantic model. An annotation that names a type not defined when the task is first called (one imported under `if TYPE_CHECKING:` only) took any value → `TypeError` at that call, naming the type.
  - A claim `{params.<name>}` whose name was no param was refused at the task call → `ValueError` where the task is declared, when the params model has no such field (a Python task's function no such parameter).
  - `typing-extensions` is a direct dependency again (pydantic already depends on it), for the defaults of the params and output types (PEP 696) on Python 3.12.
- A task is given values: a task call copies its params as JSON at the call, and a `Pending` is never a param (old → new):

  - `b(u, x=a(u))`, a task call's `Pending` among another task call's params (also in a list, a dict or a model) → `b(u, BParams(x=await a(u)))` in an `async def` flow; for an order with no output passed on, `b.options(after=[a(u)])(u)`. The old form raises `TypeError` at the call, which says how to write it.
  - A plain `def` flow that gives one task another's output → an `async def` flow that awaits the output and passes it on, best one flow call per unit under `asyncio.gather(..., return_exceptions=True)`. A plain `def` flow creates tasks that are independent or ordered with `after=` only.
  - A task whose input's writer failed was refused (`invalid_input`), and one whose input's writer was deferred was deferred (`dependency_deferred`) → the writer's `await` raises `TaskFailed` or `TaskDeferred`, and the task is not created: `deferred.jsonl` no longer gets `dependency_deferred`, and `RunReport.failed` and `deferred` count fewer.
  - The call file's `params` and a Python task's arguments were read from the upstream output files as the task started → they are the values the flow passed, copied when it called the task. A Python task's unannotated parameter is given that JSON (a model as a dict, a tuple as a list); an annotated one is converted to its annotation as before.
  - An agent task's params were validated under its params model as the task started → at the call, where params that do not validate raise `TypeError`.
  - A param that is not JSON was written as its `repr` → `TypeError` at the call. So is a Python task's default that is not JSON.
  - An `outside_state` function was given the outputs read from their files → the params as JSON, the call file's `params`.
  - `TextOutput`, the `str` a flow received for a text output → `str`.

### Fixed

- Launches that start together on one backend now ask the coding agent for its version and its models once, and make one scratch directory root, instead of one each when they asked at the same moment.
- After Ctrl-C, or when `Pipeline.run` returns, the tasks still on its event loop have 30 seconds to end once cancelled. A task that ignores its cancellation is then left behind with a warning that names it, instead of a wait with no end.
- A Codex launch's tokens no longer become 0 without notice when its rollout file cannot be read. The totals that `codex exec --json` prints in `turn.completed` are now the reference: the rollout file's calls are used only when they add up to these totals, and a resumed launch counts only its own part of the thread's totals. When the rollout file is missing, holds no line this contraagent can read, or does not add up, the launch keeps the printed totals as one call, and the new `LaunchResult.usage_unknown` (also in `launches.jsonl` and `JournalRow.usage_unknown`) is `calls`, or `tokens` when no totals were printed either. The monitor marks such an attempt, and a warning is logged once per process.
- A task's created from (`plan.jsonl` `created_from`, `Origin.created_from`, the monitor's dashed edges) now follows what caused the step of flow code that created the task. The run gives the results to the flow code one at a time, in the order they came, and lets the flow calls run until each waits again after each one. A result reaches a flow call when the step that it resumes runs in that flow call: a task it awaits, an item of a `gather` or `TaskGroup` it awaits, or a flow call it awaits, which brings that flow call's own created from. What changes (old → new):

  - A flow call took the created from of every child flow call that ended, awaited or not → only the results that reached it count: a flow call or a task that nothing awaits reaches no one.
  - The keys followed the places of the waits that gave them (a `gather`'s by position) → they are listed by the flow call that queued each, then in the order that flow call queued them.
  - Two results that came between two passes of the queue reached the flow code together → one at a time: a `TaskGroup` whose child fails cancels its other children before a later result reaches them.
- A resume runs again a task whose output file no longer reads under its output schema, its journal row's `rerun` saying so. Before, the resume skipped it and the flow received `TaskFailed` (`invalid_output`) at the `await`.
- The run knows exactly when every flow call waits: it lets flow code run until no callback of the flow's event loop is ready, instead of until three quiet turns of the event loop or 5 seconds. A flow that awaits `asyncio.gather` nested four or more deep reached its next wait one pass of the queue late; it now reaches it at once.
- The OpenCode Go usage reading (for opencode and pi on an `opencode-go/` model) now closes the response when the usage endpoint refuses the request, for example with 401 for a key that is no longer valid. Before, the open response stayed until garbage collection, and Python 3.14 warned about it with a `ResourceWarning`.
- The monitor's pipeline graph keeps its focus, zoom and pan when the outline of the flow moves beside it or above it, or first appears. Before, the graph was drawn again from the start: a reader who had just focused an item, often right after the page loaded, lost the focus, and Enter did nothing.
- A Claude Code launch that answers in one turn without a tool is hollow only when its answer is tool calls written out as text: the first line is one (`Bash(...)`, `Read(...)`), or most lines are. An answer that quotes a call inside a sentence or a code example, such as `Read(path)`, is no longer hollow, so the task is not attempted again for it.
- `contraagent run`, `check` and the other commands that load `path/to/file.py:attr` refuse a file whose name is a module that is already imported, such as `queue.py` or `types.py`, with an ImportError that says to rename it. Before, the file replaced that module in `sys.modules` for every importer in the process. A file loaded before under the same name still gives the name up to the next one.
- A run on a file system without file locks (`ENOLCK`, as on some NFS mounts) no longer fails with `RunLocked`, which said that another process held the run. It now raises `OSError` that names the lock file and says that the runs directory needs a file system with file locks. Only a lock that another open file holds reads as held.
- A debugger, profiler or other `sys.monitoring` tool that takes tool id 3 or 4 after a run ends now receives every jump again: the run turns back on the locations its loop counting disabled. The counting no longer keeps each analysed code object alive, and off CPython it counts nothing instead of failing.
- `contraagent run` and `contraagent check` explain a pydantic `ValidationError` that refused a `Pending` as the value of a params model's field: after pydantic's message, they say which field it is and how to write it, as a task call does for a `Pending` among its params (await the task call and pass its output, or give it in `.options(after=[...])` for an order only). The exception is unchanged, in `RunReport.flow_errors` too.
- A pi launch on the user's pi logins that ends `auth_failed` now says in its reason that a pi the user runs on the same login at the same time can make its refresh token invalid, since pi locks a refresh in the directory it runs with. The documentation of the agents says not to run pi on a login while a pipeline uses it.
- A relative `plugin=` or `skills_from=` path of `agent_task` now starts at the user's file that declares the task even when the call reaches `agent_task` through the standard library (for example `functools.singledispatch(agent_task)`); before, it started at the directory of the frame two calls up. A function in another directory that declares tasks for its callers takes an absolute path from them (`Path(__file__).parent / "plugins/review"`), as the guide now says.
- `FlowCall.raised_at` is the line of flow code that called a function that raised, when the function is not `async def`: a helper of the flow, or a library such as pydantic refusing a field's value. Before, it was the line inside that function, such as `pydantic/main.py:280`. Only the frames of the flow call's own coroutine and the coroutines it awaited count.
- `Pipeline.check` and the start of a run, while they find the task declarations a flow's code can reach, no longer call a module's `__getattr__` (a name imported when first used, a deprecation warning). They read a module's attributes from its namespace only.
- Every reader of a run's records ignores a field it does not know, as
  `compatibility.md` states: the monitor, the hub, a resume and the Stop hook
  (`contraagent call validate`) read the records of a later release of the same
  run format. Before, a new field in a call file, `flow_calls.jsonl`,
  `deferred.jsonl`, `launches.jsonl`, the cursor, a flow path, a time box, a
  deferral's cause or `run.json`'s `preflight` stopped the reader. The JSON
  Schemas of the records no longer say `"additionalProperties": false`. The
  config file, and a task's params against its params model, are checked as before.
- The estimates of a run and the quota readings it starts from take the most recent runs by the time of the last row of each journal, so a copy of the runs directory that did not keep the files' times reads the same runs. A journal whose last row has no time still goes by its modification time.
- `contraagent relay` logs a warning, once for each content, when a run document does not parse as JSON, and does not send it until it parses. Before, it waited for such a document without a word, as if it were half written, though documents are always replaced whole.
- A resume gives the flow the results of the tasks it skips one at a time, in the order the journal of the earlier attempts recorded them, so flow code that depends on the order in which its tasks finish (`asyncio.as_completed`, a list it appends to as each `await` returns) creates the same tasks again. Before, the skipped results came in the order the flow created the tasks. A task whose fingerprint is complete only when it starts (it declares `outside_state` or `output_of`) is skipped as soon as the tasks it waits for are done; before, it waited for a free slot, and a deadline could defer it. A task that fills in another task's file (`output_of`) takes the file's content as it was when the task was about to start into its fingerprint, not the fingerprint of the task that wrote the file. A resume skips it when the file is as it, or a task after it that fills the file in, left it (the new journal field `output_of_after`), so a file edited by hand runs again every task after its writer that fills it in. Fingerprints are made in a new way, from the digest of each part of a task's work: resuming a run of an earlier contraagent runs every task once again, and a recording imported from such a run is not played: import one from a run of this release instead.
- `contraagent run` reports a flow that raised before its first task as `contraagent check` does: one line with the flow's file and line and the message that says how to write it, and exit status 1. Before, it printed a Python traceback of about 35 lines, for a task call in an older form, `asyncio.sleep` in a flow or a generator flow. An exception that did not pass through flow code is a bug of contraagent's own and keeps its traceback.
- The monitor returns to the same place in the history list after a reload, also when the run's rows arrive in parts, as on a slow machine or connection. Before, the position was set as soon as the first rows were tall enough, and the newer rows that arrived after them, above it in the list, moved the list down by their height.
- The warning for a slow step of flow code ("heavy work belongs in a Python task") now counts only the time of flow code itself. The work contraagent does for a task call, for the creation of a flow call and for the analysis of a loop is left out, so a cold `contraagent check` or `run` on a busy machine no longer warns about a flow that does no heavy work.

## [0.6.2] - 2026-10-20

### Fixed

- A rewrite that puts back a file's old modification time and size is now seen as a
  change: outside Windows, an output contract, a task's `changes=` and a recording run
  also compare the file's status change time and inode, which a program cannot set back.
  The relay compares the content of the files a contract names, so it sends a file
  rewritten at the same size and modification time. The monitor shows a task as running
  from its in-flight marker only while the marker's process has the start time the marker
  holds, so a pid that another process now has no longer shows a finished task as
  running, and a resumed run removes the markers an earlier attempt left.
- A run record that cannot be written is no longer silent. A journal row that cannot be written no longer prints only a traceback: the run goes on, says so in a warning line of its log, and `Pipeline.run` then raises `ContraagentError`, which names the journal and the first error, and leaves the run unfinished, because a resume runs those tasks again. A record that only the monitor reads (`launches.jsonl`, `flow_calls.jsonl`, `rests.jsonl`) gets a warning line and a count by file in `RunReport.summary["record_failures"]`, and the run goes on. The run's log also says when the queue's deferral check or the completion of a fingerprint raised, and a definition or a launch marker that cannot be written is a warning of the `contraagent` logger.
- A run stopped by SIGTERM or Ctrl-C can no longer hang: the signal handler only wakes a thread that stops the agents and the services, so the teardown never waits for a lock that the interrupted main thread holds. From the signal on, no agent, Python task or service starts: a launch is refused with stop `launch_failed`, until the run has ended, and for the rest of the process on SIGTERM. A run stopped by SIGTERM now also removes its temporary directories (the file of `Pipeline(mcp_servers=)`, which may hold a secret, and each coding agent's scratch directory) before the process ends. A host application's own SIGTERM or SIGINT handler is now called at once, while the teardown runs, and the run waits for the teardown before its services stop and its lock is released.
- A launch that ended normally is `completed` whatever its answer says. A Claude Code answer that mentioned a rate limit, such as the summary of a task that added rate limiting to an API, was `rate_limited`: the route rested and the task ran again on the next hop. Only an error result's words can now make a launch `rate_limited`, `auth_failed` or `refused`. omp's text mode reads a refusal by its exit status and its stderr, so a short answer that mentions a rate limit is `completed` too. Every coding agent now reads a quota refusal or a refused credential only in the forms that it or its provider prints, such as `unexpected status 429 Too Many Requests`, `429 Go usage limit exceeded`, `Rate limit reached for ...` and Claude Code's `You've hit your limit`, `You've hit your Opus limit` and `API Error: Request rejected (429)`. A failed launch whose stderr holds `line 429` in a traceback, a path such as `rate_limit.py` or `quota.py`, or `Disk quota exceeded` no longer rests its route.
- The watchdog that stops the agents of an interpreter killed outright (SIGKILL, the OOM killer) on Linux and macOS now signals a process group only while the agent that leads it has the start time recorded when it was launched, or when that agent has ended and only the processes it started remain. It no longer signals an unrelated process that was later given the same process id.

## [0.6.1] - 2026-10-20

### Fixed

- A Python task annotated `-> Out | Partial[Out]` is a `PythonTask[Out]`, so a type checker knows that `await` on its task call, and its `Pending.output`, give an `Out`, as they do when the flow runs. It was `PythonTask[Out | Partial[Out]]`, and every `await` on such a task had to remove `Partial` from the type. A function that always returns `Partial[Out]` is a `PythonTask[Out]` too.

## [0.6.0] - 2026-10-20

### Added

- `Pipeline.run_async` and `WorkQueue.run_async` run a pipeline or a queue on a running asyncio event loop, from an `async def` function. The queue's loop is now a coroutine on an event loop, and the runners still run on threads of the queue's pool. `Pipeline.run` and `WorkQueue.run` run that coroutine on a new event loop, and raise `RuntimeError` when they are called from a thread whose event loop is running.

### Changed

- A flow that waits for outputs is an `async def` function that waits with `await` on the run's asyncio event loop, and the outputs it receives have the types of their tasks. Generator flows are refused with a `TypeError` that shows the rewrite. A flow that does not wait stays a plain `def`.

  | Old | New |
  |---|---|
  | `def flow(...):` with `yield` | `async def flow(...):` |
  | `x = yield task(...)` | `x = await task(...)` |
  | `xs = yield [a(...), b(...)]` | `xs = await asyncio.gather(a(...), b(...))`; with `return_exceptions=True` to keep each failure by position |
  | `yield [sub(u) for u in us]` (child flow calls) | `await asyncio.gather(*[sub(u) for u in us])`, `asyncio.TaskGroup`, or `asyncio.create_task` |
  | `yield from helper(...)` (the same flow call) | `await helper(...)` |
  | `yield time_box(gen, deadline_s=...)` | `await time_box(coro, deadline_s=...)`; `time_box` takes a coroutine |
  | `@max_passes(n)` on a generator function | `@max_passes(n)` on an `async def` function |

  A flow call is an asyncio Task whose coroutine is flow code, numbered `<parent>.<n>` in the order the parent creates it; `FlowCall.site` and the flow path name where the parent created it. Cancelling a flow call (a `TaskGroup` whose sibling failed, a deferral past the grace window, the end of the run) records it `closed` and leaves the tasks it created running. A coroutine that was never awaited is a warning line in a run and an error in `contraagent check`. One event loop runs one run at a time: a second `Pipeline.run_async` on it raises `RuntimeError`.

  In `contraagent.engine`, `FlowDriver` drives async flows on the running event loop: `FlowDriver.wait(item)` is what a flow awaits, `FlowDriver.add(task)` queues a task without waiting, `run_async` joins `run`, and `start` returns the `FlowCall`. `FlowDriver(created=)` and `Created` → `FlowDriver.add`; `FlowDriver.waiting` → `FlowDriver.alive()`; `FlowDriver.finish()` is a coroutine; `FlowCall.gen` → `FlowCall.task` and `FlowCall.coro`. `WorkQueue(between_passes=)` (a `BetweenPasses`) keeps the queue running while work outside it may still add tasks, and `WorkQueue.wake()` ends its wait.

### Fixed

- `agent_task` now has a precise type under `mypy --strict` and pyright `strict`: `output=Triage` gives `AgentTask[Triage]` (with `implementations=`, `Mapping[str, AgentTask[Triage]]`), no `output` gives `AgentTask[None]`, and a text output such as `Annotated[str, Field(examples=[...])]` gives `AgentTask[Any]`. Before, mypy inferred `AgentTask[Any]` and asked for an annotation on each task, and pyright `strict` reported a task with no output or a text output as partially unknown.
- The `omp-rpc` backend reads the whole stderr of the coding agent before it takes the tail, so a quota refusal printed last is always seen, and a coding agent that exits before it answers `get_state` no longer adds a 10-second wait to the launch.
- Two workers that check the same credential at the same moment now record its rests in the order they judged them: `rests.jsonl` no longer shows a rest that begins after the reading that ended it, and the quota rule is called for one account at a time.
- `contraagent run` keeps Python's handling of SIGPIPE: a write to a coding agent whose input pipe has closed is an error that its launch handles, where before it ended the run at once, with no teardown.
- A file rewritten at the same size within one tick of the file system's clock (about 16 ms on NTFS) now counts as rewritten: a task's `changes` list it as modified, a `fresh` output passes its check, and a recording run names it among its undeclared changes. A file whose modification time is recent when a task starts keeps the digest of its content, and the comparison after the task reads it. `Before` has a new field, `digest`.

## [0.5.0] - 2026-10-18

### Added

- A failover hop can name the stops it is for: `stops = ["rate_limited", "api_error"]` in a
  `[[defaults.fallbacks]]` or `[[tasks.<kind>.fallbacks]]` block (`Route.stops`). A task whose
  launch ends on another stop passes the hop over, a 429 opens the breaker only onto a hop for
  `rate_limited`, and a safety stop moves the task to a hop for `refused`. With no hop left for
  its stop, the launch's own stop stands. A block without `stops` is for every stop, as before.
- A launch refused for its credential (`auth_failed`: a 401 or 403) rests that credential on
  its coding agent and model for the rest of the run. Later tasks pass the hop over without a
  launch (`skipped_hops`), a pool goes on to its next member at once, and `rests.jsonl` and the
  monitor record the rest (`Rest.stop`, `Rest.agent`, `Rest.model`). A task with every hop
  refused fails `auth_failed` without a launch rather than being deferred. An attempt whose
  chain ends on a refused hop after a hop that ran ends on the stop of the hop that ran.

### Changed

- Renamed `contraagent.engine.QuotaRests` → `CredentialRests` and `Run.quota_rests` →
  `Run.credential_rests`: a credential also rests after a refused launch, not only on its quota.

## [0.4.0] - 2026-10-18

### Added

- The monitor serves a pipeline's own pages and shows them as panels. `Monitor(apps={"name": app})`, or `contraagent monitor --apps module:APPS`, serves an ASGI app (`contraagent.monitor.App`) under `apps/<name>/` of the monitor, behind its base path, with its own routes and files. An `embed` panel body (`EmbedBody`) shows such a page, or any http(s) URL, in a frame, with the monitor's `theme` in its URL. The monitor's API version is 3.6.0.
- Safety stops are recorded and can move a launch to its next hop. A safety stop is a safety classifier that stopped part of a launch while the launch went on: a response of the launch's own model (`response`), or a request of a model that a tool calls, as Claude Code's `WebFetch` does (`tool`). Such a launch often still ends `completed`.

  - `LaunchResult.safety_stops` and the journal's `safety_stops` list each one (`SafetyStop`: its part, the model, the category, the tool, the time and the provider's ids), read from Claude Code's stream.
  - The monitor marks an attempt that had them, and the trends count them by part, model and kind (`Trends.safety_stops`).
  - `[tasks.<kind>] safety_stop_failover` and `agent_task(safety_stop_failover=)` name the parts whose safety stop moves a launch that ended well to the next hop of the failover chain. `contraagent check` warns of a kind that names them with no chain.

### Changed

- The overview's problems and outputs stay short in a run with many of them. Each group of problems (failed, not started, partly done) shows its first five tasks and the tasks done after a retry their first three, each followed by a link to the rest in the history, filtered to them; a failure shows the first four later tasks it stopped. A reason or an output's error is one line, its whole text in its tooltip.

## [0.3.0] - 2026-10-17

### Added

- `Pipeline(service_cooloff_s=)` lets a service whose start failed start again: once that many seconds have passed since the failure, the next task that claims the name tries the start again. Without it, a failed start still fails every task that claims the name for the rest of the run.

### Fixed

- The npm packages hold only the files their sources build. A package built in a checkout
  that had built it before also carried the outputs of source files that no longer exist
  (in 0.1.0, old modules of `@contraagent/ui` such as `dist/core/route.js`); each package's
  build now starts from an empty `dist/`.

## [0.2.0] - 2026-10-17

### Added

- An agent task call names the credential of that one task: `summarize(unit,
  credential="company")` runs it as `[credentials.company]` on every route of its kind,
  failover hops included, with a failover breaker of its own. It outranks the kind's
  `[tasks.<kind>]` table and declaration; `Overrides(credential=)` outranks it. A credential
  that does not exist, lacks a trait the task `requires`, or that a route's coding agent
  cannot use is refused before the task launches, and `contraagent check` reports it. A
  resting one defers the task. The routes of `contraagent check` name the tasks whose calls
  give one (`credential=company for summarize-beta, by their task calls`), and a run's
  `[start]` line for such a task names it. It is not part of the fingerprint. `plan.jsonl`
  records it (`credential`), as do `Task.credential` and the monitor's plan;
  `RoutingPlan.call_problems` and `Router.on_credential` are new.
- A `changes=` pattern that starts with `!` leaves out what it matches, and everything
  under a directory it matches: `["**", "!.git/**"]` covers every file of the working
  directory but the version control directory, and the scan does not enter a directory
  left out. A list of `!` patterns alone covers nothing and is refused where the task is
  declared.
- `contraagent run --stub --execute` (and `--replay DIR --execute`) takes an `fnmatch`
  pattern of kinds as well as a kind: `--execute 'fetch_*'` runs the functions of every
  Python task kind that matches, and `--execute '*'` the function of every Python task, so
  only the agent tasks are played. In Python: `StubAgent(execute=["*"])`,
  `Pipeline(replay=DIR, execute=["*"])`.
- `keep_failed_changes` (`agent_task(keep_failed_changes=True)`, or
  `keep_failed_changes = true` in `[tasks.<kind>]`) leaves the files a failed attempt
  created under its `changes` patterns in place instead of removing them, so the next
  attempt starts from them. The journal row lists them as `changes.kept`, and the monitor
  shows them as kept. A kind that keeps them needs `changes` patterns, and
  `contraagent check` reports a task table that sets it for a kind without any.
- A kind sets its correction rounds: `agent_task(max_corrections=1)` or `max_corrections`
  in `[tasks.<kind>]` (0 to 20, default 3, as before). The journal row records it as
  `max_corrections` (`TaskResult.max_corrections`), beside `rounds`, and `contraagent
  check` reports a value out of range.
- `@max_passes(n)` bounds each `while` loop of one generator function of flow code at `n`
  passes, in every call of it, in place of the run's `max_passes`. `TooManyPasses` names
  the function whose bound a loop passed. The decorator on a function that is not a
  generator function, or that has no `while` loop, raises `TypeError`.
- `Pipeline(mcp_servers=)` takes a function (`McpServers`) that builds the MCP servers of
  each agent task from the task, its params and its plugin's `.mcp.json`, for every
  coding agent. What it returns replaces the plugin's servers; None keeps them. The user's
  and the project's MCP servers stay out, the servers are written to an owner-only
  temporary file and not to the run directory, and `Pipeline.check` calls the function
  for the tasks it builds.
- `contraagent monitor --base-path /monitor` and `contraagent hub --base-path /monitor`
  serve the monitor behind a reverse proxy that serves it under `/monitor/` of a site and
  takes that path off. The page names the base path in every URL it reads (`<ca-monitor
  base-url="/monitor">`, its script and icons), so the page, the API and the live feeds
  pass the proxy with no change to the HTML. The monitor answers only the paths the proxy
  passes on without the base path; a request that still carries it gets 404. The API
  documentation and the `servers` of the OpenAPI document name it too, and a hub's
  `/login` redirects to it and sets its cookie for it. A value that is not a plain path
  ends the command with exit status 2. `create_app(base_path=)` and `serve(base_path=)` in
  `contraagent.monitor` take the same. The monitor topic (`contraagent docs monitor`)
  shows an nginx configuration and what a proxy needs for the live feeds and the `Host`
  check.
- omp now runs a plugin's stop hook inside the session, as Claude Code and Codex do:
  `contraagent plugin render` writes `omp/hooks.json` beside `omp/index.ts`, and the
  extension runs it at omp's `session_stop`, so an output that fails its checks is fixed
  in the same session before the launch ends, and the journal records what the hook sent
  back (`hook_errors`). Render a plugin again to get it. omp also enforces `max_turns`
  (contraagent counts its tool calls, as for Codex) and takes `disallowed_tools`: an
  extension of contraagent's own denies whole tools and patterns of a command, a path read
  or written, a domain or a skill, and only a route that sets a pattern of another tool is
  refused (`OmpBackend.tool_deny_problem`).
- A task can declare the outside state it reads beside its params and inputs:
  `agent_task(outside_state=)` and `@python_task(outside_state=)` take a function of the
  unit and params (`OutsideState`) that returns a JSON value, such as a digest of a state
  file. The function is called when the task is about to start; the value is part of the
  fingerprint, so a resume runs the task again when the state changed. A function that
  raises refuses the task (`invalid_input`), and `contraagent check` reports it. When a
  resume runs a finished task again, the journal row says why (`rerun`), and the monitor
  shows it on the task (`PlanNode.rerun`). The journal row also holds the digest of the
  outside state (`outside`).
- Panel bodies of two more types. `code` (`contraagent.monitor.CodeBody`) is a text
  highlighted by its language (`LANGUAGES`, or a file extension), with line numbers from
  `start`, highlighted lines and ranges, a path, wrapped or scrolled, a Copy button, and
  cut after `CODE_LINES` lines. `tree` (`TreeBody`, `TreeNode`, `TreeLink`) is a list of
  nodes the reader folds and opens with the mouse or the keyboard, each with an icon, a
  badge and its tone, and either the code shown beside the tree while the node is
  selected or a link to a run panel, a task or a body of the same panel (each panel
  body's new `anchor`). `@contraagent/elements` adds `<cae-code>`
  (`@contraagent/elements/code`) and `<cae-tree>` (`@contraagent/elements/tree`), and its
  markdown highlights the same languages.
- An agent task keeps what a stopped launch wrote: with `agent_task(partial_on=["timeout",
  "stalled"])` (or `partial_on` in `[tasks.<kind>]`), a launch the runner stopped for its
  time whose output was written by the attempt and passes every check makes the task
  partial, as a Python task's `Partial` does: ok, stop `partial`, its reason the launch's
  stop, and a resume runs it again. Rows keep the rows written so far. The stub agent plays
  such a launch with `writes(value, stop=Stop.TIMEOUT)`.
- `contraagent.pipeline_table()` works in flow code that `contraagent check`
  (`Pipeline.check`) builds: it reads the table of the config the check is given, as a run
  does, so a flow may read its pipeline table in its body. `contraagent.log` and
  `contraagent.save` write into the check's temporary directory, which it removes.
- `contraagent check` and a run warn about a `[tasks.<kind>]` table that names a Python task
  kind: a task table configures agent tasks only, so its `max_concurrent` bounds no Python
  task. The tasks topic has a new section, "Concurrency", on what limits how many tasks run
  at once (the run's slots, a kind's `max_concurrent`, claims) and on how a claim keeps long
  Python tasks from taking the slots of the agent tasks.
- `contraagent recording import RUN_DIR DIR` (`contraagent.import_recording(run_dir,
  directory)`, which returns a `RecordingImport`) writes a recording of each task a run
  finished from its run directory, as if the run had been recorded, so a replay plays a past
  run's outputs without running it again. A replay plays an imported recording only for a
  task of the fingerprint that run recorded; a task changed since ends `error`, or with
  `--record-missing` launches and is recorded again. The import lists the tasks it leaves
  out: those that did not finish, and those with a missing, rewritten or too large file.
  See `contraagent docs testing`.
- An agent task's output may be rows: `agent_task(output=Rows[Finding])` declares a JSON
  Lines file whose every line is one `Finding`, checked line by line, each error naming its
  line. The agent adds each row as soon as it has it; the flow, the validators and the
  tasks it is passed to get a `Rows`, a list of the models. The call file says
  `output.format: "jsonl"`, a stub run's example is one row, a Python task may return
  `Rows` too, and the monitor shows the file's rows and the row model's fields
  (`ContractSpec.format`).
- `Pipeline(services={name: service})` names the service that a claim name stands for: a
  long-lived helper such as a worker service, a database or a local server. A `Service`
  is a function of the name that returns a context manager. The first task that claims
  the name starts the service, and every task that claims it shares it while it runs, as
  many at once as its claim capacity lets. The run's end stops it, also on an error, on
  Ctrl-C and on SIGTERM. A task reaches the service by the address its start gives:
  `contraagent.service_address(name)` in a Python task, `CONTRAAGENT_SERVICE_<NAME>` in
  an agent task's environment. A start that raises fails the tasks that claim the name
  with stop `launch_failed`. `services.jsonl` records each start and stop, the monitor
  shows them under "Services" (`Plan.services`, `ServiceSpan`), and `Pipeline.check`
  names a service that no task claims. A stub run and a replay start a service only for
  a task that really runs: a Python task whose function runs, or an agent task that
  launches a coding agent; a task they play holds none.

### Changed

- `credential` is now a word of an agent task call, as `key`, `after` and `priority` are. A
  call that passed a parameter named `credential` to a task with no params model now names
  the credential the task runs as, and a params model of an agent task with a field named
  `credential` is refused when the task is declared. Rename such a parameter.
- A message of `contraagent check` points to the topic that explains it in one form,
  `(contraagent docs <topic>, <section>)`, or `(contraagent docs <topic>)` for a whole
  topic, and its `read:` line lists those pointers: `read: (contraagent docs tasks)` in
  place of ``read: `contraagent docs tasks` ``. An error with a pointer of its own puts its
  topic in `CheckReport.topics` in place of the check's: a `max_corrections` out of range
  points to the contracts topic, and a route whose coding agent cannot deny a tool pattern
  to the agents topic. That message now names what the agent cannot hold: omp and opencode
  hold patterns of Bash, Read, Write, Edit, MultiEdit, Skill and `WebFetch(domain:...)`
  (opencode also NotebookEdit), and a pattern of another tool is refused.
- A kind name holds no `*`, `?` or `[`, the characters of a pattern of kinds that
  `--execute` takes: `agent_task` and `@python_task` raise `TypeError` for such a name.
- `run_until_valid` names its count of correction rounds as a kind does:
  `run_until_valid(max_resumes=)` → `run_until_valid(max_corrections=)`.

### Fixed

- `contraagent check` reads the answer of its output-import probe from a file, so a flow
  module that prints when it is imported no longer makes the check report "output import
  not checked: Expecting value".
- A Python task call refuses `credential=` at the call with a `TypeError` that says a
  Python task has no credential, and `contraagent check` reports it, where the run used to
  fail with a `TypeError` from the function. A call that names a keyword its function has
  no parameter for, or leaves out a required one, is refused at the call the same way. A
  task call's `key` that is not a string and an `after` that is not a list of tasks (a
  string, a number in the list) are refused at the call too, for agent and Python tasks.
## [0.1.0] - 2026-10-16

### Added

- A task is a typed Python function whose body is a coding agent (`agent_task`) or Python
  (`@python_task`), with pydantic models or text for its parameters and its output. A flow
  is plain Python that calls tasks, and passing one task's result to another is the
  dependency.
  - A generator flow `yield`s a task, a list of tasks or another flow and receives the
    checked output there, so loops, branches, fan-outs and joins are ordinary code. A task
    that did not succeed raises `TaskFailed` (or `TaskDeferred`) at the `yield`.
  - Each output is checked against its schema and its validators, Python functions or
    programs (`CommandValidator`). An output that fails goes back to the same agent session
    with the errors, for a correction round. A task whose input is missing or failed its
    checks does not start.
  - `Pipeline.run` returns a `RunReport`, and `contraagent run flow.py:flow` runs a flow
    from the command line and exits 1 when a task failed.
- An agent task's implementation is a plugin in the coding agent's own format: roles,
  skills, MCP servers and hooks. Its hooks are written once in `hooks.toml` and rendered
  for each coding agent, and `contraagent plugin new`, `lint` and `render` create, check
  and render a plugin. Each launch is given a call file with the task's parameters and its
  output contract.
- A flow can be checked and tested with nothing spent. `contraagent check` builds the task
  graph and reports every problem in the flow, the output models, the validators, the
  plugins and the routing at once, each with the documentation topic that explains it.
  `contraagent.testing.StubAgent` plays scripted replies in tests, and a stub run
  (`contraagent run --stub`) runs the whole flow on each output's example. A run records
  each attempt with `--record DIR`, and a later run replays the recordings with
  `--replay DIR`.
- Five coding agents run the same tasks, plugins and config: Claude Code (`claude -p`),
  Codex CLI (`codex exec`), opencode (`opencode run`), oh-my-pi (`omp -p`) and pi
  (`pi -p`). `register_backend` adds another one. Each launch starts in a clean context:
  the user's and the project's settings, instruction files, skills, hooks and MCP servers
  are kept out. contraagent supervises the time, the budget, stalls and denied tool calls,
  and records the tokens, the cost, the peak context and the account's 5-hour and weekly
  usage when the agent reports them. A coding agent does not outlive the pipeline that
  started it.
- One TOML file (`pipeline.toml`, with a JSON Schema) gives each kind its coding agent,
  model, effort, budget, time limits and credential, from `[defaults]` and
  `[tasks.<kind>]`.
  - Credentials are the host's own login (`ambient`), subscriptions, API keys, OAuth
    tokens, gateways, Bedrock, Vertex, workload identity and pools of them.
  - A kind's `fallbacks` move a task to its next route (another model, coding agent or
    credential) after a rate limit, a failed launch or a safeguard refusal.
  - Quota caps on a subscription's 5-hour and weekly usage rest a credential until its
    window resets, and a preflight probes every route before the first launch.
- The work queue starts the ready task with the longest remaining work first, within each
  kind's `max_concurrent`. Claims (`claims=["topic:{unit}"]`) keep tasks that share a name
  from running at the same time. A run's deadline, and time boxes over part of a flow,
  defer the tasks that cannot finish in time, and a deferred task is not a failure. A
  resumed run (`contraagent run --resume`) runs a task again only when its parameters, its
  definition or its inputs changed.
- Each run writes its records to `runs/<id>/`: the run, the journal of attempts with each
  one's tokens, cost, route and changed files, the plan, the launches, deferrals, quota
  rests, call files, outputs and transcripts. Each record has a JSON Schema, and `run.json`
  names its run format. A flow and its Python tasks keep the pipeline's own records there
  with `contraagent.log` and `contraagent.save`.
- `contraagent monitor` (the `monitor` extra) serves a live, read-only view of every run:
  its state, problems, outputs, cost, tokens and subscription usage, the pipeline graph,
  the timeline, and each task with its transcript, inputs, outputs and checks. A Trends
  page sums the runs of a period, and a pipeline adds views of its own
  (`contraagent.monitor.Panel`). The monitor speaks English and Japanese, with light, dark
  and high-contrast themes, and `openapi.json` describes its HTTP API.
  `contraagent monitor export` writes the views of the newest runs as static files that any
  web server serves.
- `contraagent hub` and `contraagent relay` (the `hub` extra) show the runs of many hosts in
  one monitor. A relay on each host sends its runs to the hub, which keeps them in Postgres
  and object storage, with a token per host, a read token for the monitor and retention.
  `contraagent docs hub-operations` describes a deployment.
- The monitor's page is built from three npm packages that work in any page or framework:
  - `@contraagent/api`: types generated from `openapi.json`, a client and the live feeds;
  - `@contraagent/elements`: generic web components, such as a data table, charts, a
    layered graph, a transcript and the themes;
  - `@contraagent/ui`: `<ca-monitor>` and an element for each of its views.
- The documentation is installed with the package and is written for the coding agent that
  writes a pipeline. `contraagent docs` prints the index, `contraagent docs <topic>` a
  topic, and `contraagent docs --pointer` a short block that points a project's coding agent
  at them, and its examples run in the tests. The same documentation, with each web
  element drawn live, is at https://t-tani.github.io/contraagent/.
- contraagent runs on Linux, macOS and Windows with Python 3.12, 3.13 and 3.14. The
  compatibility topic (`contraagent docs compatibility`) lists what is public: the public
  modules' names, the command line, the config file, the files a run writes and the
  monitor's HTTP API and the hub's protocol. Before 1.0, a minor release may change them, and
  the changelog names each change; a patch release does not.
