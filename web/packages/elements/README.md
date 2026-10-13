# @contraagent/elements

Generic web components (Lit) and the parts they are built from: the design
tokens and the built-in themes, status pills, legends, rows of facts, icons, a
segmented control, keyboard focus for a group of items, a data table, and
elements for a JSON tree, markdown and counters. Nothing here knows contraagent's data: an element
takes plain data and its words, and reports what the reader did as a `cae-*`
event. `@contraagent/ui` builds the contraagent monitor from them.

## Getting it

Lit is a peer dependency. Importing a module registers nothing; a `define`
entry registers its elements under their `cae-*` tags, or you register a class
under a tag name of your own.

```ts
import '@contraagent/elements/segmented/define'; // <cae-segmented>
import '@contraagent/elements/data-table/define'; // <cae-data-table>
import '@contraagent/elements/define'; // every cae-* element
import { pill, legend, base } from '@contraagent/elements';
```

The subpaths are `primitives`, `styles`, `themes`, `data-table`, `json-tree`,
`markdown` and `count`, and a `define` entry for each element
(`segmented/define`, `data-table/define`, `json-tree/define`,
`markdown/define`, `count/define`).

## Documentation

- [Primitives](docs/primitives.md): tones, status pills, legends, rows of facts, icons, the segmented control, roving focus and windowing.
- [Theming](docs/theming.md): colours, fonts, type and corners as `--ca-*` custom properties, and the built-in themes.
- [Strings](docs/strings.md): an element's words, in English unless the host gives its own.
- [Data table](docs/data-table.md): rows in a real table, reached and opened with the keyboard, long lists drawn by window.

Every element's properties, events and parts are in `custom-elements.json`,
generated from the sources with the package.
