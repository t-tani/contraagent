// What a hovered, focused or selected mark highlights: its unit's tasks and every
// task joined to them, each with how it is joined.
import type { PlanNode } from '@contraagent/api';
import { EDGE_TYPES, type EdgeType } from './types.js';

/** One link of a task to an earlier one: the earlier task's key, and how they are joined. */
interface Link {
  key: string;
  type: EdgeType;
}

/** The plan's tasks by key, and the links of each task to its earlier and to its later tasks. */
export interface TaskLinks {
  byKey: ReadonlyMap<string, PlanNode>;
  earlier: ReadonlyMap<string, readonly Link[]>;
  later: ReadonlyMap<string, readonly Link[]>;
}

export function taskLinks(nodes: readonly PlanNode[]): TaskLinks {
  const earlier = new Map<string, Link[]>();
  const later = new Map<string, Link[]>();
  for (const n of nodes) {
    const ls = linksOf(n);
    earlier.set(n.key, ls);
    for (const l of ls) (later.get(l.key) ?? later.set(l.key, []).get(l.key))?.push({ key: n.key, type: l.type });
  }
  return { byKey: new Map(nodes.map((n) => [n.key, n])), earlier, later };
}

/**
 * The tasks to highlight for `hl` (a unit, or the key of a task without one): the
 * unit's own (null), and every task joined to them upstream or downstream (a task
 * without a unit, another unit's), each with the weakest link on the strongest path
 * that joins it: `given` when outputs alone lead to it, `after` when order does,
 * `created` when it takes a task created after a result.
 */
export function related(nodes: readonly PlanNode[], links: TaskLinks, hl: string): Map<string, EdgeType | null> {
  const seeds = nodes.filter((n) => (n.unit ? n.unit === hl : n.key === hl)).map((n) => n.key);
  const on = new Map<string, EdgeType | null>(seeds.map((k) => [k, null]));
  // One walk per type, the strongest first, each over the links of that type and the stronger
  // ones: what a walk reaches first is joined by that type.
  for (const [i, type] of EDGE_TYPES.entries()) {
    const allowed = new Set(EDGE_TYPES.slice(0, i + 1));
    for (const next of [links.earlier, links.later]) {
      const seen = new Set(seeds);
      const queue = [...seeds];
      for (let k = queue.pop(); k !== undefined; k = queue.pop()) {
        for (const l of next.get(k) ?? []) {
          if (!allowed.has(l.type) || seen.has(l.key)) continue;
          seen.add(l.key);
          if (!on.has(l.key)) on.set(l.key, type);
          queue.push(l.key);
        }
      }
    }
  }
  return on;
}

/**
 * A task's links to the tasks it comes after, each key once by its strongest link: given
 * their outputs (`given_from`), waiting for them only (`after`), created after their
 * results (`created_from`).
 */
export function linksOf(n: PlanNode): Link[] {
  const out = new Map<string, EdgeType>();
  for (const k of n.given_from ?? []) out.set(k, 'given');
  for (const k of n.after ?? []) if (!out.has(k)) out.set(k, 'after');
  for (const k of n.created_from ?? []) if (!out.has(k)) out.set(k, 'created');
  return [...out].map(([key, type]) => ({ key, type }));
}
