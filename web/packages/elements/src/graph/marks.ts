// How a node draws its marks: a grid, or a bar of counts when it has many; and
// what a node without `counts` or `progress` shows.
import type { StateStyles } from '../primitives/states.js';
import type { GraphNode, GraphNodeInput } from './types.js';

/**
 * A node with its defaults: no marks, its marks by state as its counts, and as its
 * progress its marks whose state has the tone `done`, of all its marks, in the words
 * of `words`.
 */
export function fillNode(n: GraphNodeInput, states: StateStyles, words: (done: number, total: number) => string): GraphNode {
  const { marks = [], loose = [] } = n;
  const counts: Record<string, number> = {};
  let done = 0;
  let total = 0;
  for (const m of [...marks, ...loose]) {
    if (!m) continue;
    counts[m.state] = (counts[m.state] ?? 0) + 1;
    total++;
    if (states[m.state]?.tone === 'done') done++;
  }
  return { ...n, marks, loose, counts: n.counts ?? counts, progress: n.progress ?? { done, total, label: words(done, total) } };
}

/** How a node lays out its series marks: as many columns as series up to 12, then 10, then 20; smaller marks as they grow. */
export function markGrid(series: number): { cols: number; size: number } {
  if (series <= 12) return { cols: Math.max(1, series), size: 12 };
  if (series <= 100) return { cols: 10, size: 10 };
  return { cols: 20, size: 6 };
}

/** Above this many marks, a node shows a bar of its counts and lists its failed marks. */
export const BAR_MARKS = 200;

/** A node shows its marks as a bar of counts: it has more than `at` marks. */
export const asBar = (n: Pick<GraphNode, 'marks' | 'loose'>, at = BAR_MARKS): boolean => n.marks.filter((m) => m !== null).length + n.loose.length > at;

/** A node's bar: each state's share of its items, in `order`, the states it has only. */
export function barParts(counts: Readonly<Record<string, number>>, order: readonly string[]): { state: string; n: number; pct: number }[] {
  const total = order.reduce((a, s) => a + (counts[s] ?? 0), 0);
  return order.filter((s) => (counts[s] ?? 0) > 0).map((s) => ({ state: s, n: counts[s] ?? 0, pct: (100 * (counts[s] ?? 0)) / Math.max(1, total) }));
}
