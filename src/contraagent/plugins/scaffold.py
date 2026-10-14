"""The plugin template: `contraagent plugin new plugins/<name>`.

A working plugin for one agent task: a role whose procedure reads the call
file, a skill on writing the output, permissions, and the in-session check.
Edit `agents/worker.md`: it is the task.
"""

from __future__ import annotations

from pathlib import Path

from contraagent.plugins import hooks
from contraagent.plugins.plugin import PLUGIN_JSON, Plugin, is_plugin

FILES: dict[str, str] = {
    str(PLUGIN_JSON): """{
  "name": "@NAME@",
  "description": "contraagent agent-task plugin: @NAME@",
  "version": "0.1.0"
}
""",
    "agents/worker.md": """---
name: worker
description: Carries out one @NAME@ task call and reports it through the output file the call names.
tools: Read, Write, Edit, Bash, Grep, Glob
---

You carry out one task and report it through a file, never through chat.

1. Read the call file the prompt names. `params` is what you are given;
   `output` is the file you must leave behind and the schema it must match.
2. Do the work. Look things up in what `params` points to; do not guess.
3. Write the output file exactly as `output` describes (skill `write-output`).
4. Stop. A hook checks your file before you finish; if it reports errors, fix
   the file and stop again.
""",
    "skills/write-output/SKILL.md": """---
name: write-output
description: How to write a task's output file so it passes its checks. Use whenever you are about to write the output file named in a call file.
---

# Writing the output file

- `output.format` "json": the file is a single JSON document matching `output.json_schema`.
  No markdown, no code fences, no comments, no trailing commas.
- `output.from` "message": the output is your final message, not a file. End with the
  document as your whole message, by the same rules, and write no file.
- Field names and types are exactly those in the schema. Do not add fields; do not rename them.
- A list field is always a list, even with one element or none.
- Copy identifiers (`unit`) from the call file, never from memory.
- Write the file once, complete. A half-written file is checked as written.
- If a hook reports errors, they name the field (or the linter rule) and what was wrong.
  Fix that; do not redo the analysis.
""",
    "settings.json": """{
  "permissions": {
    "allow": ["Read", "Write", "Edit", "Grep", "Glob", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)"],
    "deny": ["WebFetch", "WebSearch"]
  }
}
""",
    "hooks.toml": """# Hooks, declared once for every coding agent. `contraagent plugin render` writes
# from this file hooks/hooks.json (Claude Code) and package.json (omp), and for a
# pre_tool or post_tool hook omp/index.ts and opencode/index.js, which run it in omp
# and opencode.

# The output check, inside the session: the agent fixes its file before it stops.
[[hooks]]
on = "stop"
run = "validate"

# [[hooks]]
# on = "pre_tool"            # exit 2 from the script blocks the call
# tool = "bash"
# match = "rm -rf"
# script = "hooks/guard.sh"
""",
    "README.md": """# @NAME@

The implementation of agent tasks: a plugin Claude Code and omp load with `--plugin-dir`, one role per kind of work.
Each task's interface (parameters, output schema, budget) is the `agent_task(..., plugin=..., role=...)` that names it.

| File | What it decides |
|---|---|
| `agents/<role>.md` | **the task**: one role per kind of work, who the agent is and how it works |
| `skills/` | detail the agent loads when it needs it |
| `settings.json` | what the agent may do (Claude Code; omp runs every built-in tool). It denies `WebFetch` and `WebSearch`: a task that searches the web removes them from `deny`, allows them (`WebFetch(domain:...)`) and lists them in its role's `tools:` (`contraagent docs plugins`) |
| `hooks.toml` | hooks, declared once (the stop hook checks the output in-session) |
| `hooks/hooks.json`, `package.json`, `omp/` | **generated** from `hooks.toml` by `contraagent plugin render` |

Each task's data arrives in a call file the prompt names; nothing here mentions a run or a path.
`contraagent plugin lint .` checks that the parts agree.
""",
}

#: What an agent task with no plugin may do in Claude Code (`agent_task(instructions=)`):
#: the template's `settings.json`, passed as `--settings`. Without it, headless Claude Code
#: denies the `Write` of the output file.
DEFAULT_SETTINGS = FILES["settings.json"]


def new_plugin(directory: str | Path, name: str = "") -> list[Path]:
    """Write the template into `directory`. Refuses to overwrite an existing plugin."""
    root = Path(directory)
    if is_plugin(root):
        raise FileExistsError(f"{root} already holds a plugin ({PLUGIN_JSON})")
    name = name or root.name
    written = []
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.replace("@NAME@", name))
        written.append(path)
    rendered, _ = hooks.write(Plugin.load(root))  # the hooks, for every coding agent
    return written + [p for p in rendered if p not in written]
