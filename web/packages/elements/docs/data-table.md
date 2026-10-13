# Data table

`<cae-data-table>` shows rows of data in a real `<table>`: a header cell per
column, and the first `rowHeader` column as the header of its row, so a screen
reader names each cell by its column and its row. Register it with
`@contraagent/elements/data-table/define`; the types and `sortRows` are in
`@contraagent/elements/data-table`.

::code{file="examples/data-table.ts"}

## Columns

A column is a `DataColumn`: its header, a CSS grid track as its width, and a
function that draws its cell for a row (a template, a string or a number).
Every row is a grid of the columns' tracks, so the rows line up with the header.

::code{file="../src/table/types.ts" from="/** A column:" to="/** The column the rows are ordered by. */"}

## Keyboard and events

The rows are one tab stop. The arrow keys move between rows, and Home and End
move to the first and the last row. Enter or a click on a row sends
`cae-activate` with the row's id (`rowKey`). With `activatable` off, they choose
the row as the selection and send `cae-select`; the selected row has the part
`row-selected`. A click on a button or a link inside a cell is that control's.

A column with `compare` (or `sortable`) has a header button that sends
`cae-sort` with the column and the direction. The table does not reorder the
rows: the host sets `sort` and the rows, ordered by `sortRows` or its own way.
`sortRows` orders by the column's `compare`, else its `text`, else its cell when
the cell is a string or a number: a column of plain values needs only `sortable`.

## Long lists

Above `windowAt` rows (200), the table draws only the rows on screen and a
spacer for the rows above and below them, so the scroll height stays that of
the whole list. The rows' height is measured; `rowHeight` is the first
estimate. The table finds the element that scrolls it, across shadow roots, or
the window.

## Look

`--cae-data-table-gap` sets the space between the columns and
`--cae-data-table-row-padding` a row's padding. The parts are `table`,
`caption`, `head`, `header-cell`, `row`, `row-selected`, `cell` and `empty`;
`rowTone` gives a row a tone (`data-tone`) and `rowAttrs` more attributes. What
the cells draw lives in the table's shadow root: `cellStyles` adds styles there,
after the table's own (the rows are `tr`, the cells `th` and `td`, each with
`data-col` set to its column's id).

The words are `strings` ([Strings](strings.md)): `empty` with no rows (or the
`empty` slot), and the sort buttons' tooltips.
