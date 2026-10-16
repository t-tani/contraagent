# Coding agents

contraagent runs five coding agents. A kind runs on the one its route names
(`agent` in the config, `contraagent run --agent <name>` for every kind of a run),
and the same task, plugin and config run on each of them. They differ in what
their CLIs can do; this page lists those differences, and the other topics link here.

| Agent (`agent`) | CLI | A launch runs |
|---|---|---|
| `claude` | Claude Code | `claude -p --output-format stream-json` |
| `omp` | oh-my-pi | `omp -p`; `omp-rpc` runs the same agent over `omp --mode rpc` and shares its column below |
| `opencode` | opencode | `opencode run --format json` |
| `pi` | pi (pi.dev) | `pi --mode json -p` |
| `codex` | Codex CLI | `codex exec --json` |

## What each one does

A cell that starts with "yes" or "no" is checked against the agent's `Backend`
class by contraagent's tests. "By contraagent" means that the
runner reads the agent's events as they arrive and ends the launch past the
budget (`Backend.watched_limits`); "by the agent" means that the CLI is given the
budget and ends the launch itself.

| | claude | omp | opencode | pi | codex |
|---|---|---|---|---|---|
| A plugin reaches it | `--plugin-dir` | `--plugin-dir` | as config: its role as `instructions`, its skills as `skills.paths`, its `.mcp.json` as `mcp`, its rendered hooks as a `plugin` | its skills by `--skill`, its hooks by `-e pi/index.ts`, its `.mcp.json` through an extension of contraagent's own | as config: its role's file in the prompt, its skills linked in a `HOME` of its own, its `.mcp.json` as `mcp_servers`, its rendered hooks as `hooks` |
| A launch's MCP servers (`Launch.mcp_config`: the plugin's `.mcp.json`, or what `Pipeline(mcp_servers=)` returns) | `--mcp-config`, with `--strict-mcp-config` | the plugin's `.mcp.json`; for servers of the task's own, a copy of the plugin in a scratch directory whose `.mcp.json` holds them | as config: `mcp` | through an extension of contraagent's own | as config: `mcp_servers` |
| Role file attached to the prompt (`needs_inline_role_file`) | no: `--agent <role>` | yes | no: added to its system prompt (`instructions`) | yes | yes |
| Permissions | the plugin's `settings.json` | none: `--approval-mode yolo` | the role's `tools:` | none | its `workspace-write` sandbox |
| Stop hook continues the session (`stop_hooks_file`) | yes: `hooks/hooks.json` | yes: `omp/hooks.json`, run by `omp/index.ts` at omp's `session_stop` | no | no | yes: `codex/hooks.json` |
| Hooks rendered from `hooks.toml` | `hooks/hooks.json` | `omp/index.ts` and `omp/hooks.json` | `opencode/index.js` | `pi/index.ts` | `codex/hooks.json`, with no `read`, `grep` or `glob` hook |
| Light launch (`light_launch`) | yes | yes | yes | yes | no |
| `max_turns` enforced | yes, by the agent (`--max-turns`) | yes, by contraagent: it counts tool calls | yes, by the agent (`steps`) | no | yes, by contraagent: it counts tool calls |
| `max_budget_usd` enforced | yes, by the agent (`--max-budget-usd`) | yes, by contraagent | yes, by contraagent | yes, by contraagent | no: it reports no cost |
| `context_budget` enforced | yes, by contraagent | no | yes, by contraagent | no | no |
| `disallowed_tools` taken | yes: whole tools and patterns | yes, by an extension of contraagent's own: whole tools, and patterns of a command (`Bash`), a path read or written (`Read`, `Write`, `Edit`, `MultiEdit`), a domain (`WebFetch(domain:...)`) or a skill (`Skill`); a pattern of another tool is refused | yes: whole tools, and patterns of a command, a path, a domain or a skill | yes: whole tools only | no: the route is refused |
| Quota readings read by contraagent before each launch (`usage_reading`) | no: in its stream, when a session starts or resumes | yes: `omp usage` | yes: for an `opencode-go` model, the OpenCode Go usage | yes: as opencode | no: in its stream, with each API call of a ChatGPT login |
| Cost of a resumed session (`cost_is_session_total`) | the session's so far | each launch's own | each launch's own | each launch's own | none reported |

On an agent whose stop hook does not continue the session (opencode, pi), the
runner's check after the launch holds the output to its contract: an output that
fails goes back to the same session as a correction round
([contracts](contracts.md)). On omp, the plugin's extension (`omp/index.ts`) runs
the stop hooks of `omp/hooks.json` when the agent is about to stop, and one that
exits 2 keeps the agent working in the same session, as on Claude Code; the journal
records what it sent back (`hook_errors`). A budget that is not enforced is still
recorded: the journal holds each launch's turns, cost and peak context as the agent
reports them. On omp, the budgets contraagent enforces are read from its event stream,
which `OmpBackend(trace=False)` turns off.

omp has no flag that denies a tool. A launch whose task sets `disallowed_tools` loads
an extension of contraagent's own (`-e`), which sees each tool call before it runs. A
tool denied whole is taken out of the tools the model is offered, and a call that a
rule denies is blocked: the model is told the rule (`denied by the task's
disallowed_tools: Bash(rm:*)`). A `Bash` pattern holds each command of the line, the
parts between `&&`, `||`, `;`, `|` and `&`. A path pattern holds the file a `read`,
`write` or `edit` call names; an `Edit` pattern also denies `ast_edit` whole, since
that tool edits every file its glob finds. `WebFetch` and `Skill` are omp's `read` of
an `http(s)://` or `skill://` URL. The docstring of `OmpBackend` (`contraagent.backends`)
gives each name's omp tools. As on Claude Code, a pattern does not hold a command that
another tool runs: a `Read` pattern does not stop `bash` from printing the file.

The details are in the other topics: how each agent loads a plugin, what each one
keeps out of a launch, and how each one gets a tool, in [plugins](plugins.md); the
flags of a light launch in [contracts](contracts.md); the credential types each one
takes, and where its quota readings come from, in [routing](routing.md). The
docstring of each `Backend` class (`ClaudeBackend`, `OmpBackend`, `OpencodeBackend`,
`PiBackend`, `CodexBackend`, in `contraagent.backends`) gives its command line and
its environment in full.

## Directories outside the run

Every coding agent's launches make their scratch directories under
`<temp dir>/contraagent-<uid>/` (`<temp dir>` is `$TMPDIR`, else `/tmp`), an
owner-only directory that contraagent refuses to use when it is a symbolic link or
another user's (a `PermissionError` that names the path); on Windows,
`%TEMP%\contraagent\`, in the user's own temporary directory. The process removes
them when it exits. Besides it:

- **pi** runs with an agent directory of contraagent's own under
  `~/.cache/contraagent/pi/` (`$XDG_CACHE_HOME`, when set, in place of `~/.cache`),
  which links the user's pi logins.
- **codex** keeps its `CODEX_HOME` under `~/.cache/contraagent/` (Codex does not
  run from one under `/tmp`), and gives each launch a temporary directory of its own
  under `<temp dir>/contraagent-<uid>/`, removed when the launch ends.

## Another coding agent

A coding agent contraagent does not know is a subclass of
`contraagent.backends.Backend`: its `argv` and `env` for a `Launch`, and its
`fold`, the reader that turns its output into a `LaunchResult` (`EventFold`). Its
class attributes say what it can do, as the table above does for the built-in
ones: `light_launch`, `stop_hooks_file`, `watched_limits` (the budgets contraagent
enforces for it, through `LimitsWatch`), `needs_inline_role_file`,
`cost_is_session_total`, and `tool_deny_problem`. A backend that does not run a
process (it plays replies, as `contraagent.testing.StubAgent` does) overrides
`run`, and calls `mark_launch` once per launch so that the monitor can split its
transcript into launches. The `Backend` docstring and those of its methods give
each override.

`register_backend(name, cls)` makes it known by name, so a config's `agent =
"<name>"` and `contraagent check` take it; `Pipeline(backends={name: instance})`
gives a pipeline its own instances instead of every registered one. The monitor
renders a transcript by its stream format: `register_normalizer(format, ...)`
teaches it one, in the monitor's process. A monitor started from the command line
renders a custom agent's transcript as a built-in format with
`contraagent monitor --stream-format <agent>=<format>` (`Monitor(stream_formats=)`),
where `<format>` is one of `claude`, `omp`, `opencode`, `pi` and `codex`; with
neither, it reads the transcript as `omp`'s.
