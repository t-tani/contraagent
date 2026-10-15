**Upgrading from a pre-release checkout.** A project that ran contraagent from a source
checkout before 0.1.0 changes the names below; old run directories are not read (start
new run ids).

- **Imports.** Each name has one public path; the implementation is in
  `contraagent._internal`, which is not public. `contraagent` keeps tasks, flows, the
  pipeline, validators, the task and result a callback is given, and every error.

  | Old import | New import |
  |---|---|
  | `contraagent.AMBIENT`, `ApiKey`, `Bedrock`, `Gateway`, `KindConfig`, `Limits`, `OAuthToken`, `Pool`, `QuotaReading`, `QuotaWindow`, `Route`, `Secret`, `Subscription`, `Vertex`, `WorkloadIdentity` | `contraagent.config.<name>` |
  | `contraagent.Credential` (the union of the credential kinds), `contraagent.backends.CredentialBase` | `contraagent.config.Credential`, their base class |
  | `contraagent.Backend`, `ClaudeBackend`, `CodexBackend`, `OmpBackend`, `OmpRpcBackend`, `OpencodeBackend`, `PiBackend`, `CallFile`, `Launch`, `LaunchResult`, `QuotaRefusal`, `Stop`, `create_backend`, `register_backend`, `register_normalizer`, `normalize_stream_line` | `contraagent.backends.<name>` |
  | `contraagent.AgentRunner`, `CursorStore`, `FlowDriver`, `InputContract`, `OutputContract`, `PythonTaskRunner`, `RetryingRunner`, `Router`, `RoutingPlan`, `Run`, `TaskAdapter`, `WorkQueue`, `run_until_valid` | `contraagent.engine.<name>` |
  | `contraagent.Plugin` | `contraagent.plugins.Plugin` |
  | `contraagent.PreflightRecord` | `contraagent.monitor.api.PreflightRecord` |
  | `contraagent.monitor.api.BlocksBody`, `ChartSeries`, `ColumnsBody`, `GridCell`, `HBar`, `HBarsBody`, `HeatmapBody`, `LinesBody`, `NoteBody`, `PANEL_TYPES`, `PanelBody`, `PanelTile`, `StatusGridBody`, `TableBody`, `TableColumn`, `TilesBody` | `contraagent.monitor.<name>` |
  | `contraagent.backends.launch.Usage`, `CallUsage` | `contraagent.backends.Usage`, `CallUsage` |
  | `contraagent.runs.source.DirectorySource`, `RunSource`; `contraagent.runs.liveness.Liveness` | `contraagent.monitor.DirectorySource`, `RunSource`, `Liveness` |
  | `contraagent.monitor.export.export`, `contraagent.monitor.trends.PeriodError` | `contraagent.monitor.export`, `PeriodError` |
  | `contraagent.dispatch.FlowCall`, `Deferral`, `Rest`; `contraagent.contracts.Check`, `Before`; `contraagent.routing.quota.QuotaRests`; `contraagent.execution.schemas.Cursor`, `UnitCursor`, `Inflight`, `HistoryEntry` | `contraagent.engine.<name>` |
  | `contraagent.calls.CallOutput`, `SchemaRef` | `contraagent.backends.CallOutput`, `SchemaRef` |
  | `contraagent.execution.schemas.JournalRow`, `contraagent.routing.quota.QuotaCap`, `contraagent.dispatch.TimeBoxRecord` | `contraagent.monitor.api.<name>` |
  | `contraagent.dispatch.Hop`, `SkippedHop`, `Changes`, `DeferralCause`, `Frame`, `Loop`, `OtherModel`, `TokenUsage`, `Origin`; `contraagent.execution.recording.RecordingError`; `contraagent.routing.quota.QuotaRule` | `contraagent.<name>` |
  | `contraagent._internal.monitor.core.PanelFn`, `TrendsPanelFn`, `TaskDetailFn` | `contraagent.monitor.<name>` |
  | `contraagent._internal.dispatch.queue.FollowUp`, `OnEvent`, `OnResult`; `contraagent._internal.dispatch.flow.WaitsFor`, `Answer`, `Created`, `OnFlowCall`; `contraagent._internal.routing.quota.AccountOf` | `contraagent.engine.<name>` |
  | `contraagent._internal.backends.process.Sink` | `contraagent.backends.Sink` |
  | `contraagent.backends.opencode.backend.PERMISSION_OF` | `contraagent.backends.OpencodeBackend.PERMISSION_OF` |
  | `contraagent.backends.process.write_launch_marker(backend.argv(launch), launch)` | `backend.mark_launch(launch)` |
  | `launch.env[contraagent.envvars.CALL]` | `contraagent.backends.CallFile.path_of(launch)` |
  | `python -m contraagent.monitor`, `python -m contraagent.hub.server`, `contraagent-monitor` | `contraagent monitor`, `contraagent hub` (or `python -m contraagent ...`) |

  Not public any more: `OMP_PREAMBLE`, `STDIN_THRESHOLD`, `Implementations` (a
  `Mapping[str, AgentTask]`), `PreflightPolicy`, `Executor`, `FlowState`, `Tone`,
  `ValueFormat`, `Window` (the annotations list the values), `MemorySource`, `TimeBoxed`
  (`time_box` returns a generator), `PlanRow`, `RestEvent`, `check_input`,
  `configs_from_tables`, `kind_name`, `make_python_task`, `require_budgets`,
  `account_digest`, `lint_plugin` (use `contraagent plugin lint`), `Script`
  (`StubAgent(script=)` takes a `Mapping[str, Any]`), and every other module under
  `contraagent.<layer>` (`dispatch`, `execution`, `routing`, `runs`, `hub`, `cli`, ...).

- **Renamed names and keys.**

  | Old | New |
  |---|---|
  | `@action`, `Action`, `ActionRunner`, `ContractActionRunner`, `Task.action` | `@python_task`, `PythonTask`, `PythonTaskRunner`, `Task.fn` |
  | `Run.actions()`, `Run.run_actions()` | `Run.python_runner()`, `Run.run_python_steps()` |
  | the `"det"` kind, `action` flag in records | a Python task's kind is its own name; `executor: "agent" \| "python"` |
  | `RunnerConfig`, `RunnerConfig.backend`, `Overrides.backend`, the journal's `backend` | `KindConfig`, `.agent`, `Overrides.agent`, `agent` |
  | `Launch.agent`, `TaskAdapter.agent()`, `needs_inline_agent_file` | `Launch.role`, `TaskAdapter.role()`, `needs_inline_role_file` |
  | `Task.resource_key`, `Task.inputs`, `missing_inputs` | `Task.unit`, `Task.params`, `missing_params` |
  | `Outcome`, `TaskResult.outcome`, `<id>.outcomes.jsonl` | `LaunchResult`, `TaskResult.launch_result`, `launches.jsonl` |
  | `return_reason`, `contract_attempts`, `contract_errors` | `reason`, `rounds`, `round_errors` |
  | `Runner`, `run_validated`, `Run.emit(result)` | `AgentRunner`, `run_until_valid`, `Run.record_attempt(result)` |
  | `WorkQueue(emit=, next=, skip_keys=)` | `WorkQueue(on_event=, follow_up=, skip=)` |
  | `carried` (tasks left at the deadline) | `deferred` |
  | `Run(session=)`, `session` | `Run(run_group=)`, `run_group` |
  | `PipelineConfig.task_plans()`, `RoutingPlan.build(defaults=, require_profile=)`, `RoutingPlan.print()`, `Route.key` | `task_tables()`, `build(declared=, budgets_required=)`, `log()`, `Route.identity` |
  | `agent_task(**profile)`, `agent_task(..., **config)` | each `[tasks.<kind>]` key by name (`agent=`, `model=`, `effort=`, ...) |
  | `Pipeline(..., **queue_options)`, `Run.queue(**kwargs)` and the like | each argument by name (`deadline_s=`, `grace_s=`, ...) |
  | `Command`, `Guard` | `CommandValidator`, `Limits` |
  | `TaskHook`, `AgentRunner(hooks=)` | `TaskScope`, `scopes=` |
  | `agent_task(prompt=)`, `call_prompt(preface=)` | `instructions=` |
  | `OutputContract.model`, `InputContract.model`, `output_model` | `.schema`, `output_schema` |
  | `UnitCursor.inner`, `advance_step(inner=)` | `loop_pass` |
  | `keep_stream` | `keep_transcripts` |
  | `normalize_stream_event` | `normalize_stream_line` (returns a list of events) |
  | `RateLimit`, `LaunchResult.rate_limit`, `rate_limits` | `QuotaReading`, `LaunchResult.quota`; a 429's cool-off is `LaunchResult.quota_refusal` |
  | `Usage.n_calls`, `input`, `output`, `cache_read`, `cache_creation` | `Usage.totals(context_window)`, `len(usage.calls)` |
  | `[[agents.fallbacks]]` | `[[defaults.fallbacks]]` |
  | `Pipeline(preflight=True)` | `Pipeline(preflight="substitute")` |
  | `context_warn` (a count of tokens) | `context_warn_pct` (a percent of `context_budget`) |
  | monitor URLs `.../stream/{slot}`, `.../task/{slot}`, the UI's `?task=` | `.../stream/{key}`, `.../task/{key}`, `?key=` |
  | `Monitor.tasks`, `/api/runs/<run>/tasks`, `TaskRollup` | removed: a task is one task key (`Monitor.task_detail(run, key)`) |

- **Behaviour.** `retries` counts the attempts after the first (`retries=2` is 3 attempts;
  a kind that set `retries=N` sets `N - 1`). A unit locks nothing: give kinds that must not
  overlap on a unit `claims=["topic:{unit}"]`. The task and the result given to a scope, an enricher or
  `row_extras` are frozen; `ResultEnricher.enrich` returns the result to keep
  (`dataclasses.replace(...)`) or None. Removed: `Stage`, `StageRunner`, `join_stage`
  (use a flow), `OneShotBackend` and `Backend.parse` / `watch` (a backend gives
  `Backend.fold`), `read_stream`, `Outcome.touched_paths`.

- **Web packages.** `ca-json-tree`, `ca-markdown`, `ca-count`, `ca-elapsed` are
  `cae-*` elements of `@contraagent/elements`, and `@contraagent/ui/themes` is
  `@contraagent/elements/themes`. `@contraagent/ui/core`: `Route`, `RoutePatch`,
  `DEFAULT_ROUTE`, `parseRoute`, `formatRoute`, `Router` → `ViewRoute`, `ViewRoutePatch`,
  `DEFAULT_VIEW_ROUTE`, `parseViewRoute`, `formatViewRoute`, `ViewRouter`. The graph's
  `EdgeRoute`, `RouteStep`, `Arrangement.routes` → `EdgePath`, `EdgePathStep`,
  `Arrangement.edgePaths`. Theme properties are named by meaning (`--ca-text`,
  `--ca-accent`, `--ca-status-failed`, ...; `--ca-fg`, `--ca-ok`, `--ca-err` and the like
  are gone). `@contraagent/ui` takes `lit` and `@lit/localize` as peer dependencies, and
  importing it no longer sets up the languages or the themes (`configureLocales()`,
  `adoptThemes()`; `<ca-monitor>` calls both).
