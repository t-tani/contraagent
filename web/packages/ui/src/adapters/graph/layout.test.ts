import { describe, expect, it } from 'vitest';
import { RETURN_BAND, isPoint, layoutGraph, returnPath, type GraphLayout, type LoopReturn, type Size } from '@contraagent/elements/graph';
import { layerGraph } from './layer.js';
import { AT, F, LOOP, RUN, ft, node, planOf, reviewRun } from './plans.fixture.js';
import type { LayerGraph } from './types.js';

const rows = (g: LayerGraph) => g.layers;

describe('layoutGraph', () => {
  const sizesOf = (g: LayerGraph, w = 130, h = 60): Map<string, Size> => {
    const m = new Map<string, Size>();
    for (const n of g.nodes) m.set(n.id, { w, h });
    for (const s of g.stubs) m.set(s.id, { w: 70, h: 22 });
    for (const b of g.boxes) m.set(`lbl:${b.id}`, { w: 150, h: 20 });
    return m;
  };
  const overlap = (a: { x: number; y: number; w: number; h: number }, b: typeof a) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  /** Every node, stub and box label as a rectangle, by id. */
  const obstacles = (g: LayerGraph, l: GraphLayout, sizes: Map<string, Size>) => {
    const out: [string, { x: number; y: number; w: number; h: number }][] = [];
    for (const n of [...g.nodes.map((x) => x.id), ...g.stubs.map((x) => x.id)]) if (l.at[n]) out.push([n, l.at[n]]);
    for (const b of g.boxes) {
      const r = l.at[b.id];
      const lbl = sizes.get(`lbl:${b.id}`) as Size;
      if (r) out.push([`lbl:${b.id}`, { x: r.x, y: r.y, w: r.w, h: lbl.h + 8 }]);
    }
    return out;
  };
  /** Checks a layout: nothing overlaps in a container, and no edge passes a node or a label other than its own ends. */
  const check = (g: LayerGraph, l: GraphLayout, sizes: Map<string, Size>) => {
    const obs = obstacles(g, l, sizes);
    const nodes = obs.filter(([id]) => !id.startsWith('lbl:'));
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) expect(overlap(nodes[i]![1], nodes[j]![1]), `${nodes[i]![0]} / ${nodes[j]![0]}`).toBe(false);
    const inside = (a: { x: number; y: number; w: number; h: number }, b: typeof a) => a.x >= b.x && a.y >= b.y && a.x + a.w <= b.x + b.w && a.y + a.h <= b.y + b.h;
    for (const e of l.edges) {
      // An edge runs inside a box only when one of its ends is in it.
      for (const b of g.boxes) {
        const r = l.at[b.id];
        const ends = [l.at[e.from], l.at[e.to]];
        if (!r || ends.some((x) => x && inside(x, r))) continue;
        const inner = { x: r.x + 1, y: r.y + 1, w: r.w - 2, h: r.h - 2 };
        for (const run of e.runs) {
          const lo = Math.min(run.a, run.b);
          const hi = Math.max(run.a, run.b);
          if (hi - lo < 1) continue;
          const seg = l.down ? { x: run.at - 0.5, y: lo, w: 1, h: hi - lo } : { x: lo, y: run.at - 0.5, w: hi - lo, h: 1 };
          expect(overlap(seg, inner), `${e.from}>${e.to} inside ${b.id}`).toBe(false);
        }
      }
      for (const [id, r] of obs) {
        if (id === e.from || id === e.to) continue;
        for (const run of e.runs) {
          const lo = Math.min(run.a, run.b) + 0.5;
          const hi = Math.max(run.a, run.b) - 0.5;
          if (hi <= lo) continue;
          const seg = l.down ? { x: run.at - 0.5, y: lo, w: 1, h: hi - lo } : { x: lo, y: run.at - 0.5, w: hi - lo, h: 1 };
          expect(overlap(seg, r), `${e.from}>${e.to} over ${id}`).toBe(false);
        }
        // A bend is in a gap: no node starts or ends inside it along the flow.
        e.runs.forEach((run, k) => {
          const next = e.runs[k + 1];
          if (!next || Math.abs(next.at - run.at) < 0.5 || id.startsWith('lbl:')) return;
          const [u0, u1] = l.down ? [r.y, r.y + r.h] : [r.x, r.x + r.w];
          const [v0, v1] = l.down ? [r.x, r.x + r.w] : [r.y, r.y + r.h];
          const crossesV = Math.max(v0, Math.min(run.at, next.at)) < Math.min(v1, Math.max(run.at, next.at));
          expect(crossesV && u0 < next.a - 0.5 && u1 > run.b + 0.5, `${e.from}>${e.to} bends over ${id}`).toBe(false);
        });
      }
    }
    // Each loop box's return to its next pass runs inside it, past its content: over no node, label or nested box.
    expect(l.returns.map((r) => r.box).sort()).toEqual(g.boxes.map((b) => b.id).sort());
    for (const r of l.returns) {
      const box = l.at[r.box] as { x: number; y: number; w: number; h: number };
      const seg = (u0: number, u1: number, v0: number, v1: number) => {
        const [a, b] = [Math.min(u0, u1), Math.max(u0, u1)];
        const [c, d] = [Math.min(v0, v1), Math.max(v0, v1)];
        return l.down ? { x: c - 0.5, y: a, w: d - c + 1, h: b - a } : { x: a, y: c - 0.5, w: b - a, h: d - c + 1 };
      };
      expect(r.from > r.to, `${r.box} returns back along the flow`).toBe(true);
      for (const sg of [seg(r.from, r.from, r.v0 + 3, r.band), seg(r.to, r.from, r.band, r.band), seg(r.to, r.to, r.v1 + 3, r.band)]) {
        expect(inside(sg, box), `${r.box} return inside its box`).toBe(true);
        for (const [id, o] of obs) expect(overlap(sg, o), `${r.box} return over ${id}`).toBe(false);
        for (const b of g.boxes) if (b.id.startsWith(`${r.box}.`)) expect(overlap(sg, l.at[b.id] as typeof box), `${r.box} return over ${b.id}`).toBe(false);
      }
    }
  };

  it('puts a point on every layer a long edge crosses, and its edge path goes around what is between', () => {
    // a -> b -> c -> d, and a -> d: the long edge passes layers 1 and 2 beside b and c.
    const plan = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['b-u'] }), node('d-u', 'u', 'd', 'done', { after: ['c-u', 'a-u'] })]);
    const g = layerGraph(plan);
    const long = g.edgePaths.find((r) => r.from === 'kind:a' && r.to === 'kind:d');
    expect(long?.steps.map((s) => (isPoint(s.id) ? 'point' : s.id))).toEqual(['kind:a', 'point', 'point', 'kind:d']);
    expect(g.slots['']?.map((row) => row.length)).toEqual([1, 2, 2, 1]);
    for (const down of [false, true]) {
      const sizes = sizesOf(g);
      const l = layoutGraph(g, sizes, down);
      check(g, l, sizes);
      // The chain a -> b -> c -> d runs straight.
      const across = (id: string) => (down ? (l.at[id]?.x ?? 0) : (l.at[id]?.y ?? 0));
      expect(new Set(['kind:a', 'kind:b', 'kind:c', 'kind:d'].map(across)).size).toBe(1);
    }
  });

  it('reduces crossings with barycentre sweeps', () => {
    // Two chains given crosswise: x1 -> y2, x2 -> y1 must not cross.
    const plan = planOf([
      node('x1-u', 'u', 'x1', 'done'), node('x2-u', 'u', 'x2', 'done'),
      node('y1-u', 'u', 'y1', 'done', { after: ['x2-u'] }), node('y2-u', 'u', 'y2', 'done', { after: ['x1-u'] }),
    ]);
    expect(rows(layerGraph(plan))).toEqual([['kind:x1', 'kind:x2'], ['kind:y2', 'kind:y1']]);
  });

  it('keeps a previous order: a point moves, the nodes do not', () => {
    const before = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['b-u'] })]);
    const g1 = layerGraph(before);
    const after = planOf([...before.nodes, node('d-u', 'u', 'd', 'pending', { after: ['c-u', 'a-u'] }), node('e-u', 'u', 'e', 'pending', { after: ['a-u'] })]);
    const g2 = layerGraph(after, [], g1.order);
    expect(rows(g2)).toEqual([['kind:a'], ['kind:b', 'kind:e'], ['kind:c'], ['kind:d']]);
  });

  it('draws loop boxes around their nodes, edges in and out of them through their sides', () => {
    for (const down of [false, true]) {
      const g = layerGraph(reviewRun({ a: 1, b: 2 }), [RUN, LOOP], undefined, down);
      const sizes = sizesOf(g);
      const l = layoutGraph(g, sizes, down);
      check(g, l, sizes);
      const box = l.at[`loop:${AT}`] as { x: number; y: number; w: number; h: number };
      for (const id of [`kind:fix@${AT}`, `kind:score@${AT}`, `kind:check@${AT}`]) {
        const r = l.at[id] as typeof box;
        expect(r.x >= box.x && r.y >= box.y && r.x + r.w <= box.x + box.w && r.y + r.h <= box.y + box.h, id).toBe(true);
      }
      // The stub from outside the layer comes first.
      const stub = l.at['stub:1:kind:prepare'] as typeof box;
      expect(down ? stub.y < (l.at['kind:summarize']?.y ?? 0) : stub.x < (l.at['kind:summarize']?.x ?? 0)).toBe(true);
    }
  });

  it('takes an edge into a box through its side, next to the layer it goes to, and out after the layer it leaves', () => {
    // s -> a -> b -> c in a loop; s -> c goes in beside a and b; b -> w comes out beside c; s -> w goes round the box.
    const L = [F(RUN), F(LOOP, AT)];
    const plan = planOf([
      ft('s-u', 'u', 's', 'done', [F(RUN), F(LOOP)]),
      ft('a-u', 'u', 'a', 'done', L, { after: ['s-u'] }),
      ft('b-u', 'u', 'b', 'done', L, { after: ['a-u'] }),
      ft('c-u', 'u', 'c', 'done', L, { after: ['b-u', 's-u'] }),
      ft('w-u', 'u', 'w', 'done', [F(RUN), F(LOOP)], { after: ['b-u', 's-u', 'c-u'] }),
    ]);
    for (const down of [false, true]) {
      const g = layerGraph(plan, [RUN, LOOP], undefined, down);
      const into = g.edgePaths.find((r) => r.from === 'kind:s' && r.to === `kind:c@${AT}`);
      expect(into?.steps.map((x) => (x.id.includes('|by:') ? 'beside' : isPoint(x.id) ? 'point' : x.id))).toEqual(['kind:s', 'beside', `loop:${AT}`, `kind:c@${AT}`]);
      const out = g.edgePaths.find((r) => r.from === `kind:b@${AT}` && r.to === 'kind:w');
      expect(out?.steps.map((x) => (x.id.includes('|by:') ? 'beside' : isPoint(x.id) ? 'point' : x.id))).toEqual([`kind:b@${AT}`, `loop:${AT}`, 'beside', 'kind:w']);
      const sizes = sizesOf(g);
      check(g, layoutGraph(g, sizes, down), sizes);
    }
  });

  it('nests boxes, each wide enough for its label', () => {
    const SCAN = 'flows.scan';
    const at = (loops: number[]) => [F(RUN), F(SCAN, ...loops)];
    const plan = planOf([
      ft('rank-a', 'a', 'rank', 'done', at([])),
      ft('propose-a', 'a', 'propose', 'done', at([30]), { created_from: ['rank-a'] }),
      ft('verify-a', 'a', 'verify', 'done', at([30, 33]), { after: ['propose-a'] }),
      ft('refine-a', 'a', 'refine', 'done', at([30, 33]), { after: ['verify-a', 'propose-a'] }),
      ft('report-a', 'a', 'report', 'done', at([]), { after: ['refine-a'] }),
    ]);
    for (const down of [false, true]) {
      const g = layerGraph(plan, [RUN, SCAN], undefined, down);
      const sizes = sizesOf(g, 60, 40);
      sizes.set('lbl:loop:30.33', { w: 400, h: 20 });
      check(g, layoutGraph(g, sizes, down), sizes);
    }
    const g = layerGraph(plan, [RUN, SCAN]);
    const sizes = sizesOf(g, 60, 40);
    sizes.set('lbl:loop:30.33', { w: 400, h: 20 });
    const l = layoutGraph(g, sizes);
    expect(l.at['loop:30.33']?.w).toBeGreaterThanOrEqual(400);
    expect((l.at['loop:30']?.w ?? 0) > (l.at['loop:30.33']?.w ?? 0)).toBe(true);
  });


  it("draws a loop's return from its last layer, along the band past its content, back to its first", () => {
    const g = layerGraph(reviewRun({ a: 1, b: 2 }), [RUN, LOOP]);
    const sizes = sizesOf(g);
    const l = layoutGraph(g, sizes);
    const box = l.at[`loop:${AT}`] as { x: number; y: number; w: number; h: number };
    const r = l.returns[0] as LoopReturn;
    const first = l.at[`kind:fix@${AT}`] as typeof box;
    const last = l.at[`kind:check@${AT}`] as typeof box;
    expect(r.to).toBe(first.x + first.w / 2);
    expect(r.from).toBe(last.x + last.w / 2);
    expect(r.band).toBe(box.y + box.h - RETURN_BAND / 2);
    // Up from the band into the first layer, with rounded corners; top to bottom, the same along x.
    expect(returnPath({ box: 'b', from: 100, v0: 40, to: 20, v1: 40, band: 60 })).toBe('M100,43 L100,54 Q100,60 94,60 L26,60 Q20,60 20,54 L20,43');
    expect(returnPath({ box: 'b', from: 100, v0: 40, to: 20, v1: 40, band: 60 }, true)).toBe('M43,100 L54,100 Q60,100 60,94 L60,26 Q60,20 54,20 L43,20');
  });

  it('draws the return of a loop of one layer under its node, either side of its middle', () => {
    const L = [F(RUN), F(LOOP, AT)];
    const plan = planOf([ft('a-u', 'u', 'a', 'done', L), ft('a-u~2', 'u', 'a', 'done', L, { pass: 2 })]);
    for (const down of [false, true]) {
      const g = layerGraph(plan, [RUN, LOOP], undefined, down);
      const sizes = sizesOf(g);
      const l = layoutGraph(g, sizes, down);
      check(g, l, sizes);
      const n = l.at[`kind:a@${AT}`] as { x: number; y: number; w: number; h: number };
      const r = l.returns[0] as LoopReturn;
      const mid = down ? n.y + n.h / 2 : n.x + n.w / 2;
      expect(r.from - mid).toBeCloseTo(mid - r.to);
      expect(r.from - r.to).toBeGreaterThan(20);
    }
  });
});
