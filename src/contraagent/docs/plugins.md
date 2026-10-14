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

A plugin is a directory Claude Code and omp load natively (`--plugin-dir`); the
docstring of `contraagent/plugins/plugin.py` lists its parts. The demo's:

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
which has no named-agent flag, gets the role's file attached. The plugin's
`settings.json` (what the agent may do) is Claude Code's; omp runs with
`--approval-mode yolo`, so on omp a role is held to its procedure, not to
permissions. A role reads its
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
`hooks/`, `omp/`) are named as such by `plugin lint`. The skills' text is part of each task's fingerprint,
as its role file is: a resume runs a task again after its skills changed.

## What a task agent sees

A task agent's instructions come from its plugin and its call file. Both coding
agents would also take on what they find in the task's working directory and the
user's home; every launch keeps that out, and keeps what the agent itself can do:

| | kept out | kept |
|---|---|---|
| Claude Code | the user's, the project's and local settings files (their hooks, skills, commands, agents, plugins, permissions), CLAUDE.md files, auto-memory, skills synced from the account | its built-in tools, skills, subagents and plugins; the task's plugin (roles, skills, hooks, `settings.json`, `.mcp.json`) and the skills of its `skills_from` |
| omp | AGENTS.md, CLAUDE.md, `.omp/`, `.claude/` and other tools' context files, skills, rules, hooks, tools and MCP servers; the user's installed Claude Code plugins | its built-in tools and subagents; the task's plugin and the skills of its `skills_from` |

A launch also leaves out the variables that tie it to a Claude Code session the
pipeline was started from. A skill, a hook, a permission or an MCP server a task
needs belongs in its plugin. omp's part is the overlay
`contraagent/backends/omp/isolation/config.yml`.

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

`contraagent plugin new` denies `WebFetch` and `WebSearch` so that a Claude
Code task stays on its inputs; a task that searches removes them from `deny`.
The queries a launch made are in its journal row (`web_queries`), for both
coding agents.

## Hooks

Hooks are declared once, agent-neutrally, and rendered into each coding agent's
own hook system, so they run inside the agent:

::code{file="examples/demo/plugins/docs/hooks.toml"}

| event | claude | omp |
|---|---|---|
| `pre_tool` | `PreToolUse`; exit 2 blocks | `tool_call` event, returns `{block, reason}` |
| `post_tool` | `PostToolUse` | `tool_result` event |
| `stop` | the agent checks its own file and carries on in the same turn | none: `omp -p` cannot continue a session from it; the runner's check resumes the session instead |

Hook scripts read the JSON Claude Code sends hooks; the omp extension builds the
same payload, so one script serves both.

## Commands

```
contraagent plugin new plugins/<name>     # a working plugin from the template
contraagent plugin lint plugins/<name>    # its parts agree: roles, skills, JSON, hook scripts, rendered hooks
contraagent plugin render plugins/<name>  # each coding agent's native hooks from hooks.toml
```

A role `agent_task` names that the plugin does not define is an error where the
task is declared.
