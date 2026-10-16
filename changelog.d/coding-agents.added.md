Five coding agents run the same tasks, plugins and config: Claude Code (`claude -p`),
Codex CLI (`codex exec`), opencode (`opencode run`), oh-my-pi (`omp -p`) and pi
(`pi -p`). `register_backend` adds another one. Each launch starts in a clean context:
the user's and the project's settings, instruction files, skills, hooks and MCP servers
are kept out. contraagent supervises the time, the budget, stalls and denied tool calls,
and records the tokens, the cost, the peak context and the account's 5-hour and weekly
usage when the agent reports them. A coding agent does not outlive the pipeline that
started it.
