// The data a `<cae-data-table>` shows: its columns, each a function of a row,
// and its words.

/** A column: its header, its width, and what a cell shows for a row. */
export interface DataColumn<R> {
  /** Unique among the columns: `data-col` on its cells, the `id` of `cae-sort`. */
  id: string;
  header: string;
  /** The header's tooltip. */
  tip?: string;
  /** `end` for numbers: right-aligned, tabular figures. */
  align?: 'start' | 'end';
  /** A CSS grid track: '72px', 'minmax(0, 1fr)' (the default). */
  width?: string;
  /** The cell: a template, a string or a number. */
  cell: (row: R, index: number) => unknown;
  /** The cell as plain text: what `sortRows` orders by when the column has no `compare`. */
  text?: (row: R) => string;
  /** The order of two rows by this column, ascending. */
  compare?: (a: R, b: R) => number;
  /**
   * The header is a button that sends `cae-sort` (true when the column has `compare`).
   * Without `compare` and `text`, `sortRows` orders by the cell when it is a string or a number.
   */
  sortable?: boolean;
  /** The cell names its row (`<th scope="row">`): the first such column does. */
  rowHeader?: boolean;
}

/** The column the rows are ordered by. */
export interface SortState {
  id: string;
  direction: 'asc' | 'desc';
}

export interface DataTableStrings {
  /** The table has no rows. */
  empty: string;
  /** A sortable header's tooltip: the click orders the rows ascending. */
  sortAscending: string;
  /** A sortable header's tooltip: the click orders the rows descending. */
  sortDescending: string;
}

export const DEFAULT_DATA_TABLE_STRINGS: Readonly<DataTableStrings> = {
  empty: 'No rows',
  sortAscending: 'Sort ascending',
  sortDescending: 'Sort descending',
};

/** Whether a column's header sorts. */
export const isSortable = <R>(c: DataColumn<R>): boolean => c.sortable ?? !!c.compare;

/** Two cells' values in order: numbers by value, the rest as text (numbers in it by value); a template after both. */
function compareValues(a: unknown, b: unknown): number {
  const plain = (v: unknown) => typeof v === 'string' || typeof v === 'number';
  if (!plain(a) || !plain(b)) return Number(!plain(a)) - Number(!plain(b));
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/**
 * `rows` ordered by the column `sort` names: by its `compare`, else its `text`, else
 * its cell when that is a string or a number; equal rows keep their order. The rows
 * as they are when no column matches.
 */
export function sortRows<R>(rows: readonly R[], columns: readonly DataColumn<R>[], sort: SortState | null): R[] {
  const c = sort && columns.find((x) => x.id === sort.id);
  if (!sort || !c) return [...rows];
  const sign = sort.direction === 'desc' ? -1 : 1;
  const { compare, text } = c;
  const keyed = rows.map((r, i) => ({ r, i, v: compare ? null : text ? text(r) : c.cell(r, i) }));
  const cmp = (a: (typeof keyed)[number], b: (typeof keyed)[number]) => (compare ? compare(a.r, b.r) : compareValues(a.v, b.v));
  return keyed.sort((a, b) => sign * cmp(a, b) || a.i - b.i).map((x) => x.r);
}
