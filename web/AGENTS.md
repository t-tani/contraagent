# contraagent web

The monitor's web UI and the documentation site, a pnpm workspace:
`packages/api` (types, client, feeds, store), `packages/elements` (generic
elements), `packages/ui` (the contraagent elements), `apps/monitor` (the page)
and `apps/docs` (the site). The root `AGENTS.md` applies here too.

## Commands

Node 22, pnpm through `corepack enable`; pnpm installs only versions published at
least 14 days ago. Run these in `web/`:

```
pnpm install
pnpm check         # generated types current, translations complete, tsc, eslint, vitest
pnpm build         # rebuilds src/contraagent/_internal/monitor/static (committed; CI fails if stale) and the site
pnpm check:dist    # the packages as an npm consumer sees them, the gzip budgets (size-budgets.json), no image in a tarball
pnpm gen           # the TypeScript types from the monitor's openapi.json
pnpm i18n          # extract msg() strings to packages/ui/xliff, rebuild src/locales
pnpm e2e           # build, then Playwright against the real monitor over the demo runs
pnpm dev           # live-reload UI against a monitor on :8787
pnpm run docs      # the documentation site, live reload (`pnpm docs` is pnpm's own command)
pnpm screenshots   # the READMEs' and docs' screenshots; --only readme,ui,elements
pnpm tarballs      # the three packages as tarballs/*.tgz to install from this checkout
```

## Layers

`api` and `elements` come first and never import each other; `ui` imports both;
`apps/*` import the packages only through the subpaths in their `exports`. Within
`elements` and `ui` the folders are ranked (`ui`: `core/`, `words/` and `lib/`,
`adapters/`, `controllers/`, `elements/<folder>/`, `define/`), and a folder imports
only earlier ranks. The full table is in `packages/ui/src/layers.test.ts`, which
checks it with `eslint.config.js` (`no-restricted-imports`); keep the two in step.

Beyond the imports:

- An element renders what its properties give it and sends events: `ca-*` from `ui`
  (`core/events.ts`), `cae-*` from `elements` (its own `core/events.ts`). Only
  `ca-monitor` holds the store and the view router. Describe the events with `@fires`
  (`packages/ui/src/fires.test.ts` checks them against what the element sends).
- A `cae-*` element takes plain data and its words (`strings`); `elements` holds no
  contraagent data, no `msg()` and no glossary word in a public name (the layers
  test checks the names).
- No module changes the page at import: the page or `ca-monitor` sets up the
  languages (`configureLocales()`) and the themes (`adoptThemes()`).

## Text the UI shows

Every visible string is wrapped in `msg()` (`@lit/localize`) and every element class
is `@localized()`. Translations are in `packages/ui/xliff/<locale>.xlf`; Japanese
follows `packages/ui/xliff/GLOSSARY.md`, and `pnpm check` fails while a message has no
translation. The words for run data come from `packages/ui/src/words/`, one word per
thing, as listed in `packages/ui/WORDS.md`.

The UI states facts about the run. It never narrates what the monitor or contraagent
does, will do, or lets the reader do: no "checked once", "the agent is asked to fix
it", "you can see ... in ...", "open X to ...", "this is to prevent ...". Show a
state, a count, a cause or a value instead ("Not started: input
out/review/zeta.json is missing because review · zeta did not finish", "No
transcript", "2 corrections"). A tooltip may define a term in a short noun phrase or
add a fact about this item, never a policy. A button's name (verb and object, "Show
source") and a key hint ("↑↓ Enter Esc") name an action; they are not narration.

Many readers do not read English as a first language, and some read the monitor
through machine translation. Keep one form for each kind of text:

- Case: sentence case for tabs, headings, column names, buttons, tile labels,
  empty-state titles and tooltips ("Scheduled tasks"); values in chips and pills, and
  code, stay as they are ("done", `journal.jsonl`).
- Names and separators: a task is `kind · unit` everywhere (`kindUnit`), and `·`
  appears only there. Facts in one row are separated by ` | ` ("Attempt 1 | done |
  0.2s | $0.061"); a list of names is a row of chips (`taskChip`) or one per line.
- Punctuation: at most one `:` in a string (a label and its value or cause); no em
  dash. `→` means "changed to" or "then" only, never a link or a button.
- Links and buttons: a link names where it goes, as a noun ("Failed attempts in
  history"); a button names its action, verb and object ("Show source"); no arrows.
- Status marks: ✓ ✕ ◌ only, always next to a word and hidden from screen readers; no
  meaning carried by a glyph or a color alone.
- Empty and unknown: an empty value is "none", an unknown number "—", an empty list
  "No <things>", with a known reason after ` | `.
- Numbers and time: the number first ("3 web searches"); "characters", not "chars";
  one duration format ("<0.1s", "4.2s", "2m 05s", "1h 02m"); dates that read the same
  in every locale; absolute times in rows and chips.
- Causes: name the cause the data has ("... failed checks"); never "X or Y" when the
  data knows which.
- Global English: common words; no idioms, phrasal verbs or slang; no abbreviations
  but API, JSON, CLI, USD and units (B, k, M). Labels may be noun phrases; a string
  that states a cause or a relation keeps its verbs and articles. Positive forms ("All
  attempts done").

## Documentation and the site

Each web package's documentation is its `README.md` (the index) and `docs/*.md`,
with examples in `docs/examples/` that compile in the tests (`docs/tsconfig.json`,
`examples.test.ts`). Elements are described in `custom-elements.json`, from JSDoc.

The site (`apps/docs`, Astro Starlight) holds only its landing page, the live
examples and the generated references; `scripts/collect.py` copies the packages'
documentation into it and fails on a quote, a link or an image that does not
resolve. The site shows elements live, never as screenshots (`LIVE` in
`collect.py`); a paragraph under `<!-- not on the site -->` is for readers of the
files only. No page runs a command when it renders: the landing page reads
`src/fixtures/landing-outputs.json` and the live examples `src/fixtures/demo-run.json`
and `public/demo/data/` (how to rewrite them: the root `AGENTS.md`).

Screenshots are for readers of the repository: a package's `docs/images/` stays out
of its tarball (`"!docs/images"`). The root README's screenshots in
`docs/assets/readme/` come from the showcase runs (`scripts/showcase.py`); each is one
region of a view at most 880 CSS px wide, captured at device scale 2 and never
scaled, shown as `<img ... width="<its CSS width>">`.
