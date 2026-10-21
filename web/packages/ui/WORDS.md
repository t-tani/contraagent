# Words the UI shows

The monitor's UI is read by engineers who use coding agents but do not know
contraagent's code, so it shows run data in their terms. The glossary's terms
(`src/contraagent/docs/concepts.md`) stay in the API, the files, and the UI's
tooltips as the secondary detail; the visible words come from `src/words/`.
One word, one meaning holds here too: each row below is the one way every
screen names that thing. A new visible term gets a row here first; its
Japanese form follows `xliff/GLOSSARY.md`, and the rules for how a string is
written are in `web/AGENTS.md`.

| Code term | UI (English) | UI (Japanese) |
|---|---|---|
| a task's outcome (`Outcome`: done, recovered, partial, failed, not_started, running, waiting, skipped; plan state `partial`, stop `partial`, `TaskCounts.partial`) | status: done, done after retrying, partly done, failed, not started, running, waiting, skipped; a partial task's reason after `Partly done:` (an agent task's, the stop its launch ended on, in words: `Partly done: timed out`); trends columns: Done, Tasks done, Partly done; Done 97%; Attempts not done | 状態: 完了, リトライ後に完了, 一部のみ完了, 失敗, 未実行, 実行中, 待機中, スキップ |
| stop (`completed`, `invalid_input`, `timeout`, ...) | outcome; each value in words (`stopLabel`) | 結果 |
| a cancelled task (stop `cancelled`, plan state `cancelled`, `TaskCounts.cancelled`, `PlanGroup.cancelled`: called with `.options(cancellable=True)`, and no flow call waited for it any longer) | cancelled; N cancelled (finished, never a failure: in every count of tasks, never among failed attempts) | 取り消し; 取り消し N 件 |
| where a flow call stopped (`FlowCallNode.raised_at`, `raised_by`) | on the failed task: This failure stopped `function` at `file:line`; on the flow call: Stopped at `file:line` by the failure of `kind · unit`; a row: Stopped | この失敗で `function` が `file:line` で停止; `kind · unit` の失敗により `file:line` で停止; 停止 |
| unawaited tasks (`FlowCallNode.unawaited` of a top flow call) | N tasks not awaited, with their chips; tooltip names the field | 待たれなかったタスク N 件 |
| a rerun (`JournalRow.rerun`) and the parts of the fingerprint that changed (`fingerprint_parts`: `definition`, `params`, `outside`, `output_of`, `input_files`); a divergence (`divergence: ...`) | Ran again after a resume \| Changed: params; definition, params, outside state, the file it fills in, input files; divergence (a pill, and a fact of the attempt) | 再開後に再実行 \| 変更: パラメータ; 定義, パラメータ, 外部の状態, 書き足す対象のファイル, 入力ファイル; 分岐 |
| the forecast (`Forecast`: tasks expected from the run of the same flow that finished last before this one) | Forecast: N more tasks \| `time` of task time \| `$`; Not in the plan yet: `group +n`; a kind node: +N (a dotted outline), N more tasks expected (forecast) | 見込み: あと N タスク; タスクの所要時間; まだ登録されていない種別; あと N 件の見込み（forecast） |
| plan state `blocked` | not started | 未実行 |
| plan state `pending` after the run ended | not run | 実行されず |
| a deferred task (`PlanNode.deferred`, from `deferred.jsonl`), in a live run too | not run, with its cause in words (`deferredText`, from `deferred_cause`; the recorded reason only for a cause it does not know) | 実行されず |
| deferral causes `deadline`, `grace_window`, `cannot_finish`, `dependency_not_queued`, `dependency_deferred` | Past the deadline; Past the deadline and its finishing time; Cannot finish before the deadline \| needs `time` \| `time` left; An earlier task was never scheduled; An earlier task was not run | 締め切りを過ぎた; 締め切りと仕上げの猶予を過ぎた; 締め切りまでに終わらない \| 必要な時間 \| 残り; 依存先タスクが登録されなかった; 依存先タスクが実行されなかった |
| a credential's quota rest (`Rest`, `rests.jsonl`, deferral cause `rest`) | Identity `name` paused \| 5-hour usage 93% \| limit 90% \| until `time`; a pill: paused until `time`; over a run: Paused `time` → `time` | 認証情報 `name` は休止中; `time` まで休止; 休止 `time` → `time` |
| a quota cap (`max_five_hour_pct`, `max_seven_day_pct`) | limit 90%; Limits: weekly 95% \| 5-hour 90% | 上限 |
| the quota rule (`Pipeline(quota_rule=)`) and what it said | Usage rule; Usage rule: `text` | 利用率のルール |
| a credential refused on one model (`Rest.stop` `auth_failed`, `rests.jsonl`) | Identity `name` paused \| Authentication failed \| `model`; a pill: paused | 認証情報 `name` は休止中 \| 認証エラー \| `model` |
| a skipped hop (`skipped_hops`), in a model switch | `model` (identity paused) → `model` | （認証情報が休止中） |
| attempt | attempt N | N 回目 |
| a retry (an attempt after a failed attempt of the same task) | retry; tooltip: An attempt after a failed attempt (retries) | リトライ |
| stop `error` | error | エラー |
| stop `denied` (a tool call the permissions did not allow) | permission denied; trends: Denied tool calls (never "refused") | 権限エラー; 権限エラーになったツール呼び出し |
| a safety stop (`JournalRow.safety_stops`, `Trends.safety_stops`: a safety classifier stopped part of an agent session, which went on; not stop `refused`) and its part (`response`, `tool`, `unread`) | N safety stops (an attempt's mark; the attempt keeps its outcome); a line per stop: part \| model \| category \| tool \| time; parts: model response, tool request, unrecognized; trends: Safety stops, Stopped part; tooltip: A safety classifier stopped part of the agent session, and the session went on (safety_stops) | 安全分類器による停止 N 件; モデルの応答, ツールのリクエスト, 内容不明; 停止した部分 |
| correction (an output's failed checks sent back to the agent session: an objection of the stop hook within a round, `hook_errors`, or a correction round; what `max_corrections` bounds) | N corrections, Done after N corrections, attempts with corrections; tile: Corrections; tooltip: Failed checks sent back to the same agent session, within its round or in a correction round (hook_errors, rounds) | 修正依頼 N 回 |
| correction round (a round after the first, `rounds`) | Correction round N (a transcript's round); after N correction rounds (a checked file); tooltip: Another round in the same agent session after failed checks (rounds) | 修正ラウンド N |
| hop, failover | model switch; tooltip: A new agent session on the next model after a failed one (Router hops) | モデル切り替え |
| contract, off-contract, valid | checked file, failed checks, passed (a checked file only; attempts and tasks are done) | 検証対象のファイル, 検証エラー, OK |
| rows (`ContractSpec.format` `jsonl`: a JSON Lines output, `schema_name` `Rows[Row]`) | JSON Lines, one object of schema `Row` per line; N rows (the lines that parse) | JSON Lines（1 行ごとに JSON オブジェクト、スキーマ `Row`）; N 行 |
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
| a service (`Plan.services`, `ServiceSpan`, `services.jsonl`) and its state | Services (tooltip: A long-lived helper that the tasks holding one lock share (services.jsonl)); running, stopped, did not start, stop not recorded; Started `time` in `duration` \| Stopped `time` \| The run ended, The run was stopped by a signal \| Stop failed | サービス; 稼働中, 停止, 開始できず, 停止の記録なし; `time` に開始（`duration`） \| `time` に停止 \| 実行が終了した, 実行がシグナルで停止された \| 停止でエラー |
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
| `changes` (created, modified, deleted, removed, kept) | changed files: created, modified, deleted; created, removed after the failed attempt; created, kept after the failed attempt | 変更したファイル: 作成, 変更, 削除, 作成、試行の失敗後に削除, 作成、試行の失敗後も保持 |
| `output_from` `message` (an output taken from the agent's final message) | Output: `Verdict` \| from the final message | 最後のメッセージから |
| a stub run (`RunSummary.stub`), a mark beside the run's name | stub agent | スタブエージェント |
| a replay (`RunSummary.replay`), a mark beside the run's name; one that also launched (`stub` false, `record_missing`) | replay; replay and new sessions | リプレイ; リプレイと新しいセッション |
| a played attempt (`JournalRow.replayed`), marked only in a replay that also launched | replayed (an attempt's fact); a history filter: attempts replayed; tooltip: Played from a recording (replayed) | リプレイ; リプレイした試行 |
| an implementation kind's base kind (`TaskDefinition.base_kind`); a group named by a base kind shows its kinds | Implementation of (a task definition's fact); Implementation of `kind` (a list of kinds); Kinds (a group's) | 実装する種別; `kind` の実装; 種別 |
| an export (`Info.export`), the header's mark in place of the connection; a view it does not hold | Exported `time`; tooltip: Not in this export: transcripts and processes; not in this export | `time` 時点の書き出し; この書き出しに含まれないもの; 書き出しに含まれない |
| `unread_events` | unrecognized events | 未対応のイベント |
| `usage_unknown` (`calls`, `tokens`), a mark on an attempt | Tokens per API call unknown; Tokens unknown | API 呼び出しごとのトークンは不明; トークンは不明 |
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
| the lineage of a task to an earlier one (`Lineage`; an edge of the pipeline graph, a tag of an earlier or a later task): `given_from` (solid), `after` alone (dotted, order only), `created_from` (dashed) | given output; runs after; created after result; a node's rows: Given output of, Runs after, Created after; tooltips name the field | 出力を受け取る; 完了を待つ; 結果を受けて作成; 入力元, 順序のみの依存先, 作成元 |
| a time box (`time_box`, `FlowCallNode.time_box`): a flow call's own deadline | Deadline (a function node's and a flow call's row); deferred: Past the deadline of `function`; tooltip: A deadline of its own (time_box) | 締め切り; `function` の締め切りを過ぎた |
| a loop's return to its next pass (a dotted edge in its box) | next pass | 次の周 |
| a function node or a loop box (their layer, their passes) | has a level below | 下の階層あり |
| a function drawn open (`FlowBox`), its control; every function's | Show inside / Hide inside; Show all inside / Hide all inside | 中を表示 / 中を隠す; すべての中を表示 / すべての中を隠す |
| a chain of functions in one box (`FlowBox.parts`) | `a › b › c` (each part a link to its layer) | `a › b › c` |
| the outline (`outlineTree`); an item folded or unfolded | Outline of the flow; Fold `x` / Unfold `x` | フローの構成; `x` を折りたたむ / `x` を展開 |
| `executor` of a kind node | agent task / Python task | エージェントタスク / Python タスク |
| selection, inspector | selected item; links: Task detail, Tasks of `kind`, Inside `function`, Passes of the loop | 選択中の項目; タスク詳細, `kind` のタスク, `function` の内部, ループの各周 |
| an attempt of a later run start (`runStarts`) | attempt N \| resumed run | N 回目 \| 再開後 |
| an input file (`TaskIO.input_files`: an `InputFile` param, by its path and hash) and its check as the task was about to start (`passed`, `refused`, `not_checked`) | Input files; Param `name` \| sha256 `12 digits` \| Output of `kind · unit`; same content at the start, changed before the start, not checked | 入力ファイル; パラメータ `name`; 開始時も同じ内容, 開始前に変更された, 未確認 |
| a file an input contract checks (`TaskIO.inputs`, `InputContract`, from an engine `TaskAdapter`) and its origin | Checked files it reads; Output of `kind · unit`; File from before the run | 読み込むファイル（検証あり）; `kind · unit` の出力; 実行前からあるファイル |
| host (`host_id`), shown only on a hub (`Info.hosts`) | host; `Host h1` as a fact; the hosts page: Hosts | ホスト; ホスト h1; ホスト一覧 |
| a host's `up` / not `up` (heartbeats stopped, or never sent) | up / no report; no report since `time` (a run picker's host header) | 稼働中 / 報告なし; `time` 以降報告なし |
| `HostSummary.last_seen`, `interval_s` | last report; report interval | 最終報告; 報告間隔 |
| `RunSummary.unresponsive`, `RunActivity` `unresponsive` (its host stopped reporting while the run was alive) | no report from host; N with no report from host (a count) | ホストからの報告なし; ホストからの報告なし N 件 |
| a run's `last_ts` while its host is not reporting | last activity | 最終更新 |
| a count of runs / hosts | 1 run, N runs / 1 host, N hosts | 実行 N 件 / ホスト N 台 |
| trends (`/api/trends`, `?page=trends`: what the runs of a period add up to) | Trends; Totals of the runs in a period (tooltip) | 推移 |
| a tab of the Trends page (`Panel.tab`, view route `trendsTab`) | the first: Summary; the others: the `tab` as written | 全体 |
| a trends period (`Period`: from, to, tz) | period; 7 days / 14 days / 30 days / Dates; `Oct 1 to Oct 14, 2026 \| Asia/Tokyo` | 期間; 7 日間 / 14 日間 / 30 日間 / 日付指定 |
| a task's `priority` (`PlanNode.priority`), only when not 0 | Priority 2; tooltip: Tie-breaker in the queue's order (priority) | 優先度 2 |
| a task's own working directory (`PlanNode.cwd`, the `cwd` of its call options), only when it has one | Working directory `path`; tooltip: Directory the task worked in, named by its task call in place of the run's (cwd) | 作業ディレクトリ `path` |
| peak context (`usage.peak_context`, `ModelUsage.peak_context`), `context_budget`, `context_warned` | Peak context: 142k \| 71% of the context limit 200k; near the context limit (91%) | 最大コンテキスト; コンテキストの上限; コンテキストの上限に接近（91%） |
| the preflight (`Plan.preflight`): its `dropped`, `substituted`, `kept`, `stopped` | Model availability: all models available; Unavailable; Model replaced: `kind` \| `a / m` → `a / m`; No available model; Ended before the first agent session | モデルの利用可否; すべてのモデルが利用可能; 利用不可; モデルの置き換え; 利用できるモデルなし; 最初のエージェントのセッションの前に終了 |
| a replay (`RunSummary.replay`), the mark beside the run's name in place of "stub agent" | replay; tooltip: Agent sessions played from the recordings in `dir` (replay) | リプレイ |
| a Python task's `retries`, `retry_on` | Retries: up to 2; Retried exceptions | リトライ: 最大 2 回; リトライ対象の例外 |
| `preserve` (a task definition's, an output contract's) | Must stay unchanged | 変更禁止の箇所 |
| `output_of` (a task definition's) | Output: `path` \| output of `kind` | `kind` の出力 |
