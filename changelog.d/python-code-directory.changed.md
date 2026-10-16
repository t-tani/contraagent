**Where Python code runs, and `--config` in the checks.** `contraagent docs contracts` and
`tasks` say that a Python task and a Python validator run in the process's current directory
(a relative path from `params` resolves there, not against `Pipeline(cwd=)`). The pointer
(`contraagent docs --pointer`), the index and `testing` show `--config pipeline.toml` in the
`check` and stub-run commands, so a stub run's `[route]` lines name the config's routes.
