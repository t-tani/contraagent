// The order of a layered drawing: each item's layer by longest path, and the order
// within each layer that reduces crossings. Reads ids and links only.

export const push = <K, V>(m: Map<K, V[]>, k: K, v: V): void => {
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
