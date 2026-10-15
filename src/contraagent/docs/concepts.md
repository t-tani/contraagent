# Concepts

Each word below has exactly one meaning: in the Python API, in the files a run
writes, in the monitor's HTTP API, in the web components and in this
documentation. No other word is used for the same thing.

## Work

| Word | Means | In code |
|---|---|---|
| **coding agent** | the CLI program that does the work (`claude`, `omp`, `opencode`, `pi`, `codex`) | `agent` in config, routes, journal and monitor; `Backend` is its Python adapter |
| **LLM** | the language model the coding agent runs on, nothing else | `model` |
| **agent task** / **Python task** | a task a coding agent executes / one this process executes | `agent_task`, `@python_task`; on disk `executor: "agent" \| "python"` |
| **kind** | the class of work (`summarize`); a Python task's kind is its own name | `Task.kind` |
| **unit** | what a kind is applied to (`alpha`): it names a task and its output, and locks nothing | `Task.unit` |
| **claim** / **claim capacity** | a name a task holds while it runs, its declaration a template (`topic:{unit}`, `topic:{params.topics}`: one name per element of a list); one task holds a name at a time / how many running tasks may hold one name instead, given by the name or by an `fnmatch` pattern that gives each name it matches a capacity of its own | `agent_task(claims=)`, `@python_task(claims=)`, `Task.claims`; plan `claims` / `claim_capacity`, `[defaults.claim_capacity]`, `WorkQueue.capacity` |
| **task** | one kind applied to one unit | `Task` |
| **key** | a task's stable identity: `<kind>-<unit>` or `key=`; the n-th task a flow call creates under one key is `<key>~n` | `Task.key`, field `key` everywhere, monitor URL `key` |
| **params** | what a task is given | `Task.params`, call file `params`, `CONTRAAGENT_PARAMS` |
| **flow** | the plain function that calls the tasks | `Pipeline.run(flow, ...)` |
| **flow call** | one run of a generator in a flow: the top flow, or a generator it yields; it waits at each `yield` for tasks or other flow calls; ids `0`, `0.1`, `0.1.2`, ...; a flow that does not yield is flow call `0` | `FlowCall`, `FlowDriver`, `flow_calls.jsonl`; monitor `Plan.flow_calls`, `FlowCallNode` |
| **flow error** | an exception a top flow call raised after its first task was queued | `RunReport.flow_errors` |
| **origin** | where a flow created a task: its flow path (with each loop's pass), created from and flow call | `Task.origin`, `Origin`; plan `flow`, `created_from`, `flow_call` |
| **flow path** | the frames of flow code that created a task, outermost first, across flow calls; a flow call's flow path is its parent's where the parent yielded it | `Origin.flow`, `Frame`; plan and flow call `flow` |
| **call site** | where a frame of the flow path was when the task was created: function (`module.qualname`), file and line; a flow call's site is where its parent yielded it | `Frame.function`, `.file`, `.line`; `FlowCall.site` |
| **loop** | a `for` or `while` statement in a generator of flow code, named by its first line; a call site's loops are those whose pass it is in, outermost first; a comprehension is not a loop | `Loop.line`, `Frame.loops`; `flow[].loops[].line` |
| **pass** | one iteration of one loop, numbered from 1 each time the loop is entered; never an attempt, never the `~n` of a key | `Loop.pass_`, `flow[].loops[].pass`; `max_passes` (the passes a `while` loop may make; a `for` loop has no limit), `TooManyPasses` |
| **created from** | the keys whose results a flow call had received when it created a task | `Origin.created_from` |
| **fingerprint** | a digest of what defines a task's work: kind, unit, key, params, its definition (instructions, role file, its plugins' skills, schemas, validators; a Python task's source), and per task it waits for, that task's output file when the flow received it, else its fingerprint; resume skips a key whose last journal row is ok with the same fingerprint, but not a task declared `rerun_on_resume` | `Task.fingerprint`, journal `fingerprint`; `AgentTask.digest`, `PythonTask.digest` |

## Definition

| Word | Means | In code |
|---|---|---|
| **interface** | what an agent task takes, produces and may spend | `agent_task(params=, output=, max_turns=, ...)` |
| **implementation** | how an agent task is done: a plugin directory, with the skills of the skill plugins it names | `agent_task(plugin=)`, `Plugin` |
| **skill plugin** | a plugin that holds skills and nothing else that acts; tasks with different plugins load it to share its skills | `agent_task(skills_from=)`, `Plugin.skills_only` |
| **role** | a named agent definition in a plugin: its procedure | `agents/<role>.md`, `Launch.role`, Claude Code's `--agent` |
| **instructions** | text before the call protocol, for an agent task with no plugin | `agent_task(instructions=)` |
| **hook** | a hook inside the coding agent, declared by a plugin; nothing else | `hooks.toml`, `plugins/hooks.py` |
| **call file** | the params and output contract handed to one agent task | `CallFile`, `runs/<run>/calls/<key>.json` |
| **changes** | the files one attempt created, modified or deleted under the patterns its task declares, beside its output; the files a failed attempt created are removed | `agent_task(changes=)`, `TaskAdapter.changes`, `TaskResult.changes`, journal `changes` |
| **final message** | the agent's last message of a launch; an agent task whose output is its final message has it written to its output file and checked there | `LaunchResult.result_text`; `agent_task(output_from="message")`, call file `output.from`, `OutputContract.from_message` |
| **unwrap** | taking the JSON document out of a final message that wraps it (a sentence before it, a fence around it): the output is the document, the whole message is kept beside it | `agent_task(unwrap=True)`, `OutputContract.unwrap`, `unwrap_json`; `<output>.message.txt`; `LaunchResult.unwrapped` |

## Checking

| Word | Means | In code |
|---|---|---|
| **schema** | the pydantic class a file is checked against | `agent_task(output=)`, `OutputContract.schema` |
| **validator** | a check a file must pass beyond its schema | `agent_task(validators=)`, `CommandValidator`, any `(path, value) -> errors` |
| **contract** | a file plus its schema and validators | `OutputContract`, `InputContract` |
| **preserve** | the parts of an output file a launch must keep as they were before it: JSON pointers (RFC 6901, a segment `*` for every member), each value they select in the file before the launch equal in it after | `agent_task(preserve=)`, `OutputContract.preserve`, `contraagent.pointers`; call file `output.preserve` |
| **check** | what can be found wrong with a flow without a launch | `Pipeline.check`, `CheckReport`, `contraagent check` |
| **reachable kind** | a kind whose task declaration a generator flow's code refers to, directly or through the functions, modules, closures and containers it refers to; checked, routed and probed before the first launch. A candidate, not a use: of two declarations of one kind, the one whose tasks are created is the kind's | `pipeline/reach.py`, `CheckReport.later_kinds` |
| **stub agent** | a coding agent that plays scripted replies instead of an LLM, for tests | `contraagent.testing.StubAgent` |
| **stub run** | a run whose tasks the stub agent plays: agent tasks, and Python tasks but the kinds it executes; flow code runs as in any run | `Pipeline(stub=)`, `StubAgent(default=, execute=)`, `writes_smallest`, `contraagent run --stub`; `run.json` `stub` |

## Routing

| Word | Means | In code |
|---|---|---|
| **task table** | one kind's `[tasks.<kind>]` table in the config | `PipelineConfig.task_tables()`, `TASK_TABLE_KEYS` |
| **`[defaults]`** | run-wide routing, including `[[defaults.fallbacks]]` | `PipelineConfig.defaults()`, `.fallbacks()` |
| **routing plan** | how each kind is routed (not `plan.jsonl`) | `RoutingPlan` |
| **`KindConfig`** | one kind's resolved routing and budgets | `RoutingPlan.configs` |
| **hop** | one route in a failover chain | `Route`, `Router` |
| **budget** | the turn, time, cost and stall caps of a launch | `max_turns`, `timeout_s`, ...; `Limits`, `Launch.limits` |
| **credential** | the identity (and so the account) an agent's API calls are billed to | `[credentials.<name>]`, `Launch.credential` |
| **trait** | a label on a credential that a task may require (`zdr`) | `traits`, `agent_task(requires=)` |
| **pool** / **gateway** | several credentials used as one / your own endpoint (LiteLLM, a proxy) | `Pool`, `Gateway` |
| **ambient** | the built-in credential: the host's own setup, untouched | `AMBIENT` |
| **quota** | a subscription's utilization of its 5-hour and weekly windows (and a model's own windows), as the coding agent reports it: account-wide | `RateLimit`, `LaunchResult.rate_limits`; journal `quota` (`QuotaReading`, `windows`) |
| **account** | the billing account a quota reading is of, as a 12-hex-digit digest of its login's UUID or of the credential's secret, never the value itself; one credential can stand for two (`ambient` on two coding agents, a token replaced between runs), and a credential's rests are judged by the readings of the account a launch as it bills | `RateLimit.account`, `QuotaReading.account`, `Backend.account`, `account_digest` |
| **quota cap** / **quota rule** | the utilization past which a credential rests / a domain's own test of a credential's latest quota reading | `max_five_hour_pct`, `max_seven_day_pct` / `Pipeline(quota_rule=)` |
| **rest** | not launched on for a time: a hop or a pool member after a 429, a credential past a quota cap or rule until its window resets; a task takes the next hop; with none left it ends `rate_limited` after 429s, and is deferred (never launched) when its credentials rest on their quota. A quota rest is recorded as data (`Rest`: window, reading, cap, or what the rule said, and until when) as it begins and ends | `Router`, `CredentialPool`, `QuotaRests`, `Rest`; `rests.jsonl` |
| **skipped hop** | a hop an attempt passed over without a launch because its credential rested on its quota; not one of the attempt's hops, which are launches | `TaskResult.skipped_hops`, journal `skipped_hops` (`SkippedHop`) |

## Running

| Word | Means | In code |
|---|---|---|
| **launch** | one run of a coding agent, and its result | `Launch`, `Backend.run`, `LaunchResult` |
| **light launch** | the launch of an agent task declared with no tools: its role's text (or its instructions) replaces the coding agent's system prompt, its params and output schema are in the prompt, no plugin, settings or MCP server is loaded, and its final message is its output | `agent_task(tools=())`, `AgentTask.light`, `KindConfig.light`, `Backend.light_launch` |
| **resident** | the whole input of an attempt's first API call: what the coding agent loads before the task starts | `TokenUsage.resident`, `Usage.resident` |
| **other model** | a model a launch called besides the one it ran on (Claude Code summarizes a fetched page on a smaller model): its cost is in the launch's, its tokens are not in the launch's `usage`, and the models' spend counts it apart | `LaunchResult.other_models`, `Hop.other_models` (`OtherModel`) |
| **round** | one launch within a session: the first, or a resume after contract errors; an attempt's cost counts each round once | `rounds`, `round_costs` |
| **attempt** | a retry of a task with a fresh session | `RetryingRunner`, journal rows |
| **result** | a task's final result / what `Pipeline.run` returns | `TaskResult` / `RunReport` |
| **run** / **run group** | one `runs/<id>/` directory / a label grouping runs | `Run`, `Run(run_group=)` |
| **run uid** / **host id** | the id no other run has, on any host, kept when the run is resumed / the host that drives the run | `run.json` `run_uid` / `host_id` (`CONTRAAGENT_HOST_ID`, else the host name) |
| **run source** / **liveness** | where the monitor reads runs' records / which runs are live and their processes | `RunSource` (`DirectorySource`, `MemorySource`, `HubSource`) / `Liveness` (`ProcLiveness`, `StaticLiveness`, `HeartbeatLiveness`), `contraagent/monitor/source.py` |
| **hub** / **relay** | the server that holds every host's runs and serves their monitor / the process on a host that ships its runs to a hub (never "agent", which is the coding agent) | `contraagent hub`, `Hub`, `HubStore` / `contraagent relay`, `HubClient`; `contraagent/hub/` |
| **heartbeat** | a relay's report that its host is up, with its runs' live processes; a host's runs are live while its heartbeats keep arriving | `protocol.Heartbeat`, `HeartbeatLiveness` |
| **blob** | a file's content on a hub, named by its SHA-256 | `BlobStore` |
| **segment** / **open segment** | a sealed part of a transcript on a hub: one object of zstd frames with an index of their first lines / the part still being written, a file on the hub's disk | `SegmentedStreamLogs`, `segment_format`, `SegmentIndex`; `--segments` / `--streams-dir` |
| **held** / **durable** | the lines of a log a hub holds / those of them that survive the loss of the hub's disk (sealed segments, the database) | `Held`, `Accepted.logs` / `Accepted.durable` |
| **retention** / **prune** | how long a hub keeps a run after its last activity / removing what is older, with everything the hub holds of it | `contraagent hub --retain-days`, `Hub.prune`, `PruneReport`, `contraagent hub prune` |
| **grace period** | how long an unreferenced blob is kept before a prune removes it (it may be on its way) | `Hub.prune(blob_grace=)` |
| **active transcript** | a transcript whose task is running or whose file grew in the last seconds; a relay ships it between its full passes | `Relay.fast_once` |
| **journal** / **plan** | the finished attempts / the queued tasks | `journal.jsonl` / `plan.jsonl` |
| **unread event** | an event type a coding agent sent that its reader in this contraagent does not know: a newer coding agent | `LaunchResult.unread_events`, `JournalRow.unread_events` |
| **web fetch** | the coding agent reading a web page by its URL (Claude Code `WebFetch`, omp `read` of a URL, opencode `webfetch`, Codex `web_search` opening a page) | a transcript's tool call `web_fetch` |
| **web search** | a search of the web by the coding agent's own tool (Claude Code `WebSearch`, omp `web_search`, opencode `websearch`, Codex `web_search`); its query is recorded | `LaunchResult.web_queries`, `JournalRow.web_queries`; a transcript's tool call `web_query` |
| **tail** | the expected wall time of the work a flow creates after a task, not queued when the task is: the median, over tasks with the same flow path's function names, kind and loop passes (capped) in recent runs and in this one, of the longest complete chain of wall times after them along `after` and created from | `Task.tail_s`, `JournalEstimates.tail`, `TailKey` |
| **bottom level** | a queued task's estimate plus the longer of its known dependents' path and its tail: the queue's priority | `WorkQueue._blevel` |
| **overdue** | a queued task startable for longer than `overdue_s`: it goes before the others, and while it is the first that cannot start, no later task takes the last place it needs on a name it claims or under its kind's cap (the starvation guard) | `WorkQueue(overdue_s=)` |
| **slack** | the time before the deadline from which the queue orders for the deadline: shortest remaining work first, deferring what cannot finish | `WorkQueue(slack_s=)` |
| **time box** | a deadline over part of a run: the run's own (`deadline_s`), or a flow call's, counted from its start, over the tasks it and the flow calls it starts create; past it only its finishing kinds launch, for its grace window; a task is held to every time box it is in | `time_box(flow, deadline_s=, grace_s=, finishing_kinds=, slack_s=)`, `TimeBox`, `Task.time_boxes`; `flow_calls.jsonl` and monitor `FlowCallNode.time_box`; a deferral's cause `flow_call` |
| **stream file** | the raw transcript of a task's launches | `streams/<key>.stream.jsonl`; `keep_transcripts` |
| **stream format** | how a stream file is parsed (`claude`, `omp`, `opencode`, `pi`, `codex`) | `normalize_stream_line(format, ...)` |
| **stage** | a run phase | cursor `stage` |
| **`TaskScope`** | the context manager around one attempt of an agent task (every hop of it) | `Pipeline(scopes=)`, `AgentRunner(scopes=)` |
| **`ResultEnricher`** | what sees an agent task before one attempt and its result after, and may add to the result (`payload`) or change its verdict (`ok`, `stop`) | `Pipeline(enrichers=)`, `AgentRunner(enrichers=)` |
| **row extras** | a pipeline's own columns of a journal row, named by the pipeline: what `row_extras(result)` adds | `Pipeline(row_extras=)`, `Run(row_extras=)`; monitor `RunSummary.row_extras`, `TaskDetail.row_extras` |

The runners: `AgentRunner` (one agent task, with failover), `RetryingRunner`,
`PythonTaskRunner`. Queue callbacks: `on_event`, `on_result`, `follow_up`.
A task not launched by the deadline (of a time box it is in), whose remaining
work cannot finish before it, or with every hop on a resting credential, finishes `deferred`, and
`deferred.jsonl` records why: a `Deferral`, its reason in one line and its cause
as data (`deadline`, `grace_window`, `cannot_finish`, each with the `flow_call`
whose time box it was, `dependency_not_queued`, `rest`; `AgentRunner.deferral`); a follow-up task the
queue refuses because its key is in flight finishes `duplicate_key`. A task a
flow waited for that did not succeed raises `TaskFailed` at the `yield`
(`TaskDeferred` when it was deferred). A text output a flow receives is a
`TextOutput`, a `str`.

## The monitor

| Word | Means | In code |
|---|---|---|
| **group** | a column of the plan | `Monitor(groups=)` |
| **period** | days `from`..`to`, both included, in a time zone, over which runs are summed | `trends.Period`; `/api/trends?from=&to=&tz=`; its runs as a trends panel reads them: `PeriodRuns` |
| **trends** | what the runs of a period add up to, day by day: cost by kind (or group), each kind's tasks, success and time, each model's spend, failures, refused tool calls, utilization, rests, deferrals, run starts; read from each run's digest, kept in a finished run's `trends.json` | `Monitor.trends`, `/api/trends`, `Trends`; `Panel(scope="trends")` |
| **function drawn open** | a function node of the pipeline graph drawn as a box holding its own layer, in the layer shown; a chain of functions, each the only function in the layer of the one before, is one box named by its path | `FlowBox`, `compound` (`@contraagent/ui/adapters`), cluster id `fx::<place>` |
| **place** | where a function node is across every layer: its layer and its id there | `placeKey`, `<layer>/<id>` |
| **outline** | the pipeline graph's list of every function of the flow and the loops they are in, as a tree | `outlineTree`, `nav.outline` |
| **tab** | one top-level view (`overview`, `journal`, ..., `panel:<name>`); on the Trends page, the trends with the trends panels of no `tab`, or the trends panels of one `tab` | `Tab`, route `tab`; `Panel.tab`, `PanelInfo.tab`, route `trendsTab` (`?page=trends&tab=`) |
| **panel** / **panel body** | a view a pipeline adds to the monitor: computed per run (`scope="run"`, a tab of each run) or over the runs of a period (`scope="trends"`, `fn(runs, period)`) / what it returns: a typed body (`tiles`, `table`, `columns`, `lines`, `heatmap`, `status_grid`, `hbars`, `note`, `blocks` of them) the monitor draws, or any other JSON object, shown as a JSON tree | `monitor.Panel`, `Period`; `api.PanelBody`; `contraagent monitor --panels` |
| **status grid** / **note** | a panel body of a state per row and column, each named by its label and coloured by its tone (a `heatmap` is a number per cell, in shades of one colour) / a panel body of text beside the figures, markdown shown escaped | `api.StatusGridBody`, `GridCell`; `api.NoteBody`; the element `cae-state-grid` |
| **task view** | what the stream tab shows of a task: `transcript`, `input`, `output`, `definition` | `TaskView`, route `view` |
| **route** | where the reader is, kept in the URL | `Route`, `Router` in `@contraagent/ui` |
| **element** | a web component: `ca-*` in `@contraagent/ui`, `cae-*` in `@contraagent/elements` | `CaMonitor`, `CaTranscript`, `CaeSegmented`, ... |
| **tone** | the status colour a value takes: failed, attention, done, running, muted, neutral | `Tone`, `data-tone` |
| **selection** | what is selected in the pipeline graph's layer: a node, a loop box or a mark | route `sel`, `markSel`, `parseSelection` |
| **inspector** | the card beside the selection in the pipeline graph's frame (a sheet under the frame on a narrow screen) that shows its facts and where it leads | `ca-pipeline-graph` (its content), the `inspector` slot of `cae-layered-graph` |
| **cluster** | a box of nodes in a layered graph; a loop box is one | `GraphClusterInput`, `.cluster` |
| **series** | the id that lines marks up across a layered graph's nodes; the pipeline graph's units | `GraphInput.series` |
| **adapter** | a function in `@contraagent/ui/adapters` that turns run data into a generic element's model | `graphFromPlan`, `matrixFromPlan`, `kpiTiles`, ... |
| **wrapper** | a `ca-*` element that feeds a `cae-*` element through an adapter and turns its `cae-*` events into `ca-*` events | `ca-pipeline-graph`, `ca-kpis`, ... |
| **run start** | one start of a run over its directory: the first, or a resume; a task numbers its attempts from 0 in each | `run.json` `started_at` (the latest), `runStarts` |
| **export** | the monitor's views of some runs written as files (the page and the JSON each route answers), read with no server; it holds no transcripts and no processes, and this machine's paths and name are taken out | `contraagent monitor export`, `monitor/export.py`; `Info.export` (`ExportInfo`); `createExportClient`, `openExportFeed`, `<ca-monitor export="data/">` |

The monitor's screens show some of these in the words of engineers who use
coding agents (a round after contract errors is a "correction", a task's
`Outcome` its "status"); the words above stay in its tooltips.
