# Routing and credentials

The code declares what a task is and its default budget. The TOML file decides
where it runs: coding agent, model, effort, credential, failover chain, and
budgets that outrank the declared ones. The demo's:

::code{file="examples/demo/pipeline.toml"}

## Precedence

Highest first: overrides (`Pipeline(overrides=...)`, e.g. from command-line
flags), the kind's `[tasks.<kind>]` table, `agent_task(...)`, `[defaults]`, the
built-in default.

Refused before anything launches: a kind with no turn or time budget anywhere,
an effort the coding agent's CLI does not accept, an unknown agent in a chain,
and any credential problem (below). A `[tasks.<name>]` table that names no task
of the flow is reported, not fatal: one config file often serves several flows,
but it may be a typo.

## Budgets

`max_turns` and `timeout_s` are required for every kind. `max_budget_usd` caps
a launch's cost as the coding agent reports it: Claude Code enforces it itself;
on omp and opencode contraagent sums the cost the agent reports for each API
call and ends the launch (`budget`) once it passes the cap; Codex reports no
cost, so the cap does not hold there. On Codex `max_turns` counts tool calls.
Every key: the reference at the end.

`disallowed_tools` (in a task table or `agent_task(...)`) lists tools a kind's
launches may not use, in Claude Code's names: a whole tool (`WebFetch`) or a
tool with a pattern of what it is given (`Bash(rm:*)`). It narrows what the
role's `tools:` allow. Claude Code denies both (`--disallowedTools`); opencode a
`Bash(...)` pattern as a command pattern and any other tool whole; pi whole tools
(`--exclude-tools`), so a pattern there is refused; omp and Codex have no way to
deny a tool, and a route on them is refused before anything launches
(`Backend.tool_deny_problem`), failover hops included.

## Failover

Each kind gets its own failover breaker: on a 429 the task walks its chain of
(agent, model, credential) hops, and a half-open probe returns to the primary
once the provider's stated cool-off has passed. Until then every task of that
kind starts on the hop, not only the one that was rate limited (the log says so:
`[route] <key>: starting on hop 2/2 ...`). `Pipeline(preflight=True)`
probes every distinct route once before the first task and drops the ones that
cannot answer.

Any other failure of a launch (an error, a refusal, a timeout, an output still
off-contract after its fix-ups, ...) moves only that task to the next hop; the
next task still starts on the primary. Two failures do not move it: an input
that is off-contract (nothing was launched) and a launch that ran as another
identity than its credential (`credential_mismatch`). A launch ended by a signal
(the run is stopping) does not either.

An override of the agent or the model (`contraagent run --agent omp`) runs every
kind there and nowhere else: no kind has failover hops. An override of the
credential (`Overrides(credential=...)`) is every hop's credential as well.

## Credentials

Three questions, answered in three places:

| Question | Answered by |
|---|---|
| What may this task's data be sent under? | the task, in code: the traits it `requires` (e.g. `zdr`) |
| Which identities exist, and what are they? | the config: `[credentials.<name>]`, each with a type and its `traits` |
| Which identity does each task use? | the config: `credential` in `[defaults]`, `[tasks.<kind>]` and each failover hop |

With no credential configured, every task runs as `ambient`: the host's own
setup, untouched. `ambient` carries no traits, so a task that requires any never
runs on it. Traits are free-form labels; what they promise (zero data
retention, company billing) is for whoever writes the config to know. Secrets
are references (`env:NAME`, `file:/path`) read in the launching process and
never written anywhere.

Each coding agent says which credential types it can use:

| type | claude | omp | opencode | pi | codex |
|---|---|---|---|---|---|
| `subscription` | the `/login` in a `CLAUDE_CONFIG_DIR` | the login in an omp profile; a ChatGPT login (`provider = "openai"`) runs `openai-codex/<model>`; an OpenCode one is `OPENCODE_API_KEY`, which omp also reads from its `.env` files | the provider's stored login (`opencode providers login`) | the `/login` in a pi agent directory (`config_dir`, by default `~/.pi/agent`); for `opencode` and `opencode-go` with no such login there, opencode's stored login | the ChatGPT login in a `CODEX_HOME` (`provider = "openai"`) |
| `api_key` | Anthropic | any provider (`<PROVIDER>_API_KEY`) | any provider | any provider (`<PROVIDER>_API_KEY`) | OpenAI (`CODEX_API_KEY`) |
| `oauth_token` | `CLAUDE_CODE_OAUTH_TOKEN` | Anthropic | — | Anthropic | — |
| `gateway` | an Anthropic-API endpoint (bearer or API key, custom headers) | a provider endpoint (`litellm` by default) | a provider endpoint: a provider opencode knows (`anthropic`, `openai`, ...) keeps its own API, another name is OpenAI-compatible | an OpenAI-compatible endpoint (`litellm` by default, custom headers) | a Responses-API endpoint (bearer or API key, custom headers) |
| `workload_identity`, `bedrock`, `vertex` | yes | — | — | — | — |
| `pool` | several of the above used as one (`in_order`, `round_robin`) | the same | the same | the same | the same |

A **gateway** is your own endpoint: LiteLLM, a company proxy, a self-hosted
API. Claude Code speaks the Anthropic Messages API to it; omp, opencode and pi
address it as a provider, so its models are `<provider>/<model>`
(`litellm/<model>`; on opencode, `anthropic/<model>` with `provider =
"anthropic"` and a `base_url` ending in `/v1`). pi speaks the OpenAI
chat-completions API to `base_url`, and its token stays in the environment, not
in the `models.json` that names the provider. Codex speaks the OpenAI Responses
API to it (`<base_url>/responses`, so `base_url` ends in `/v1`), as a model
provider named after `provider`; its models are the gateway's own names.

A **pool** uses several credentials as one. `in_order` uses the first member
until it answers 429, then the next; `round_robin` turns to the next member on
every launch. A member that answers 429 rests on that model for the provider's
stated retry-after, and the task goes to the next member at once; with every
member resting, the route's own failover takes over. A pool carries only the
traits every member carries.

## Quota caps

A subscription's quota (its 5-hour and weekly usage) belongs to the account,
so its caps are the credential's: `max_five_hour_pct` and `max_seven_day_pct`
in its `[credentials.<name>]` table (on a pool, the cap of each member that
sets none). `Pipeline(quota_rule=fn)` adds a test of your own: `fn(credential,
reading)` returns why the credential rests now, or None, from its latest reading
(`RateLimit`); or the reason and when the rest ends, `(reason, datetime)` (a time
with no zone is UTC).

A credential past a cap or the rule **rests** until the window its reading
names resets. Nothing launches as it meanwhile: a pool passes over the member,
and a task skips the hop without launching it and takes the next hop of its
failover chain (a gateway, an API key), the reason in its journal row
(`personal rests: 5-hour usage 93%, max 90%; ran on hop 2/2 ...`) and the hop
it passed over in `skipped_hops`. A task with no hop left is deferred at once:
it spent nothing and did not fail, and `deferred.jsonl` says why, as does the
monitor ("not run" and the cause). A task of `finishing_kinds` still launches
on a resting credential for `grace_s` after the rest began, as it does past a
deadline.

A rest by the rule lasts until the end the rule gave with its reason, and the rule
is not asked again before it: a daily budget rests to the next day's start, a weekly
one to the weekly window's reset. A rule that gives a reason alone rests the
credential while the reading it judged stands: until the earliest reset among that
reading's windows (a window that names no reset stands for its length after the
reading arrived). Nothing launches on a resting credential, so no
newer reading comes; after that time the stale reading no longer counts, the
credential does not rest, and the next launch brings a reading for the rule to
judge again. The rest records the reading it judged (`reading`: when it arrived,
each window's usage and reset) and its end (`until`).

`run.json` records the run's caps (`quota_caps`) and the rule's name
(`quota_rule`), and `rests.jsonl` each rest as it begins and ends: the window,
the reading, the cap (or what the rule said and the reading it judged) and when it
ends. The
monitor's overview shows them beside each account's usage: the limit on each
window, the identity paused until when, and its rests over the run.

The readings are those the coding agents report: Claude Code when a session
starts or resumes, omp at each launch, Codex with each API call of a ChatGPT
login. opencode and pi report none, so for an `opencode-go` model contraagent reads
the OpenCode Go subscription's usage itself at each launch, from the route OpenCode's
console serves (`<base>/v1/usage` with the key; omp reads the same): the 5-hour and
weekly windows, and the monthly one by name in `windows`. The run starts
from the newest of recent runs' journals and takes each launch's as it ends, so
tasks that start together all start before the first of them reports the cap is
reached. A credential with no readings (a gateway, an API key, an OpenCode Zen model)
never rests on a quota. A quota opencode is refused on ends the launch
`rate_limited` at once: opencode itself would wait as long as the provider asks.

A reading names the **account** that reported it, so one credential's accounts
are kept apart: `ambient` is each coding agent's own login (two accounts when
Claude Code and omp are logged in as different users), and a credential's token
can be replaced between runs. A hop is judged by the readings of the account a
launch on it bills (`Backend.account`): an earlier token's 98% does not rest the
new one. The account is a digest (`account_digest`: SHA-256 over a fixed prefix,
the source and the value, cut to 12 hex digits), never the value: Claude Code's
is its login's `oauthAccount.accountUuid` (in the config directory's
`.claude.json`; for an ambient launch, a key or token in its environment first)
or the token or key the credential holds; omp's is the account its usage report
names. An OpenCode key is its own account on every agent: the digest of the key
opencode, pi or omp would send (on omp, `OPENCODE_API_KEY` of the launch's
environment, else of omp's `.env` files), so one login used on all three is one
account, and a rest on one of them holds on the others. A UUID and a token of one account give two digests, so a reading counts
for the source it came from. A reading with no account (an older journal) counts
for every account of its credential.

A reading keeps what the coding agent reported beside the two windows: every
window by its name (`windows`, a model's own such as `seven_day_opus` too), the
window the status is about (`status_window`), the threshold past which it warns
(`threshold_pct`), whether usage past the limit is allowed (`overage_status`,
`overage_disabled_reason`, `using_overage`), and any other field as `extra`.

What is guaranteed:

- **Before launch**, every route of every kind (failover hops and pool members
  included) is checked: the credential exists, carries the traits the task
  requires, and the coding agent can use it with that model. A 429 can never
  move a ZDR task onto a subscription.
- **Nothing else in the environment.** For any credential but `ambient`, every
  credential-selecting variable, and every variable that looks like a secret
  (`*_API_KEY`, `*_AUTH_TOKEN`, ...), is removed from the child before the chosen
  one is set. A tool that needs a key of its own gets it back through
  `Pipeline(env=...)`.
- **Nothing the agent loads by itself.** Claude Code runs with empty config
  directories, so a key that does not work fails instead of falling back to a
  stored login. omp runs in a profile with no stored logins; omp keeps some
  logins outside its profiles, so for providers other than `anthropic`,
  `openai-codex` and `litellm` a task that requires traits is refused on omp.
  omp also reads `.env` files at start (its working directory's, its agent
  directory's, its config root's and `~/.env`), and fills from them every
  variable the launch's environment leaves unset: when one of them sets the key
  or endpoint variable of the launch's provider and the credential does not, the
  binding says which file, and a task that requires traits is refused on omp. opencode gets no
  stored login but the chosen one, and the chosen key in its launch config,
  over any key in the user's own opencode config; an OAuth login (which opencode
  refreshes and writes back over every stored login) is not narrowed, so a task
  that requires traits is refused on it. Codex runs with an empty `CODEX_HOME`
  and without the user's `config.toml`.
- **What the agent says it used.** A launch whose reported credential source
  does not match its credential ends `credential_mismatch` and is not ok.

The journal records each launch's credential *name*, never a secret.

## Every table and key

::code{file="examples/reference/pipeline.toml"}
