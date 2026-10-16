**Routing and credentials.** One TOML file (`pipeline.toml`, with a JSON Schema) gives
each kind its coding agent, model, effort, budget, time limits and credential, from
`[defaults]` and `[tasks.<kind>]`.

- Credentials: `ambient` (the host's own login), subscriptions, API keys, OAuth tokens,
  gateways (your own endpoint, such as LiteLLM), Bedrock, Vertex, workload identity, and
  pools of them.
- Failover: a kind's `fallbacks` chain moves a task to its next hop (another model, agent
  or credential) after a failed launch, and a breaker per kind after a rate limit.
- Quota caps (`max_five_hour_pct`, `max_seven_day_pct`) and `Pipeline(quota_rule=)` rest a
  credential until its window resets; tasks take the next hop meanwhile, or are deferred.
- A preflight probes every route before the first launch (`preflight = "substitute"`,
  `"stop"` or `"off"`).
- `disallowed_tools`, `context_budget` and `context_warn_pct`, and a pipeline's own tables
  (`[pipeline.<name>]`, read with `pipeline_table`).
