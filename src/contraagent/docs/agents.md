# Coding agents

contraagent runs six coding agents. A kind runs on the one its route names
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
| `agy` | Antigravity CLI | `agy -p --output-format stream-json` |

## What each one does

A cell that starts with "yes" or "no" is checked against the agent's `Backend`
class by contraagent's tests. "By contraagent" means that the
runner reads the agent's events as they arrive and ends the launch past the
budget (`Backend.watched_limits`); "by the agent" means that the CLI is given the
budget and ends the launch itself.

| | claude | omp | opencode | pi | codex | agy |
|---|---|---|---|---|---|---|
| A plugin reaches it | `--plugin-dir` | `--plugin-dir` | as config: its role as `instructions`, its skills as `skills.paths`, its `.mcp.json` as `mcp`, its rendered hooks as a `plugin` | its skills by `--skill`, its hooks by `-e pi/index.ts`, its `.mcp.json` through an extension of contraagent's own | as config: its role's file in the prompt, its skills linked in a `HOME` of its own, its `.mcp.json` as `mcp_servers`, its rendered hooks as `hooks` | a directory of the launch's own, added to its workspace (`--add-dir`): its `.agents/` holds a copy of the plugin's skills, its rendered hooks behind a bridge of contraagent's own, and its `.mcp.json` as `mcp_config.json` |
| A launch's MCP servers (`Launch.mcp_config`: the plugin's `.mcp.json`, or what `Pipeline(mcp_servers=)` returns) | `--mcp-config`, with `--strict-mcp-config` | the plugin's `.mcp.json`; for servers of the task's own, a copy of the plugin in a scratch directory whose `.mcp.json` holds them | as config: `mcp` | through an extension of contraagent's own | as config: `mcp_servers` | `mcp_config.json` in that directory, each server allowed by a permission rule |
| Role file attached to the prompt (`needs_inline_role_file`) | no: `--agent <role>` | yes | no: added to its system prompt (`instructions`) | yes | yes | yes |
| How the system prompt reaches it | a file: `--system-prompt-file` | a file: `--system-prompt=<file>` | a file its config names: `{file:<file>}` for a light launch, `instructions` for another | a file: `--system-prompt <file>` | a file: `model_instructions_file` | in a light launch, the file of an agent of agy's own (`--agent`); in another launch, at the head of the prompt |
| How a `preamble` param reaches it | it does not | at the head of the prompt | at the head of the prompt | at the head of the prompt | at the head of the prompt | at the head of the prompt |
| Permissions | the plugin's `settings.json` | none: `--approval-mode yolo` | the role's `tools:` | none | its `workspace-write` sandbox | its `auto` mode, set for the launch: each command in agy's terminal sandbox, with the network, and agy's own review of a command that asks to leave it |
| Stop hook continues the session (`stop_hooks_file`) | yes: `hooks/hooks.json` | yes: `omp/hooks.json`, run by `omp/index.ts` at omp's `session_stop` | no | no | yes: `codex/hooks.json` | yes: `agy/hooks.json`, run by the bridge at agy's `Stop` |
| Hooks rendered from `hooks.toml` | `hooks/hooks.json` | `omp/index.ts` and `omp/hooks.json` | `opencode/index.js` | `pi/index.ts` | `codex/hooks.json`, with no `read`, `grep` or `glob` hook | `agy/hooks.json` |
| Light launch (`light_launch`) | yes | yes | yes | yes | no | yes |
| `max_turns` enforced | yes, by the agent (`--max-turns`) | yes, by contraagent: it counts `turn_start`, and stops the turn past the cap as it begins | yes, by the agent (`steps`) | yes, by contraagent, as on omp | yes, by contraagent: it counts the turns of the rollout file (`token_usage_record`), and stops the turn past the cap as it ends | yes, by contraagent: it counts the model's responses, and stops the turn past the cap as its text begins, or as it ends when it has no text |
| `max_budget_usd` enforced | yes, by the agent (`--max-budget-usd`) | yes, by contraagent | yes, by contraagent | yes, by contraagent | no: it reports no cost | no: it reports no cost |
| `context_budget` enforced | yes, by contraagent | no | yes, by contraagent | no | no | yes, by contraagent |
| `disallowed_tools` taken | yes: whole tools and patterns | yes, by an extension of contraagent's own: whole tools, and patterns of a command (`Bash`), a path read or written (`Read`, `Write`, `Edit`, `MultiEdit`), a domain (`WebFetch(domain:...)`) or a skill (`Skill`); a pattern of another tool is refused | yes: whole tools, and patterns of a command, a path, a domain or a skill | yes: whole tools only | no: the route is refused | yes, by a deny rule of its permissions: a command or its prefix (`Bash`), a file or a directory read or written (`Read`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`), a domain (`WebFetch(domain:...)`) or an MCP tool; another tool, or a wildcard inside a pattern, is refused |
| Quota readings read by contraagent before each launch (`usage_reading`) | no: in its stream, when a session starts or resumes | yes: `omp usage` | yes: for an `opencode-go` model, the OpenCode Go usage | yes: as opencode | no: in its stream, with each API call of a ChatGPT login | yes: `agy -p /usage`, for a Google login |
| Cost of a resumed session (`cost_is_session_total`) | the session's so far | each launch's own | each launch's own | each launch's own | none reported | none reported |

On an agent whose stop hook does not continue the session (opencode, pi), the
runner's check after the launch holds the output to its contract: an output that
fails goes back to the same session as a correction round
([contracts](contracts.md)). On omp, the plugin's extension (`omp/index.ts`) runs
the stop hooks of `omp/hooks.json` when the agent is about to stop, and one that
exits 2 keeps the agent working in the same session, as on Claude Code; the journal
records what it sent back (`hook_errors`). Claude Code, Codex, omp and agy tell a stop hook
that runs after an objection in the same round (`stop_hook_active` true in its JSON),
so the plugin's stop hook objects at most once per round. Each objection is a
correction, and `max_corrections` counts them with the correction rounds. A budget that is not enforced is still
recorded: the journal holds each launch's turns, cost and peak context as the agent
reports them. On omp, the budgets contraagent enforces are read from its event stream,
which `OmpBackend(trace=False)` turns off.

Codex prints a launch's token totals in its `turn.completed` event, and each API call's
tokens, the model's context window and the plan's quota only in its rollout file
(`$CODEX_HOME/sessions/`), a file of its own that contraagent reads after the launch.
Its calls are checked against the printed totals. When the file is
missing, holds nothing this contraagent can read, or does not add up, the launch keeps
the printed totals as one call, has no quota reading, and its journal row says so:
`usage_unknown` is `calls`, or `tokens` when the launch printed no totals either. The
monitor marks such an attempt. After a newer Codex, a run whose rows show
`usage_unknown` needs a newer contraagent for its per-call tokens and its peak context.

No text of a task is on an agent's command line or in its environment: Linux does not
start a process with one argument or variable longer than 131,072 bytes, and the
instructions of a light launch hold its params. A system prompt is a file in the
launch's scratch directory, which only the user can read, and the command line holds
its path. A prompt longer than 60,000 bytes in UTF-8 (16,000 UTF-16 code units on
Windows) goes over stdin, and a `preamble` param goes at the head of the prompt, in its
one first message. Codex takes `Launch.append_system_prompt` at the head of the prompt
too: it has no file for developer instructions.

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

omp reads two files of the directory it runs in when it starts. `.omp/config.yml` holds
the project's settings, its model chains (`retry.fallbackChains`) among them, and `.env`
fills each variable that the launch's environment leaves unset, a provider's key among
them; omp lists the models of each provider it has a key for. A launch runs in its
task's working directory: the one its task call names (`.options(cwd=)`), else the run's
(`Pipeline(cwd=)`). contraagent reads these files in the same directory, never in the
directory the pipeline process was started in. The checks before the first launch look
in the run's working directory, and in the directory of each task call that names one,
for a key in `.env` that would undo a credential's isolation ([routing](routing.md)).
The model list that `contraagent check` and the preflight compare each route's model
with is the one omp gives in the run's working directory. The preflight probes each
route there, and its line on omp's own model chain is that directory's; a task in
another directory runs with the settings of that directory. A git worktree holds `.env`
and `.omp/` only when git tracks them, so a flow that gives a task a worktree of its own
copies them there when omp needs them ([tasks](tasks.md)).

agy has no flag for a plugin, an MCP server or a system prompt: it finds them in the
`.agents/` directory of each folder of its workspace. A launch gets a directory of its
own, made afresh in its scratch directory and added to the workspace (`--add-dir`). Its
`.agents/` holds a copy of each skill of the task's plugins (agy follows no link to a
skill), a `hooks.json` and the launch's MCP servers (`mcp_config.json`). agy's hooks read
and answer in a form of their own, and agy fails a tool call whose hook exits with
another status than 0. So each handler of that `hooks.json` runs `contraagent plugin
hook --agent agy`, which runs the plugin's hooks of `agy/hooks.json` with the input
Claude Code sends and answers agy in its own terms. A `pre_tool` script that exits 2
denies the call with its words, and a `stop` hook that exits 2 continues the session
with them. agy takes no words from a hook that runs after a tool, so the words of a
`post_tool` script that exits 2 reach the model before its next response, as a message
of the system. agy's stream does not show what a hook said: the bridge records each
objection of a stop hook in the launch's scratch directory, and the journal holds it
(`hook_errors`).

An agent of agy's own has only the tools its file lists, and none when it lists none.
So a role is not such an agent: its file is attached to the prompt. A light launch
runs as one, whose file is the launch's system prompt, with no tools and with none of
the workspace's customizations. Every other launch on agy reads the rules and the
`.agents/` directory of its working directory and of each directory above it up to
the repository's root (`AGENTS.md`, `GEMINI.md`), and the user's own under
`~/.gemini/`: agy has no switch for them.

`agy -p` takes its prompt on its command line only. A prompt longer than 60,000 bytes
goes over stdin as one JSON message (`--input-format stream-json`). agy reports the
tokens of each response and no cost, and a resumed conversation's totals count its
earlier launches, so a launch's tokens are those of its own responses. A resume that
names a conversation agy does not find would start a new one: contraagent ends such a
launch as it starts (`error`).

A launch on agy runs in agy's `auto` mode, which the launch sets for itself (`agentMode`
in its settings), whatever mode the user saved. In that mode agy edits files without
asking and runs each command in its terminal sandbox. agy's sandbox has no network by
itself, and reaches the domains a permission rule lets agy read. A launch allows every
domain (`read_url(*)`), so a command reaches the network inside the sandbox, as on
Codex. A task that denies `WebFetch` (`disallowed_tools`) gets no such rule, and its
commands have no network there. A command that asks to leave the sandbox is reviewed
by agy itself, and runs when the review lets it through. In agy's other modes a command needs an approval, and a headless
session has nobody to give one: agy then ends the launch at that call, with no
output. It does the same in `auto` mode for a command its review does not let
through, and for every command on an account that has no `auto` mode. Such a launch
ends `denied`, and its reason and its `denied` in `launches.jsonl` name the call. So a
task whose commands need a path the sandbox does not reach depends on agy's review of
each of them. agy does not review what a command sends from inside the sandbox.

agy names a model's reasoning level in the model's id (`gemini-3.8-flash-high`), or
takes it as an effort beside an id that names none (`model = "gemini-3.8-flash"` with
`effort = "high"`). It refuses an effort beside an id that names a level, and beside a
model that has no levels. So a launch passes `effort` only with a model id that names
no level, and not for a model that `agy models` lists without one. `agy models` prints
the ids of the login's plan, and `contraagent check` compares a route's model with them.

The tool names a hook script sees on agy are those of the tools agy gives the model.
agy 1.5.9 gives its Gemini, Claude and GPT models the same ones: `run_command`,
`read_file`, `write_file`, `edit_file` and `search_web`, which reach a script as `Bash`,
`Read`, `Write`, `Edit` and `WebSearch` with Claude Code's argument names. These models
list and search files with shell commands, which a `bash` hook sees. agy's
documentation lists other tool names for hooks (`view_file`, `write_to_file`,
`replace_file_content`, `grep_search`, `find_by_name`, `list_dir`,
`read_url_content`): for one of them a script gets Claude Code's tool name and agy's
own argument names.

The details are in the other topics: how each agent loads a plugin, what each one
keeps out of a launch, and how each one gets a tool, in [plugins](plugins.md); the
flags of a light launch in [contracts](contracts.md); the credential types each one
takes, and where its quota readings come from, in [routing](routing.md). The
docstring of each `Backend` class (`ClaudeBackend`, `OmpBackend`, `OpencodeBackend`,
`PiBackend`, `CodexBackend`, `AgyBackend`, in `contraagent.backends`) gives its command line and
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
  which links the user's pi logins. pi refreshes a login under a lock in the directory
  it runs with, so a pi that the user runs on the same login at the same time does not
  wait for the refresh of a launch. Some providers replace the refresh token at each
  refresh, and then one of the two is left with a token that no longer works. While a
  pipeline uses a pi login, the user does not run pi on that login. A launch that ends
  `auth_failed` on a pi login says this in its reason.
- **codex** keeps its `CODEX_HOME` under `~/.cache/contraagent/` (Codex does not
  run from one under `/tmp`), and gives each launch a temporary directory of its own
  under `<temp dir>/contraagent-<uid>/`, removed when the launch ends.
- **agy** saves every conversation under `~/.gemini/antigravity-cli/`, the user's own
  directory: it has no flag that names another one. A launch whose session is not kept
  for a resume removes its conversation there when it ends (`conversations/<id>.db`,
  `brain/<id>/` and `presence/<id>.lock`); a conversation kept for a correction round is removed after the last
  round.

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
where `<format>` is one of `claude`, `omp`, `opencode`, `pi`, `codex` and `agy`; with
neither, it reads the transcript as `omp`'s.
