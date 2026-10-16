A kind sets its correction rounds: `agent_task(max_corrections=1)` or `max_corrections`
in `[tasks.<kind>]` (0 to 20, default 3, as before). The journal row and
`launches.jsonl` record it as `max_corrections`, beside `rounds`, and `contraagent
check` reports a value out of range.
