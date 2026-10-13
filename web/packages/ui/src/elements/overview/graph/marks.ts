// How a node draws its marks: a grid, or a bar of counts when it has many.
import type { TaskState } from '@contraagent/api';
import type { GraphNode, NodeCounts } from './types.js';

/** How a node lays out its unit marks: as many columns as units up to 12, then 10, then 20; smaller marks as they grow. */
export function markGrid(units: number): { cols: number; size: number } {
  if (units <= 12) return { cols: Math.max(1, units), size: 12 };
  if (units <= 100) return { cols: 10, size: 10 };
  return { cols: 20, size: 6 };
}

/** Above this many marks, a node shows a bar of its counts and lists its failed marks. */
export const BAR_MARKS = 200;

/** A node shows its marks as a bar of counts. */
export const asBar = (n: Pick<GraphNode, 'units' | 'single'>): boolean => n.units.filter((m) => m !== null).length + n.single.length > BAR_MARKS;

/** A node's bar: each state's share of its marks, in `order`, the states it has only. */
export function barParts(c: NodeCounts, order: readonly TaskState[]): { state: TaskState; n: number; pct: number }[] {
  return order.filter((s) => c[s] > 0).map((s) => ({ state: s, n: c[s], pct: (100 * c[s]) / Math.max(1, c.total) }));
}
