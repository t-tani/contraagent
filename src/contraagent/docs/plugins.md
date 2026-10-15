# Plugins

The prompt carries no task knowledge. The runner writes the task's data to a
**call file** (its params, the output path, format and JSON Schema, where to
import the model from, the command validators), and the prompt only says
"carry out this call". What to do is the plugin's; what to do it *with* is the
call file's. A plugin can be tried on its own with a call file written by hand.

```
agent_task (interface) ──► call file ──► coding agent + plugin (implementation)
                                             │  stop hook: checks the output in-session
                                             ▼
                          runner: checks the output again, resumes the session if it fails
```

## Layout

A plugin is a directory Claude Code and omp load natively (`--plugin-dir`);
opencode gets its parts as config (its role as `instructions`, its skills as
`skills.paths`, its `.mcp.json` as `mcp`, its rendered hooks as a `plugin`), and
Codex, which loads no plugin directory, its role's file, its skills and its
`.mcp.json` (below). The
docstring of `contraagent/_internal/plugins/plugin.py` lists its parts. The demo's:

```
examples/demo/plugins/docs/
  .claude-plugin/plugin.json
  agents/                  one role per kind of work: its procedure
    summarizer.md
    reviewer.md
    reviser.md
    writer.md
  skills/write-output/SKILL.md
  hooks.toml               hooks, declared once for every coding agent
  hooks/hooks.json         rendered for Claude Code
  settings.json            permissions
```

## Roles

A role is a named agent definition. Claude Code gets `--agent <role>`; omp,
which has no named-agent flag, gets the role's file attached, and Codex gets it
in its prompt; opencode gets it
added to its own system prompt (`instructions`: opencode's free models refuse a
session whose system prompt is replaced). The plugin's `settings.json` (what the
agent may do) is Claude Code's; omp runs with `--approval-mode yolo` and Codex in
its `workspace-write` sandbox, so there a role is held to its procedure, not to
permissions. opencode allows the tools
the role's `tools:` lists and denies the others. A role reads its
call file, does the work, writes the output as the call describes, and stops:

::code{file="examples/demo/plugins/docs/agents/summarizer.md"}

## Skills several tasks share

A task's own plugin holds its role, and so its permissions, tools and hooks. A
skill that tasks with different roles share goes in a skill plugin of its own:
a plugin with `skills/` and nothing else that acts (no `agents/`, `commands/`,
`settings.json`, `.mcp.json` or hooks). Each task names it in `skills_from`:

::code{file="examples/skills/tasks.py" from="summarize = agent_task(" to="def notes("}

The coding agent loads the task's plugin first, then each skill plugin
(`--plugin-dir`, in that order); the role, `settings.json` and `.mcp.json` come
from the task's plugin alone. Claude Code names a skill `<plugin name>:<skill>`
(`house-style:house-style`). A skill plugin that holds anything else is refused
where the task is declared, since it would act on every task that loads it.
`plugin lint` checks a skill plugin's skills only, and `contraagent check` lints
every plugin a task loads. A skill plugin declares no hooks, so `plugin render`
writes nothing in it; files an earlier render left there (`package.json`,
`hooks/`, `omp/`, `opencode/`, `pi/`) are named as such by `plugin lint`. The skills' text is part of each task's fingerprint,
as its role file is: a resume runs a task again after its skills changed.

## An implementation per unit

When one step needs different tools for different units (a Python module and a
Go package, or units on hosts with different local tools installed), one
declaration names each implementation, a plugin directory by name. Every other
argument is shared, and the flow chooses the implementation from a fact about
the unit:

::code{file="examples/implementations/flow.py" from="review = agent_task(" to="return counts"}

Each implementation is a kind of its own, `<kind>-<name>` (`review-python`,
`review-go`); `review` is their base kind. `review["go"]` is the declaration of
`review-go`, `review.kinds` lists the kinds, and `review` iterates over the names
as a dict does. Each kind keeps what is its own:

- its definition: its role, skills, permissions and `.mcp.json` (each plugin starts
  its own MCP servers; a session never loads the other's), and its fingerprint,
  so a resume runs again only the tasks of the kind whose role or skills changed;
- its routing: the base kind's `[tasks.review]` table is every implementation's,
  and a `[tasks.review-go]` table changes one implementation's coding agent, model,
  budget or credential key by key; its `fallbacks` replace the base kind's chain;
- in the monitor, its row in Definitions and its numbers in the trends. Its tasks
  are drawn in the base kind's group (one column of the plan, and one line of the
  trends' cost), unless `Monitor(groups=)` (`--groups`) puts the kind in a group.

::code{file="examples/reference/pipeline.toml" from="# A base kind's table" to="timeout_s = 900"}

Every implementation kind is a reachable kind, so `contraagent check` routes and
lints each before the first launch, even before the flow creates a task of it.

## What a task agent sees

A task agent's instructions come from its plugin and its call file. Every coding
agent would also take on what it finds in the task's working directory and the
user's home; every launch keeps that out, and keeps what the agent itself can do:

| | kept out | kept |
|---|---|---|
| Claude Code | the user's, the project's and local settings files (their hooks, skills, commands, agents, plugins, permissions), CLAUDE.md files, auto-memory, skills synced from the account | its built-in tools, skills, subagents and plugins; the task's plugin (roles, skills, hooks, `settings.json`, `.mcp.json`) and the skills of its `skills_from` |
| omp | AGENTS.md, CLAUDE.md, `.omp/`, `.claude/` and other tools' context files, skills, rules, hooks, tools and MCP servers; the user's installed Claude Code plugins | its built-in tools and subagents; the task's plugin and the skills of its `skills_from` |
| opencode | the project's AGENTS.md, `opencode.json` and `.opencode/`; the user's `~/.claude/` (CLAUDE.md, skills) and `~/.agents/` skills; the user's opencode database (a session is kept in memory, or in its own directory when it may be resumed) | its built-in tools, skills and agents; the user's own opencode config (`~/.config/opencode`); the task's plugin and the skills of its `skills_from` |
| pi | AGENTS.md, CLAUDE.md, `.pi/` and `.agents/` files; the user's pi settings, `SYSTEM.md`, extensions, skills, prompt templates and MCP servers | its built-in tools; the user's pi logins and custom providers (`ambient`, `subscription`); the task's plugin (skills, hooks, `.mcp.json`) and the skills of its `skills_from` |
| Codex | AGENTS.md, the project's skills (`.agents/skills`, `.codex/skills`), the user's skills (`~/.agents/skills`), plugins, hooks and execpolicy rules; with any credential but `ambient`, the user's `config.toml` | its built-in tools and skills; the task's role, skills and `.mcp.json`, and the skills of its `skills_from` |

A launch also leaves out the variables that tie it to a Claude Code session the
pipeline was started from. A skill, a hook, a permission or an MCP server a task
needs belongs in its plugin. omp's part is the overlay
`contraagent/_internal/backends/omp/isolation/config.yml`; opencode's, the variables in
`DEFAULT_ENV` of `contraagent/_internal/backends/opencode/backend.py`. pi runs with an agent
directory of contraagent's own (`PI_CODING_AGENT_DIR`, under
`~/.cache/contraagent/pi/`) that links the user's logins and holds nothing else of
theirs, and with its discovery turned off by flag (`contraagent/_internal/backends/pi/agent_dir.py`).
Codex finds skills only in fixed places, so it runs with a `HOME` of its own whose
`.agents/skills` links to each skill of the task's plugin, then of its
`skills_from` (a name already taken is not linked again); the commands it runs see
the real `HOME`. It names a skill `<plugin name>:<skill>`, as Claude Code does.

A task declared with no tools (`agent_task(tools=())`, a light launch) keeps less
still: no tool, no plugin, and its role's text in place of the coding agent's own
system prompt (see "A judgement in one turn" in [contracts](contracts.md)).

## Tools a task may use

A task gets a tool through its plugin, and each coding agent reads a different
part of it:

| | how a task gets a tool | web search |
|---|---|---|
| Claude Code | the role's `tools:` frontmatter lists it, and the plugin's `settings.json` allows it; a call nothing allows is denied (the launch's `denied` in `launches.jsonl`) | `WebSearch` and `WebFetch` in `tools:`, and `"allow": ["WebSearch", "WebFetch(domain:docs.python.org)"]` with both left out of `deny` |
| omp | every built-in tool is on; it runs `--approval-mode yolo` and reads neither `tools:` nor `settings.json` | the built-in `web_search` (`web_search.enabled`, on by default), with the search provider configured in omp; a page is read with `read` and its URL (`fetch.enabled`) |
| opencode | the role's `tools:` lists it (Claude Code's names, as opencode's permissions); with no `tools:`, every built-in tool is on. It runs `--auto` and does not read `settings.json` | `websearch` (opencode's own search, where opencode offers it) and `webfetch` |
| pi | its default tools are on (`read`, `bash`, `edit`, `write`), and the tools of the plugin's MCP servers; it asks no permission and reads neither `tools:` nor `settings.json` | none built in: a plugin's MCP server or a script the task runs |
| Codex | every built-in tool is on; it runs in its `workspace-write` sandbox (network on) and reads neither `tools:` nor `settings.json` | the built-in `web_search`, which also opens a page by its URL |

`contraagent plugin new` denies `WebFetch` and `WebSearch` so that a Claude
Code task stays on its inputs; a task that searches removes them from `deny`.
The queries a launch made are in its journal row (`web_queries`), for every
coding agent.

## Hooks

Hooks are declared once, agent-neutrally, and rendered into each coding agent's
own hook system, so they run inside the agent:

::code{file="examples/demo/plugins/docs/hooks.toml"}

| event | claude | omp, pi | opencode |
|---|---|---|---|
| `pre_tool` | `PreToolUse`; exit 2 blocks | `tool_call` event, returns `{block, reason}` | `tool.execute.before`; exit 2 blocks, the reason is the error the agent sees |
| `post_tool` | `PostToolUse`; exit 2 sends the script's words to the agent | `tool_result` event; exit 2 adds the script's words to the result the agent sees | `tool.execute.after`; exit 2 adds the script's words to the tool's output |
| `stop` | the agent checks its own file and carries on in the same turn | none: `omp -p` and `pi -p` cannot continue a session from it; the runner's check resumes the session instead | none, as on omp: `opencode run` ends once the session is idle |

On every agent, a `post_tool` script that exits 2 has the agent fix what it says
in the same session (checked live on each).

Hook scripts read the JSON Claude Code sends hooks; the omp and pi extensions
(`omp/index.ts`, `pi/index.ts`, both declared in `package.json`) and the opencode
plugin (`opencode/index.js`) build the same
payload, so one script serves every agent. The tool input comes in Claude Code's
names whatever the agent calls its arguments:

| Claude Code | omp | pi | opencode |
|---|---|---|---|
| `file_path` (Read, Write, Edit) | `path` | `path` | `filePath` |
| `old_string`, `new_string` (Edit) | `old_string`, `new_string` | `edits: [{oldText, newText}]`, when it holds one edit | `oldString`, `newString` |
| `replace_all` (Edit) | `replace_all` | none | `replaceAll` |
| `command`, `pattern`, `path` (Bash, Grep, Glob), `content` (Write) | the same | the same | the same |

The `tool` of a hook names the tool as `hooks.toml` does (`bash`, `read`, `write`,
`edit`, `grep`, `glob`), so a `glob` hook runs on pi's and omp's `find` too.

## Commands

```
contraagent plugin new plugins/<name>     # a working plugin from the template
contraagent plugin lint plugins/<name>    # its parts agree: roles, skills, JSON, hook scripts, rendered hooks
contraagent plugin render plugins/<name>  # each coding agent's native hooks from hooks.toml
```

A role `agent_task` names that the plugin does not define is an error where the
task is declared.
