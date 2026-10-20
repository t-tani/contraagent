# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The changes not released yet are the fragments in [`changelog.d/`](changelog.d/);
`towncrier build --draft` shows them as the next release's section.

<!-- towncrier release notes start -->

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
