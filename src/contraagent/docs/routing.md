# Routing and credentials

The code declares what a task is and its default budget. The TOML file decides
where it runs: coding agent, model, effort, credential, failover chain, and
budgets that outrank the declared ones. The demo's, whose agent `stub` is the demo's
own `Backend` that `examples/demo/run.py` registers (`contraagent check ... --stub`
checks a config that names it):

::code{file="examples/demo/pipeline.toml"}

## Precedence

Highest first: overrides (`Pipeline(overrides=...)`, e.g. from command-line
flags), the kind's `[tasks.<kind>]` table, `agent_task(...)`, `[defaults]`, the
built-in default. A credential has one more place, the task call (below): it sits
under the overrides and over the kind's table.

`[defaults]` takes the routing keys (`agent`, `model`, `effort`, `credential`,
`model_failover`, `fallbacks`), the run's own settings (`max_passes`, `preflight`,
`claim_capacity`) and the default of every kind that gives none (`context_warn_pct`),
nothing else. A budget (`max_turns`, `timeout_s`, `max_budget_usd`,
`max_corrections`, ...) is a kind's: it goes in `[tasks.<kind>]` or `agent_task(...)`,
and `[defaults]` refuses it.

Refused before anything launches: a kind with no turn or time budget anywhere,
an effort the coding agent's CLI does not accept, an unknown agent in a chain,
and any credential problem (below). A `[tasks.<name>]` table that names no task
of the flow is reported, not fatal: one config file often serves several flows,
but it may be a typo.

A pipeline keeps its own settings in the same file, each in a **pipeline table**
`[pipeline.<name>]`. Flow code and Python tasks read one of the run's config (or of
the config a check is given) with
`contraagent.pipeline_table(name)` ([tasks](tasks.md)), other code with
`PipelineConfig.table(name)`; either is an empty table when the file has none.
contraagent never checks the keys inside; a `pipeline.<name>` that is not a table is
refused. Any other top-level table is refused before
anything launches.

## Budgets

`max_turns` and `timeout_s` are required for every kind. `max_budget_usd` caps
a launch's cost as the coding agent reports it: Claude Code enforces it itself;
on omp, opencode and pi contraagent sums the cost the agent reports for each API
call and ends the launch (`budget`) once it passes the cap; Codex reports no
cost, so the cap does not hold there. On Codex `max_turns` counts tool calls, and
omp and pi do not enforce it. [Coding agents](agents.md) has each agent's budgets
in one table. Every key: the reference at the end.

`context_budget` caps a launch's peak context: the whole input (fresh input,
cache read and cache write) of its largest API call. Claude Code and opencode
launches end `context_budget` once one call passes it; omp, pi and Codex report
each call's tokens but are not stopped. `context_warn_pct` (1 to 99, in a task
table, `agent_task(...)` or `[defaults]`) is a percent of `context_budget` and
stops nothing: an attempt whose peak context passed it is recorded
(`context_warned` in the journal, beside `context_budget` and
`usage.peak_context`) and logged (`[context] <key>: peak context ...`). The
journal's `usage.context_window` is the window of the model the peak context was
on, as the coding agent reports it: in its stream (Claude Code, Codex, omp RPC) or,
when the stream gives none, in its model catalogue for the model the launch ran on
(omp `-p`, pi, opencode; `Backend.context_window`). `launches.jsonl` holds it and
`context_pct`, the peak context as a percent of it, both null when the coding agent
reports no window. A kind with
a `context_warn_pct` but no `context_budget` is refused before anything launches;
`[defaults].context_warn_pct` applies to every kind with a `context_budget` and
none of its own.

`max_corrections` (0 to 20, default 3, in a task table or `agent_task(...)`) caps the correction rounds of a kind: how many times an output that
fails its checks goes back to the same session ([contracts](contracts.md#checked-twice-by-the-same-rules)).
A value out of that range is refused before anything launches.

`keep_failed_changes = true` (in a task table, which outranks `agent_task(...)`) leaves
the files a failed attempt created under the kind's `changes` patterns in place, for
the next attempt to start from
([Files a task changes](tasks.md#files-a-task-changes)). A kind with no `changes`
patterns cannot keep them, and `contraagent check` reports a table that sets it.

`max_concurrent` (in a task table or `agent_task(...)`) is how many tasks of a kind
run at once. The run's own limits sit beside it, and
[Concurrency](tasks.md#concurrency-how-many-tasks-run-at-once) says how they work
together: the run's slots, a kind's limit and the claims, and how a claim keeps long
Python tasks from taking the agent tasks' slots.

`disallowed_tools` (in a task table or `agent_task(...)`) lists tools a kind's
launches may not use, in Claude Code's names: a whole tool (`WebFetch`) or a
tool with a pattern of what it is given (`Bash(rm:*)`). It narrows what the
role's `tools:` allow. Claude Code denies both (`--disallowedTools`); opencode
whole tools and a pattern of a command (`Bash(git push:*)`), a path (`Read(secrets/**)`,
`Edit(...)`), a domain (`WebFetch(domain:example.com)`) or a skill (`Skill(deploy)`),
each after the rule the tool had, so the rest of the tool stays allowed; a pattern of
another tool there is refused; omp, in an extension of contraagent's own that sees
each call before it runs, whole tools and a pattern of a command, a path read or
written (`Read`, `Write`, `Edit`, `MultiEdit`; an `Edit` pattern also denies omp's
`ast_edit` whole), a domain or a skill, so a pattern of another tool there is refused; pi whole tools (`--exclude-tools`), so a pattern there is refused;
Codex has no way to deny a tool. A route that cannot deny what the task names is
refused before anything launches (`Backend.tool_deny_problem`), failover hops
included ([Coding agents](agents.md)).

## Failover

Each kind gets its own failover breaker: on a 429 the task walks its chain of
(agent, model, credential) hops, and a half-open probe returns to the primary
once the provider's stated cool-off has passed. Until then every task of that
kind starts on the hop, not only the one that was rate limited (the log says so:
`[route] <key>: starting on hop 2/2 ...`).

Any other failure of a launch (an error, a refusal, a timeout, an output still
off-contract after its correction rounds, ...) moves only that task to the next hop; the
next task still starts on the primary. Two failures do not move it: an input
that is off-contract (nothing was launched) and a launch that ran as another
identity than its credential (`credential_mismatch`). A launch ended by a signal
(the run is stopping) does not either.

A failover hop can name the stops it is for (`stops`): the stops of an earlier hop's
launch after which a task may take it. A hop without `stops` is for every stop. A task
whose launch ended on another stop passes the hop over and takes the next hop that is
for its stop, so a mirror of the same model for quota does not get a task that the model
refused. A 429 opens the breaker only onto a hop for `rate_limited`. When no hop after
the launch is for its stop, the launch's own stop stands. The stops a hop can name are
every stop but `completed`, `invalid_input` and `credential_mismatch`; the `[route]` line
of a kind shows them (`hop 2/3 omp/... on rate_limited, api_error`). Claude Code's own
model failover (`model_failover`) never takes a hop that names its stops.

A launch refused for its credential (`auth_failed`: a 401 or 403, such as an expired or
revoked key, or a model the key may not use) is refused the same way on every later
launch. So the credential **rests** on that launch's coding agent and model for the rest
of the run: later tasks pass the hop over without a launch, the rest in their journal row
(`skipped_hops`, `stop: "auth_failed"`), and a pool goes on to its next member at once.
Another model of the same credential still launches. A task with every hop refused
fails `auth_failed` without a launch; it is not deferred, since nothing in the run changes
the credential. When the last hop a task reached was refused after a hop that ran, the
attempt ends on the stop of the hop that ran (`timeout`, for example), with the refused hop
in its `hops`. `rests.jsonl` records the rest as it begins, and the monitor shows the
identity paused on that model. A resumed run starts with no such rest.

A launch that ended well can still have had a safety stop: a safety classifier
stopped part of it, and it went on (`SafetyStop`, the journal's `safety_stops`). It
may then have finished without the work, saying that it could not do it, in an
output that passes its checks. A kind's `safety_stop_failover` names the parts whose
safety stop moves such a launch to the next hop, which starts the task again:
`"response"`, a response of the launch's own model, and `"tool"`, a request of a
model that a tool calls (Claude Code's `WebFetch` summarizes a page on a smaller
model of its own). A hop on another model of the same coding agent keeps that
tool, so a `"tool"` safety stop needs a hop on another coding agent. The last hop's
result stands. An output that a safety stop left off-contract fails its checks and
fails over as any failure does, with no `safety_stop_failover`.

::code{file="examples/reference/pipeline.toml" from="[tasks.research]" to="# A base kind's table"}

An override of the agent or the model (`contraagent run --agent omp`) runs every
kind there and nowhere else: no kind has failover hops. An override of the
credential (`Overrides(credential=...)`) is every hop's credential as well.

## Preflight

The preflight probes every distinct route of the run's reachable kinds once,
before the first task: a model its coding agent does not list is dropped
without a launch, and every other route gets one minimal launch (`max_turns=1`);
a route whose probe does not complete (a 429, an error, a timeout) is dropped.
Past the first 8 routes the rest are kept unprobed. Each failover chain is rebuilt on the routes left. The preflight policy says what
happens to a kind with no route left:

| Policy | A kind with no route left |
|---|---|
| `substitute` | runs on the first route that answered, when that route runs as the kind's own credential; else it runs as configured |
| `stop` | the run raises `PreflightStopped`, naming each such kind and why each of its routes was dropped; nothing launches |
| `off` | nothing is probed (the default) |

`Pipeline(preflight="stop")`, `contraagent run --preflight stop`, or
`preflight = "stop"` in `[defaults]`; the argument and the flag outrank the
config. `run.json` records what the preflight did (`preflight`: the policy, the
routes dropped and the kinds that held them, each kind moved from one route to
another, each kind left as configured and why, and the kinds that stopped the
run), and the monitor returns it with the run's plan (`Plan.preflight`).

## Credentials

Three questions, answered in three places:

| Question | Answered by |
|---|---|
| What may this task's data be sent under? | the task, in code: the traits it `requires` (e.g. `zdr`) |
| Which identities exist, and what are they? | the config: `[credentials.<name>]`, each with a type and its `traits` |
| Which identity does each task use? | the config: `credential` in `[defaults]`, `[tasks.<kind>]` and each failover hop; for one task, its call |

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
stated retry-after, one refused for its credential rests on that model for the rest of
the run, and the task goes to the next member at once; with every
member resting, the route's own failover takes over. A pool carries only the
traits every member carries.

## A task call's credential

A kind runs as one credential, but the data of one unit may have to go under another
account. The task call names it, as the name of a `[credentials.<name>]`:

::code{file="examples/credentials/flow.py" from="#: The documents"}

::code{file="examples/credentials/pipeline.toml"}

The rule is that the narrower choice outranks the wider one, and an override
outranks them all. The config outranks the declaration because a declaration is the
default of a whole kind. The config has no table for one unit, so the task call is
the only place that can name a credential for it, and it outranks the kind's
`[tasks.<kind>]` table, `agent_task(...)` and `[defaults]`. An override
(`Overrides(credential=...)`) is the choice of the person who runs the pipeline and
outranks the call too: the task runs as the override's credential, and the log says so.

The call's credential is the credential of every route of the kind: the primary and
each failover hop, whatever credential the hop names. A 429 or a refusal moves the task
to the next hop as the same credential, never to another identity. Two hops that become
the same route are one hop. The tasks of one kind and one call credential share a
failover breaker of their own: a 429 as that credential does not move the kind's other
tasks, and a 429 of theirs does not move these.

A credential that does not exist, that does not carry a trait the task `requires`, or
that the coding agent of one of the routes cannot use with its model, is refused before
the task launches: by `contraagent check` for the tasks the flow creates before its
first wait, by `Pipeline.run` before anything launches for those same tasks, and at the
task call for a task a generator flow creates later (a `ValueError` in that flow call).
The preflight does not probe a route as a call's credential.

A call's credential that rests on its quota is passed over like any resting
credential: every hop is on it, so the task is deferred, not failed.

The `[route]` line of a kind names the kind's credential. `contraagent check` adds the
tasks whose calls name another one to their kind's line (`credential=company for
summarize-beta, by their task calls`), and a run's `[start]` line names the call's
credential (`[start] summarize-beta credential=company`). With an override, neither
does, since the override's credential is in effect.

A credential is who the work is billed to, not what the work is: it is not part of the
fingerprint, and a resumed run that names another credential for a call skips the task
it already finished. `plan.jsonl` records the call's credential (`credential`) when it is
in effect, and the journal records the credential each launch ran as, as for every task.

## Quota caps

A subscription's quota (its 5-hour and weekly usage) belongs to the account,
so its caps are the credential's: `max_five_hour_pct` and `max_seven_day_pct`
in its `[credentials.<name>]` table (on a pool, the cap of each member that
sets none). `Pipeline(quota_rule=fn)` adds a test of your own: `fn(credential,
reading)` returns why the credential rests now, or None, from its latest reading
(`QuotaReading`); or the reason and when the rest ends, `(reason, datetime)` (a time
with no zone is UTC).

A credential past a cap or the rule **rests** until the window its reading
names resets. Nothing launches as it meanwhile: a pool passes over the member,
and a task skips the hop without launching it and takes the next hop of its
failover chain (a gateway, an API key), the reason in its journal row
(`personal rests: 5-hour usage 93%, max 90%; ran on hop 2/2 ...`) and the hop
it passed over in `skipped_hops`. A task with no hop left is deferred at once:
it spent nothing and did not fail (`RunReport.deferred`, not `failed`), a task
that reads its output is deferred with it, and `deferred.jsonl` says why, as does the
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
the OpenCode Go subscription's usage itself at each launch, from the endpoint OpenCode's
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
new one. The account is a digest (SHA-256 over a fixed prefix,
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

The JSON Schema of the file is `schemas/pipeline.schema.json` beside this page
([Compatibility](compatibility.md)); the reference file's first line gives it to an
editor that reads `#:schema`.

::code{file="examples/reference/pipeline.toml"}
