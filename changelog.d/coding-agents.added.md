**Coding agents.** Claude Code (`claude -p`), oh-my-pi (`omp -p`, and its RPC mode),
opencode (`opencode run`), pi (`pi -p`) and Codex CLI (`codex exec`), each a `Backend`;
`register_backend` adds one of your own. Each launch is supervised (time, budget, stalls,
refused tool calls) and reports its tokens, cost, peak context and the account's 5-hour
and weekly usage when the agent gives them. A task's agent sees its plugin and call file
only: the user's and the project's settings, instruction files, skills, hooks and MCP
servers are kept out, on every agent. A coding agent does not outlive the pipeline that
started it.
