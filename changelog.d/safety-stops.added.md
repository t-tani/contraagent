Safety stops are recorded and can move a launch to its next hop. A safety stop is a safety classifier that stopped part of a launch while the launch went on: a response of the launch's own model (`response`), or a request of a model that a tool calls, as Claude Code's `WebFetch` does (`tool`). Such a launch often still ends `completed`.

- `LaunchResult.safety_stops` and the journal's `safety_stops` list each one (`SafetyStop`: its part, the model, the category, the tool, the time and the provider's ids), read from Claude Code's stream.
- The monitor marks an attempt that had them, and the trends count them by part, model and kind (`Trends.safety_stops`).
- `[tasks.<kind>] safety_stop_failover` and `agent_task(safety_stop_failover=)` name the parts whose safety stop moves a launch that ended well to the next hop of the failover chain. `contraagent check` warns of a kind that names them with no chain.
