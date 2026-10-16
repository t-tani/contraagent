# docs

The implementation of agent tasks, one role per kind of work: a plugin that the coding agents load (`claude`, `omp`, `opencode`, `pi`, `codex`).
Each task's interface (parameters, output schema, budget) is the `agent_task(..., plugin=..., role=...)` that names it.

| File | What it decides |
|---|---|
| `agents/<role>.md` | **the task**: one role per kind of work, who the agent is and how it works |
| `skills/` | detail the agent loads when it needs it |
| `settings.json` | what the agent may do |
| `hooks.toml` | hooks, declared once (the stop hook checks the output in-session) |
| `hooks/hooks.json`, `codex/hooks.json`, `package.json`, `omp/index.ts`, `omp/hooks.json`, `opencode/index.js`, `pi/index.ts` | **generated** from `hooks.toml` by `contraagent plugin render` |

Each task's data arrives in a call file the prompt names; nothing here mentions a run or a path.
`contraagent plugin lint .` checks that the parts agree.
