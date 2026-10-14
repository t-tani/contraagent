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

/**
 * The rows a viewport of `viewport` px, scrolled to `scrollTop`, shows, when rows
 * differ in height: `offsets[i]` is where row `i` starts and `offsets[total]` is
 * the height of all of them (`rowOffsets`), with `overscan` more rows on each side.
 */
export function windowRowsAt(offsets: readonly number[], scrollTop: number, viewport: number, overscan = 8): RowWindow {
  const n = Math.max(0, offsets.length - 1);
  const all = offsets[n] ?? 0;
  if (!n || all <= 0) return { from: 0, to: n, padTop: 0, padBottom: 0 };
  const top = Math.max(0, scrollTop);
  const first = rowAt(offsets, top);
  const last = rowAt(offsets, top + Math.max(0, viewport));
  const from = Math.max(0, first - overscan);
  const to = Math.min(n, Math.max(from, last + 1 + overscan));
  return { from, to, padTop: offsets[from]!, padBottom: all - offsets[to]! };
}

/** Where each of `total` rows starts, and the height of all of them last: `height(i)` is row `i`'s. */
export function rowOffsets(total: number, height: (i: number) => number): number[] {
  const out = new Array<number>(Math.max(0, total) + 1);
  out[0] = 0;
  for (let i = 0; i < total; i++) out[i + 1] = out[i]! + Math.max(0, height(i));
  return out;
}

/** The row that holds `y`: the last `i` with `offsets[i] <= y`, at most the last row. */
function rowAt(offsets: readonly number[], y: number): number {
  const n = offsets.length - 1;
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (offsets[mid]! <= y) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}
