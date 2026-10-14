# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- A unit locks nothing: tasks of different kinds on one unit run together unless they
  claim a name they share (`claims=`). Write `claims=["topic:{unit}"]` on the kinds that
  must not overlap on a unit.
- `data-ca-theme` sets the `--ca-*` properties themselves on its element (it set
  `--ca-theme-*` before), so a page's own CSS reads the theme by the elements' names:
  `var(--ca-bg)`, `var(--ca-text-secondary)`. A `--ca-*` property of the page wins when
  it is set on that element or inside it; an embedded `<ca-monitor>` carries
  `data-ca-theme`, so a theme of your own goes on it. `themeRules()` takes the page's
  selector by default (`pageThemeSelector`, no specificity); `themeProp` is removed.
- `ca-json-tree`, `ca-markdown`, `ca-count` and `ca-elapsed` are
  `cae-json-tree`, `cae-markdown`, `cae-count` and `cae-elapsed` in
  `@contraagent/elements`. `@contraagent/ui` no longer exports the styles,
  the themes, markdown (`md`, `mdFile`, `highlight`) or these elements, and
  `@contraagent/ui/themes` is `@contraagent/elements/themes`.
- Rows in Tasks and History are reached with Tab and the arrow keys, and opened
  with Enter. Both lists are tables (`<cae-data-table>`), and a long list draws
  only the rows on screen. The lists' filters (`filterTasks`, `filterJournal`,
  ...) and columns (`taskColumns`, `journalColumns`) are in
  `@contraagent/ui`'s `adapters/`.
- The pipeline graph's Graph | Table switch and the header's language switch
  are radio groups (`<cae-segmented>`): one tab stop, the arrow keys choose.
  The legends are lists for screen readers.
- The monitor's tabs are a tab list ("Views"): one tab stop, the arrow keys,
  Home and End move between the tabs, Enter opens one, and the view below is
  its tab panel. The selected tab is bold as well as underlined.
- `<ca-monitor history="memory">` leaves the host page alone:
  - its single-key shortcuts (1 to 9, `r`, `/`) work only while the focus is
    inside it; the new `shortcuts` attribute (`page`, `element`, `off`) sets
    where they work, `page` being the default with `history="url"`;
  - it writes no `document.title`, and adds no listener to the document or the
    window (the run picker and the theme menu listen for a click outside them
    only while they are open);
  - it keeps its scroll position and the open sections of Outputs and
    definitions in its own memory, not in the page's history entry, so two
    monitors on one page do not share them.
  `e2e/embed.spec.ts` checks this with two monitors in a host page that has its
  own field and shortcuts. A `<cae-data-table>` in a scrolling box follows the
  box's size (a `ResizeObserver`), not the window's.
- The run picker is a dialog: its search field (a combobox) takes the focus
  when it opens and keeps it, the arrow keys name the active run, and Escape or
  a pick returns the focus to the run button.
- Every element that opens something on a click opens it from the keyboard too:
  the task names in Problems and Processes, the rows of Outputs in the
  overview, the definitions, the running tasks, a tool call in a transcript and
  a definition file are buttons. Notices are read by screen readers (failures
  at once). `pnpm e2e` checks every tab with axe (`e2e/a11y.spec.ts`; serious
  and critical violations fail it).
- The monitor writes a list of names (tasks, passes, models, identities) as the
  page's language writes a list: "a, b, and c" in English, "a、b、c" in
  Japanese (`listText()` in `@contraagent/ui`, with `Intl.ListFormat`).
  `factList()` returns the facts of a row as a list, which `facts()` joins.
- `@contraagent/api` reads a refusal's reason: `inputProblems(reason)` (the
  inputs it names, missing or failed checks) and `runRelative(text, run)`
  (paths cut to the run directory).
- `Router` takes an `onLeave` callback, called before it pushes a new history
  entry.
- The monitor API's `JournalRow.stop` is an enum in `openapi.json`: every
  `Stop`, and `skipped` (a row a domain wrote with its own value still
  validates). `@contraagent/api` exports it as `Stop`; a stop the schema adds
  fails type-checking in `@contraagent/ui` until it has a tone and words.
- `@contraagent/ui` exports one name per meaning:
  - `tokenCount()` (was `tokens()`) formats a token count;
  - `tokenStyles` (was `tokens`) is the stylesheet with the design tokens;
  - `taskStatusLabel` and `contractStatusLabel`/`contractStatusWhy` (were
    both `statusLabel`, `statusWhy`).
  The layout engine of the overview (`autoLayer`, `layerGraph`, `kpis`,
  `timeline` and their types) and the `Flow*` type aliases are no longer
  exported; the plan's types are `@contraagent/api`'s.
- Every event an element sends is in `CaEventMap`: the run picker sends
  `ca-close` (was `close`), and `ca-transcript` sends `ca-rounds` (was
  `rounds-changed`; it does not bubble). `RoundsChangedDetail`, `RoundInfo`
  and `TryResult` are with the other event details. `emit()` takes
  `{bubbles: false}`.
- A retry is a try that ran after a try of the same task ran and failed
  (`retries()` in `@contraagent/api`): a task refused for its input and then
  done is not counted as retried in the overview or in the history's
  "tasks retried" filter.
- `@contraagent/ui` takes `lit` and `@lit/localize` as peer dependencies: a
  page that imports it installs them, and its bundle holds one copy of Lit.
- One view of `@contraagent/ui` can be imported alone: `@contraagent/ui/monitor`,
  `/overview`, `/pipeline-graph`, `/task-view`, `/transcript`, `/task-table`,
  `/journal-table`, `/contracts`, `/definitions`, `/kpis`, `/timeline` and
  `/procs` each register their `ca-*` elements and the `cae-*` elements they
  render; `/adapters`, `/words`, `/core` and `/localize` register nothing.
- Importing `@contraagent/ui` no longer configures Lit Localize or adds the
  themes' rules to the document. `configureLocales()` (`@contraagent/ui/localize`)
  sets up the languages and `adoptThemes(document)` (`@contraagent/elements/themes`)
  the themes; `<ca-monitor>` calls both when it connects. On a page that
  configured Lit Localize itself, the elements stay in English and the
  monitor shows no language switch.
- The Japanese text loads when a reader first chooses Japanese: the monitor
  serves it as `ja.js` beside `app.js` (110 kB gzip, from 126 kB), and
  `<ca-monitor>` draws its first view once it is loaded.
- `@contraagent/ui/bundle` is minified: 117 kB gzip, from 139 kB. It keeps
  Lit and the Japanese text in one file. In it and in the monitor's `app.js`
  and `ja.js`, the indentation of the elements' HTML templates is left out
  and the Japanese text is keyed by short prefixes of its message ids.
- `@contraagent/api` makes its requests with `fetch` itself and no longer
  depends on `openapi-fetch`; `createMonitorClient` keeps its options and calls.
- `@contraagent/elements/themes`: each token's meaning is `TOKEN_MEANINGS[name]`,
  not `TokenInfo.meaning`, so the elements' code does not carry the text.
- `custom-elements.json` of `@contraagent/elements` lists the elements' modules
  and their `define` entries only, not the layout and model modules.
- The monitor's colours mean a status, and only where it applies: totals, cost,
  tokens, time and the tabs' counts are in the text colour (the Tasks total is
  no longer red when a task failed), a count of a problem (failed attempts, not
  started) takes its status colour only above 0, and done is a green ✓ beside
  the word rather than a green fill. Failed and not started carry ✕ and ◌ in
  pills and chips, a run's dot is a square when it failed, and links, focus and
  selection share one accent, apart from the cyan of running. The tool icons,
  the coding agent and model chips and the token bars are neutral or identity
  colours that no status uses.
- Theme properties are named by meaning: `--ca-text`, `--ca-text-secondary`,
  `--ca-text-muted`, `--ca-accent`, `--ca-status-failed` (`-attention`, `-done`,
  `-running`, `-muted`, each with a `-bg`), `--ca-agent`, `--ca-meter`,
  `--ca-tok-*` and `--ca-code-*` (syntax colours); `--ca-fg`, `--ca-fg2`,
  `--ca-mut`, `--ca-muted`, `--ca-ok`, `--ca-warn`, `--ca-err`, `--ca-info`,
  `--ca-live` and `--ca-llm` are gone. No colour is fixed in an element's
  stylesheet, so the light theme covers the whole monitor, its header included.
- The pipeline graph's inspector is a card next to the selected mark, node or
  loop box, inside the frame, joined to it by a pointer: it flips to stay in the
  frame, follows pans and zooms, and hides while the item is out of view. With no
  selection the graph has the panel's whole width. On a narrow screen the card is
  a sheet under the frame. Tab goes on from the selected item to its links.
- `ca-toasts`: `ToastKind` is `done`, `failed`, `attention`, `running` or `agent`.
- Python 3.12 or later (`requires-python = ">=3.12"`).
- `WorkQueue` schedule: a greedy list schedule by bottom level, with no
  reservation. A task startable for longer than `overdue_s` (600 s) is overdue:
  overdue tasks go first, the longest waiting first, and while the first task
  that cannot start is overdue, no later task takes a tag, the unit or a place
  under the kind's cap it needs (`aging_per_s` and the time-based reservation are
  gone). With `deadline_s`, from `deadline - slack_s` (a quarter of `deadline_s`
  by default) on, `finishing_kinds` go first, then the shortest remaining work,
  and a task whose remaining work cannot finish before the deadline is deferred
  at once; before that point `finishing_kinds` have no precedence. A task with
  no estimate is ordered as 300 s (was 60 s). `Pipeline` passes `overdue_s` and
  `slack_s` through to the queue.
- A resumed run skips a task only when its key's last journal row is ok and has
  the task's fingerprint (its kind, unit, key and params; its definition: an
  agent task's instructions, role file, output schema, validators and params
  schema, a Python task's function source, output schema and validators; and per
  task it waits for, the content of that task's output file when the flow
  received it, else that task's fingerprint): a changed parameter or definition
  runs the task again, and a task after it when the output it received changed
  (in a flow that does not yield, every task after it). `Journal.last_rows()` and
  `contraagent.execution.run.finished_before` replace `done_keys()`.
- The same kind on the same unit created twice by one flow call is numbered
  (`summarize-u~2`, output `u~2.json`) instead of raising; one key created by two
  flow calls raises `ValueError` at the second, naming `key=`.
- Two `agent_task` declarations of one kind raise at the second task call.
- `Pipeline.check` and `contraagent check` run a generator flow to its first
  wait (every flow call it starts) and check the tasks created by then, the
  exceptions its flow calls raised, and the kinds its code reaches
  (`contraagent.pipeline.reach`: the task declarations the flow refers to through
  its globals, module attributes, closures, defaults and containers, and through
  the functions it calls): their declarations, schemas, validators, plugins and
  routing. `CheckReport.later_kinds` lists those its first step did not create.

- The monitor's English follows one set of words and one form: a task's
  status, an attempt's outcome, "attempt N", "correction", "model", "reasoning",
  "earlier tasks" / "later tasks", the `ambient` credential as "default (this
  machine's login)"; sentence case, facts separated by ` | `, `·` only inside a
  task's name, links named by where they go, ✓ ✕ ◌ always beside a word.
  Times read the same in every locale (`Oct 12, 10:38:40`), durations have one
  format (`<0.1s`, `4.2s`, `2m 05s`), and raw codes (an unknown stop, a quota
  status) show in words.
- A task that did not start names its cause from the run: the input, whether it
  is missing or failed checks, and the earlier task that failed or did not
  start. A waiting task is shown as waiting, not as not started, and a task that
  never ran shows no time, end or model.
- The run card's title is the run's state ("Finished with errors"); an attempt
  chip shows attempt, outcome, time and cost, the rest in its tooltip; each cell
  of the scheduled-tasks matrix has an accessible name.
- An agent or model override (`--agent`, `--model`, `Overrides`) runs every kind
  without failover hops: a hop would run it on another agent or model.
- Any failed launch moves its task to the next failover hop, not only a 429 or a
  safeguard refusal (a provider's 403, a timeout, an output still off-contract,
  ...); only a 429 moves the kind's breaker. `invalid_input`,
  `credential_mismatch` and a launch ended by a signal do not fail over.
- A credential override (`Overrides(credential=...)`) is every failover hop's
  credential too; a hop that named its own ran under that one after a 429.
- The monitor names tasks in a list as chips that open them: the tasks a
  failure kept from running (overview) and the tasks running now (header).
  Tooltips that describe a task put one item per line, so the `·` inside a
  task's name (`kind · unit`) is not also the separator between items.
  `Activity.unit` in `@contraagent/api`.
- The monitor names causes the data has: a task that did not start says
  whether its input is missing or failed checks (`not started (input missing)`),
  or which earlier task failed (`earlier task review · zeta failed`); an output
  that is not written says why in parentheses (`not written (task failed)`). A
  count by status ("3 failed") and a cause are separate messages, so each
  language can order them its own way. A loop is named by its file and line
  (`Loop at flow.py:130`); the Retries, Corrections and Model switches tiles say
  how many tasks ("2 tasks retried"); an agent's own resend of an API request
  shows the error it got. Labels in tiles, table headers, chips, legends and the
  Definitions list wrap at spaces and between Japanese phrases, never inside a
  word or a fact.
- The pipeline graph shows a failure inside a flow call at every layer: a flow
  call's mark shows the most severe state of its tasks and of the flow calls it
  started, and failed when the call raised or was closed, so a call that caught
  a task's failure and returned shows it failed. A node's count is its tasks done
  of its tasks ("28/30"), followed by the others by status ("1 failed | 1 not
  started"); a function node names its flow calls that stopped with an error.
- The Cost tile puts the most expensive kind on one line and its cost and share
  of the total on the next. A failed task's output that was not written shows
  its status once, with no second line repeating it.
- The monitor's Japanese reads as written in Japanese, not translated: tooltips
  are whole sentences that say the cause first, stiff words are plain, and one
  word keeps one meaning (再送 for an agent's own request after a provider
  error, リトライ only for a new session; ツール実行中に中止 for `aborted`,
  中断 only for a call cut off in a transcript; 料金の上限 for `budget`; 未実行
  for a task that never ran, not 未開始). The
  English says "resent its request" for the agent's own retry. The reason beside
  a not-started output no longer repeats its status ("Not started: ..."). A model switch
  is labelled as following any failure, not only a rate limit.
- Coding agent and role: `RunnerConfig.backend`, `Overrides.backend` and
  `Outcome.backend` (and the journal's `backend`) are now `agent`; `Launch.agent`,
  `TaskAdapter.agent()` and `Backend.needs_inline_agent_file` are now
  `Launch.role`, `TaskAdapter.role()` and `needs_inline_role_file`. The prompt's
  `TELEMETRY` line says `role=`, and the monitor's process and launch records
  carry `role`.
- Schema: `OutputContract.model` / `InputContract.model` are now `.schema`
  (`check_file(path, schema)`), and `output_model` is now `output_schema`.
- Python tasks: `@action` / `Action` are now `@python_task` / `PythonTask`;
  `step_task` is now `make_python_task`; `dispatch/action.py` is now
  `dispatch/python_task.py` (`PythonTaskPayload`); `ActionRunner` and
  `ContractActionRunner` are merged into `PythonTaskRunner`
  (`execution/python_tasks.py`); `Run.actions()` / `Run.run_actions()` are now
  `Run.python_runner()` / `Run.run_python_steps()`; `Task.action` is now `Task.fn`.
  A Python task's kind is its own name (no `"det"` kind, no `step` field), its
  key starts with `python:` (and ends with `-<unit>` when it has one), and every
  record says who executed a task with `executor: "agent" | "python"` instead of
  an `action` flag. In the monitor, `InflightAction` is now `InflightPythonTask`,
  `Procs.actions` is now `Procs.python_tasks` and `Procs.children` is now
  `Procs.launches` (agents running inside the run's own process included).
- Units and params: `Task.resource_key` is now `Task.unit`; `Task.inputs` is now
  `Task.params` (`CONTRAAGENT_PARAMS`, a contract record's `params`, the monitor's
  `TaskIO.params`); `TaskAdapter.missing_inputs` is now `missing_params`.
- Task keys are `key` everywhere: the journal row, `CallFile`, contract records
  and the monitor's task detail, upstream and downstream entries.
- Results: `Outcome` is now `LaunchResult`, `TaskResult.outcome` is now
  `.launch_result`, and `runs/<id>/<id>.outcomes.jsonl` is now
  `runs/<id>/launches.jsonl`; `return_reason` is now `reason`;
  `contract_attempts` is now `rounds` (the monitor's `ContractSpec.rounds`), and
  the monitor's `RunSummary.tasks` / `TaskRollup.runs` are now `attempts`.
- Run groups: `Run(session=)` and the journal's, `run.json`'s and the monitor's
  `session` are now `run_group`.
- The monitor's `task_detail` callback type is `TaskDetailFn`; plan columns are
  called groups (`Monitor(groups=)` takes `kinds` only).
- Runners: `Runner` is now `AgentRunner` (`Run.agent_runner()`); `run_validated`
  is now `run_until_valid`; `Run.emit(result)` is now `Run.record_attempt(result)`.
- Queue callbacks: `WorkQueue(emit=, next=)` and `Run.queue(next=)` are now
  `on_event=` / `follow_up=`; a failing follow-up is reported as
  `follow_up_failed`. Tasks left unlaunched at the deadline are `deferred`, not
  `carried` (the queue event, `WorkQueue.deferred`, the summary key).
- Per-kind config: `RunnerConfig` is now `KindConfig`; `PipelineConfig.task_plans()`
  is now `task_tables()`, `configs_from_plans` is now `configs_from_tables`,
  `check_plans` is now `check_task_tables`, `require_profiles` is now
  `require_budgets`, `LAUNCH_KNOBS` is now `TASK_TABLE_KEYS`;
  `RoutingPlan.build(defaults=, require_profile=)` is now
  `build(declared=, budgets_required=)`; `RoutingPlan.print()` is now `log()`;
  `Route.key` is now `Route.identity`. `agent_task(**profile)` /
  `AgentTask.profile` are now `**config` / `.config`.
- The run-wide failover chain moved from `[[agents.fallbacks]]` to
  `[[defaults.fallbacks]]`.
- Validators and budgets: `Command` is now `CommandValidator`; `Guard` is now
  `Limits` (`Launch.limits`, `KindConfig.limits()`).
- `TaskHook` is now `TaskScope`, and `AgentRunner(hooks=)` is now `scopes=`
  ("hook" means a plugin's in-agent hook only).
- `agent_task(prompt=)` and `call_prompt(preface=)` are now `instructions=`; a
  task definition records them as part `instructions`.
- `UnitCursor.inner` (and the monitor's `UnitPosition.inner`) is now `loop_pass`;
  `advance_step(inner=)` is now `loop_pass=`.
- `keep_stream` is now `keep_transcripts` (`Pipeline`, `AgentRunner`).
- `make_python_task(inputs=, outputs=)` and `record_contracts` take
  `input_contracts=` / `output_contracts=`.
- `normalize_stream_event`, `read_stream` and `register_normalizer` take a stream
  `format` (was `backend`); `resolve_format` takes the coding agent's name.
- Monitor URLs: `/api/runs/{run}/stream/{key}`, `/events/stream?run=&key=`,
  `/api/runs/{run}/task/{slot_or_key}`, and the UI's `?key=` (was `task`). The
  `task_detail` callback's failure is reported as `task_detail_error` (was
  `hook_error`).
- `WorkQueue(skip_keys=)` is `skip=`, a function of the task; the queue's
  `follow_up` is a public attribute.
- `RunReport.results` and `contraagent run`'s list of failed tasks include the
  tasks deferred past the deadline.

### Removed

- The `contraagent-monitor` command: the monitor is `contraagent monitor`.
- `Outcome.touched_paths` and `STATE_PATH_RE`: they matched only another
  project's state-file names and nothing read them.
- `Stage`, `StageRunner` and `join_stage`: `FlowDriver` replaces them.
- API 3.0.0: the monitor's per-(kind, unit) rollup: `Monitor.tasks`,
  `/api/runs/<run>/tasks`, `TaskRollup`, the feed's `tasks` event and
  `RunState.tasks`. It made two passes of one task (`review-gamma`,
  `review-gamma~2`) one row and left out tasks with no journal row. A task is one
  task key everywhere: `deriveRun(journal, plan).rows` in `@contraagent/api`, and
  `latestTask(rows)` picks the task the monitor opens by default (in place of
  `latestSlot`). `/api/runs/<run>/task/<key>` and `Monitor.task_detail(run, key)`
  take a task key only, not a `<kind>-<unit>` slot; the `task_detail` callback is
  `fn(run, key, rows)`.

### Added

- Typed panel bodies: a `monitor.Panel` may return tiles, a table, charts (`columns`,
  `lines`, `heatmap`, `hbars`) or `blocks` of them (`contraagent.monitor.api.PanelBody`,
  as models or dicts with their `type`), which the monitor draws with its own elements;
  any other dict is still a JSON tree. `Panel(scope="trends")` is a view over the runs
  of a period (`fn(runs, period)`, `Period`); it is not a run's tab.
- `contraagent monitor --panels views.py:PANELS` (also `--groups` and `--task-detail`):
  a pipeline's own views from a file or a module, with no script of its own.
- `@contraagent/elements/charts`: `<cae-column-chart>` (stacked or side by side),
  `<cae-line-chart>`, `<cae-heatmap>` and `<cae-bar-chart>`, each with a legend, a
  tooltip reached with the pointer or the keys, and a table of its values; the series
  take `--ca-series-1` to `--ca-series-6`, and past six they fold into one.
- The monitor's overview shows each model's share of a run's agent sessions, by cost,
  tokens, time or sessions, as one bar and a table of every model (`Plan.models`). Each
  journal hop records its coding agent and its own tokens (`Hop.agent`, `Hop.usage`), so a
  failover's hops count on their own models. The themes carry six series colours
  (`--ca-series-1` ... `--ca-series-6`), and `@contraagent/elements/primitives` a share bar
  (`shareBar`, `wholePercents`).
- A light launch for a judgement in one turn: `agent_task(tools=())` runs the task with
  no tools, its role's text (or its instructions) in place of the coding agent's system
  prompt, its params and output schema in the prompt, and no plugin, settings or MCP
  server; it needs `output_from="message"`. Claude Code and omp both run it
  (`--system-prompt`, `--tools ""` / `--no-tools`); a coding agent that cannot is refused
  by routing (`Backend.light_launch`). On Haiku it is one call: on omp 658 tokens of input
  where the same task with tools takes two calls of 12,311; on Claude Code 1,180 where a
  role with tools takes two calls of 2,230 (16,863 with the agent's default prompt and tools).
- `usage.resident` in a journal row: the input of the attempt's first API call. The
  monitor shows it on the tokens of each attempt.
- omp launches take `Launch.system_prompt`, `Launch.append_system_prompt` and
  `Launch.tools`, which they left out before.
- Time boxes: `yield time_box(flow, deadline_s=, grace_s=, finishing_kinds=, slack_s=)` runs a
  flow call with a deadline of its own, counted from its start, over the tasks it and the
  flow calls it starts create; the steps outside it are not held to it. Inside, the run's
  deadline rules apply: past it only its finishing kinds launch, for its grace window, the
  rest are deferred and the flow receives `TaskDeferred`. Nested boxes and the run's
  `deadline_s` each hold, so the earliest deadline stops a task. `flow_calls.jsonl` records
  the box, a deferral's cause names it (`flow_call`), and the monitor shows a function's
  deadline and when each of its flow calls' falls.
- A tutorial (`contraagent docs tutorial`): a pipeline from an empty directory, step by
  step, through a stub run, a run on a coding agent and a test; its pipeline is
  `examples/tutorial/`.
- Claims: `agent_task(claims=[...])` and `@python_task(claims=...)` name what each task
  holds while it runs, and one task at a time holds a name, whatever its kind. A claim
  is a template: `{unit}`, `{key}`, `{kind}` and `{params.<name>}` (a list gives one name
  per element), so `["topic:{unit}"]` writes one topic at a time and
  `["topic:{params.topics}"]` holds every topic a task names. `claim_capacity` (a
  `Pipeline` argument, and `[defaults.claim_capacity]` in the config) lets more tasks
  hold a name, by the name or by an `fnmatch` pattern that gives each name it matches a
  capacity of its own. The plan records each task's claims (`PlanNode.claims`), and the
  monitor shows them in the task's detail and finds tasks by them.
- The monitor shows a pipeline's own journal columns (`row_extras`): a column each in the
  history, under its name as written, and the values of each attempt in the task's
  detail. `RunSummary.row_extras` and `TaskDetail.row_extras` name them.
- `agent_task(skills_from=[...])`: skill plugins whose skills a task loads after its own
  plugin's, so tasks with different roles share skills. A skill plugin holds skills only;
  one that holds agents, commands, settings, MCP servers or hooks is refused where the
  task is declared. `plugin lint` checks a skill plugin's skills only. A task's
  fingerprint now covers the skills of its plugins, its own plugin's too.
- Quota caps: `max_five_hour_pct` and `max_seven_day_pct` on a `[credentials.<name>]`, and
  `Pipeline(quota_rule=)` for a rule of your own. A credential past one rests until its
  window resets: tasks skip its hops without launching and take the next hop of their
  failover chain (a gateway, say); a task with no hop left is deferred. `finishing_kinds`
  still launch on it for `grace_s`.
- `deferred.jsonl` records each deferred task and why: a reason in one line and its
  cause as data (`Deferral`: `deadline`, `grace_window`, `cannot_finish`,
  `dependency_not_queued`, `rest` with each resting credential's window, reading, cap
  and reset). The monitor shows a deferred task as "not run" with its cause in the
  reader's language, while the run goes on too (`PlanNode.deferred_cause`).
- Quota rests in the monitor: `run.json` records the caps (`quota_caps`) and the quota
  rule (`quota_rule`), `rests.jsonl` each start and end of a credential's rest, and a
  journal row the hops it passed over (`skipped_hops`). The overview's subscription usage
  shows each window's limit, an identity paused and until when, its rests over the run
  and the usage rule (`Plan.quota_caps`, `.rests`, `.quota_rule`); a model switch names
  a hop passed over as "(identity paused)".
- `agent_task(changes=["topics/{unit}/**"])`: the files a task may change beside its
  output. Each attempt's journal row records what it created, modified and deleted under
  them (`changes`), and the files a failed attempt created are removed. The monitor's task
  detail lists them per attempt ("Changed files").
- `Pipeline(scopes=, enrichers=, row_extras=)`: a `TaskScope` around each attempt of an
  agent task, `ResultEnricher`s that see its result (after its changes are recorded),
  and a domain's own journal columns, as `AgentRunner` and `Run` take them.
- A stub run: `contraagent run --stub` (`Pipeline(stub=StubAgent(...))`) plays every task
  with the smallest output its schema accepts (`contraagent.contracts.smallest`,
  `testing.writes_smallest()`), Python tasks included (their functions do not run, but the
  kinds named with `--execute` / `StubAgent(execute=)`), runs the flow to its end, and
  lists the tasks it created. `StubAgent(default=)` is the reply of a task with none
  scripted; a Python task's reply is its return value. The run id is `<flow>-stub`,
  `run.json` says `stub: true`, and the monitor marks the run "stub agent".
- `agent_task(output_from="message")`: the agent's final message is the task's output.
  The runner writes it to the output file and checks it there, and a message that fails
  its checks goes back to the same session; the call file says so (`output.from`), the
  stop hook leaves it to the runner, and a passing message is never taken for a hollow
  launch. The monitor's definition shows the output "from the final message". The review
  example's `review` gives its verdict this way.
- `<cae-layered-graph>`: the part `keys` is the line of key hints. A node's `marks`, `loose`, `counts` and
  `progress` are optional: `counts` and `progress` default to what its marks say
  (`strings.progress`, `fillNode`). graph.md lists the parts and the rules of size,
  series and `key`.
- `sortRows` orders a `sortable` column without `compare` or `text` by its cell when the
  cell is a string or a number.
- `pnpm tarballs` in `web/` packs `@contraagent/api`, `@contraagent/elements` and
  `@contraagent/ui` into `web/tarballs/`, naming each other by path, so npm and pnpm
  install them from a checkout. The packed `package.json` has no `source` export
  condition.
- Documentation examples: "Building a page" in `@contraagent/elements` (a CI pipeline's
  page from the generic elements, live on the documentation site), and `<ca-monitor>` in
  a Vite application in `@contraagent/ui`'s "Embed the monitor".
- The monitor on a hub shows the hosts behind the runs: the run picker groups runs by
  host (each host's state in its header) and filters them by host, the header names the
  run's host, a run whose host stopped reporting reads "no report from host" wherever its
  state shows, and the hosts page (`?page=hosts`) lists the hosts and each account's
  usage over every run. A monitor of one host looks as before.
- `run.json` names the run across hosts: `run_uid`, an id no other run has (kept when
  the run is resumed), and `host_id` (`CONTRAAGENT_HOST_ID`, else the host name).
- `Monitor(source=..., liveness=...)`: the monitor reads runs through a `RunSource` and a
  `Liveness` (`contraagent.monitor.source`). `DirectorySource` and `ProcLiveness`, the
  defaults, read the runs directory and `/proc`; `MemorySource` and `StaticLiveness`
  hold records in memory. The layout of a run's records is `contraagent.rundir`.
- `contraagent hub` and `contraagent relay` (the `hub` extra): every host's runs in one
  monitor. A relay on each host ships its runs' records, the files their contracts name
  and a heartbeat to a hub, at least once and in order; a hub stores records in Postgres,
  file contents in object storage by SHA-256, and transcripts as segments (an open
  segment on its disk, sealed segments of zstd frames in object storage, their index in
  Postgres), and serves the monitor over them. Ingest takes per-host tokens; the monitor
  takes a read token (`/login`). The wire is `contraagent/hub/openapi.json`; see the
  documentation topic "Many hosts: the hub".
- Hub retention: `contraagent hub --retain-days N` (or `CONTRAAGENT_RETENTION_DAYS`)
  removes runs with no activity for N days, with their records, transcripts and file
  references, on a schedule (`--prune-every`); live runs, runs whose host stopped
  reporting and runs with no activity time are kept. Blobs no run references go after a
  grace period. `contraagent hub prune [--dry-run]` prunes once.
- `GET /healthz` on the hub: 200 when its record, blob and transcript stores answer, 503
  naming the ones that do not.
- A deployable hub in `docs/examples/hub/`: a `Dockerfile`, a `compose.yaml` with
  Postgres and MinIO, `make-tokens`, and a systemd unit for the relay; the documentation
  topic "Operating a hub" covers setup, tokens, retention, backups, upgrades and
  troubleshooting.
- The monitor's transcript feed wakes when a transcript grows instead of every second,
  sends each message with its line number as the event id, and resumes from
  `Last-Event-ID` or `?from=` with no gap and no duplicate.
- A page of a transcript carries at most 1,500 lines and 4 MiB.
- Every run document (`run.json`, `contracts/`, `definitions/`, `calls/`, `inflight/`) is
  written atomically (`rundir.write_document`).

- `Pipeline.check(flow, ...)` and `contraagent check tasks.py:flow`: the task
  graph is built and checked with nothing launched, and every problem is reported
  at once:
  - the flow (an exception, at the caller's line; an `after=` naming no task);
  - parameters against their `params` model;
  - output models the in-session hook cannot import, checked in a fresh interpreter;
  - command validators whose program is not on `PATH`;
  - plugin lint;
  - the routing plan, with its warnings.
- `contraagent.testing.StubAgent`: a coding agent for tests that plays scripted
  replies per task key or kind:
  - an output, nothing, a failure or a 429;
  - a list (one reply per launch) or a callable;
  - every launch is recorded.
  `stub.backends()` puts it under every coding agent's name, so a pipeline's
  own config routes to it. The demo's `test_demo.py` tests it this way.
- Documentation installed with each package, matching its version:
  - `contraagent`: `contraagent/docs/` (its `README.md` is the PyPI page), with
    the demo pipeline and the reference config under `docs/examples/`;
  - `@contraagent/ui`: its `README.md` and `docs/`, with the browser examples;
  - `@contraagent/api`: its `README.md`.
- `contraagent docs [topic] [--path]` prints the installed documentation.
- `contraagent docs --pointer` prints a block for a project's AGENTS.md or
  CLAUDE.md that points its coding agent at the installed documentation.
- `contraagent run <file.py>:<flow>`: runs a flow with the arguments `check`
  takes (`--config`, `--kwargs`, `--agent`, `--model`), plus `--run-id`,
  `--resume` and `--runs-dir`; logs progress at INFO and exits 1 when a task failed.
- `contraagent check` names the documentation topic that explains each error,
  and reports every routing problem of a config at once (`RoutingError.errors`).
- `contraagent docs <topic>` prints the code a topic quotes. The site renders
  the same expansion (`contraagent.docs.expand`).
- A validator may take the task's `params` and its call file (`call`) by
  keyword; `CommandValidator` replaces `{call}` with the call file, so a check
  of the output against the input also runs in the agent's session.
- `RunReport.value`: what the flow returned; a `Pending` in it reads its task's output.
- API 2.0.0: `JournalRow.round_errors`, the errors of each round that failed its
  output checks (each was sent back; after `invalid_output` the last still
  stood), replaces `contract_errors`, which held only the last.
- Progress on the `contraagent.*` loggers at INFO, as it happens: each task's
  start and end (stop, time, rounds, the hop it ended on), each fix-up with the
  errors it was sent, each model switch with its reason.
- `RunExists`: a run id that already holds a run is refused unless `resume=True`.
- Config errors name the closest valid key, table or agent ("did you mean"), a
  failover hop by its block (`block 1 (hop 2)`), and a missing budget by where it
  goes; a refused effort is reported once for every kind it applies to.
- `Task.declared_unit`: the unit a task was given, empty when none.
- `contraagent.testing.StubAgent`, as Claude Code, runs the launch's plugins'
  Stop hooks before it ends its turn and replies again in the same launch when
  one sends the output back (`StubLaunch.in_turn`).
- A command validator runs in the task's working directory (recorded in the call
  file, `CallFile.cwd`), and runs even when the schema check fails.
- Logs: `[route]` per kind for the whole plan, a task that starts on a hop
  because its kind's breaker is open, and `[skip]` for a task a resume skips.
- API 2.1.0: `TaskCounts.running`, the tasks running now in a live run.
- API 2.2.0: `JournalRow.hook_errors`, what the plugin's stop hook sent back
  within a launch (Claude Code fixes it before its turn ends); the monitor counts
  each as a fix-up and shows the hook's message in the transcript.
- API 2.3.0: `JournalRow.web_queries`, the queries of the web searches an attempt
  made, from Claude Code's `WebSearch` and omp's `web_search` alike; the monitor
  shows them with the attempt.
- API 2.4.0: a transcript's tool call carries `web_query` when it is a web search
  (Claude Code `WebSearch`, omp `web_search`), and `web_fetch` when it reads a web
  page (Claude Code `WebFetch`, omp `read` of a URL). `ca-transcript` shows a web
  search as its query and the pages it returned as links, and a web page read as
  its URL as a link; `revealWebSearch(query, nth)` opens a search's card. The task
  view's list of web searches opens each one's card in the transcript.
- Task agents take their instructions from their plugin and call file only, and
  keep their built-in tools, skills and subagents:
  - Claude Code runs with no settings files (`--setting-sources ""`: no user,
    project or local hooks, skills, commands, agents, plugins or permissions),
    no CLAUDE.md files and no auto-memory;
  - omp runs with its discovery of AGENTS.md, CLAUDE.md, `.omp/`, `.claude/` and
    other tools' skills, rules, hooks and MCP servers turned off, all but the
    task's plugin (`--config backends/omp/isolation/config.yml`, an empty
    `CLAUDE_CONFIG_DIR`);
  - neither inherits the variables of a Claude Code session that started the
    run (its id, messaging socket and token).
- omp launches report their tokens and cost (summed from each assistant
  message's `usage`) and the account's 5-hour and weekly usage at the launch's
  start: what the latest request reported in its headers, as `omp usage` keeps it.
- The monitor's web UI is rebuilt as web components (Lit, TypeScript) in
  `web/`: `@contraagent/api` (types generated from the OpenAPI document, a REST
  client, the live feeds, a store) and `@contraagent/ui` (`<ca-monitor>` and an
  element per view, usable in any page or framework, themed by `--ca-*`
  properties). The built page is committed under
  `src/contraagent/monitor/static`; CI checks that it and the generated types
  are current.
- The monitor keeps where the reader is in the URL (run, tab, task, task view,
  round, definition, filters): Back and Forward step between places, and Back,
  Forward and a reload also restore the scroll position and the open cards.
  Typing in a filter no longer adds history entries.
- The monitor speaks English and Japanese (`@lit/localize`): a switch in its
  header changes the language in place and remembers it; without a choice it
  follows the browser. `<ca-monitor locale=>` and `setLocale` set it for an
  embedding page. Run data (kind names, stops, transcripts) is not translated.
- A documentation site (`web/apps/docs`, Astro Starlight) that renders each
  package's documentation, with live examples of the elements fed with the demo
  pipeline's run, and references generated from the OpenAPI document, the custom
  elements manifest and the theme's stylesheet.
- The monitor speaks to engineers who use coding agents but do not know this
  code: states, counts and reasons in their terms (AGENTS.md, "Words the UI
  shows"), with the code's names kept in tooltips. The overview lists problems
  by cause (a failed task with the tasks it stopped), counts tasks rather than
  attempts, and tells a finished run from a stopped one; a task's page says in
  one line what happened to it, tells retries from fix-ups, and no longer blames
  `keep_transcripts` for a task that never started.
- API 1.2.0: `RunSummary.tasks` counts the run's tasks by how they ended
  (the numbers its own page shows), and `RunSummary.not_run` the journal rows of
  tasks that never ran (refused for an input, or skipped); a task's `io.params` are its call file's params, values from earlier
  tasks included, not only the scalar ones.
- An attempt's `wall_s` in the journal is the time of every hop: a model
  switch after a rate limit no longer drops the time spent before it (nor does
  a pool member that answered 429). The demo agent reports the time a
  launch actually took.
- A Python task's kind records its definition too (`definitions/<kind>.json`):
  the function's module, file and line, signature, docstring, output and
  source; the monitor shows it like a function's documentation. A kind's
  definition no longer shows a coding agent or model: which agent runs a kind is
  configuration, not definition (the task detail and history show what ran).
- The journal records what each attempt spent: `usage` (input, output, cache
  read and write tokens, API calls) and `cost_usd` as the coding agent reports
  them, summed over its rounds and hops; each hop also records its credential
  and cost. `RunSummary` adds the run's `cost_usd` and `tokens`. The monitor
  shows them per attempt, task, kind and run, with the identity each attempt
  ran under.
- For a subscription, the journal keeps every utilization reading the coding
  agent sent during an attempt (`quota`: 5-hour and weekly %, reset times, when
  it arrived, and the credential, i.e. the account, it belongs to; Claude Code
  sends one when a session starts or resumes), and `RunSummary.quota` each
  account's first and last reading over the run. Readings are account-wide:
  parallel tasks on one account share them.
- The plan reports a task refused for a missing or off-contract input as
  `blocked` (not started) rather than `failed`, and so is everything waiting
  behind it.
- The run feed (`/events`) sends `ready` once its first round, the whole journal
  replay included, is out (`ReadyMessage`; API 1.1.0). The UI uses it to tell new
  journal rows from replayed ones instead of waiting a fixed 1.5 s.
- `contraagent check` checks each route's model against the list its coding agent
  keeps locally (`omp models`): a `provider/model` id the list lacks is an error,
  with the closest listed id; a bare name the list lacks is a warning.
- `contraagent run` ends with the run's time, cost and fix-ups.
- omp's two wires (`--mode json`, RPC) are read by one `TraceReader`, tested on
  recordings of a real omp (`tests/fixtures/omp/<version>/`, written by
  `record.py`). An event type it does not know is counted in
  `LaunchResult.unread_events` and `JournalRow.unread_events` (API 2.4.0) and
  logged once; the monitor marks the attempt in the history and the task view.
- `contraagent docs plugins` says how a task gets a tool, web search included,
  on each coding agent.
- `FlowDriver` runs generator flows over a `WorkQueue`: `yield` a task, a batch
  (list or tuple) or a generator (its own flow call, run concurrently), and
  receive the answer there; `yield from` stays in the same flow call. What a
  yield waits for and what it receives come from callbacks (`waits_for`,
  `answer`, `created`, `on_flow_call`); by default a flow yields `Task`s and
  receives `TaskResult`s. With `answer=result_or_raise`, a task that did not
  succeed raises `TaskFailed` at the `yield`, `TaskDeferred` when it was deferred;
  past the grace window a waiting flow call is closed.
- `Task.tail_s`: the expected time of the work after a task that is not queued
  yet; the queue's bottom level counts it. `Pipeline` sets it from the runs
  directory (`JournalEstimates.tail`): the median, per tail key (the flow path's
  function names, the kind, and the passes of the loops around the task, each
  capped at 3), of the longest chain of wall times along `after` and
  `created_from` after the task. Only the 10 most recent runs are read, only
  complete chains are sampled (every task after it completed, every flow call
  around it returned), and the run itself adds samples as it goes: each attempt
  to its kind's duration (`estimate`), each flow call that returns to the tails
  of the tasks it created.
- `WorkQueue.extend(tasks)` queues follow-up work and finishes a task it
  refuses as `duplicate_key`.
- Generator flows in `Pipeline.run`: a flow that is (or returns) a generator
  yields a task call and receives its checked output at the `yield` (a list or
  tuple waits for every item; a generator item is its own flow call); loops,
  branches, fan-outs sized by a result and joins across units are plain Python.
  Passing a received output on to another task is the dependency, as passing
  its `Pending` is; a text output is received as a `TextOutput` (a `str`) so it
  is recognized. A task that did not succeed raises `TaskFailed` at the `yield`,
  `TaskDeferred` when it was deferred. Every kind the flow's code reaches is
  routed, and probed by `preflight=True`, before the first launch; a kind
  declared inside the flow's body is routed when its first task is created, so a
  config problem raises at that task call.
- Each task records its origin (`Task.origin`, `Origin`, `Frame`, `Loop`):
  `plan.jsonl` gains `flow` (the frames of flow code that created it, outermost
  first, each with the loops around its call site and the pass of each,
  `loops: [{line, pass}]`), `created_from` and `flow_call`; each flow call's
  start (with `flow`, its parent's frames where it was yielded) and end are in
  `flow_calls.jsonl`; journal rows carry `fingerprint` and `flow_call`. A pass is
  one iteration of one loop of flow code, counted as the code runs
  (`sys.monitoring`), from 1 each time the loop is entered; a comprehension is a
  fan-out, not a loop.
- `RunReport.flow_errors`: a top flow call that raised after its first task was
  queued; it makes `ok` False and `contraagent run` exit 1.
- `Pipeline(max_passes=)` and `[defaults] max_passes` (10): a task call, or a
  `yield` of a child flow call, in a later pass of a `while` loop raises
  `TooManyPasses`, naming the loop (`file:line`) and the pass. A `for` loop has
  no limit: it ends with its iterable.
- API 2.5.0: `PlanNode.flow` (`FlowFrame`: function, file, line, loops;
  `FlowLoop`: line, pass), `created_from` and `flow_call`; `Plan.flow_calls`
  (`FlowCallNode`: id, parent, function, flow, state, error) from `flow_calls.jsonl`, empty for a
  run whose tasks no flow created; `JournalRow.fingerprint` and `flow_call`. A
  flow code file under the run's working directory is given relative to it
  (`run.json` records `cwd`, `Run(cwd=)`). `@contraagent/api` exports
  `FlowFrame`, `FlowLoop`, `FlowCallNode` and `FlowCallState`, and the overview's
  graph reads them from the plan.
- `RoutingPlan.build(all_kinds=False)`: a plan of some kinds only, which does not
  log the task tables naming other kinds.
- The overview's pipeline graph is drawn by layer of the flow: a node per kind
  for the tasks a function created itself, a node per function it called as a
  flow call (its marks are the flow calls), and the nodes one loop created in a
  box, a nested loop's box inside it, with a dotted edge back to its first layer
  for its next pass. A kind node shows who runs its tasks (agent or Python). Each box counts its own loop's passes ("up to 3 passes", and "1 pass: 4 |
  2 passes: 1" when its units differ), and a unit's mark shows the passes it
  ran. Opening a box shows its passes: a row per unit, a column per node and
  pass, a nested loop's passes nested in each outer pass, sortable by number of
  passes or by status. A node above 200 marks shows a bar of its counts and its
  failed units. The layout is layered, with edges routed between the layers,
  never over a node or a box's label. A breadcrumb (Pipeline › function › loop)
  names every layer below the top; the layer is in the URL, and Escape goes up;
  Shift and an arrow key follow an edge. While a layer holds a single node the
  graph opens it, and stops at a node whose flow call raised. A dashed edge joins
  a task to a result it was created after, where it does not wait for that output.
  A click selects a mark, a node or a loop box, and a panel beside the graph
  shows its facts and links to its task detail, its kind's tasks, its function's
  layer or its loop's passes; a double click or Enter follows the first. The
  selection is in the URL (`sel`). A link to a layer the run does not have opens
  the first layer and names it; a function's qualified name alone opens its layer
  when the run reaches it one way only.
- `contraagent.docs.examples.analysis`: a nested generator flow (three layers of
  flow calls, nested loops, a fan-out sized at run time, a kind chosen on a
  result, `heavy`-tagged parsers). The demo pipeline's `docs` flow is a generator
  (a review loop per unit, gamma's summary revised once), with `docs_one_review`
  as the static flow; the demo also writes a run of the nested flow (`analyse`).
- Built-in themes for the monitor and every element: contraagent Dark (the
  default), contraagent Light, and themes of code editors (GitHub Dark, GitHub
  Light, One Dark, Nord, and High contrast from GitHub's dark high contrast).
  Text reads at 4.5:1 on every surface and tint (7:1 in High contrast). The
  header's theme control changes the theme at once and remembers it; System
  follows the system's colour scheme. `<ca-monitor theme="...">` fixes it;
  `data-ca-theme` on any ancestor themes any element; `--ca-*` properties still
  override one token at a time. `@contraagent/elements/themes` holds the themes
  as data, and `adoptThemes()` adds their rules to a document or a shadow root.
  New properties: `--ca-backdrop`, `--ca-shadow`, `--ca-focus`,
  `--ca-focus-width`, `--ca-selection`, `--ca-tint`, `--ca-color-scheme`. The
  example of a theme of one's own is Solarized Light.
- A type and radius scale for the elements: `--ca-font-size-xs`, `-sm`, `-md`,
  `-lg`, `-xl`, `-2xl` (10, 11, 12, 13, 15 and 28 px) and `--ca-radius-sm`,
  `-md`, `-lg`, `-pill` (4, 8, 12 and 999 px), the same in every theme. The
  shared stylesheets read them; `@contraagent/elements/styles` exports each
  shared sheet (`resetStyles`, `textStyles`, `statusStyles`, `chipStyles`,
  `layoutStyles`, `motionStyles`, `meterStyles`, `factStyles`), and `base` is
  the list every element starts from.
- `@contraagent/elements`: generic web components and their parts, with no
  contraagent data and no localization library (Lit is a peer dependency):
  - the design tokens, the shared stylesheets and the built-in themes;
  - primitives: a tone (`Tone`: failed, attention, done, running, muted,
    neutral) and status pills (`pill`, `statusWord`, `statusChip`), `legend`,
    `factLine`, `icon`, `RovingFocusController` (one tab stop for a group of
    items) and `windowRows`;
  - elements: `<cae-segmented>` (one choice among a few, a radio group that
    sends `cae-change`), `<cae-json-tree>`, `<cae-markdown>` (its words in
    `strings`), `<cae-count>` and `<cae-elapsed>`, with markdown and code
    highlighting (`md`, `mdFile`, `highlight`).
  Importing a module registers nothing: `@contraagent/elements/define` registers
  every `cae-*` element, and `…/segmented/define`, `…/json-tree/define`,
  `…/markdown/define` and `…/count/define` one each. Its documentation:
  primitives, theming and strings.
- `<cae-data-table>` (`@contraagent/elements/data-table`, registered by
  `…/data-table/define`): rows in a real `<table>`, one tab stop for the rows
  (the arrow keys, Home and End), Enter or a click as a row's action
  (`cae-activate`) or selection (`cae-select`), sortable headers (`cae-sort`,
  `sortRows`), and above `windowAt` rows only the rows on screen drawn. Its
  columns are `DataColumn`s; documented in `docs/data-table.md`.
- `<cae-stat-tiles>` (`@contraagent/elements/tiles`): figures as tiles, each a
  label, a value that counts up, lines of facts and a link (`cae-action`).
  `<cae-lanes>` (`@contraagent/elements/lanes`): bars on a time axis, a lane
  per group, overlapping bars stacked (`stack`), running bars growing until
  now. `<cae-check-table>` (`@contraagent/elements/check-table`): named values
  checked one by one, with `verdict()` for a verdict elsewhere. Each has a
  `define` entry and a page in the package's `docs/`. `@contraagent/ui` builds
  `ca-kpis`, `ca-timeline` and a checked file's field table on them, from the
  adapters `kpiTiles`, `lanesFromJournal` and `checkRowsFromContract`.
- `<cae-layered-graph>` (`@contraagent/elements/graph`): nodes in layers, joined
  by edges, in clusters (a cycling cluster draws its return), each node a group of
  marks lined up by series; pan, zoom, a card for the selection (the `inspector`
  slot), the keyboard, a node table, and `arrange` and `layoutGraph` for the order
  and the drawing. `<cae-mark-matrix>` (`@contraagent/elements/matrix`): marks in
  a table under nested groups of columns. Events `cae-drill` and
  `cae-view-change`. `ca-pipeline-graph` is built on them, from the adapters
  `graphFromPlan` and `matrixFromPlan`; both are documented in `docs/graph.md`
  and `docs/matrix.md`.
- `<cae-transcript>` (`@contraagent/elements/transcript`, registered by
  `…/transcript/define`): a conversation with an agent in sections, with
  bubbles, reasoning, notices and tool cards (a web search lists its pages,
  a page read shows its URL), a section picker, following the end as it grows
  and counting what arrived below (`cae-section-change`, `cae-section-shown`,
  `cae-load-earlier`); documented in `docs/transcript.md`. `<ca-transcript>`
  draws a task's transcript with it, from the adapter `transcriptSections`
  and the `StreamController` that tails the stream feed.

### Fixed

- A long table (the monitor's history, its tasks) no longer hangs the page when it is
  scrolled fast: `<cae-data-table>` keeps each drawn row's height, so rows of different
  heights no longer move its window back and forth, and it measures again on the next
  frame, never within an update.
- `contraagent plugin render` writes nothing in a skill plugin (it wrote `package.json`
  and `hooks/`, after which the plugin was no longer a skill plugin), and `plugin lint`
  names such files as what an earlier render left.
- A skill whose directory is a symbolic link is read like any other: its files are part
  of the task's fingerprint and show in the monitor's definition (they were left out).
- A read of a transcript on a hub no longer fails when several segments are sealed while
  it runs: a sealed segment's file stays until the reads that hold it end.
- `<cae-layered-graph>`: the line of key hints keeps its height when the graph has no
  focus, so a click into the graph no longer moves what is under it (a click on a sort
  header there was lost); on a touch screen there is no such line. There is no card
  while the `inspector` slot is empty. A height set on the element is the frame's: the
  frame fills it, the drawing fitted in it.
- `<ca-monitor>` takes `base-url`, `history` and `run` whenever they change, also
  after it connects; a new `base-url` closes the old server's feeds. A request to the
  API that gets no JSON answer (an HTML page, a 404, a network error) is shown with its
  URL and cause, and written to the console, in place of "No runs yet". `ApiError`
  has the `url`, a `failure`, the `status` and the media `type`; `MonitorSnapshot` has
  `error` and `runsLoaded`.
- Below 760 px wide, the open run picker spans the header 16 px from each side; it ran
  off the right edge and scrolled the page sideways.
- The monitor's transcript feed no longer skips the lines after a page that stopped at
  its event or byte limit, no longer sends a transcript's last page again on reconnect,
  and holds a half-written last line until it is complete.
- A new agent session that starts while the reader is scrolled up in a
  transcript keeps the session being read on screen; it showed the new one.
- Failures that stopped for a limit, a rate limit, an API or authentication
  error, a refusal, a permission denial or a wrong identity are shown in the
  failure colour, with ✕, in the history, the problems list and the outputs.
  One rule set draws every status: a status element carries `data-tone`
  (and `data-mark` for ✓ ✕ ◌) in place of a class per stop, outcome or
  contract status (`.o-*`, `.p-*`, `.j-*`, `.t-*`, `.mk-*`, `.ct-chip.<status>`).
  The notices, the run's result, a task's summary line, a round's verdict in
  the transcript and the stage chips take `data-tone` too; the dot beside a
  transcript's live round is in the running colour again.
- Task counts agree everywhere: done counts tasks done and done after retrying;
  skipped tasks are counted on their own. The pipeline graph's nodes, the
  overview's progress line and the run's result counted skipped tasks as done;
  the run list and the tasks figure now show the skipped count too.
- A task that did not start for an input and then ran is done, not done after
  retrying: a refusal is not a failed attempt.
- Panning and zooming the pipeline graph is smooth on large runs: the view
  moves the drawing without drawing it again, and the nodes are measured only
  when the graph changes.
- History and the timeline name why a task did not start as the tasks list
  does (`<ca-journal-table>` and `<ca-timeline>` take the run's `plan`).
  `@contraagent/api` derives the tasks, their counts and their problems once
  per state, in `deriveRun(journal, plan)`; `outcomeOf`, `planOutcome`,
  `isFinished`, `progress`, `result`, `tryCounts` and `elapsedS` are exported
  from it.
- The pipeline's table and a loop's passes are drawn in the graph's frame, which
  keeps its height; a "Graph | Table" switch stays at one place in every view; a
  table row shows its node's status in one column and is selected as a node is;
  a loop's passes are centred. The breadcrumb names each loop by where it is
  ("Loop at flow.py:122"), as the loop's card and its link do.
- The Tasks and History tabs' filters are in the URL only on those tabs; a kind
  node's link to its tasks clears a kind filter left from before.
- A task's attempts in a resumed run no longer read "Attempt 1" twice: an
  attempt of a later run start reads "Attempt 1 | resumed run", and each agent
  session button shows the attempt its journal row belongs to.
- A task's input view lists each file it reads with the earlier task it comes
  from, in place of an "Also an input" chip on the earlier task.

- An agent task with no plugin (`agent_task(instructions=)`) can write its output
  file in Claude Code: it runs with the plugin template's permissions
  (`--settings`). Headless Claude Code denied the `Write`, so the task always
  ended `invalid_output`.
- Tasks of one kind and one unit given different `key=` write their own output
  files (`out/<kind>/<key>.json`); they wrote one file (`out/<kind>/<unit>.json`)
  and raced.
- A kind with no failover chain records the route it ran on (`route`, `hops`) in
  the journal; it recorded none.
- A fix-up for a file that met its schema and failed only its validators no
  longer resends the JSON Schema.
- The template's `hooks.toml` says `omp/index.ts` is written only for a tool hook.
- omp's tool calls are counted once each (`tool_uses`); each was counted at its
  call and again at its execution.
- `omp-rpc` records each API call's tokens and cost from omp's `message_end`, as
  `omp` does; it recorded none (it waited for a stats frame omp does not send).
- An omp launch whose provider error omp retried past ends `completed`, not
  `rate_limited`: the latest assistant message decides.
- An omp launch the provider refused (`403 ...`) names the provider's message as
  its reason (`stderr_tail`); omp writes it to no stderr, and the reason was empty.
- `omp-rpc` reads its session id from `get_state` even when other frames arrive
  before the response (it read only the next frame).
- A generator flow whose code reaches two declarations of one kind (a
  function's default argument and the one its caller passes instead) runs; it
  failed before the first launch with "two agent_task declarations share kind".
  A reachable kind is a candidate: the declaration whose tasks are created is the
  kind's, routed again when its `config` or `requires` differ. Creating tasks of
  two declarations of one kind that differ raises `ValueError` at the second task
  call and names what differs (`AgentTask.differences`); two `agent_task` calls
  that declare one kind the same way are one kind. `Pipeline.check` reports two
  reachable declarations of one kind that differ as a warning.

- The monitor returns a text output's content (it returned null for anything
  that is not JSON).
- The monitor's tasks tab lists every task of the plan, one row each, with the
  same count as the header and the overview: a task that never ran (waiting,
  not started, not run) is a row with its status and cause, and the passes of a
  loop over one unit are a row each, with their pass. It listed one row per kind
  and unit, from the journal only. `@contraagent/api` adds `deriveRun` and
  `loopPass`; `<ca-task-table>` and `<ca-definitions>` take the run's `journal`
  and `plan` in place of `tasks`.
- A refused task's reason names the task whose output it was missing.
- A Python task without a unit writes `<kind>.json`, not `python:<kind>.json`.
- `contraagent monitor --openapi` without a path writes to stdout, not into the
  installed package.
- `contraagent.testing.StubAgent` answers to each coding agent's name in the
  journal and writes its transcript in that agent's stream format.
- A unitless Python task has the same (empty) unit in the journal and in its
  contract record.
- A config built in code is named `<config>` in its errors, not `None`.
- A config table that is not `[defaults]`, `[tasks.*]` or `[credentials.*]` is an
  error, not ignored.
- `contraagent` output piped into `head` ends quietly.
- A task table with an unknown key is still read, so its other problems are
  reported in the same check; an unknown role names the closest one.
- The monitor names the tool on each tool result of a transcript.
- A task the queue defers finishes through `follow_up` (`stop="deferred"`), so
  the work that waits for it is answered, and the queue keeps running the
  follow-up work it queues (a `finishing_kinds` task); a finishing task that
  depends on a deferred one launches.
- A follow-up task the queue refuses as a key in flight finishes through
  `follow_up` (`stop="duplicate_key"`); its waiter was never answered.
- A long chain of skipped follow-ups on resume, or of queued tasks linked by
  `after`, no longer exceeds Python's recursion limit.

## [0.1.0] - 2026-10-10

First version.

### Added

- Layers, each importing only the ones below it: `dispatch` (tasks, work
  queue, stages), `backends` (`claude -p`, `omp -p`, `omp --mode rpc`, the
  supervised subprocess loop, transcript normalizers), `contracts` and
  `validators`, `routing`, `execution` (run directory, journal, resume cursor),
  `plugins`, `pipeline` and `monitor`.
- Typed tasks: `agent_task` and `@action` with pydantic parameters and outputs;
  a flow is a plain function whose `Pending` results are the dependencies;
  `Pipeline.run` returns a `RunReport` and can resume from the journal.
- Plugins as task implementations (roles, skills, hooks declared once in
  `hooks.toml` and rendered for each coding agent), with `contraagent plugin
  new | lint | render`; each agent task is handed a call file with its
  parameters and output contract.
- Output and input contracts checked by schema and validators (`Command`
  among them); an output that fails goes back to the same session.
- Routing from one TOML file: per-kind agent, model, effort, budget and
  credential; credentials (subscriptions, API keys, gateways such as LiteLLM),
  credential pools, per-kind failover chains on rate limits, and an optional
  preflight of every route.
- A read-only live monitor with a typed HTTP and Server-Sent Events API:
  pydantic response models in `contraagent.monitor.api`, the committed
  `openapi.json`, local-only `Host` checks and opt-in CORS.
- A `ContraagentError` hierarchy for the errors the library raises, and
  progress reported through `logging` on the `contraagent.*` loggers.
