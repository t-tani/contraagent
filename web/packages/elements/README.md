# @contraagent/elements

Generic web components (Lit) and the parts they are built from: the design
tokens and the built-in themes, status pills, legends, rows of facts, icons, a
segmented control, keyboard focus for a group of items, a data table, stat
tiles, time lanes, a check table, a transcript, and elements for a JSON tree, markdown and counters. Nothing here knows contraagent's data: an element
takes plain data and its words, and reports what the reader did as a `cae-*`
event. `@contraagent/ui` builds the contraagent monitor from them.

## Getting it

Lit is a peer dependency. Importing a module registers nothing and changes no
page; a `define` entry registers its elements under their `cae-*` tags (and
the `cae-*` elements they render), or you register a class under a tag name of
your own. An element speaks English unless the page gives its words in its
`strings` property ([Strings](docs/strings.md)), and takes its colours from the
themes once `adoptThemes(document)` has added their rules ([Theming](docs/theming.md)).

```ts
import '@contraagent/elements/segmented/define'; // <cae-segmented>
import '@contraagent/elements/data-table/define'; // <cae-data-table>
import '@contraagent/elements/tiles/define'; // <cae-stat-tiles>
import '@contraagent/elements/graph/define'; // <cae-layered-graph>, <cae-mark-matrix>
import '@contraagent/elements/define'; // every cae-* element
import { pill, legend, base } from '@contraagent/elements';
```

The subpaths are `primitives`, `styles`, `themes`, `data-table`, `graph`,
`matrix`, `tiles`, `lanes`, `check-table`, `transcript`, `json-tree`,
`markdown` and `count`, and a `define` entry for each element
(`segmented/define`, `data-table/define`, `graph/define`, `matrix/define`,
`tiles/define`, `lanes/define`, `check-table/define`, `transcript/define`,
`json-tree/define`, `markdown/define`, `count/define`).

The package is not in the npm registry; install it from a checkout of the
repository.

## Use it from a checkout

In the repository's `web/` (Node 22, pnpm through `corepack enable`):

```
pnpm install && pnpm tarballs
```

`pnpm tarballs` builds the packages and writes one `.tgz` file for each to
`web/tarballs/`. Then, in your project, with npm or pnpm:

```
npm install <checkout>/web/tarballs/contraagent-elements-*.tgz
pnpm add <checkout>/web/tarballs/contraagent-elements-*.tgz
```

## Documentation

- [Primitives](docs/primitives.md): tones, status pills, legends, rows of facts, icons, the segmented control, roving focus and windowing.
- [Theming](docs/theming.md): colours, fonts, type and corners as `--ca-*` custom properties, and the built-in themes.
- [Strings](docs/strings.md): an element's words, in English unless the host gives its own.
- [Data table](docs/data-table.md): rows in a real table, reached and opened with the keyboard, long lists drawn by window.
- [Layered graph](docs/graph.md): nodes in layers, joined by edges, in clusters, each a group of marks lined up by series; pan, zoom, a card for the selection and the keyboard.
- [Mark matrix](docs/matrix.md): marks in a table, a row per series, the columns under nested groups.
- [Stat tiles](docs/tiles.md): figures as tiles, each a label, a value that counts up, lines of facts and a link.
- [Lanes](docs/lanes.md): bars on a time axis, a lane per group, running bars growing until now.
- [Charts](docs/charts.md): columns (stacked or side by side), lines, a heatmap and horizontal bars of plain series, each with a legend, a tooltip and a table of its values.
- [Check table](docs/check-table.md): named values checked one by one, each with what it must be, what it is and the verdict.
- [Transcript](docs/transcript.md): a conversation with an agent in sessions: bubbles, reasoning, tool cards and web searches, following the end as it grows.
- [Building a page](docs/page.md): a CI pipeline's page from several elements: a theme switch, stat tiles, a sortable table, a graph with shards and a retry loop, and a detail panel.

Every element's properties, events and parts are in `custom-elements.json`,
generated from the sources with the package.

A `::code` line quotes a file of the package; the documentation site (`pnpm docs` in `web/`) shows the quoted lines in place. The same declarations, with their comments, are in `dist/**/*.d.ts`.
