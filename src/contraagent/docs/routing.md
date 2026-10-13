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
on omp contraagent sums the cost omp reports for each API call and ends the
launch (`budget`) once it passes the cap. Every key: the reference at the end.

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

| type | claude | omp |
|---|---|---|
| `subscription` | the `/login` in a `CLAUDE_CONFIG_DIR` | the login in an omp profile |
| `api_key` | Anthropic | any provider (`<PROVIDER>_API_KEY`) |
| `oauth_token` | `CLAUDE_CODE_OAUTH_TOKEN` | Anthropic |
| `gateway` | an Anthropic-API endpoint (bearer or API key, custom headers) | a provider endpoint (`litellm` by default) |
| `workload_identity`, `bedrock`, `vertex` | yes | — |
| `pool` | several of the above used as one (`in_order`, `round_robin`) | the same |

A **gateway** is your own endpoint: LiteLLM, a company proxy, a self-hosted
API. Claude Code speaks the Anthropic Messages API to it; omp addresses it as a
provider, so its models are `litellm/<model>`.

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
(`RateLimit`).

A credential past a cap or the rule **rests** until the window its reading
names resets. Nothing launches as it meanwhile: a pool passes over the member,
and a task skips the hop without launching it and takes the next hop of its
failover chain (a gateway, an API key), the reason in its journal row
(`personal rests: 5-hour usage 93%, max 90%; ran on hop 2/2 ...`). A task
with no hop left is deferred at once: it spent nothing and did not fail, and
`deferred.jsonl` says why, as does the monitor ("not run" and the reason). A
task of `finishing_kinds` still launches on a resting credential for `grace_s`
after the rest began, as it does past a deadline.

The readings are those the coding agents report: Claude Code when a session
starts or resumes, omp at each launch. The run starts from the newest of
recent runs' journals and takes each launch's as it ends, so tasks that start
together all start before the first of them reports the cap is reached. A
credential with no readings (a gateway, an API key) never rests on a quota.

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
  logins outside its profiles, so for providers other than `anthropic` and
  `litellm` a task that requires traits is refused on omp.
- **What the agent says it used.** A launch whose reported credential source
  does not match its credential ends `credential_mismatch` and is not ok.

The journal records each launch's credential *name*, never a secret.

## Every table and key

::code{file="examples/reference/pipeline.toml"}
