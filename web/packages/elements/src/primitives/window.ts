// Windowing: which rows of a long list of fixed-height rows are drawn, and the
// space that stands for the rows above and below them.

export interface RowWindow {
  /** The first row drawn. */
  from: number;
  /** The row after the last drawn. */
  to: number;
  /** The height that stands for the rows above `from`. */
  padTop: number;
  /** The height that stands for the rows from `to` on. */
  padBottom: number;
}

/**
 * The rows of `total` rows of `rowHeight` px that a viewport of `viewport` px,
 * scrolled to `scrollTop`, shows, with `overscan` more rows on each side.
 */
export function windowRows(total: number, scrollTop: number, viewport: number, rowHeight: number, overscan = 8): RowWindow {
  const n = Math.max(0, Math.floor(total));
  if (!n || rowHeight <= 0) return { from: 0, to: n, padTop: 0, padBottom: 0 };
  const first = Math.floor(Math.max(0, scrollTop) / rowHeight);
  const shown = Math.ceil(Math.max(0, viewport) / rowHeight) + 1;
  const from = Math.min(n, Math.max(0, first - overscan));
  const to = Math.min(n, Math.max(from, first + shown + overscan));
  return { from, to, padTop: from * rowHeight, padBottom: (n - to) * rowHeight };
}
