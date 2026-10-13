# contraagent

Run coding-agent CLIs (`claude -p`, `omp -p`) as typed, supervised, observable
tasks.

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
