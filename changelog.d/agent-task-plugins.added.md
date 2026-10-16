An agent task's implementation is a plugin in the coding agent's own format: roles,
skills, MCP servers and hooks. Its hooks are written once in `hooks.toml` and rendered
for each coding agent, and `contraagent plugin new`, `lint` and `render` create, check
and render a plugin. Each launch is given a call file with the task's parameters and its
output contract.
