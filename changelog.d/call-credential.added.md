An agent task call names the credential of that one task: `summarize(unit,
credential="company")` runs it as `[credentials.company]` on every route of its kind,
failover hops included, with a failover breaker of its own. It outranks the kind's
`[tasks.<kind>]` table and declaration; `Overrides(credential=)` outranks it. A credential
that does not exist, lacks a trait the task `requires`, or that a route's coding agent
cannot use is refused before the task launches, and `contraagent check` reports it. A
resting one defers the task. The routes of `contraagent check` name the tasks whose calls
give one (`credential=company for summarize-beta, by their task calls`), and a run's
`[start]` line for such a task names it. It is not part of the fingerprint. `plan.jsonl` records it
(`credential`), as do `Task.credential` and the monitor's plan; `RoutingPlan.call_problems`
and `Router.on_credential` are new.
