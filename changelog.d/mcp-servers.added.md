`Pipeline(mcp_servers=)` takes a function (`McpServers`) that builds the MCP servers of
each agent task from the task, its params and its plugin's `.mcp.json`, for every
coding agent. What it returns replaces the plugin's servers; None keeps them. The user's
and the project's MCP servers stay out, the servers are written to an owner-only
temporary file and not to the run directory, and `Pipeline.check` calls the function
for the tasks it builds.
