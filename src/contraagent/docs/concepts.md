# Concepts

Each word below has exactly one meaning: in the Python API, in the files a run
writes, in the monitor's HTTP API, in the web components and in this
documentation. No other word is used for the same thing.

## Work

| Word | Means | In code |
|---|---|---|
| **coding agent** | the CLI program that does the work (`claude`, `omp`) | `agent` in config, routes, journal and monitor; `Backend` is its Python adapter |
| **LLM** | the language model the coding agent runs on, nothing else | `model` |
| **agent task** / **Python task** | a task a coding agent executes / one this process executes | `agent_task`, `@python_task`; on disk `executor: "agent" \| "python"` |
| **kind** | the class of work (`summarize`); a Python task's kind is its own name | `Task.kind` |
| **unit** | what a kind is applied to (`alpha`); tasks of different kinds on one unit do not overlap | `Task.unit` |
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
| **fingerprint** | a digest of what defines a task's work: kind, unit, key, params, its definition (instructions, role file, its plugins' skills, schemas, validators; a Python task's source), and per task it waits for, that task's output file when the flow received it, else its fingerprint; resume skips a key whose last journal row is ok with the same fingerprint | `Task.fingerprint`, journal `fingerprint`; `AgentTask.digest`, `PythonTask.digest` |

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

## Checking

| Word | Means | In code |
|---|---|---|
| **schema** | the pydantic class a file is checked against | `agent_task(output=)`, `OutputContract.schema` |
| **validator** | a check a file must pass beyond its schema | `agent_task(validators=)`, `CommandValidator`, any `(path, value) -> errors` |
| **contract** | a file plus its schema and validators | `OutputContract`, `InputContract` |
| **check** | what can be found wrong with a flow without a launch | `Pipeline.check`, `CheckReport`, `contraagent check` |
| **reachable kind** | a kind whose task declaration a generator flow's code refers to, directly or through the functions, modules, closures and containers it refers to; checked, routed and probed before the first launch. A candidate, not a use: of two declarations of one kind, the one whose tasks are created is the kind's | `pipeline/reach.py`, `CheckReport.later_kinds` |
| **stub agent** | a coding agent that plays scripted replies instead of an LLM, for tests | `contraagent.testing.StubAgent` |

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

## Running

| Word | Means | In code |
|---|---|---|
| **launch** | one run of a coding agent, and its result | `Launch`, `Backend.run`, `LaunchResult` |
| **round** | one launch within a session: the first, or a resume after contract errors | `rounds` |
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
| **web fetch** | the coding agent reading a web page by its URL (Claude Code `WebFetch`, omp `read` of a URL) | a transcript's tool call `web_fetch` |
| **web search** | a search of the web by the coding agent's own tool (Claude Code `WebSearch`, omp `web_search`); its query is recorded | `LaunchResult.web_queries`, `JournalRow.web_queries`; a transcript's tool call `web_query` |
| **tail** | the expected wall time of the work a flow creates after a task, not queued when the task is: the median, over tasks with the same flow path's function names, kind and loop passes (capped) in recent runs and in this one, of the longest complete chain of wall times after them along `after` and created from | `Task.tail_s`, `JournalEstimates.tail`, `TailKey` |
| **bottom level** | a queued task's estimate plus the longer of its known dependents' path and its tail: the queue's priority | `WorkQueue._blevel` |
| **overdue** | a queued task startable for longer than `overdue_s`: it goes before the others, and while it is the first that cannot start, no later task takes a resource it needs (the starvation guard) | `WorkQueue(overdue_s=)` |
| **slack** | the time before the deadline from which the queue orders for the deadline: shortest remaining work first, deferring what cannot finish | `WorkQueue(slack_s=)` |
| **stream file** | the raw transcript of a task's launches | `streams/<key>.stream.jsonl`; `keep_transcripts` |
| **stream format** | how a stream file is parsed (`claude`, `omp`) | `normalize_stream_event(format, ...)` |
| **stage** | a run phase | cursor `stage` |
| **`TaskScope`** | the context manager around a task's dispatch | `AgentRunner(scopes=)` |

The runners: `AgentRunner` (one agent task, with failover), `RetryingRunner`,
`PythonTaskRunner`. Queue callbacks: `on_event`, `on_result`, `follow_up`.
A task not launched by the deadline, or whose remaining work cannot finish
before it, finishes `deferred`; a follow-up task the
queue refuses because its key is in flight finishes `duplicate_key`. A task a
flow waited for that did not succeed raises `TaskFailed` at the `yield`
(`TaskDeferred` when it was deferred). A text output a flow receives is a
`TextOutput`, a `str`.

## The monitor

| Word | Means | In code |
|---|---|---|
| **group** | a column of the plan | `Monitor(groups=)` |
| **tab** | one top-level view (`overview`, `journal`, ..., `panel:<name>`) | `Tab`, route `tab` |
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

The monitor's screens show some of these in the words of engineers who use
coding agents (a round after contract errors is a "correction", a task's
`Outcome` its "status"); the words above stay in its tooltips.
