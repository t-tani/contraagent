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
(edges from outside the graph). A node's marks are aligned with `series`; a mark
outside any series is in `loose`. A state is any id: `states` (`StateStyles`)
gives each its word, its tone and its shape, and its key order is the legend's.

::code{file="../src/graph/types.ts" from="export interface GraphNodeInput {" to="/** A box of nodes"}

A cluster is a box of nodes (and of other clusters). A cluster that `cycle`s draws
a return from its last layer to its first; an edge with `ranks: false` closes that
cycle: it never sets the layers and is not drawn.

## Order and drawing

`arrange` gives each item its layer by the longest path to it, orders each layer to
reduce crossings, and routes each edge through a point on every layer it crosses.
The order depends on the structure only. Give the element the `order` of an earlier
drawing of the same graph to keep its items in place: an item that appears later is
added at the end of its layer. `layoutGraph` places everything from the measured
sizes; the element measures its nodes itself. Below 640 px of width, `direction:
'auto'` draws top to bottom.

## Selection and events

A click selects a mark, a node or a cluster and sends `cae-select`; the element
does not select by itself: the host sets `selected`. Enter or a double click sends
`cae-activate`, or `cae-drill` for an item with `drill` (an inner view). The card of
the selected item is the host's content in the `inspector` slot; its first heading
and its `[data-status]` element name the item to a screen reader. "Graph | Table"
sends `cae-view-change`: the table is a row per node with the nodes it is joined
to. With `matrix`, the frame shows a [mark matrix](matrix.md) as the table.

Hovering, focusing or selecting a mark highlights its series; `related` names more
marks to light (a mark's id, or a series id, to the ids of the marks it lights).

## Look

The words are `strings` ([Strings](strings.md)). `renderIcon` draws the icons a
node names (`icons`), and `iconStyles` adds styles for them. The parts are listed
in `custom-elements.json`; a mark has the part `mark` and the state's look as
`data-tone` and `data-shape`.
