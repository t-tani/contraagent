`contraagent run --stub --execute-all` (and `--replay DIR --execute-all`) runs the
function of every Python task, so only the agent tasks are played; it is not taken with
`--execute`. In Python: `StubAgent(execute_all=True)`, `Pipeline(replay=DIR,
execute_all=True)`.
