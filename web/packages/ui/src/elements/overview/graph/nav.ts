// Keyboard moves: across a grid of marks, and along a drawn edge.
import type { LayerGraph } from './types.js';

/**
 * Where a key moves in a grid of marks (`has[r][c]`: a mark there), from (`r`, `c`):
 * left and right to the next mark in the row, up and down to the nearest row with a
 * mark in the column, Home and End to the row's first and last, with Ctrl to the
 * first and last row's, PageUp and PageDown `page` rows. Null when it does not move.
 */
export function gridStep(has: readonly (readonly boolean[])[], r: number, c: number, key: string, ctrl = false, page = 10): [number, number] | null {
  const at = (i: number, j: number) => has[i]?.[j] === true;
  const first = (i: number) => (has[i] ?? []).findIndex(Boolean);
  const last = (i: number) => (has[i] ?? []).lastIndexOf(true);
  const rowWith = (from: number, step: number, col: number): number => {
    for (let i = from; i >= 0 && i < has.length; i += step) if (at(i, col)) return i;
    return -1;
  };
  const near = (i: number): [number, number] | null => {
    // The mark of row i nearest to column c.
    const row = has[i] ?? [];
    let best = -1;
    row.forEach((x, j) => x && (best < 0 || Math.abs(j - c) < Math.abs(best - c)) && (best = j));
    return best < 0 ? null : [i, best];
  };
  switch (key) {
    case 'ArrowRight':
    case 'ArrowLeft': {
      const s = key === 'ArrowRight' ? 1 : -1;
      for (let j = c + s; j >= 0 && j < (has[r]?.length ?? 0); j += s) if (at(r, j)) return [r, j];
      return null;
    }
    case 'ArrowDown':
    case 'ArrowUp': {
      const s = key === 'ArrowDown' ? 1 : -1;
      const i = rowWith(r + s, s, c);
      if (i >= 0) return [i, c];
      for (let k = r + s; k >= 0 && k < has.length; k += s) if (first(k) >= 0) return near(k);
      return null;
    }
    case 'Home': {
      const i = ctrl ? has.findIndex((row) => row.some(Boolean)) : r;
      return i < 0 || first(i) < 0 ? null : [i, first(i)];
    }
    case 'End': {
      let i = r;
      if (ctrl) for (i = has.length - 1; i >= 0 && last(i) < 0; i--);
      return i < 0 || last(i) < 0 ? null : [i, last(i)];
    }
    case 'PageDown':
    case 'PageUp': {
      const s = key === 'PageDown' ? 1 : -1;
      const target = Math.max(0, Math.min(has.length - 1, r + s * page));
      for (let k = target; k !== r; k -= s) if (first(k) >= 0) return near(k);
      return null;
    }
    default:
      return null;
  }
}

/**
 * The node joined to `from` along a drawn edge: a later one (`later`, that waits for
 * it or was created after it) or an earlier one; of several, the one nearest across
 * the flow (`across`), then the first in drawing order. Null when there is none.
 */
export function alongEdge(g: LayerGraph, from: string, dir: 'later' | 'earlier', across: (id: string) => number): string | null {
  const rank = new Map(g.nodes.map((n, i) => [n.id, i]));
  const ids = [...new Set(g.edges.filter((e) => !e.back && (dir === 'later' ? e.from === from : e.to === from)).map((e) => (dir === 'later' ? e.to : e.from)))];
  const at = across(from);
  ids.sort((a, b) => Math.abs(across(a) - at) - Math.abs(across(b) - at) || (rank.get(a) ?? 0) - (rank.get(b) ?? 0));
  return ids[0] ?? null;
}
