# Check table

`<cae-check-table>` shows named values checked one by one: a row per name,
with what it must be, what it is and the verdict. Register it with
`@contraagent/elements/check-table/define`; the types, `verdict` and
`verdictStyles` are in `@contraagent/elements/check-table`.

::code{file="examples/check-table.ts"}

## Rows

A row is a `CheckRow`. The host judges each value; the table shows the
verdict: `pass` (✓ and its word), `fail` (✕ and its word, in the failed
tone), `warn` (its word, in the attention tone) or `none` (its word, muted, or
an empty cell without one). The marks are hidden from screen readers, which
read the word.

::code{file="../src/checks/types.ts" from="export interface CheckRow" to="export interface CheckTableStrings"}

A value is shown in one line: a string quoted and cut, a list's length and its
first items, an object's first keys. A row with `extra` names a value that is
not expected: its `expected` is a phrase, not code. Without `showValues`, the
table shows only the names and what each must be.

## Verdicts elsewhere

`verdict(v, label, tip)` draws a verdict as the table does, for a host that
shows one outside a table; add `verdictStyles` to the host's styles.

## Look

The table is as wide as its content, so each verdict sits next to the value it
judges; a long value wraps. The parts are `table`, `row` and `verdict`. The
words are `strings` ([Strings](strings.md)): the headers, `optional`, and the
summaries of a list (`items`) and an object.
