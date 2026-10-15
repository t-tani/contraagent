# contraagent: notes for coding agents

`contraagent` runs coding-agent CLIs (`claude -p`, `omp -p`) as typed,
supervised tasks. This file is for agents changing the package itself.

## One word, one meaning

The glossary is `src/contraagent/docs/concepts.md`. Every word there means
exactly one thing in the code, the files a run writes, the monitor (API and UI),
the documentation and the examples. Do not use one of these words in another
sense, and do not add a second word for the same thing; a new word goes into
that glossary first.

## Words the UI shows

The monitor's UI is read by engineers who use coding agents but do not know
this code, so it shows run data in their terms. The glossary's terms stay in
the API, the files, and the UI's tooltips (as the secondary detail); the visible
words come from `web/packages/ui/src/words/`, and the same rule applies
there: one word, one meaning, on every screen. Japanese follows
`web/packages/ui/xliff/GLOSSARY.md`.

| Code term | UI (English) | UI (Japanese) |
|---|---|---|
| a task's outcome (`Outcome`: done, recovered, partial, failed, not_started, running, waiting, skipped; plan state `partial`, stop `partial`, `TaskCounts.partial`) | status: done, done after retrying, partly done, failed, not started, running, waiting, skipped; a partial task's reason after `Partly done:`; a trends column: Partly done | 状態: 完了, リトライ後に完了, 一部のみ完了, 失敗, 未実行, 実行中, 待機中, スキップ |
| stop (`completed`, `invalid_input`, `timeout`, ...) | outcome; each value in words (`stopLabel`) | 結果 |
| plan state `blocked` | not started | 未実行 |
| plan state `pending` after the run ended | not run | 実行されず |
| a deferred task (`PlanNode.deferred`, from `deferred.jsonl`), in a live run too | not run, with its cause in words (`deferredText`, from `deferred_cause`; the recorded reason only for a cause it does not know) | 実行されず |
| deferral causes `deadline`, `grace_window`, `cannot_finish`, `dependency_not_queued` | Past the deadline; Past the deadline and its finishing time; Cannot finish before the deadline \| needs `time` \| `time` left; An earlier task was never scheduled | 締め切りを過ぎた; 締め切りと仕上げの猶予を過ぎた; 締め切りまでに終わらない \| 必要な時間 \| 残り; 依存先タスクが登録されなかった |
| a credential's quota rest (`Rest`, `rests.jsonl`, deferral cause `rest`) | Identity `name` paused \| 5-hour usage 93% \| limit 90% \| until `time`; a pill: paused until `time`; over a run: Paused `time` → `time` | 認証情報 `name` は休止中; `time` まで休止; 休止 `time` → `time` |
| a quota cap (`max_five_hour_pct`, `max_seven_day_pct`) | limit 90%; Limits: weekly 95% \| 5-hour 90% | 上限 |
| the quota rule (`Pipeline(quota_rule=)`) and what it said | Usage rule; Usage rule: `text` | 利用率のルール |
| a skipped hop (`skipped_hops`), in a model switch | `model` (identity paused) → `model` | （認証情報が休止中） |
| attempt | attempt N | N 回目 |
| stop `error` | error | エラー |
| round after contract errors | correction | 修正依頼 |
| hop, failover | model switch | モデル切り替え |
| contract, off-contract, valid | checked file, failed checks, passed | 検証対象のファイル, 検証エラー, OK |
| wall, wall_s | time | 所要時間 |
| launch | agent session | エージェントのセッション |
| worker, max_concurrent | running at once | 同時実行 |
| journal (tab) | history | 実行履歴 |
| plan | scheduled tasks | 登録済みのタスク |
| stream (tab) | task detail | タスク詳細 |
| run not live | not running / finished | 実行中ではありません / 終了 |
| TaskAdapter (a kind without a plugin) | defined in Python code | Python コードで定義 |
| panel (`monitor.Panel`) | custom view | カスタムビュー |
| a panel body's charts (`columns`, `lines`, `heatmap`, `hbars`): the switch, the sum of a stacked bar, the series past the sixth, a chart's table column of labels, a heatmap's scale | Show table / Show chart; Total; Other; Label; `low` to `high` | 表で表示 / グラフで表示; 合計; その他; 項目; `low` 〜 `high` |
| a pipeline's own journal column (`row_extras`; `RunSummary.row_extras`, `TaskDetail.row_extras` name them) | a column headed by its name as written; tooltip: custom column (row_extras) | カスタム列 |
| `Plan.models` (`ModelUsage`: what the agent sessions spent on each model, each hop on its own; the measures cost, tokens, time, agent sessions) | Models; Share; Measure; Other models (past six); the measures in their own words (Cost, Tokens, Time, Agent sessions) | モデル別の内訳; 割合; 指標; その他のモデル |
| credential (`JournalRow.credential`, per hop) | identity | 認証情報 |
| the built-in credential `ambient` | default; tooltip: local credentials (ambient) | 既定 |
| a task with no unit (`unit` empty), as a row of units | No unit; tooltip: tasks that run once per run, not once per unit | ユニットなし |
| `claims` (names a task holds while it runs) | Locks (before the names; tooltip: Names this task holds while it runs (claims)) | ロック; tooltip: 実行中にこのタスクが占有する名前（claims） |
| `model` (the LLM a session ran on) | model (never "LLM") | モデル |
| `thinking` (the model's reasoning in a transcript) | reasoning | 思考 |
| upstream / downstream tasks | earlier tasks / later tasks | 依存先タスク / 後続タスク |
| the agent's own resend of an API request (`auto_retry_start`) | API request sent again | 再送 |
| `cost_usd` (reported by the coding agent) | cost | 料金 |
| `usage` (input, output, cache_read, cache_creation, calls) | tokens: input, output, cache read, cache write, API calls | トークン: 入力, 出力, キャッシュ読み込み, キャッシュ書き込み, API 呼び出し |
| `usage.resident` | input of the first API call (a tooltip on an attempt's tokens) | 最初の API 呼び出しの入力 |
| a light launch (`TaskDefinition.tools` `[]`) | Tools: none (a task definition's fact) | ツール: なし |
| `web_queries`; a web search tool card (`web_query`, the pages it returned) | web searches; query, results | Web 検索; 検索語, 検索結果 |
| a web fetch tool card (`web_fetch`) | page | ページ |
| `changes` (created, modified, deleted, removed) | changed files: created, modified, deleted; created, removed after the failed attempt | 変更したファイル: 作成, 変更, 削除, 作成、試行の失敗後に削除 |
| `output_from` `message` (an output taken from the agent's final message) | Output: `Verdict` \| from the final message | 最後のメッセージから |
| a stub run (`RunSummary.stub`), a mark beside the run's name | stub agent | スタブエージェント |
| a replay (`RunSummary.replay`), a mark beside the run's name; one that also launched (`stub` false, `record_missing`) | replay; replay and new sessions | リプレイ; リプレイと新しいセッション |
| a played attempt (`JournalRow.replayed`), marked only in a replay that also launched | replayed (an attempt's fact); a history filter: attempts replayed; tooltip: Played from a recording (replayed) | リプレイ; リプレイした試行 |
| an implementation kind's base kind (`TaskDefinition.base_kind`); a group named by a base kind shows its kinds | Implementation of (a task definition's fact); Implementation of `kind` (a list of kinds); Kinds (a group's) | 実装する種別; `kind` の実装; 種別 |
| an export (`Info.export`), the header's mark in place of the connection; a view it does not hold | Exported `time`; tooltip: Not in this export: transcripts and processes; not in this export | `time` 時点の書き出し; この書き出しに含まれないもの; 書き出しに含まれない |
| `unread_events` | unrecognized events | 未対応のイベント |
| `quota` (a subscription's utilization, account-wide) | 5-hour / weekly usage at the start of a session | 5 時間枠 / 週の利用率（セッション開始時点） |
| a reading's windows (`status_window`, `windows`: `five_hour`, `seven_day`, `seven_day_<model>`) | 5-hour, weekly, weekly (`model`); a status with its window: near the limit \| weekly | 5 時間枠, 週, 週（`model`） |
| `threshold_pct`, `overage_status` of a reading | Warning threshold; Extra usage: allowed / not allowed | 警告のしきい値; 上限を超えた利用: 可 / 不可 |
| account (`QuotaReading.account`, a digest), shown when one identity has two | account `3f9c2a`; Account: `digest` (tooltip) | アカウント |
| a layer of the flow path (the pipeline graph's level) | Pipeline › `function` › loop (breadcrumb) | パイプライン › `function` › ループ |
| a function node (tasks created in a function the flow called) | the function's name; function (tooltip) | 関数 |
| flow call | flow call (tooltip only) | フロー呼び出し |
| loop (a loop box) | loop | ループ |
| a loop's `pass` (`flow[].loops[].pass`) | pass N; up to N passes | N 周目; 最大 N 周 |
| the passes a unit ran of a loop (`LayerMark.passes`, `MatrixRow.passes`) | N passes (the number in a mark); number of passes (legend); Passes (column) | N 周; 周回数 |
| `LoopBox.spread` (units by the passes they ran) | 1 pass: 4 \| 2 passes: 1; tooltip: units by number of passes | 1 周: 4 \| 2 周: 1; ユニットごとの周回数 |
| `passMatrix` (a loop's passes: a row per unit, a column per node and pass) | Unit, Passes, Pass N (columns); sort units: scheduled order, number of passes, status | ユニット, 周回数, N 周目; 並び順: 登録順, 周回数, 状態 |
| a node above 200 marks (`asBar`) | a bar of its counts, its failed units by name, +N for the rest | 件数のバー, 失敗したユニット名, +N |
| the graph's key hints | Tab: next node \| Arrow keys: marks \| Shift + arrow keys: earlier and later tasks \| Enter: open \| Esc: up a level | Tab: 次のノード \| 矢印キー: マーク \| Shift + 矢印キー: 依存先タスク・後続タスク \| Enter: 開く \| Esc: 1 つ上の階層 |
| `after` (an edge) | waits for output | 出力を待つ |
| a time box (`time_box`, `FlowCallNode.time_box`): a flow call's own deadline | Deadline (a function node's and a flow call's row); deferred: Past the deadline of `function`; tooltip: A deadline of its own (time_box) | 締め切り; `function` の締め切りを過ぎた |
| `created_from` (an edge) | created after result | 結果を受けて作成 |
| a loop's return to its next pass (a dotted edge in its box) | next pass | 次の周 |
| a function node or a loop box (their layer, their passes) | has an inner view | 内部の表示あり |
| a function drawn open (`FlowBox`), its control; every function's | Show inside / Hide inside; Show all inside / Hide all inside | 中を表示 / 中を隠す; すべての中を表示 / すべての中を隠す |
| a chain of functions in one box (`FlowBox.parts`) | `a › b › c` (each part a link to its layer) | `a › b › c` |
| the outline (`outlineTree`); an item folded or unfolded | Outline of the flow; Fold `x` / Unfold `x` | フローの構成; `x` を折りたたむ / `x` を展開 |
| `executor` of a kind node | agent task / Python task | エージェントタスク / Python タスク |
| selection, inspector | selected item; links: Task detail, Tasks of `kind`, Inside `function`, Passes of the loop | 選択中の項目; タスク詳細, `kind` のタスク, `function` の内部, ループの各周 |
| an attempt of a later run start (`runStarts`) | attempt N \| resumed run | N 回目 \| 再開後 |
| an input file's origin | Output of `kind · unit`; File from before the run | `kind · unit` の出力; 実行前からあるファイル |
| host (`host_id`), shown only on a hub (`Info.hosts`) | host; `Host h1` as a fact; the hosts page: Hosts | ホスト; ホスト h1; ホスト一覧 |
| a host's `up` / not `up` (heartbeats stopped, or never sent) | up / no report; no report since `time` (a run picker's host header) | 稼働中 / 報告なし; `time` 以降報告なし |
| `HostSummary.last_seen`, `interval_s` | last report; report interval | 最終報告; 報告間隔 |
| `RunSummary.unresponsive`, `RunActivity` `unresponsive` (its host stopped reporting while the run was alive) | no report from host; N with no report from host (a count) | ホストからの報告なし; ホストからの報告なし N 件 |
| a run's `last_ts` while its host is not reporting | last activity | 最終更新 |
| a count of runs / hosts | 1 run, N runs / 1 host, N hosts | 実行 N 件 / ホスト N 台 |
| trends (`/api/trends`, `?page=trends`: what the runs of a period add up to) | Trends; Cost, tasks and models over the runs of a period (tooltip) | 推移 |
| a tab of the Trends page (`Panel.tab`, view route `trendsTab`) | the first: Summary; the others: the `tab` as written | 全体 |
| a trends period (`Period`: from, to, tz) | period; 7 days / 14 days / 30 days / Dates; `Oct 1 to Oct 14, 2026 \| Asia/Tokyo` | 期間; 7 日間 / 14 日間 / 30 日間 / 日付指定 |
| a task's `priority` (`PlanNode.priority`), only when not 0 | Priority 2; tooltip: Tie-breaker in the queue's order (priority) | 優先度 2 |
| peak context (`usage.peak_context`, `ModelUsage.peak_context`), `context_budget`, `context_warned` | Peak context: 142k \| 71% of the context limit 200k; near the context limit (91%) | 最大コンテキスト; コンテキストの上限; コンテキストの上限に接近（91%） |
| the preflight (`Plan.preflight`): its `dropped`, `substituted`, `kept`, `stopped` | Model availability: all models available; Unavailable; Model replaced: `kind` \| `a / m` → `a / m`; No available model; Ended before the first agent session | モデルの利用可否; すべてのモデルが利用可能; 利用不可; モデルの置き換え; 利用できるモデルなし; 最初のエージェントのセッションの前に終了 |
| a replay (`RunSummary.replay`), the mark beside the run's name in place of "stub agent" | replay; tooltip: Agent sessions played from the recordings in `dir` (replay) | リプレイ |
| a Python task's `retries`, `retry_on` | Retries: up to 2; Retried exceptions | リトライ: 最大 2 回; リトライ対象の例外 |
| `preserve` (a task definition's, an output contract's) | Must stay unchanged | 変更禁止の箇所 |
| `output_of` (a task definition's) | Output: `path` \| output of `kind` | `kind` の出力 |

The UI states facts about the run; it never narrates what the monitor or
contraagent does, will do, or lets the reader do. No "checked once", "the agent
is asked to fix it", "shown here while running", "you can see ... in ...",
"open X to ...", "this is to prevent ...". Show a state, a count, a cause or a
value instead: "Not started: input out/review/zeta.json is missing because
review · zeta did not finish", "No transcript", "2 corrections". How the system
works belongs in the documentation, not on the screen; a tooltip may define a
term in a short noun phrase or add a fact about this item, never a policy. A
button's name (verb and object, "Show source") and a key hint ("↑↓ Enter Esc")
name an action; they are not narration.

### Form

Many readers do not read English as a first language, and some read the
monitor through machine translation. Write global English, and keep one form
for each kind of text.

- **Case.** Sentence case for tabs, headings, column names, buttons, tile
  labels, empty-state titles and tooltips ("Scheduled tasks"). Values in chips
  and pills, and code, stay as they are ("done", `journal.jsonl`).
- **Task names and separators.** A task is named `kind · unit` everywhere
  (`kindUnit`), and `·` appears only inside a task's name. Facts in one row are
  separated by ` | ` ("Attempt 1 | done | 0.2s | $0.061"); a list of names is a
  row of chips (`taskChip`) or one name per line.
- **Punctuation.** At most one `:` in a string (a label and its value or
  cause); no em dash. `→` means "changed to" or "then" only (a model switch,
  first → last reading), never a link or a button.
- **Links and buttons.** A link names where it goes, as a noun ("Failed
  attempts in history", "All outputs"); a button names its action, verb and
  object ("Show source"). No arrows in either.
- **Status marks.** ✓ ✕ ◌ only, always next to a word, and hidden from screen
  readers; no meaning carried by a glyph or a color alone.
- **Empty and unknown.** An empty value is "none"; an unknown number is "—";
  an empty list is "No <things>", with a known reason after ` | `.
- **Numbers and time.** The number first in text ("3 web searches");
  "characters", not "chars"; one duration format ("<0.1s", "4.2s", "2m 05s",
  "1h 02m"); dates that read the same in every locale; absolute times in rows
  and chips.
- **Causes.** Name the cause the data has ("input out/review/zeta.json is
  missing", "... failed checks"); never "X or Y" when the data knows which.
- **Global English.** Common words; no idioms, phrasal verbs or slang; no
  abbreviations but API, JSON, CLI, USD and units (B, k, M). Labels may be noun
  phrases; a string that states a cause or a relation keeps its verbs and
  articles. Positive forms ("All attempts passed"). The text must keep its
  meaning through machine translation.

## Kept on purpose

| Name | Why it stays |
|---|---|
| `--agent` | Claude Code's own flag; the Claude backend maps `Launch.role` to `--agent <role>` |
| `plugin render --agent claude\|omp` | there "agent" is the coding agent, as everywhere |
| `Backend`, `create_backend`, `register_backend`, `known_agents` | the adapter for a coding agent and its registry, keyed by agent name |
| `[tasks.<kind>]`, `kind` | the config's table name and the task class; unambiguous |
| `Launch`, `TaskResult`, `RunReport`, `Pending`, `WorkQueue`, `CursorStore`, `TaskAdapter` | already one meaning each |
| `Route`, `Router`, hop | the failover chain (a route is one entry of it; a hop is one launch on one route) |
| `ambient` | the built-in credential: the host's own setup |
| `effort`, `max_turns`, `max_budget_usd` | the coding agents' own flag names |
| cursor `stage` | a run phase |
| `streams/`, `*.stream.jsonl` | the on-disk layout |
| `hollow` | defined in the `LaunchResult` docstring |
| `RoutingPlan` | routing; `plan.jsonl` is the queue |

## Public modules and layers

The implementation is under `src/contraagent/_internal/`. A user imports only the
public modules: `contraagent`, `contraagent.config`, `contraagent.backends`,
`contraagent.engine`, `contraagent.plugins`, `contraagent.monitor`,
`contraagent.monitor.api` and `contraagent.testing`. A public module holds no
definitions: it imports names from `_internal`, lists them in `__all__` and calls
`publish(__name__, __all__)` (`_internal/public.py`), which makes it each name's
`__module__`. Public modules import only from `_internal`; nothing in `_internal`
imports a public module. Each object has one public path. A name a user, the
documentation or an example uses gets a public home; every contraagent type a public
signature, field or callback argument reaches is exported too; the rest stays in
`_internal`. A signature reaches a type only when its user needs it: a helper hides
behind a method (`Backend.mark_launch`), a value returns the type it behaves as
(`agent_task(implementations=)` a `Mapping`, `time_box` a generator). The type of a
function a user writes or passes (a rule, a scope, a validator, a panel, a callback) is a
`Protocol` with a docstring stating the call and `__call__` its signature (positional-only
parameters, so any function of that shape fits), never a `Callable` alias; it is exported
where the user meets it. A named alias a signature reaches (a union) is exported like a
class; an alias of literal values is not (its annotation lists them, and the
documentation names the field, not the alias). A public signature names every argument
it takes, typed and documented: no `**kwargs` passed through to another function (the
`**` a test allows: a task's own parameters, a flow's arguments, a record's fields); an
argument set that mirrors another (`agent_task`'s task table keys, `Pipeline`'s
`WorkQueue` arguments) has a test that holds the two equal. No public docstring names
`contraagent._internal`: it names the public object. `contraagent.monitor.api` holds the
schemas of the monitor's OpenAPI document that have no other public home, its
`API_VERSION` and the union of transcript events (`AnyTranscriptEvent`), and nothing
else. The examples in `docs/examples/` import only public modules; nothing outside the
package imports `_internal` but the tests. The public modules import without the
`monitor` and `hub` extras. `tests/test_public_api.py` checks the public modules and what
they export.

`tests/api/contraagent.api.txt` is the public API as griffe reads it: every name in
a public module's `__all__`, with its signature, fields and defaults. A change to the
public API shows in its diff; `uv run python tests/api/snapshot.py` rewrites it, and
a test fails while it is stale. Every public symbol has a declared, known type
(`pyright --verifytypes`, below): give a public parameter, return, field and attribute
an annotation, and a `dict`, `list` or generic class its type arguments.

A deprecated name (from 1.0, see Compatibility below) stays readable in its public
module: the module sets
`__getattr__ = migration(__name__, moved={"Old": "contraagent.engine:New"}, removed={"gone": "use ... instead"})`
(`_internal/public.py`), and reading it warns `ContraagentDeprecationWarning` or says
what to use. The tests turn that warning into an error, so contraagent itself never
uses a deprecated name.

Inside `_internal`, each layer imports only the layers above it in the list in the
`src/contraagent/_internal/__init__.py` docstring (`errors`, `platform`,
`commandline`, `public`, `docs`, `runs`, `dispatch`, `backends`, `contracts`,
`routing`, `execution`, `plugins`, `pipeline`, `monitor`, `hub`, `testing`, `cli`).
`platform/` (`procfs`, `envvars`, `telemetry`: the host and the names of a live agent
process) and `commandline` are leaf modules, importing nothing else of the package.
`runs/` (the run records layer: layout, files, times, `RunSource`, `Liveness`)
imports only the standard library and `platform/`; every reader and writer of a run's
files goes through it.
`dispatch/` imports nothing but the standard library, pydantic and `runs/` (its record
types, `dispatch/records.py`, are what every later layer writes and reads).
`hub/` does not import `monitor/`, but for `hub/server.py`, which serves the monitor's
app. Never import a later layer from an earlier one; pass a callback or a protocol
instead.

`uv run lint-imports` checks these import rules: one contract each in pyproject.toml's
`[tool.importlinter]`, an exception only as a commented `ignore_imports` line.
"The examples import no `_internal`" is the `protected` contract: the examples are
modules of `contraagent.docs`, and only `_internal` and the public modules may import
`_internal`. The tests are not in the graph. `tests/test_layers.py` runs it, so
`uv run pytest` fails on a broken contract.

The web UI in `web/` has the same rule: `@contraagent/api` (types, client,
feeds, store; no UI) and `@contraagent/elements` (generic elements and their
parts: tokens, themes, primitives; no contraagent data) come before
`@contraagent/ui` (the contraagent elements), which comes before `apps/monitor`
(the page). `api` and `elements` never import each other. Within `ui`, an
element renders what its properties give it and sends `ca-*` events
(`core/events.ts`); only `ca-monitor` holds the store and the view router. No
module changes the page at import: the languages (`configureLocales()`) and the
themes (`adoptThemes()`) are set up by the page or by `ca-monitor` when it
connects. A `cae-*`
element of `elements` takes plain data and its words (`strings`), and sends
`cae-*` events (`core/events.ts` there).

| Where | Imports only |
|---|---|
| `@contraagent/api` | its own files; no `lit`, `@lit/*` or other `@contraagent/*` |
| `@contraagent/elements` | its own files and `lit`; no `@contraagent/*`, no `@lit/localize`, no `msg()`, and no glossary word in an exported name or in a `types.ts` property |
| `elements`: its folders, in order: `core/`; `themes/`; `styles/`; `primitives/`; the components (`table/`, `matrix/`, `json/`, `markdown/`, `count/`, ...); `graph/` (it shows a mark matrix); `define/` | the folders before it and its own; a component imports another only from an earlier rank, and only `define/` registers a tag |
| `ui`: `core/` (view route, view router, events, i18n, memory, scroll) | `@contraagent/api`, `@contraagent/elements`, `lit`, `@lit/localize` and each other; never `words/`, `lib/`, `adapters/`, `controllers/` or `elements/` |
| `ui`: `words/` (the words the UI shows), `lib/` | the above and each other; never `adapters/`, `controllers/` or `elements/` |
| `ui`: `adapters/` (run data → what a generic element takes: a table's columns, the lists' filters) | the above and each other; never `controllers/` or `elements/` |
| `ui`: `controllers/` (Lit reactive controllers: a task's detail, the theme, the language, the shortcuts) | the above and each other; never `elements/` |
| `ui`: `elements/<folder>/` | the above, its own folder and `elements/shared/`; another folder only by a bare `import '../x/ca-y.js'`, which registers a tag it renders |
| `ui`: `define/` (one entry per subpath of a view, `define/all.ts` for `index.ts`) | the above; only `index.ts` imports it |
| `apps/*` | the packages, through the subpaths in their `exports` |

`eslint.config.js` (`no-restricted-imports`, generated from one table) and
`packages/ui/src/layers.test.ts` check this table; the test also checks that a
package imports another workspace package only when it depends on it.
`packages/ui/src/fires.test.ts` checks that each element's `@fires` tags name
exactly the events it sends, and that every event is in `CaEventMap` (`ca-*`)
or `CaeEventMap` (`cae-*`).

Every visible string in an element is wrapped in `msg()` (`@lit/localize`) and
every element class is `@localized()`. Translations live in
`web/packages/ui/xliff/<locale>.xlf`; Japanese follows the terms in
`xliff/GLOSSARY.md`, the same one-word-one-meaning rule as the glossary.
`pnpm check` fails while a message has no translation.

## Checks

```
uv run ruff check .
uv run ruff format --check .
uv run pyright          # 0 errors; the "yaml" source warning is expected
uv run lint-imports     # the import contracts (pyproject.toml); tests/test_layers.py runs it too
uv run pytest           # live tests: CONTRAAGENT_LIVE=1 uv run pytest -m live (spend tokens)
uv run pytest -m e2e    # the hub and relays as processes over Postgres and RustFS (docker)
docker build -t contraagent-hub:dev .   # the hub's image from these sources and uv.lock
uv run pyright --verifytypes contraagent --ignoreexternal
uv run griffe check --search src contraagent --against <last tag>
```

`--verifytypes` lists every public symbol whose type is unknown or only inferred; it
must list none outside `contraagent.docs` (`tests/test_public_api.py` checks this).
Its score stays below 100% only because the examples under `contraagent.docs.examples`
are installed with the package and counted as public; they are documentation, written
without the annotations an API carries. `griffe check` lists the changes since a
release that break a caller (a removed name, a new required parameter, a changed
default); from 0.1.0 such a change waits for the release Compatibility below allows.
Releases are tagged `<version>` (`0.1.0` is the first).

pytest runs in parallel (pytest-xdist, at most 6 processes; `-n0` runs it in one).
Tests that share something across a module (one hub, the `live-demo` directory, an agent's
rate limits) carry an `xdist_group` so one worker runs them in order; the live and perf
tests get theirs in `tests/conftest.py`. A test does not wait out a retry's backoff
(`RetryingRunner.backoff` is 0 there; `backoff_s` has its own test).

After an omp upgrade, record its wire (`uv run python tests/fixtures/omp/record.py`,
spends a few cents) and run `tests/test_omp_wire.py`: an event `TraceReader` does
not know fails it.

After changing a monitor response model or route, regenerate the committed
contract: `uv run contraagent monitor --openapi src/contraagent/_internal/monitor/openapi.json`
(a test fails while it is stale), then the TypeScript types: `pnpm gen` in `web/`.

After changing a command's arguments or help, rewrite every command's `--help`:
`uv run python tests/cli/help.py` writes `tests/cli/help.txt` (a test fails while it is
stale; argparse's output depends on the Python version, so it compares on the version
the file names, the one in `.python-version`).

After changing a model of a run record (`_internal/execution/schemas.py`, the records
in `_internal/dispatch/records.py` they hold) or the config file's tables, regenerate
the JSON Schemas in `src/contraagent/docs/schemas/`:
`uv run python -m contraagent._internal.execution.file_schemas` (a test fails while
one is stale).

The web UI (Node 22, pnpm via `corepack enable`; pnpm installs only versions
published at least 14 days ago), in `web/`:

```
pnpm install
pnpm check              # generated types current, tsc, eslint, vitest (every package)
pnpm build              # rebuilds src/contraagent/_internal/monitor/static (committed; CI fails if stale), and the site
pnpm check:dist         # the built packages type-check as an npm consumer sees them, stay within the gzip budgets in size-budgets.json, and web/consumer builds one component alone (consumer/consumer.test.mjs)
pnpm tarballs           # builds the three packages into tarballs/*.tgz that npm and pnpm install from this checkout
pnpm dev                # live-reload UI against a monitor on :8787
pnpm e2e                # build, then Playwright against the real monitor over the demo runs
pnpm docs               # the documentation site, live reload
pnpm i18n               # extract msg() strings to packages/ui/xliff, rebuild src/locales
```

## Documentation

Each package holds its own documentation, installed with it and matching its
version; nothing else holds that text.

| Package | Index | Topics | Examples |
|---|---|---|---|
| `contraagent` | `src/contraagent/docs/README.md` (also the PyPI page) | `src/contraagent/docs/*.md` | `src/contraagent/docs/examples/` |
| `@contraagent/ui` | `web/packages/ui/README.md` | `web/packages/ui/docs/*.md` | `web/packages/ui/docs/examples/` |
| `@contraagent/elements` | `web/packages/elements/README.md` | `web/packages/elements/docs/*.md` | `web/packages/elements/docs/examples/` |
| `@contraagent/api` | `web/packages/api/README.md` | — | — |

- **An index lists its topics** (`- [Title](file.md): summary`). That list is
  the order of the site's sidebar and what `contraagent docs` prints. A new
  topic is a file plus a line in its index.
- **Code is quoted, never pasted**: a line `::code{file="..." from="..." to="..."}`
  quotes a file of the same package. The examples run or compile in the tests
  (`tests/test_docs.py`; `docs/tsconfig.json` and `examples.test.ts` in each
  web package), so update them with any API change.
- **Facts live in the code**: signatures and arguments in docstrings, options in
  `--help`, config keys in `examples/reference/pipeline.toml`, elements in
  `custom-elements.json` (describe an element's events with `@fires` in its
  JSDoc), the HTTP API in `openapi.json`. Prose points to them.
- **The site** (`web/apps/docs`, Astro Starlight) renders the packages'
  documentation: `scripts/collect.py` writes it into `src/content/docs/python/`
  and `node/` (not committed) and fails on a quote or a link that does not
  resolve. The site itself holds only its landing page, the live examples and the
  references generated from `openapi.json`, `custom-elements.json` and the
  elements' stylesheet. The live examples read `src/fixtures/demo-run.json`;
  rewrite it with `uv run python web/apps/docs/scripts/fixture.py` after a change
  to what the monitor returns.
- The root `README.md` points to the packages and holds no documentation of its own.
- `CHANGELOG.md`: record user-visible changes under `[Unreleased]`.

## Compatibility

The public API is what `src/contraagent/docs/compatibility.md` lists: the
public modules' `__all__`, the command line, the config file, the files a run
writes and the monitor's `openapi.json`. `contraagent._internal` is not public:
change it freely, with no aliases or shims inside it.

- **Until 0.1.0 is tagged**: rename the public API freely too, with no
  compatibility aliases, no deprecation shims and no readers for old run
  directories; `CHANGELOG.md` records each rename as old → new.
- **From 0.1.0**: a change to the public API is deliberate. The checks (the
  API snapshot, the `--help` snapshot, `openapi.json`, the file schemas) show
  it, `CHANGELOG.md` records it, and it waits for a minor release (from 1.0, a
  major one, after `ContraagentDeprecationWarning` for two minor releases).
  A record change that a reader of the current run format cannot read raises
  `FORMAT` in `_internal/runs/layout.py` and adds the new format's fixture
  beside `tests/fixtures/runs/v1/`; the monitor keeps reading every run format
  in `FORMATS`.
