`contraagent run --stub --execute` (and `--replay DIR --execute`) takes an `fnmatch`
pattern of kinds as well as a kind: `--execute 'fetch_*'` runs the functions of every
Python task kind that matches, and `--execute '*'` the function of every Python task, so
only the agent tasks are played. In Python: `StubAgent(execute=["*"])`,
`Pipeline(replay=DIR, execute=["*"])`.
