# Tree

`<cae-tree>` shows items in a tree, the children of each under it, folded and
opened by the reader: files and directories, say. Register it with
`@contraagent/elements/tree/define`; the types are in
`@contraagent/elements/tree`.

<!-- not on the site -->
Live on this topic's page of the documentation site (`pnpm run docs` in `web/`).

::code{file="examples/tree.ts"}

## Items

An item is a `TreeItem`: an `id` unique in the tree, a `name` and its
`children`. Its icon is a directory for an item with children and a file for one
without, unless `icon` names one. A `badge` is a word beside the name in the
colour of its `tone`, with the tone's mark (✓ done, ✕ failed, ◌ attention).
`open: false` folds an item at first.

::code{file="../src/tree/tree.ts" from="/** One item of a tree" to="export interface TreeStrings"}

## Selection

`selected` is the selected item's id; the element shows it and opens its
ancestors, and the host sets it. A click, Enter or Space on a selectable item
sends `cae-select` with its id: by default an item with no children is
selectable, and an item with children opens and closes instead. The toggle
before an item with children, Right and Left open and close it and send
`cae-toggle`. A host pairs a tree with `<cae-code>` by showing the selected
file's text beside it ([Code](code.md)).

## Keyboard

The tree is one tab stop, on the selected item or else the first. Up and Down
move between the items shown, Right opens an item and then moves to its first
child, Left closes it or moves to its parent, Home and End go to the first and
the last item, and a letter moves to the next item whose name starts with it. A
screen reader hears each item's level, its place among its siblings, and whether
it is open and selected.

## Look

The parts are `tree`, `item` (with `data-id`) and `empty`.
