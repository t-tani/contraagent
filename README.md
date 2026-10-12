# contraagent

Run coding-agent CLIs (`claude -p`, `omp -p`) as typed, supervised, observable
tasks.

This repository holds three packages, each with its documentation:

| Package | What it is | Documentation |
|---|---|---|
| `contraagent` (Python) | pipelines of coding-agent tasks, their runner, the monitor | [src/contraagent/docs/](src/contraagent/docs/README.md) |
| `@contraagent/ui` (npm) | the monitor and its views as web components | [web/packages/ui/](web/packages/ui/README.md) |
| `@contraagent/api` (npm) | the typed client for the monitor's API | [web/packages/api/](web/packages/api/README.md) |

The documentation site renders all three: `pnpm docs` in `web/`.

Working on contraagent itself: [AGENTS.md](AGENTS.md). Changes:
[CHANGELOG.md](CHANGELOG.md). MIT licensed.
