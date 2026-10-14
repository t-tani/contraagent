# Japanese terms

One word, one meaning, as in AGENTS.md: each term below is translated the same
way everywhere. Identifiers stay as they are: code names (`OutputContract`,
`max_concurrent`, `Task.kind`), file names, and data the run wrote (kind and
unit names, stop values such as `completed`, model and role names).

| English | 日本語 |
|---|---|
| coding agent | コーディングエージェント |
| model (the LLM a session ran on; the UI never says "LLM") | モデル（「LLM」は使わない） |
| role | ロール |
| agent task / Python task | エージェントタスク / Python タスク |
| task | タスク |
| kind | 種別 |
| unit | ユニット |
| key | キー |
| params | パラメータ |
| run / run group | 実行 / 実行グループ (a run that is not live: 停止中) |
| running (a task, a run) | 実行中 |
| launch | 起動 |
| round | ラウンド |
| attempt | 試行 |
| retry | リトライ |
| hop / failover | ホップ / フェイルオーバー |
| journal | ジャーナル |
| plan | プラン |
| transcript | トランスクリプト |
| contract | コントラクト (input/output contract: 入力コントラクト / 出力コントラクト) |
| schema | スキーマ |
| validator | バリデータ |
| output / input | 出力 / 入力 |
| definition | 定義 |
| plugin | プラグイン |
| panel | カスタムビュー (see below) |
| process | プロセス |
| resume cursor | 再開カーソル |
| stage | ステージ |
| tool call | ツール呼び出し |
| prompt | プロンプト |
| live | ライブ |
| validate, validation | 検証 (not 検査) |
| optional / required (a field) | 任意 / 必須 |
| sent back with the errors | エラーを返してやり直させる |
| return annotation | 戻り値の型ヒント |
| finished (a task, a run) | 終了した (not 終わった); completed: 完了 |
| earlier tasks / later tasks (the tasks it waits for / that wait for it) | 依存先タスク / 後続タスク |
| valid / off-contract (a contract's status) | OK / 検証エラー |
| rendered / source (a markdown view) | プレビュー / ソース |
| wall time | 所要時間 |
| snapshot | スナップショット |
| stub agent (a coding agent with scripted replies instead of a model; a stub run's mark) | スタブエージェント |
| hover | ホバー |
| instructions (an agent task with no plugin) | 指示 |
| final message (the agent's last message of a session; an output taken from it) | 最後のメッセージ |
| worker (a WorkQueue place for one concurrent task) | 枠 (idle worker: 空き) |
| launch time (summed wall time of launches; the tile "Agent session time") | エージェントの所要時間 |
| last (time of the last attempt) | 最終試行 |
| items (length of a list) | 要素 N 個 |
| paused (an identity past its usage limit or rule: a quota rest) | 休止中; paused until 14:30: 14:30 まで休止 |
| limit (a quota cap) | 上限 |
| usage rule (the quota rule) | 利用率のルール |
| deadline / finishing time (the grace window after it) | 締め切り / 仕上げの猶予 |

Tabs: overview 概要, tasks タスク, journal 実行履歴, outputs 出力, definitions
定義, processes プロセス, stream タスク詳細. The tab list as a whole (its
label for a screen reader, "Views"): ビュー.

## Words the UI shows for run data

The UI names run data in the reader's terms (AGENTS.md, "Words the UI shows");
these are their Japanese forms. They take precedence over the code terms above
wherever the UI shows a state or a count to the reader.

| English (UI) | 日本語 |
|---|---|
| done / done after retrying | 完了 / リトライ後に完了 |
| failed / not started | 失敗 / 未実行（文の中では「実行されていません」「実行されなかった」） |
| waiting / running / skipped | 待機中 / 実行中 / スキップ |
| status (a task's outcome: done, failed, not started, ...) | 状態 |
| outcome (how one attempt ended) | 結果 |
| attempt N | N 回目 (not 「N 回目の試行」) |
| error (stop `error`: the process failed without a result) | エラー |
| correction (the agent asked to fix its output in the same session) | 修正依頼（「差し戻し」は使わない） |
| model switch (to the next failover hop, after a failure) | モデル切り替え |
| checked file / failed checks / passed | 検証対象のファイル / 検証エラー / OK |
| time | 所要時間 |
| agent session | エージェントのセッション |
| running at once | 同時実行 |
| history (the journal tab) | 実行履歴 |
| task detail (the stream tab) | タスク詳細 |
| scheduled tasks | 登録済みのタスク |
| not running / finished | 実行中ではありません / 終了 |
| finished with errors (a run with failed or not-started tasks) | エラーで終了 |
| defined in Python code | Python コードで定義 |
| custom view (a `monitor.Panel`: an extra view the pipeline's code adds) | カスタムビュー |
| custom column (`row_extras`: a journal column the pipeline's code adds; its name is the pipeline's, shown as written) | カスタム列 |
| identity (the credential an attempt authenticated as) | 認証情報 |
| default (the built-in credential `ambient`: local credentials) | 既定 |
| No unit (a row for tasks that run once per run, not once per unit) | ユニットなし |
| Also locks (a task's extra units: units it locks while it runs, besides its own) | 併せてロックするユニット |
| reasoning (the model's thinking in a transcript) | 思考 |
| cost (USD, as the coding agent reports it) | 料金 |
| tokens / input / output / cache read / cache write / API calls | トークン / 入力 / 出力 / キャッシュ読み込み / キャッシュ書き込み / API 呼び出し |
| web searches (the queries of the coding agent's web search tool) | Web 検索 |
| query (what a web search searched for) | 検索語 |
| results (the pages a web search returned; not a task's outcome) | 検索結果 |
| changed files (`changes`: what an attempt did under the task's patterns) | 変更したファイル |
| created / modified / deleted (a changed file) | 作成 / 変更 / 削除 |
| page (the web page a web fetch read) | ページ |
| unrecognized events (`unread_events`: event types from a coding agent that this contraagent does not recognize) | 未対応のイベント |
| 5-hour / weekly usage (a subscription's utilization) | 5 時間枠 / 週の利用率 |
| a value the coding agent reported / read later | 報告した値 / 値（「報告値」「観測値」は使わない） |
| API request sent again (the agent's own resend after an API error) | 再送（「リトライ」は新しいセッションでの再試行だけ） |
| aborted (stop `aborted`: stopped during a tool call) | ツール実行中に中止（「中断」はトランスクリプトで途中で切れた呼び出しだけ） |
| cost limit reached (stop `budget`) | 料金の上限（「コスト」「予算」は使わない） |
| Pipeline (the breadcrumb's first level: the layer the graph opens on) | パイプライン |
| function (a node holding the tasks created in a function the flow called) | 関数 |
| flow call (one run of a generator of the flow) | フロー呼び出し |
| loop (a box of the nodes one loop of the flow created) | ループ |
| pass N / up to N passes (`flow[].loops[].pass`: one iteration of one loop; never an attempt) | N 周目 / 最大 N 周（「回目」は試行だけ） |
| N passes / number of passes / Passes (how many passes a unit ran of a loop) | N 周 / 周回数 / 周回数 |
| 1 pass: 4 \| 2 passes: 1 (how many units ran each number of passes; tooltip: units by number of passes) | 1 周: 4 \| 2 周: 1（ツールチップ: ユニットごとの周回数） |
| next pass (a loop box's dotted return from its last layer to its first) | 次の周 |
| has an inner view (a function node's layer, a loop box's passes; the legend of their two-card mark) | 内部の表示あり |
| Selected item / Clear selection (the inspector beside the pipeline graph) | 選択中の項目 / 選択を解除 |
| Task detail / Tasks of review / Inside review_loop / Passes of the loop at flow.py:130 (the inspector's links: where each goes) | タスク詳細 / review のタスク / review_loop の内部 / flow.py:130 のループの各周 |
| No layer X in this run (a link to a layer the run does not have) | この実行には階層 X がありません |
| attempt N \| resumed run (an attempt of a later start of the run, after a resume) | N 回目 \| 再開後 |
| Output of prepare · zeta / File from before the run (where an input file comes from) | prepare · zeta の出力 / 実行前からあるファイル |
| 2 output files \| 1 read by this task (an earlier task's files, and those this task reads) | 出力ファイル 2 件 \| このタスクの入力 1 件 |
| Sort units / scheduled order / status (a loop's passes) | 並び順 / 登録順 / 状態 |
| key hints: next node / next row / marks / earlier and later tasks / open / up a level | 次のノード / 次の行 / マーク / 依存先タスク・後続タスク / 開く / 1 つ上の階層 |
| View: Graph \| Table (the pipeline's two views of a layer, a loop's passes being its table) | 表示形式: グラフ \| 表 |
| Nested loop (a loop box inside another) | 入れ子のループ |
| waits for output (a solid edge: `after`) | 出力を待つ |
| created after result (a dashed edge: `created_from`) | 結果を受けて作成 |
| Unit: alpha / Clear highlight (the unit highlighted across layers) | ユニット: alpha / ハイライトを解除 |
| not run (a task still waiting when the run ended; not the same as not started) | 実行されず |
| counts by state in one row: 12 done \| 3 failed \| 2 not started (a count only; a cause has its own message) | 完了 12 件 \| 失敗 3 件 \| 未実行 2 件（状態の語が先、数と「件」が後） |
| N attempts / N tasks (a count) | 試行 N 回 / N タスク |
| 29 of 31 tasks done / 5 of 31 tasks not done; review: 1 of 1 done | 31 タスク中 29 件完了 / 31 タスク中 5 件が未完了; review: 1 件中 1 件完了 |
| Waits for / Created after / Later tasks (the graph's table and a node's label) | 依存先 / 作成元 / 後続タスク |
| Loop at flow.py:130 / Nested loop at flow.py:130 (a loop named by where it is in the flow's code: file and first line; `line N` when the file is not known; also each loop's level in the breadcrumb) | flow.py:130 のループ / flow.py:130 の入れ子のループ（`line N` は「N 行目」） |
| input X is missing because Y failed (why an input stopped a task) | 入力 X がありません（Y が失敗） |
| input missing / input failed checks (why a task did not start; `not started (input missing)` for the stop `invalid_input`) | 入力ファイルなし / 入力ファイルに検証エラー（両方: 入力ファイルの不足または検証エラー）; 未実行（入力ファイルなし） |
| earlier task Y failed (why a task did not start: the failed task it waited for) | 依存先タスク Y が失敗 |
| waits for output of Y / of N earlier tasks (why a waiting task has not run: the earlier tasks that have not finished) | 依存先タスク Y の出力待ち / 依存先タスク N 件の出力待ち |
| not written (task failed) / not written yet (task running) (an output file's state, then its cause) | 書き込みなし（タスクが失敗） / 書き込み待ち（タスクが実行中） |
| N tasks retried / N tasks with corrections / N tasks with model switches (a tile's sub-line) | リトライしたタスク N 件 / 修正依頼のあったタスク N 件 / モデル切り替えのあったタスク N 件 |
| Must be written during the task: yes / no; Check time: when the task starts (a checked file's conditions) | タスク実行中の書き込みが必須: はい / いいえ; 検証のタイミング: タスクの開始時 |
| monitor / filter | モニター / フィルター |
| No monitor API at URL: the response is HTML, not JSON / the response status is 404 / network error, no response (a request to the API with no JSON answer) | URL にモニター API がありません: 応答が JSON ではなく HTML / HTTP ステータス 404 / ネットワークエラーで応答なし |
| host / Hosts (the hosts page, on a hub) / Host h1 / All hosts (the host filter) | ホスト / ホスト一覧 / ホスト h1 / すべてのホスト |
| up / no report / no report since 10:41:03 (a host's state: its reports keep arriving, or stopped) | 稼働中 / 報告なし / 10:41:03 以降報告なし |
| last report / report interval (when a host last reported; seconds between its reports) | 最終報告 / 報告間隔 |
| no report from host (a run whose host stopped reporting while it ran: neither running nor finished) / 1 with no report from host | ホストからの報告なし / ホストからの報告なし 1 件 |
| last activity (the time of a run's last record, while its host is not reporting) | 最終更新 |
| 2 runs / 2 hosts / 1 with no report (hosts) | 実行 2 件 / ホスト 2 台 / 報告なし 1 台（ホストは「台」で数える） |

## Style

**Separators and symbols** are the same in every language (AGENTS.md, "Form"):
`·` only inside a task's name (「review · gamma」); facts in one row are
separated by 「 | 」; 「→」 only for "changed to" or "then", never a link or a
button; ✓ ✕ ◌ only, always next to a word.

**Facts, not narration.** The UI states facts about the run. It never narrates
what the monitor or contraagent does or will do, and never addresses the
reader with what they can do: no 「〜します」「〜しません」「〜させます」
「〜できます」「〜してください」「〜のためです」 about the system. Use a state,
a count, a cause or a value: 「未実行: 入力 out/review/zeta.json がありません（review ·
zeta が未完了）」「トランスクリプトなし」「修正依頼 2 回」. How the system works
belongs in the documentation. A tooltip may define a term in a short noun
phrase or add a fact about this item, never a policy.

**Nothing obvious, no lists of absences.** Do not state what follows from the
item's kind (a Python task is defined in code), and do not list what it lacks
(「プラグイン、ロール、プロンプトなし」). Show what it has.

Write the Japanese a software engineer uses every day in tools, logs and
technical documentation, as if written from scratch, not translated from the
English. When in doubt, pick the word a Japanese engineer would type in a
review comment or a commit message.

- **No literal translation.** Translate what the English means, not its words
  or sentence structure. Reorder, split or merge clauses freely. Drop English
  habits that read oddly in Japanese (stacked nouns, "the ... of the ...",
  pronouns like "it" and "its", "you").
- **No uncommon kanji compounds.** Use the words engineers use in Japanese
  documentation and UIs. Prefer 「〜を確認する」 to 「〜を検証済とする」,
  「まだありません」 to 「未存在」, 「止まった」 to 「停止状態となった」. A plain
  phrase is better than a compact but stiff 漢語.
- **No metaphors.** Say literally what happens. Where the English uses an
  image ("at a glance", "lands", "walks its chain", "the tail"), write the
  plain fact (「一覧で」, 「届いた」, 「順に切り替える」, 「末尾」).
- Labels, headings, tab and column names are short nouns or noun phrases, no 。.
- Sentences (empty states, tooltips, notes) use です・ます and end with 。 when
  the English ends with a full stop.
- Keep `code` spans, identifiers, file names and `<x .../>` placeholders exactly
  as they are; put Japanese particles around them naturally.

## Themes

The theme control in the header. A theme's own name stays as it is, in every
language: contraagent Dark, contraagent Light, GitHub Dark, GitHub Light, One
Dark, Nord.

| English (UI) | 日本語 |
|---|---|
| Theme (the header's control; its tooltip: Theme: GitHub Dark) | テーマ（ツールチップ: テーマ: GitHub Dark） |
| System (the theme follows the system's colour scheme) | システム設定に合わせる |
| High contrast | ハイコントラスト |
| Editor themes (the group of themes from code editors) | エディタのテーマ |
