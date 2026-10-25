// The layout as it was first written, with a scan of every edge per container and per
// slot: the faster one in layout.ts must give the same drawing.
import { isPoint } from './arrange.js';
import type { Arrangement, EdgeStyle, EdgePathStep } from './types.js';

export interface Size {
  w: number;
  h: number;
}

/** A rectangle in the drawing. */
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A straight stretch of an edge along the flow, from `a` to `b`, `at` across it; an edge bends between two. */
export interface Stretch {
  a: number;
  b: number;
  at: number;
}

export interface GraphLayout {
  /** The drawing's size, its margin included. */
  w: number;
  h: number;
  /** Every node, stub and cluster, by id. */
  at: Record<string, Rect>;
  /** Every edge path, with its runs. */
  edges: { from: string; to: string; style: EdgeStyle; runs: Stretch[] }[];
  /** Each cycling cluster's return to its next round. */
  returns: LoopReturn[];
  down: boolean;
}

/**
 * A cluster's return to its next round, along the flow (`u`) and across it (`v`): from
 * the far side of its last layer's outermost item (`from`, at `v0`) out to a band
 * past its content (`band`), back along the band, and in to its first layer's
 * outermost item (`to`, at `v1`). Left to right the band is under the nodes; top to
 * bottom, on their right.
 */
export interface LoopReturn {
  box: string;
  from: number;
  v0: number;
  to: number;
  v1: number;
  band: number;
}

/** The spaces of a drawing; left to right unless `down`. */
export interface LayoutSpace {
  /** Between two layers, at the top level and in a cluster. */
  gap: number;
  boxGap: number;
  /** Between two items of a layer, and next to a point an edge passes. */
  sep: number;
  pointSep: number;
  /** A cluster's padding, and the space under its label. */
  pad: number;
  /** The space after a box's content, across the flow: the band its return to the next round runs in. */
  padEnd: number;
  margin: number;
}

/** The band past a cluster's content that its return to the next round runs in, and the return's corner radius. */
export const RETURN_BAND = 24;
export const RETURN_R = 6;

export const SPACE: Record<'across' | 'down', LayoutSpace> = {
  across: { gap: 56, boxGap: 40, sep: 16, pointSep: 12, pad: 12, padEnd: RETURN_BAND, margin: 16 },
  down: { gap: 40, boxGap: 32, sep: 16, pointSep: 12, pad: 10, padEnd: RETURN_BAND, margin: 16 },
};

/** Tops (across the flow) nearest to `want` that keep the order and each gap: weighted isotonic regression (pool adjacent violators). */
function placeRow(want: readonly number[], gaps: readonly number[], weight: readonly number[]): number[] {
  const off: number[] = [0];
  for (let i = 1; i < want.length; i++) off.push((off[i - 1] as number) + (gaps[i - 1] as number));
  const blocks: { sum: number; w: number; n: number }[] = [];
  want.forEach((v, i) => {
    const w = weight[i] ?? 1;
    blocks.push({ sum: w * (v - (off[i] as number)), w, n: 1 });
    while (blocks.length > 1) {
      const b = blocks[blocks.length - 1] as { sum: number; w: number; n: number };
      const a = blocks[blocks.length - 2] as { sum: number; w: number; n: number };
      if (a.sum / a.w <= b.sum / b.w) break;
      blocks.splice(-2, 2, { sum: a.sum + b.sum, w: a.w + b.w, n: a.n + b.n });
    }
  });
  const out: number[] = [];
  for (const b of blocks) for (let k = 0; k < b.n; k++) out.push(b.sum / b.w + (off[out.length] as number));
  return out;
}

/**
 * Where everything of a layered graph is drawn, from the sizes of its nodes, its stubs
 * and its clusters' labels (`lbl:<box id>`): left to right, or top to bottom when
 * `down`. Each container is laid out inside out, a box being one item of its parent:
 * its layers side by side, an item at the start of its layer; across the flow, each
 * item as near as its order allows to the items it is joined to (sweeps of weighted
 * isotonic regression), so chains run straight. An edge runs along its points and
 * bends only in the gap between two layers; it enters and leaves a box where its
 * point inside is, and never passes a node or a box's label.
 */
export function layoutGraph(g: Pick<Arrangement, 'clusters' | 'slots' | 'edgePaths'>, sizes: ReadonlyMap<string, Size>, down = false): GraphLayout {
  const S = SPACE[down ? 'down' : 'across'];
  const len = (s: Size) => (down ? s.h : s.w);
  const brd = (s: Size) => (down ? s.w : s.h);
  const boxIds = new Set(g.clusters.map((b) => b.id));
  const parentOf = new Map(g.clusters.map((b) => [b.id, b.parent]));
  const label = (box: string): Size => sizes.get(`lbl:${box}`) ?? { w: 0, h: 0 };
  // A box's padding: along the flow, and across it. Its label is in a band at its top: across
  // the flow left to right; along it top to bottom, where a gap under the label lets edges in.
  const padOf = (box: string) =>
    down
      ? { u0: label(box).h + S.pad + S.gap / 2, u1: S.pad, v0: S.pad, v1: S.padEnd, minU: 0, minV: label(box).w + 2 * S.pad }
      : { u0: S.pad, u1: S.pad, v0: label(box).h + S.pad, v1: S.padEnd, minU: label(box).w + 2 * S.pad, minV: 0 };
  const extent = new Map<string, { u: number; v: number }>(); // a box's size, along and across
  const slotSize = (id: string): { u: number; v: number } => {
    if (boxIds.has(id)) return extent.get(id) ?? { u: 0, v: 0 };
    if (isPoint(id)) return { u: 0, v: 0 };
    const s = sizes.get(id) ?? { w: 0, h: 0 };
    return { u: len(s), v: brd(s) };
  };
  interface Local {
    rows: string[][];
    start: number[];
    width: number[];
    top: Map<string, number>;
    u: number;
    v: number;
  }
  const local = new Map<string, Local>();
  const layerIn = new Map<string, Map<string, number>>();
  const depth = (c: string): number => (c === '' ? 0 : 1 + depth(parentOf.get(c) ?? ''));
  const containers = ['', ...g.clusters.map((b) => b.id)].sort((a, b) => depth(b) - depth(a));
  // Where an edge meets a slot, across the flow from the slot's top: a node's middle,
  // a point, or (a box) where the edge's step inside it is.
  const attach = (ri: number, si: number): number => {
    const steps = g.edgePaths[ri]?.steps ?? [];
    const s = steps[si] as EdgePathStep;
    if (isPoint(s.id)) return 0;
    if (!boxIds.has(s.id)) return slotSize(s.id).v / 2;
    const inner = steps[si - 1]?.in === s.id ? si - 1 : si + 1;
    const step = steps[inner] as EdgePathStep;
    return padOf(s.id).v0 + (local.get(s.id)?.top.get(step.id) ?? 0) + attach(ri, inner);
  };
  for (const c of containers) {
    const rows = (g.slots[c] ?? []).map((r) => [...r]);
    layerIn.set(c, new Map(rows.flatMap((r, i) => r.map((id) => [id, i] as const))));
    const width = rows.map((r) => Math.max(0, ...r.map((id) => slotSize(id).u)));
    const gap = c === '' ? S.gap : S.boxGap;
    const start: number[] = [];
    width.forEach((_, i) => start.push(i ? (start[i - 1] as number) + (width[i - 1] as number) + gap : 0));
    // The joins inside this container: slot a of layer l to slot b of layer l + 1.
    const links: { a: string; b: string; oa: number; ob: number }[] = [];
    g.edgePaths.forEach((r, ri) =>
      r.steps.forEach((s, si) => {
        const p = r.steps[si - 1];
        if (si && p && p.in === c && s.in === c && layerIn.get(c)?.get(p.id) !== layerIn.get(c)?.get(s.id)) links.push({ a: p.id, b: s.id, oa: attach(ri, si - 1), ob: attach(ri, si) });
      }),
    );
    // Points sit close to each other and to a node, further from a box (its next-pass mark is on its edge).
    const sepOf = (a: string, b: string | undefined) =>
      b === undefined ? 0 : boxIds.has(a) || boxIds.has(b) || !(isPoint(a) || isPoint(b)) ? S.sep : S.pointSep;
    const top = new Map<string, number>();
    for (const r of rows) {
      let v = 0;
      r.forEach((id, i) => {
        top.set(id, v);
        v += slotSize(id).v + sepOf(id, r[i + 1]);
      });
    }
    const place = (r: string[], want: (id: string) => number[]) => {
      const desired = r.map((id) => {
        const xs = want(id);
        return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : (top.get(id) ?? 0);
      });
      const gaps = r.map((id, i) => slotSize(id).v + sepOf(id, r[i + 1]));
      // The nodes first, as if the points between them were fixed in size; then the points, around the nodes.
      const real = r.map((id, i) => (isPoint(id) ? -1 : i)).filter((i) => i >= 0);
      const span = (i: number, j: number) => gaps.slice(i, j).reduce((a, b) => a + b, 0);
      const at = placeRow(
        real.map((i) => desired[i] as number),
        real.map((i, k) => (k + 1 < real.length ? span(i, real[k + 1] as number) : 0)),
        real.map(() => 1),
      );
      real.forEach((i, k) => (desired[i] = at[k] as number));
      placeRow(desired, gaps, r.map((id) => (isPoint(id) ? 1 : 1e6))).forEach((v, i) => top.set(r[i] as string, Math.round(v * 100) / 100));
    };
    // A node lines up with the nodes it is joined to, when it has any on that side, else with the points;
    // a point lines up with whatever it is joined to, so a chain runs straight and a long edge goes round it.
    const near = (id: string, ls: { other: string; at: number }[]) => {
      const real = isPoint(id) ? ls : ls.filter((x) => !isPoint(x.other));
      return (real.length ? real : ls).map((x) => x.at);
    };
    const fromPrev = (id: string) => near(id, links.filter((l) => l.b === id).map((l) => ({ other: l.a, at: (top.get(l.a) ?? 0) + l.oa - l.ob })));
    const fromNext = (id: string) => near(id, links.filter((l) => l.a === id).map((l) => ({ other: l.b, at: (top.get(l.b) ?? 0) + l.ob - l.oa })));
    for (let sweep = 0; sweep < 8; sweep++) {
      const order = rows.map((_, i) => i);
      if (sweep % 2) order.reverse();
      for (const i of order) place(rows[i] as string[], sweep % 2 ? fromNext : fromPrev);
    }
    for (const r of rows) place(r, (id) => [...fromPrev(id), ...fromNext(id)]);
    const lo = top.size ? Math.min(...top.values()) : 0;
    for (const [id, v] of top) top.set(id, v - lo);
    const u = (start[start.length - 1] ?? 0) + (width[width.length - 1] ?? 0);
    const v = Math.max(0, ...rows.flat().map((id) => (top.get(id) ?? 0) + slotSize(id).v));
    local.set(c, { rows, start, width, top, u, v });
    if (c !== '') {
      const p = padOf(c);
      extent.set(c, { u: Math.max(p.u0 + u + p.u1, p.minU), v: Math.max(p.v0 + v + p.v1, p.minV) });
    }
  }

  // Inside out, then outside in: each container's place in the drawing.
  const at: Record<string, Rect> = {};
  const origin = new Map<string, { u: number; v: number }>();
  const rect = (u: number, v: number, s: { u: number; v: number }): Rect => (down ? { x: v, y: u, w: s.v, h: s.u } : { x: u, y: v, w: s.u, h: s.v });
  const put = (c: string, ou: number, ov: number) => {
    origin.set(c, { u: ou, v: ov });
    const l = local.get(c) as Local;
    l.rows.forEach((r, i) =>
      r.forEach((id) => {
        if (isPoint(id)) return;
        const u = ou + (l.start[i] as number);
        const v = ov + (l.top.get(id) ?? 0);
        at[id] = rect(u, v, slotSize(id));
        if (boxIds.has(id)) {
          const p = padOf(id);
          put(id, u + p.u0, v + p.v0);
        }
      }),
    );
  };
  put('', S.margin, S.margin);
  const whole = local.get('') as Local;
  const U = whole.u + 2 * S.margin;
  const V = whole.v + 2 * S.margin;

  // A container's layer l: where it starts and ends along the flow, in the drawing.
  const col = (c: string, l: number): [number, number] => {
    const lc = local.get(c) as Local;
    const o = origin.get(c) ?? { u: 0, v: 0 };
    const c0 = o.u + (lc.start[l] ?? 0);
    return [c0, c0 + (lc.width[l] ?? 0)];
  };
  const layer = (c: string, id: string) => layerIn.get(c)?.get(id) ?? 0;
  const byOf = (s: EdgePathStep | undefined): string => (s && isPoint(s.id) ? (/\|by:([^|]*)\|/.exec(s.id)?.[1] ?? '') : '');
  const edges = g.edgePaths.map((r, ri) => {
    const vOf = (si: number): number => {
      const s = r.steps[si] as EdgePathStep;
      const o = origin.get(s.in) ?? { u: 0, v: 0 };
      return o.v + (local.get(s.in)?.top.get(s.id) ?? 0) + attach(ri, si);
    };
    const runs: Stretch[] = r.steps.map((s, si): Stretch => {
      const prev = r.steps[si - 1];
      const next = r.steps[si + 1];
      const [c0, c1] = col(s.in, layer(s.in, s.id));
      const v = vOf(si);
      if (si === 0) return { a: c0 + slotSize(s.id).u, b: c1, at: v };
      if (si === r.steps.length - 1) return { a: c0, b: c0, at: v };
      if (isPoint(s.id)) {
        const box = byOf(s);
        // Beside a box: from where it left the box's side, or up to where it goes in.
        if (box && prev?.id === box) return { a: col(box, layer(box, r.steps[si - 2]?.id ?? '') + 1)[0], b: c1, at: v };
        if (box && next?.id === box) {
          const ln = layer(box, r.steps[si + 2]?.id ?? '');
          const gap = ln > 0 ? col(box, ln - 1)[1] : (at[box] ? (down ? at[box].y : at[box].x) : c0) + label(box).h + S.pad;
          return { a: c0, b: gap, at: v };
        }
        return { a: c0, b: c1, at: v };
      }
      const p = padOf(s.id);
      const inner = local.get(s.id) as Local;
      // Out of a box: at its far side, or through its side after the layer it leaves.
      if (prev?.in === s.id) {
        if (byOf(next) === s.id) {
          const u = col(s.id, layer(s.id, prev.id) + 1)[0];
          return { a: u, b: u, at: vOf(si + 1) };
        }
        return { a: c0 + p.u0 + inner.u, b: c1, at: v };
      }
      // Into a box: at its near side, or through its side before the layer it goes to.
      if (byOf(prev) === s.id) {
        const u = col(s.id, layer(s.id, next?.id ?? ''))[0];
        return { a: u, b: u, at: vOf(si + 1) };
      }
      return { a: c0, b: c0 + p.u0, at: v };
    });
    return { from: r.from, to: r.to, style: r.style, runs };
  });
  // Each box's return to its next round: from its last layer's item that reaches furthest
  // across the flow, along the band past the content, to its first layer's.
  const returns = g.clusters.flatMap((b): LoopReturn[] => {
    if (!b.cycle) return [];
    const l = local.get(b.id);
    const o = origin.get(b.id);
    if (!l || !o) return [];
    const outer = (row: readonly string[] | undefined) => {
      const ids = (row ?? []).filter((id) => !isPoint(id));
      let best: { u: number; v: number } | null = null;
      for (const id of ids) {
        const s = slotSize(id);
        const v = (l.top.get(id) ?? 0) + s.v;
        if (!best || v > best.v) best = { u: s.u, v };
      }
      return best;
    };
    const real = l.rows.map((r, i) => (r.some((id) => !isPoint(id)) ? i : -1)).filter((i) => i >= 0);
    const fi = real[0] ?? 0;
    const li = real[real.length - 1] ?? 0;
    const last = outer(l.rows[li]);
    const first = outer(l.rows[fi]);
    if (!last || !first) return [];
    // An item's middle along the flow, as wide as its layer; one layer: either side of its middle.
    let from = o.u + (l.start[li] ?? 0) + (l.width[li] ?? 0) / 2;
    let to = o.u + (l.start[fi] ?? 0) + (l.width[fi] ?? 0) / 2;
    if (from - to < 4 * RETURN_R) {
      const d = Math.max(2 * RETURN_R, Math.min(28, Math.min(last.u, first.u) / 4));
      from = (from + to) / 2 + d;
      to = from - 2 * d;
    }
    return [{ box: b.id, from, v0: o.v + last.v, to, v1: o.v + first.v, band: o.v + l.v + RETURN_BAND / 2 }];
  });
  return { w: down ? V : U, h: down ? U : V, at, edges, returns, down };
}
