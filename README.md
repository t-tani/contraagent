# contraagent

Run coding-agent CLIs (`claude -p`, `omp -p`, `opencode run`, `pi -p`, `codex exec`) as typed,
supervised, observable tasks.

```
uv add 'contraagent[monitor]'
```

The main path: the tasks and the flow in `tasks.py`, how the agent does each task in
a plugin (`contraagent plugin new`), `contraagent check` and a stub run before
anything is spent, `contraagent run` on the coding agent the config names, and
`contraagent monitor` to watch it. The
[tutorial](src/contraagent/docs/tutorial.md) takes these steps from an empty
directory.

This repository holds four packages, each with its documentation:

| Package | What it is | Documentation |
|---|---|---|
| `contraagent` (Python) | pipelines of coding-agent tasks, their runner, the monitor | [src/contraagent/docs/](src/contraagent/docs/README.md) |
| `@contraagent/ui` (npm) | the monitor and its views as web components | [web/packages/ui/](web/packages/ui/README.md) |
| `@contraagent/elements` (npm) | generic web components (`cae-*`), themes and design tokens, with no contraagent data | [web/packages/elements/](web/packages/elements/README.md) |
| `@contraagent/api` (npm) | the typed client for the monitor's API | [web/packages/api/](web/packages/api/README.md) |

The documentation site renders all four: `pnpm docs` in `web/`. The npm
packages are not in the npm registry: `pnpm tarballs` in `web/` packs them for
installing from this checkout.

Working on contraagent itself: [AGENTS.md](AGENTS.md). Changes:
[CHANGELOG.md](CHANGELOG.md). MIT licensed.
