omp now runs a plugin's stop hook inside the session, as Claude Code and Codex do:
`contraagent plugin render` writes `omp/hooks.json` beside `omp/index.ts`, and the
extension runs it at omp's `session_stop`, so an output that fails its checks is fixed
in the same session before the launch ends, and the journal records what the hook sent
back (`hook_errors`). Render a plugin again to get it. omp also enforces `max_turns`
(contraagent counts its tool calls, as for Codex) and takes `disallowed_tools`: an
extension of contraagent's own denies whole tools and patterns of a command, a path read
or written, a domain or a skill, and only a route that sets a pattern of another tool is
refused (`OmpBackend.tool_deny_problem`).
