import { describe, expect, it } from 'vitest';
import { arrangeBefore } from './arrange-before.fixture.js';
import { arrange, crossingPairs, type GraphShape } from './arrange.js';
import { layoutGraph as layoutBefore } from './layout-before.fixture.js';
import { layoutGraph } from './layout.js';
import type { EdgeStyle } from './types.js';

const random = (seed: number) => () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const STYLES: EdgeStyle[] = ['solid', 'dotted', 'dashed'];

/** A random compound graph: clusters in clusters, nodes in them or at the top, edges across them, stubs. */
function randomShape(seed: number): GraphShape {
  const r = random(seed);
  const pick = <T>(xs: readonly T[]): T => xs[Math.floor(r() * xs.length)] as T;
  const clusters: GraphShape['clusters'][number][] = [];
  const nc = Math.floor(r() * 5);
  for (let i = 0; i < nc; i++) clusters.push({ id: `c${i}`, parent: i && r() < 0.5 ? `c${Math.floor(r() * i)}` : null, cycle: r() < 0.5 });
  const nn = 1 + Math.floor(r() * 18);
  const nodes = Array.from({ length: nn }, (_, i) => ({ id: `n${i}`, cluster: nc && r() < 0.6 ? `c${Math.floor(r() * nc)}` : null }));
  const ne = Math.floor(r() * nn * 2);
  const edges = Array.from({ length: ne }, () => ({ from: pick(nodes).id, to: pick(nodes).id, style: pick(STYLES), ranks: r() < 0.8 }));
  const ns = Math.floor(r() * 3);
  const stubs = Array.from({ length: ns }, (_, i) => ({ id: `stub:${i % 2}`, to: pick(nodes).id, style: pick(STYLES) }));
  return { nodes, clusters, edges, stubs };
}

/** The same structure, as other objects. */
const copy = (g: GraphShape): GraphShape => JSON.parse(JSON.stringify(g)) as GraphShape;

describe('arrange', () => {
  it('gives what the first arrangement gave, on random compound graphs', () => {
    for (let s = 1; s <= 400; s++) {
      const g = randomShape(s);
      for (const down of [false, true]) {
        const a = arrange(g, undefined, down);
        expect(a, `seed ${s}`).toEqual(arrangeBefore(g, undefined, down));
        // The graph grown by a node: the order of the last drawing is kept.
        const more = { ...g, nodes: [...g.nodes, { id: 'late', cluster: g.nodes[0]?.cluster ?? null }], edges: [...g.edges, { from: g.nodes[0]?.id ?? 'late', to: 'late', style: 'solid' as const, ranks: true }] };
        expect(arrange(more, a.order, down), `seed ${s}, grown`).toEqual(arrangeBefore(more, a.order, down));
      }
    }
  });

  it('gives the same object for a graph of the same structure, and another for a changed one', () => {
    const g = randomShape(7);
    const a = arrange(g);
    expect(arrange(copy(g))).toBe(a);
    const moved = copy(g);
    moved.edges = [...moved.edges, { from: 'n0', to: 'n0', style: 'dashed', ranks: false }];
    expect(arrange(moved)).not.toBe(a);
    // undefined and null are not the same parent.
    const loose = { ...copy(g), clusters: [{ id: 'x', parent: undefined as unknown as null }] };
    const none = { ...copy(g), clusters: [{ id: 'x', parent: null }] };
    expect(arrange(loose).clusters[0]?.parent).toBeUndefined();
    expect(arrange(none).clusters[0]?.parent).toBeNull();
  });
});

describe('layoutGraph', () => {
  it('draws what the first layout drew, on random compound graphs and sizes', () => {
    for (let s = 1; s <= 200; s++) {
      const g = randomShape(s);
      const r = random(s + 1000);
      for (const down of [false, true]) {
        const a = arrange(g, undefined, down);
        const sizes = new Map([...g.nodes.map((n) => n.id), ...g.stubs.map((x) => x.id), ...g.clusters.map((c) => `lbl:${c.id}`)].map((id) => [id, { w: 20 + Math.floor(r() * 200), h: 10 + Math.floor(r() * 80) }]));
        expect(layoutGraph(a, sizes, down), `seed ${s}`).toEqual(layoutBefore(a, sizes, down));
      }
    }
  });
});

describe('crossingPairs', () => {
  const pairwise = (ls: readonly (readonly [number, number])[]): number => {
    let n = 0;
    for (let i = 0; i < ls.length; i++)
      for (let j = i + 1; j < ls.length; j++) if (((ls[i] as [number, number])[0] - (ls[j] as [number, number])[0]) * ((ls[i] as [number, number])[1] - (ls[j] as [number, number])[1]) < 0) n++;
    return n;
  };

  it('counts the pairs a pairwise count counts, ties included', () => {
    for (let s = 1; s <= 500; s++) {
      const r = random(s);
      const n = Math.floor(r() * 40);
      const w = 1 + Math.floor(r() * 10);
      const ls = Array.from({ length: n }, () => [Math.floor(r() * w), Math.floor(r() * w)] as const);
      expect(crossingPairs(ls), `seed ${s}`).toBe(pairwise(ls));
    }
    expect(crossingPairs([[0.5, 1], [1, 0], [2, -1]])).toBe(3);
  });
});
