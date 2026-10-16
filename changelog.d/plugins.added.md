**Plugins.** What an agent task does lives in a plugin the coding agent loads itself:
roles, skills, MCP servers and hooks, the hooks written once in `hooks.toml` and rendered
for each coding agent. `contraagent plugin new | lint | render` creates, checks and
renders a plugin. Each agent task is given a call file with its parameters and its output
contract.
