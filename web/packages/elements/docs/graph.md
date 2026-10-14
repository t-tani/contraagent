# Layered graph

`<cae-layered-graph>` draws nodes in layers, joined by edges, inside clusters: a
pipeline, a build, any flow of steps. Each node holds a group of marks, one per
series id, at the same place in every node, so one series can be followed across
the graph. Register it with `@contraagent/elements/graph/define` (it registers
`<cae-mark-matrix>` and `<cae-segmented>` too); the types, `arrange` and
`layoutGraph` are in `@contraagent/elements/graph`.

::code{file="examples/graph.ts"}

## The model

A `GraphInput` names the series, the nodes, the clusters, the edges and the stubs
(edges from outside the graph). A state is any id: `states` (`StateStyles`) gives
each its word, its tone and its shape, and its key order is the legend's.

A mark is in a series when the same item has a mark in several nodes: a service
built, tested and deployed is a series, and its marks line up across the steps.
A mark of one node only (a job of one CI step) is in that node's `loose`.

A node's `counts` (the bar of a node with many marks) and `progress` (the count
in its header, "2/3") default to what its marks say: its marks by state, and its
marks whose state has the tone `done` of all its marks, in the words of
`strings.progress`. Give them when a node stands for more items than it has marks.

::code{file="../src/graph/types.ts" from="export interface GraphNodeInput {" to="/** A node as the graph draws it"}

A cluster is a box of nodes (and of other clusters). A cluster that `cycle`s draws
a return from its last layer to its first; an edge with `ranks: false` closes that
cycle: it never sets the layers and is not drawn. An edge may join items in
different clusters, at any depth: it leaves and enters each box on its way.

An item the host can draw open or closed carries `toggle`: a node with `toggle:
'closed'` draws a control in its header (`strings.open`, "Show inside") and a
cluster with `toggle: 'open'` one in its corner (`strings.close`); either sends
`cae-toggle` with the item's id and whether it is to be open, and the host draws
the graph again. A cluster named by a `path` of parts shows them as "a › b › c":
the first part is its name, and each later part sends `cae-drill` with that part's
id. `focusToggle(id)` puts the focus on an item's control once it is drawn again.

`key` is the graph's identity. A new `key` is a new graph: the frame shows all of
it again, and the focused mark of each node is forgotten. Keep the `key` while the
same graph changes (a run in progress), so the reader's zoom and pan stay.

## Order and drawing

`arrange` gives each item its layer by the longest path to it, orders each layer to
reduce crossings, and routes each edge through a point on every layer it crosses.
The order depends on the structure only. Give the element the `order` of an earlier
drawing of the same graph to keep its items in place: an item that appears later is
added at the end of its layer. `layoutGraph` places everything from the measured
sizes; the element measures its nodes itself. Below 640 px of width, `direction:
'auto'` draws top to bottom. `extentOf(arrangement)` gives a drawing's shape before
it is measured: the layers it spans along the flow and the items it stacks across
it at most, a cluster counted as what it holds; a host can choose the direction,
or how much to draw, from it.

## Size

The element is as wide as its container. Without a height, the frame is as tall
as the whole drawing at that width (never scaled up), up to 70% of the window's
height or 360 px, whichever is more; top to bottom, as tall as the drawing. With a
height set on the element (or given by a flex or grid container), the `crumbs`
slot and the row under the frame keep their height, and the frame takes the rest,
with the whole drawing fitted and centred in it.

## Selection and events

A click selects a mark, a node or a cluster and sends `cae-select`; the element
does not select by itself: the host sets `selected`. Enter or a double click sends
`cae-activate`, or `cae-drill` for an item with `drill` (an inner view). "Graph |
Table" sends `cae-view-change`: the table is a row per node with the nodes it is
joined to. With `matrix`, the frame shows a [mark matrix](matrix.md) as the table.

The card of the selected item is the host's content in the `inspector` slot,
beside the item in the frame; its first heading and its `[data-status]` element
name the item to a screen reader. With nothing in the slot when the element
draws (a new `selected` draws it), there is no card: a page that shows the
selection elsewhere leaves the slot empty.

Hovering, focusing or selecting a mark highlights its series; `related` names more
marks to light (a mark's id, or a series id, to the ids of the marks it lights).

The line under the legend holds the key hints. It keeps its height at all times,
and shows its words while the graph has the focus. On a screen with touch alone
(no fine pointer) there is no line; `::part(keys) { display: none; }` removes it
everywhere.

## Look

The words are `strings` ([Strings](strings.md)). `renderIcon` draws the icons a
node names (`icons`), and `iconStyles` adds styles for them. A mark has the state's
look as `data-tone` and `data-shape`. The parts, for `::part()`:

| Part | What it is |
|---|---|
| `frame` | the frame every view is drawn in |
| `stage` | what pans and zooms |
| `node`, `node-header`, `node-name` | each node, its first line, its name |
| `mark` | each mark |
| `cluster`, `cluster-label` | each cluster, its header |
| `edge`, `stub` | each edge, each stub |
| `legend` | the legend |
| `keys` | the line of key hints |
| `inspector` | the selected item's card |
| `table`, `row` | the node table, each of its rows |
