// What a hovered, focused or selected mark highlights: its unit's tasks and every
// task joined to them.
import type { PlanNode } from '@contraagent/api';

/** The plan's tasks by key, and the tasks that wait for each task. */
export interface TaskLinks {
  byKey: ReadonlyMap<string, PlanNode>;
  waiters: ReadonlyMap<string, readonly string[]>;
}

export function taskLinks(nodes: readonly PlanNode[]): TaskLinks {
  const waiters = new Map<string, string[]>();
  for (const n of nodes) for (const d of n.after ?? []) (waiters.get(d) ?? waiters.set(d, []).get(d))?.push(n.key);
  return { byKey: new Map(nodes.map((n) => [n.key, n])), waiters };
}

/**
 * The tasks to highlight for `hl` (a unit, or the key of a task without one): the
 * unit's own, and every task joined to them upstream or downstream (a task without a
 * unit, another unit's).
 */
export function related(nodes: readonly PlanNode[], links: TaskLinks, hl: string): Set<string> {
  const seeds = nodes.filter((n) => (n.unit ? n.unit === hl : n.key === hl)).map((n) => n.key);
  const on = new Set(seeds);
  const walk = (next: (key: string) => readonly string[]) => {
    const seen = new Set(seeds);
    const queue = [...seeds];
    for (let k = queue.pop(); k !== undefined; k = queue.pop()) {
      for (const x of next(k)) {
        if (seen.has(x)) continue;
        seen.add(x);
        on.add(x);
        queue.push(x);
      }
    }
  };
  walk((k) => links.waiters.get(k) ?? []);
  walk((k) => links.byKey.get(k)?.after ?? []);
  return on;
}
