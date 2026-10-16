One TOML file (`pipeline.toml`, with a JSON Schema) gives each kind its coding agent,
model, effort, budget, time limits and credential, from `[defaults]` and
`[tasks.<kind>]`.
- Credentials are the host's own login (`ambient`), subscriptions, API keys, OAuth
  tokens, gateways, Bedrock, Vertex, workload identity and pools of them.
- A kind's `fallbacks` move a task to its next route (another model, coding agent or
  credential) after a rate limit, a failed launch or a safeguard refusal.
- Quota caps on a subscription's 5-hour and weekly usage rest a credential until its
  window resets, and a preflight probes every route before the first launch.
