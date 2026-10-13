// The layers of the run's flow: the graph of one, the one the graph opens on, and
// the layer a route's segments name.
import type { Plan } from '@contraagent/api';
import { indexOf, instanceOf, placeOf, shortName, startsWith, type FlowTask } from './flow-index.js';
import { project } from './project.js';
import { LOOP_SEGMENT, type LayerGraph, type LayerOrder } from './types.js';

/**
 * The layer `path` of the plan's flow. Pass the `order` of the last graph of this layer as
 * `prev` to keep its nodes in place; `down` routes the edges for a drawing top to bottom
 * (a box's label is then on the side its edges come in).
 */
export function layerGraph(plan: Plan, path: readonly string[] = [], prev?: LayerOrder, down = false): LayerGraph {
  return project(plan, path, prev, down).graph;
}

/**
 * The layer the graph opens on: from the top, down while a layer has a single
 * node and it is a function's. It stops at a single function node whose flow call
 * raised or was closed, so a run that failed inside a flow opens on the node that
 * shows it, not inside it. A failed or not started task does not stop it: the layer
 * below shows that task's own mark. A static flow lands on its kinds.
 */
export function autoLayer(plan: Plan): string[] {
  const ix = indexOf(plan);
  const path: string[] = [];
  // The failure sites: flow calls that raised or were closed with no raised descendant.
  // The graph stops on the node that shows one, not inside it. A plan with no flow calls
  // cannot tell its failure sites, so it descends as if there were none.
  const raised = new Set<string>();
  if (ix.calls) for (const c of ix.calls.values()) if (c.state === 'raised' || c.state === 'closed') raised.add(c.id);
  const isSite = (id: string): boolean => raised.has(id) && ![...raised].some((r) => r !== id && r.startsWith(`${id}.`));
  for (;;) {
    let only: { id: string; name: string } | null = null;
    let one = true;
    const mine: FlowTask[] = [];
    for (const t of ix.tasks) {
      if (!startsWith(t.path, path)) continue;
      const p = placeOf(t, path.length);
      if (p.type === 'kind' || (only && only.id !== p.id)) {
        one = false;
        break;
      }
      only = p;
      mine.push(t);
    }
    // Stop before entering a single function node that is itself a failure site.
    const atSite = mine.some((t) => isSite(instanceOf(t, path.length, ix.calls).id));
    if (!one || !only || atSite) return path;
    path.push(only.name);
  }
}

/** A layer's segments: its path, and the loop box entered at its end (null when none). */
export function splitLayer(segments: readonly string[]): { path: string[]; loop: string | null } {
  const last = segments[segments.length - 1];
  return last?.startsWith(LOOP_SEGMENT) ? { path: segments.slice(0, -1), loop: last } : { path: [...segments], loop: null };
}

/**
 * The layer `segments` names, as the plan has it: the segments themselves when the
 * plan has that layer (a prefix of a task's flow path, and the loop box after it);
 * else, when the last function is named by its `module.qualname` (or, failing that,
 * its name) and the plan reaches it by one flow path only, that flow path, with the
 * loop box when the layer there has it. Null when the plan has no such layer.
 */
export function resolveLayer(plan: Plan, segments: readonly string[]): string[] | null {
  const { path, loop } = splitLayer(segments);
  const ix = indexOf(plan);
  const hasLoop = (p: readonly string[]) => !loop || layerGraph(plan, p).boxes.some((b) => b.id === loop);
  if (ix.tasks.some((t) => startsWith(t.path, path))) return hasLoop(path) ? [...segments] : null;
  const name = path[path.length - 1];
  if (name === undefined) return null;
  const found = (match: (fn: string) => boolean): string[][] => {
    const by = new Map<string, string[]>();
    for (const t of ix.tasks) t.path.forEach((fn, i) => match(fn) && by.set(t.path.slice(0, i + 1).join('/'), t.path.slice(0, i + 1)));
    return [...by.values()];
  };
  const exact = found((fn) => fn === name);
  const named = exact.length ? exact : found((fn) => shortName(fn) === name);
  const only = named.length === 1 ? (named[0] as string[]) : null;
  return only && hasLoop(only) ? (loop ? [...only, loop] : only) : null;
}

/** One level up from `segments`: null at the top (the layer the graph opens on, `auto`), [] for that layer. */
export function parentLayer(segments: readonly string[], auto: readonly string[]): string[] | null {
  if (segments.length <= auto.length) return null;
  const up = segments.slice(0, -1);
  return up.length <= auto.length ? [] : up;
}
