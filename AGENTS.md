# contraagent

`contraagent` runs coding-agent CLIs (`claude -p`, `omp -p`, Codex, opencode, pi)
as typed, supervised tasks: a Python package (`src/contraagent/`) and a web monitor
(`web/`). This file is for agents changing contraagent itself. Before changing
anything under `web/`, read `web/AGENTS.md`.

## Commands

```
uv run ruff check . && uv run ruff format --check .
uv run pyright                # 0 errors; the "yaml" source warning is expected
uv run pytest                 # parallel (xdist, at most 6 workers; -n0 for one); runs lint-imports too
uv run pytest -m e2e          # the hub and relays as processes over Postgres and RustFS (docker)
CONTRAAGENT_LIVE=1 uv run pytest -m live   # real coding agents; spends tokens
```

A committed file that a test compares against goes stale when its source changes;
the test names it. Rewrite it with:

| After changing | Run |
|---|---|
| the public API | `uv run python tests/api/snapshot.py` (`tests/api/contraagent.api.txt`) |
| a command's arguments or help | `uv run python tests/cli/help.py` (`tests/cli/help.txt`, on the Python of `.python-version`) |
| a monitor response model or route | `uv run contraagent monitor --openapi src/contraagent/_internal/monitor/openapi.json`, then `pnpm gen` in `web/` |
| a run record model or the config's tables | `uv run python -m contraagent._internal.execution.file_schemas` (`src/contraagent/docs/schemas/`) |
| what the monitor returns | `uv run python web/apps/docs/scripts/fixture.py` (the docs site's fixtures) |
| what the CLI prints on the demo | `uv run python web/apps/docs/scripts/landing.py` |
| the omp version | `uv run python tests/fixtures/omp/record.py` (spends a few cents), then `tests/test_omp_wire.py` |

Release checks: `uv run pyright --verifytypes contraagent --ignoreexternal` (no unknown
type outside `contraagent.docs`), `uv run griffe check --search src contraagent --against
<last tag>` (breaking changes since a release; tags are `<version>`),
`docker build -t contraagent-hub:dev .` (the hub's image).

### Releasing

A pushed tag `X.Y.Z` releases: `.github/workflows/release.yml` checks that the tag,
pyproject.toml, the three package.json and CHANGELOG.md agree, runs ci.yml, and
publishes to PyPI and npm. The steps and the one-time setup are in
[docs/releasing.md](docs/releasing.md).

A test never waits out a retry's backoff (`RetryingRunner.backoff` is 0 in the tests).
Tests that share something across a module (one hub, the `live-demo` directory, an
agent's rate limits) carry an `xdist_group`.

## One word, one meaning

The glossary is `src/contraagent/docs/concepts.md`. Every word there means exactly
one thing in the code, the files a run writes, the monitor (API and UI), the
documentation and the examples. Do not use one of these words in another sense, and
do not add a second word for the same thing; a new word goes into the glossary first.
The monitor's UI shows its own reader-facing words for the same terms
(`web/packages/ui/WORDS.md`).

Some names stay although they look like a second word: `--agent` (Claude Code's flag,
from `Launch.role`), `Backend`/`create_backend`/`register_backend`/`known_agents` (keyed
by agent name), `[tasks.<kind>]` and `kind`, `Route`/`Router`/hop (the failover chain:
a route is one entry, a hop one launch on one route), `ambient` (the host's own
credential), `effort`/`max_turns`/`max_budget_usd` (the agents' flag names), cursor
`stage`, `streams/` and `*.stream.jsonl`, `hollow` (see `LaunchResult`), `RoutingPlan`
(`plan.jsonl` is the queue), `run_until_valid(max_resumes=)` (the count a kind's
`max_corrections` gives it).

## Public API and layers

The implementation is under `src/contraagent/_internal/`. Users import only the
public modules (`contraagent`, `.config`, `.backends`, `.engine`, `.plugins`,
`.monitor`, `.monitor.api`, `.testing`); each only re-exports names from `_internal`
and calls `publish(__name__, __all__)`. A name that a user, the documentation or an
example uses gets one public home; everything else stays in `_internal`. Keep public
signatures small: a helper hides behind a method, a value returns the type it behaves
as, and a function a user passes is a `Protocol`. `tests/test_public_api.py` checks
the rest (one path per object, every reached type exported, no `**kwargs`, full types).

Inside `_internal`, a layer imports only the layers listed before it in the
`_internal/__init__.py` docstring; pass a callback or a protocol instead of importing
a later layer. Every reader and writer of a run's files goes through `runs/`.
`uv run lint-imports` checks this (pyproject.toml's
`[tool.importlinter]`; an exception only as a commented `ignore_imports` line), and
`tests/test_layers.py` runs it.

## Documentation

Each package holds its own documentation; its index lists its topics, and that list
is the site's sidebar and what `contraagent docs` prints:
`src/contraagent/docs/README.md`, `web/packages/ui/README.md`,
`web/packages/elements/README.md`, `web/packages/api/README.md`.

- The package documentation, the docstrings and the messages of `contraagent check`
  are written for a coding agent that writes a pipeline from them alone: every fact it
  needs is reachable from `contraagent docs`, without contraagent's source. The root
  `README.md` and the monitor are for the person who asks for the pipeline, runs it
  and reviews it.
- Code is quoted, never pasted: `::code{file="..." from="..." to="..."}`. The examples
  run in the tests (`tests/test_docs.py`), so update them with any API change. The root
  `README.md` writes its code out, after `<!-- ::code{...} -->` lines that the same
  test checks.
- Facts live in the code (docstrings, `--help`, `examples/reference/pipeline.toml`,
  `custom-elements.json`, `openapi.json`); prose points to them.
- The site (`web/apps/docs`) is built from the packages' documentation by
  `scripts/collect.py`; see `web/AGENTS.md`.

Prose style, for the READMEs and topics: plain declarative sentences and short
paragraphs. A paragraph or list item starts with a sentence that carries its point,
not a bold run-in label; a part that needs a label gets a heading. Bold marks at most
a few words in a page. A link sits on the words it names, never in a parenthetical
after them. No slogan fragments, no "Label: fragment" sentences; vary the openings.
Write global English: common words, no idioms, phrasal verbs or slang, no
abbreviations but API, JSON, CLI, USD and units; the text must keep its meaning
through machine translation.

## Changes and commits

- A user-visible change adds a fragment `changelog.d/<slug>.<type>.md` (types and
  rules in `changelog.d/README.md`); towncrier writes `CHANGELOG.md` at a release.
  `uv run towncrier check --compare-with origin/main` checks a branch.
- A change reaches `main` through a pull request: push a branch and open one. CI runs
  on the pull request only, and its jobs must pass, on a branch up to date with
  `main`, before the merge, a merge commit. Nobody pushes to `main` or rewrites it. A
  pull request's description follows the same style as a commit message.
- Commit messages follow Google's CL description style: a short imperative first
  line, a blank line, then a body that says what changed and why, wrapped at about
  72 columns. No attribution trailers (`Co-Authored-By`, session links), no model
  names, no local paths.

## Compatibility

The public API is what `src/contraagent/docs/compatibility.md` lists: the public
modules' `__all__`, the command line, the config file, the files a run writes and the
monitor's `openapi.json`. `contraagent._internal` is not public: change it freely,
with no aliases or shims.

- Until 0.1.0 is tagged, rename the public API freely too: no compatibility aliases,
  no deprecation shims, no readers for old run directories; a changelog fragment
  records each rename as old → new.
- From 0.1.0, a public API change is deliberate: the snapshots show it, a fragment
  records it, and it waits for a minor release (from 1.0, a major one, after
  `ContraagentDeprecationWarning` for two minor releases, through `migration()` in
  `_internal/public.py`). A run record change that the current reader cannot read
  raises `FORMAT` in `_internal/runs/layout.py` and adds a fixture beside
  `tests/fixtures/runs/v1/`; the monitor reads every format in `FORMATS`.
