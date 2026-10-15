// The order of a layered drawing: each item's layer by longest path, and the order
// within each layer that reduces crossings. Reads ids and links only.
//
// The drawing is a layered (Sugiyama) layout of a compound graph, by container (the
// top level, then each cluster, a cluster being one item of its parent): layers by
// longest path, with the edges that close a cycle (`ranks: false`) left out; a point
// (`~...`) on every layer a long edge crosses, so no edge runs over a node; crossings
// reduced by barycentre sweeps. `layoutGraph` then places it from measured sizes.
// The order depends on the structure only, and keeps a previous order: items that
// appear later are appended to their layer.
import type { Arrangement, EdgeStyle, GraphClusterInput, GraphEdgeInput, GraphNodeInput, GraphOrder, GraphStubInput, EdgePathStep } from './types.js';

const push = <K, V>(m: Map<K, V[]>, k: K, v: V): void => {
  const xs = m.get(k);
  if (xs) xs.push(v);
  else m.set(k, [v]);
};

const pairKey = (a: string, b: string) => `${a}\u0000${b}`;

/**
 * Each id's layer by longest path. Edges that close a cycle (found depth first, in
 * `ids` order) are left out; `fixed` ids keep their layer.
 */
export function rankLayers(ids: readonly string[], edges: readonly (readonly [string, string])[], fixed: ReadonlyMap<string, number>): Map<string, number> {
  const known = new Set(ids);
  const all = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const [a, b] of edges) if (a !== b && known.has(a) && known.has(b) && !all.get(a)?.includes(b)) all.get(a)?.push(b);
  const back = new Set<string>();
  const seen = new Map<string, 1 | 2>();
  for (const root of ids) {
    if (seen.has(root)) continue;
    seen.set(root, 1);
    const stack: [string, number][] = [[root, 0]];
    while (stack.length) {
      const top = stack[stack.length - 1] as [string, number];
      const ss = all.get(top[0]) ?? [];
      if (top[1] < ss.length) {
        const s = ss[top[1]++] as string;
        const st = seen.get(s);
        if (st === 1) back.add(pairKey(top[0], s));
        else if (!st) {
          seen.set(s, 1);
          stack.push([s, 0]);
        }
      } else {
        seen.set(top[0], 2);
        stack.pop();
      }
    }
  }
  const succ = new Map<string, string[]>(ids.map((id) => [id, []]));
  const pred = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const [a, ss] of all) {
    for (const b of ss) {
      if (back.has(pairKey(a, b))) continue;
      succ.get(a)?.push(b);
      pred.get(b)?.push(a);
    }
  }
  // Longest path, in topological order (Kahn's).
  const indeg = new Map(ids.map((id) => [id, pred.get(id)?.length ?? 0]));
  const queue = ids.filter((id) => !indeg.get(id));
  const layer = new Map<string, number>();
  for (let q = queue.shift(); q !== undefined; q = queue.shift()) {
    layer.set(q, fixed.get(q) ?? Math.max(0, ...(pred.get(q) ?? []).map((p) => (layer.get(p) ?? 0) + 1)));
    for (const s of succ.get(q) ?? []) {
      indeg.set(s, (indeg.get(s) ?? 0) - 1);
      if (!indeg.get(s)) queue.push(s);
    }
  }
  return layer;
}

/** Pairs (a, b) between adjacent layers that cross, for the order `pos`. */
function crossings(rows: readonly string[][], links: readonly (readonly [string, string])[], pos: ReadonlyMap<string, number>, layerOf: ReadonlyMap<string, number>): number {
  let n = 0;
  const by = new Map<number, [number, number][]>();
  for (const [a, b] of links) {
    const l = layerOf.get(a);
    if (l === undefined) continue;
    push(by, l, [pos.get(a) ?? 0, pos.get(b) ?? 0]);
  }
  for (const ls of by.values())
    for (let i = 0; i < ls.length; i++)
      for (let j = i + 1; j < ls.length; j++) {
        const [a1, b1] = ls[i] as [number, number];
        const [a2, b2] = ls[j] as [number, number];
        if ((a1 - a2) * (b1 - b2) < 0) n++;
      }
  return rows.length ? n : 0;
}

/** True for a point where an edge crosses a layer. */
export const isPoint = (id: string): boolean => id.startsWith('~');

/**
 * The order within each layer that reduces crossings: barycentre sweeps, down and
 * up, four times, keeping the best. `links` join a slot to one in the next layer.
 * With `keep`, those ids keep their order (a previous layout's, new ones after
 * them) and only the other slots (the points) move between them.
 */
export function orderRows(rows: string[][], links: readonly (readonly [string, string])[], keep: boolean): string[][] {
  const layerOf = new Map<string, number>();
  rows.forEach((row, i) => row.forEach((id) => layerOf.set(id, i)));
  const pred = new Map<string, string[]>();
  const succ = new Map<string, string[]>();
  for (const [a, b] of links) {
    push(succ, a, b);
    push(pred, b, a);
  }
  const pos = new Map<string, number>();
  const fix = (row: readonly string[]) => row.forEach((id, i) => pos.set(id, i));
  const cur = rows.map((r) => [...r]);
  cur.forEach(fix);
  const score = () => crossings(cur, links, pos, layerOf);
  let best = cur.map((r) => [...r]);
  let bestN = score();
  const sortRow = (row: string[], near: Map<string, string[]>): string[] => {
    const bc = new Map<string, number>();
    for (const id of row) {
      const ps = (near.get(id) ?? []).map((p) => pos.get(p)).filter((x): x is number => x !== undefined);
      bc.set(id, ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : (pos.get(id) ?? 0));
    }
    const at = (id: string) => bc.get(id) ?? 0;
    if (!keep) return [...row].sort((a, b) => at(a) - at(b) || (pos.get(a) ?? 0) - (pos.get(b) ?? 0));
    // The kept ids stay in their order; each point goes before the first kept id it is left of.
    const fixed = row.filter((id) => !isPoint(id));
    const points = row.filter(isPoint).sort((a, b) => at(a) - at(b) || (pos.get(a) ?? 0) - (pos.get(b) ?? 0));
    const out: string[] = [];
    let p = 0;
    for (const id of fixed) {
      while (p < points.length && at(points[p] as string) < at(id)) out.push(points[p++] as string);
      out.push(id);
    }
    return [...out, ...points.slice(p)];
  };
  for (let sweep = 0; sweep < 4; sweep++) {
    const down = sweep % 2 === 0;
    const order = down ? cur.map((_, i) => i).slice(1) : cur.map((_, i) => i).reverse().slice(1);
    for (const i of order) {
      const row = sortRow(cur[i] as string[], down ? pred : succ);
      cur[i] = row;
      fix(row);
    }
    const n = score();
    if (n < bestN) {
      bestN = n;
      best = cur.map((r) => [...r]);
    }
  }
  return score() <= bestN ? cur : best;
}

/** What `arrange` reads of a graph: ids, where each node is, and the links. */
export interface GraphShape {
  nodes: readonly Pick<GraphNodeInput, 'id' | 'cluster'>[];
  clusters: readonly (Pick<GraphClusterInput, 'id' | 'parent'> & { cycle?: boolean })[];
  edges: readonly Pick<GraphEdgeInput, 'from' | 'to' | 'style' | 'ranks'>[];
  stubs: readonly Pick<GraphStubInput, 'id' | 'to' | 'style'>[];
}

const arranged = new WeakMap<GraphShape, { prev: GraphOrder | undefined; down: boolean; out: Arrangement }[]>();

/**
 * The order of `g`'s drawing: each container's layers (the top level, then each
 * cluster, a cluster being one item of its parent), the order within each layer,
 * and the slots each edge passes. Pass a previous `order` of the same graph as
 * `prev` to keep its items where they are (new ones are appended to their layer);
 * `down` lays out the edge paths for a drawing top to bottom (a cluster's label is then on
 * the side its edges come in). The same `g`, `prev` and `down` give the same object.
 */
export function arrange(g: GraphShape, prev?: GraphOrder, down = false): Arrangement {
  const seen = arranged.get(g) ?? [];
  const hit = seen.find((x) => x.prev === prev && x.down === down);
  if (hit) return hit.out;
  const out = arrangeNew(g, prev, down);
  arranged.set(g, [...seen.slice(-3), { prev, down, out }]);
  return out;
}

function arrangeNew(g: GraphShape, prev: GraphOrder | undefined, down: boolean): Arrangement {
  const clusterIds = new Set(g.clusters.map((c) => c.id));
  const parentOf = new Map(g.clusters.map((c) => [c.id, c.parent]));
  const boxOf = new Map<string, string>(); // node id -> its innermost cluster
  for (const n of g.nodes) if (n.cluster) boxOf.set(n.id, n.cluster);
  const stubIds = [...new Set(g.stubs.map((s) => s.id))];
  const isStub = new Set(stubIds);

  // The clusters an id sits in, innermost first (for a cluster id, itself first).
  const boxPath = (id: string): string[] => {
    const out: string[] = [];
    let b: string | null = clusterIds.has(id) ? id : (boxOf.get(id) ?? null);
    while (b) {
      out.push(b);
      b = parentOf.get(b) ?? null;
    }
    return out;
  };
  // The direct child of `container` (a cluster, or '' for the top level) that holds a node `id`.
  const itemIn = (id: string, container: string): string | undefined => {
    const bp = boxPath(id);
    if (container === '') return bp[bp.length - 1] ?? id;
    const i = bp.indexOf(container);
    return i < 0 ? undefined : i === 0 ? id : bp[i - 1];
  };
  // The deepest cluster holding both ends of an edge (the top level when none).
  const commonBox = (a: string, b: string): string => {
    const bp = boxPath(a);
    return bp.find((x) => boxPath(b).includes(x)) ?? '';
  };
  // The container a slot is in: a stub's is the top level.
  const containerOf = (id: string): string => (isStub.has(id) ? '' : (boxOf.get(id) ?? ''));

  // Layers, by container: the top level, then each cluster (its own nodes and the
  // clusters nested in it). Each cluster is one item of its parent.
  const containers = ['', ...g.clusters.map((c) => c.id)];
  const kidsOf = new Map<string, string[]>(containers.map((c) => [c, []]));
  for (const { id } of g.nodes) {
    for (const c of containers) {
      const it = itemIn(id, c);
      if (it !== undefined && !kidsOf.get(c)?.includes(it)) kidsOf.get(c)?.push(it);
    }
  }
  const lay = new Map<string, Map<string, number>>();
  for (const c of containers) {
    const kids = kidsOf.get(c) ?? [];
    const prevRows = c === '' ? prev?.layers : prev?.clusters[c];
    const fixed = new Map<string, number>();
    prevRows?.forEach((row, i) => row.forEach((id) => kids.includes(id) && fixed.set(id, i)));
    // An edge that closes a cycle does not set the layers.
    const es = g.edges
      .filter((e) => e.ranks && commonBox(e.from, e.to) === c)
      .map((e) => [itemIn(e.from, c) as string, itemIn(e.to, c) as string] as const);
    lay.set(c, rankLayers(kids, es, fixed));
  }
  // Stubs, in the top level: in the layer before the first they lead to (a new first layer when that is the first).
  const top = lay.get('') as Map<string, number>;
  const prevTop = new Map<string, number>();
  prev?.layers.forEach((row, i) => row.forEach((id) => prevTop.set(id, i)));
  const stubAt = new Map(
    stubIds.map((id) => [id, prevTop.get(id) ?? Math.min(...g.stubs.filter((s) => s.id === id).map((s) => top.get(itemIn(s.to, '') as string) ?? 0)) - 1]),
  );
  if ([...stubAt.values()].some((l) => l < 0)) {
    for (const [id, l] of top) top.set(id, l + 1);
    for (const [id, l] of stubAt) stubAt.set(id, l + 1);
  }
  for (const [id, l] of stubAt) top.set(id, l);
  const layerOf = (c: string, id: string): number => lay.get(c)?.get(id) ?? 0;
  const lastLayer = (c: string): number => Math.max(0, ...(lay.get(c)?.values() ?? []));

  // Every edge whose end is not in a later layer than its start goes back: not drawn.
  const isBack = (from: string, to: string): boolean => {
    const c = commonBox(from, to);
    return layerOf(c, itemIn(from, c) as string) >= layerOf(c, itemIn(to, c) as string);
  };
  const back = g.edges.map((e) => isBack(e.from, e.to));

  // Each container's rows: its items by layer, a previous order kept, new items after it.
  const rows = new Map<string, string[][]>();
  for (const c of containers) {
    const prevRows = c === '' ? prev?.layers : prev?.clusters[c];
    const kept = (prevRows ?? []).flat();
    const ids = [...(c === '' ? [...stubIds] : []), ...(kidsOf.get(c) ?? [])];
    ids.sort((a, b) => {
      const ka = kept.indexOf(a);
      const kb = kept.indexOf(b);
      return (ka < 0 ? Infinity : ka) - (kb < 0 ? Infinity : kb);
    });
    const r: string[][] = Array.from({ length: lastLayer(c) + 1 }, () => []);
    for (const id of ids) r[layerOf(c, id)]?.push(id);
    rows.set(c, r);
  }

  // Edge paths: the drawn edges through points on the layers they cross. The points of
  // edges from one place (of one style) are shared, so their lines run as one.
  const edgePaths: Arrangement['edgePaths'] = [];
  const points = new Set<string>();
  const point = (c: string, origin: string, style: string, l: number): EdgePathStep => {
    const id = `~${c}|${origin}|${style}|${l}`;
    if (!points.has(id)) {
      points.add(id);
      rows.get(c)?.[l]?.push(id);
    }
    return { id, in: c };
  };
  // A point beside a cluster, in its layer of the container around it: an edge that leaves or
  // enters the cluster through its side, between two of its layers, passes there.
  const byPoint = (c: string, box: string, origin: string, style: string): EdgePathStep => {
    const l = layerOf(c, box);
    const id = `~${c}|by:${box}|${origin}|${style}|${l}`;
    if (!points.has(id)) {
      points.add(id);
      rows.get(c)?.[l]?.push(id);
    }
    return { id, in: c };
  };
  // An edge enters a cluster at its near side only to reach the cluster's first layer (and,
  // top to bottom, not even then: the cluster's label is on that side); else through its
  // side, next to the layer it goes to. It leaves at the far side only from the cluster's
  // last layer, else through its side. So it runs inside a cluster only where it starts or ends.
  const edgePath = (from: string, to: string, style: EdgeStyle): EdgePathStep[] => {
    const c = isStub.has(from) ? '' : commonBox(from, to);
    let curIn = containerOf(from);
    let cur = from;
    const steps: EdgePathStep[] = [{ id: from, in: curIn }];
    // Out of the clusters around the source, up to the common container.
    while (curIn !== c) {
      const up = parentOf.get(curIn) ?? '';
      steps.push({ id: curIn, in: up });
      if (layerOf(curIn, cur) < lastLayer(curIn)) steps.push(byPoint(up, curIn, cur, style));
      cur = curIn;
      curIn = up;
    }
    // Across the common container, then into the clusters around the target.
    const target = itemIn(to, c) as string;
    for (let l = layerOf(c, cur) + 1; l < layerOf(c, target); l++) steps.push(point(c, cur, style, l));
    const bp = boxPath(to);
    const inward = bp.slice(0, c === '' ? bp.length : bp.indexOf(c)).reverse();
    const origin = `>${c}:${cur}`;
    let k = c;
    for (const box of inward) {
      const n = itemIn(to, box) as string;
      if (layerOf(box, n) > 0 || down) steps.push(byPoint(k, box, origin, style));
      steps.push({ id: box, in: k });
      k = box;
    }
    steps.push({ id: to, in: k });
    return steps;
  };
  g.edges.forEach((e, i) => {
    if (!back[i]) edgePaths.push({ from: e.from, to: e.to, style: e.style, steps: edgePath(e.from, e.to, e.style) });
  });
  for (const s of g.stubs) edgePaths.push({ from: s.id, to: s.to, style: s.style, steps: edgePath(s.id, s.to, s.style) });

  // The order within each layer.
  const slots: Record<string, string[][]> = {};
  for (const c of containers) {
    const links: [string, string][] = [];
    const lv = new Map((rows.get(c) ?? []).flatMap((r, i) => r.map((id) => [id, i] as const)));
    for (const r of edgePaths)
      for (let i = 1; i < r.steps.length; i++) {
        const a = r.steps[i - 1] as EdgePathStep;
        const b = r.steps[i] as EdgePathStep;
        if (a.in === c && b.in === c && lv.get(a.id) !== lv.get(b.id)) links.push([a.id, b.id]);
      }
    const hasPrev = c === '' ? !!prev : !!prev?.clusters[c];
    // A point beside a cluster is right after it.
    slots[c] = orderRows(rows.get(c) ?? [], links, hasPrev).map((row) => {
      const by = row.filter((id) => id.includes('|by:'));
      const rest = row.filter((id) => !id.includes('|by:'));
      return rest.flatMap((id) => [id, ...by.filter((p) => p.includes(`|by:${id}|`))]);
    });
  }
  const real = (r: readonly string[][]) => r.map((row) => row.filter((id) => !isPoint(id)));
  const clusters = g.clusters.map((c) => ({ id: c.id, parent: c.parent, cycle: !!c.cycle, layers: real(slots[c.id] ?? []).filter((r) => r.length) }));
  const outerRows = real(slots[''] ?? []).map((row) => row.filter((id) => !isStub.has(id)));
  const byId = new Map(clusters.map((c) => [c.id, c]));
  // Every node id, in drawing order: expand each cluster to the nodes nested in it.
  const expand = (ids: readonly string[]): string[] =>
    ids.flatMap((id) => (clusterIds.has(id) ? expand((byId.get(id)?.layers ?? []).flat()) : [id]));
  return {
    drawn: expand(outerRows.flat()),
    layers: outerRows.filter((r) => r.length),
    clusters,
    back,
    slots,
    edgePaths,
    order: { layers: real(slots[''] ?? []), clusters: Object.fromEntries(clusters.map((c) => [c.id, real(slots[c.id] ?? [])])) },
  };
}

/**
 * How many layers the drawing spans along its flow, and how many items it stacks across
 * it at most, counting a cluster as what it holds: an estimate of the drawing's shape,
 * before it is measured (`span` items wide left to right, `stack` items high).
 */
export function extentOf(a: Pick<Arrangement, 'layers' | 'clusters'>): { span: number; stack: number } {
  const byId = new Map(a.clusters.map((c) => [c.id, c]));
  const memo = new Map<string, { span: number; stack: number }>();
  const of = (layers: readonly string[][]): { span: number; stack: number } => {
    let span = 0;
    let stack = 0;
    for (const row of layers) {
      let deep = 0;
      let across = 0;
      for (const id of row) {
        const c = byId.get(id);
        const e = c ? (memo.get(id) ?? memo.set(id, of(c.layers)).get(id) ?? { span: 1, stack: 1 }) : { span: 1, stack: 1 };
        deep = Math.max(deep, e.span);
        across += e.stack;
      }
      span += deep;
      stack = Math.max(stack, across);
    }
    return { span, stack };
  };
  return of(a.layers);
}
