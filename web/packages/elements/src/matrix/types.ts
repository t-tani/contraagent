// A mark matrix's model: rows of marks under nested groups of columns.
import type { Fact } from '../primitives/fact-line.js';

/** One mark of a matrix cell (the same shape as a graph's mark). */
export interface MatrixMark {
  /** Unique in the matrix: the selection id. */
  id: string;
  /** A key of `StateStyles`. */
  state: string;
  /** The accessible name. */
  label: string;
  tip?: string;
  /** The mark opens an inner view: Enter and a double click send `cae-drill`, not `cae-activate`. */
  drill?: boolean;
}

/** A header cell: a group of columns (`group`), or a column's own (`column`, spanning down to the last header row). */
export interface MatrixHeadCell {
  id: string;
  label: string;
  tip?: string;
  /** The accessible name; default: `label`. */
  summary?: string;
  /** Icon names (`registerIcon`) before its label. */
  icons?: readonly string[];
  /** The label is a name in code: drawn in the monospace font. */
  code?: boolean;
  span: number;
  rows: number;
  type: 'group' | 'column';
}

export interface MatrixColumnInput {
  id: string;
  /** The ids of the groups it is under, outermost first: a border marks where a group starts. */
  groups: readonly string[];
}

export interface MatrixRowInput {
  /** Its id: what the matrix highlights (the series of the selected or hovered mark). */
  id: string;
  label: string;
  tip?: string;
  /** Its label in the plain, muted face (a row that stands for no item of its own). */
  muted?: boolean;
  /** The value column's cell, and whether it stands out. */
  value?: string | number;
  strong?: boolean;
  /** One per column: its mark, or null. */
  cells: readonly (MatrixMark | null)[];
}

export interface MarkMatrixInput {
  /** The line above the table, and its tooltip. */
  caption: string;
  captionTip?: string;
  /** The table's accessible name. */
  label: string;
  /** Facts beside the caption. */
  facts?: readonly (string | Fact)[];
  /** The header rows, outermost first. */
  head: readonly (readonly MatrixHeadCell[])[];
  columns: readonly MatrixColumnInput[];
  /** Already in the order chosen (`sort`): the host sorts them. */
  rows: readonly MatrixRowInput[];
  /** A column of one value per row, after the rows' labels, and its header. */
  value?: { label: string; tip?: string };
  /** The orders the reader may choose, and the one chosen. */
  sorts?: readonly { id: string; label: string }[];
  sort?: string;
}

export interface MarkMatrixStrings {
  /** The label of the sort control. */
  sortBy: string;
  /** The header of the rows' labels. */
  rowsHeader: string;
}

export const DEFAULT_MARK_MATRIX_STRINGS: Readonly<MarkMatrixStrings> = {
  sortBy: 'Sort',
  rowsHeader: 'Row',
};
