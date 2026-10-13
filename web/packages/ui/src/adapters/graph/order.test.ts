// The graph's order and drawing, frozen: for every layer of the demo run and of
// the plans in `plans.fixture.ts`, left to right and top to bottom, the slots,
// routes and order `layerGraph` gives (the generic `arrange` on the layer's
// projection), where `layoutGraph` puts everything, and every loop's passes. A
// change here changes how a run's graph is drawn. The snapshot names an edge's
// style by its type (solid: `after`, dashed: `created`), the order's clusters
// `boxes`, as the graph did before the order moved to @contraagent/elements: the
// file is unchanged since, so the drawing is the same.
import type { Plan } from '@contraagent/api';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { autoLayer, layerGraph } from './layer.js';
import { passMatrix } from './matrix.js';
import { edgePath, layoutGraph, returnPath, type GraphOrder, type Size } from '@contraagent/elements/graph';
import { node, planOf, reviewRun, RUN, LOOP, shapes } from './plans.fixture.js';
import type { LayerGraph } from './types.js';

const demoRun = JSON.parse(readFileSync(new URL('../../../../../apps/docs/src/fixtures/demo-run.json', import.meta.url), 'utf8')) as { plan: Plan };

/** Sizes that differ by node, so the drawing depends on them. */
function sizesOf(g: LayerGraph): Map<string, Size> {
  const m = new Map<string, Size>();
  for (const n of g.nodes) m.set(n.id, { w: 90 + 4 * n.label.length, h: 40 + 12 * Math.ceil(n.units.length / 6) + 10 * n.single.length });
  for (const s of g.stubs) m.set(s.id, { w: 60 + 4 * s.label.length, h: 22 });
  for (const b of g.boxes) m.set(`lbl:${b.id}`, { w: 120 + 3 * b.id.length, h: 20 });
  return m;
}

const rect = (r: { x: number; y: number; w: number; h: number }) => `${r.x},${r.y} ${r.w}x${r.h}`;

/** One layer, one direction: what the drawing depends on, as text. */
/** An edge style by its type, as the snapshot names it. */
const typed = (s: string): string => s.replaceAll('|solid|', '|after|').replaceAll('|dashed|', '|created|');
const typeOf = (style: string): string => (style === 'solid' ? 'after' : 'created');

function frozen(plan: Plan, path: readonly string[], down: boolean, prev?: GraphOrder) {
  const g = layerGraph(plan, path, prev, down);
  const l = layoutGraph(g, sizesOf(g), down);
  return {
    nodes: g.nodes.map((n) => `${n.id} [${n.units.map((m) => m?.key ?? '-').join(' ')}] [${n.single.map((m) => m.key).join(' ')}]`),
    layers: g.layers,
    boxes: g.boxes.map((b) => `${b.id} < ${b.parent ?? ''} passes ${b.passes} spread ${JSON.stringify(b.spread)} ${JSON.stringify(b.layers)}`),
    edges: g.edges.map((e) => `${e.from} > ${e.to} ${e.type} ${e.tasks}${e.back ? ' back' : ''}`),
    stubs: g.stubs.map((s) => `${s.id} > ${s.to} ${s.type} ${s.tasks}`),
    units: g.units,
    slots: Object.fromEntries(Object.entries(g.slots).map(([c, rows]) => [c, rows.map((row) => row.map(typed))])),
    routes: g.routes.map((r) => `${typeOf(r.style)}: ${r.steps.map((s) => `${typed(s.id)}@${s.in}`).join(' | ')}`),
    order: { layers: g.order.layers, boxes: g.order.clusters },
    size: `${l.w}x${l.h}`,
    at: Object.entries(l.at).map(([id, r]) => `${id} ${rect(r)}`),
    lines: l.edges.map((e) => `${e.from} > ${e.to}: ${edgePath(e.runs, down)}`),
    returns: l.returns.map((r) => `${r.box}: ${returnPath(r, down)}`),
  };
}

/** Every layer of `plan` reachable from the top, each loop's passes, both directions. */
function walk(plan: Plan): Record<string, unknown> {
  const out: Record<string, unknown> = { auto: autoLayer(plan).join(' / ') };
  const seen = new Set<string>();
  const visit = (path: string[]) => {
    const name = path.join(' / ') || '(top)';
    if (seen.has(name)) return;
    seen.add(name);
    out[`${name} | across`] = frozen(plan, path, false);
    out[`${name} | down`] = frozen(plan, path, true);
    const g = layerGraph(plan, path);
    for (const b of g.boxes) {
      const m = passMatrix(plan, path, b.id, g.order);
      out[`${name} | ${b.id}`] = m && {
        columns: m.columns.map((c) => `${c.node.id}|${c.passes.join('.')}`),
        head: m.head.map((r) => r.map((h) => `${h.type === 'node' ? h.node.id : `${h.type} ${h.box.id}${h.type === 'pass' ? ` ${h.pass}` : ''}`} ${h.span}x${h.rows}`)),
        rows: m.rows.map((r) => `${r.unit} ${r.passes} ${r.state}: ${r.cells.map((c) => c?.key ?? '-').join(' ')}`),
      };
    }
    for (const n of g.nodes) if (n.type === 'flow') visit([...path, n.name]);
  };
  visit([]);
  return out;
}

describe('the graph of each plan, frozen', () => {
  it('the demo run', () => {
    expect(walk(demoRun.plan)).toMatchSnapshot();
  });
  it.each(Object.entries(shapes()))('%s', (_, plan) => {
    expect(walk(plan)).toMatchSnapshot();
  });
  it('with a previous order', () => {
    const first = layerGraph(reviewRun({ a: 0, b: 1 }), [RUN, LOOP]);
    const before = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['a-u'] })]);
    const after = planOf([node('z-u', 'u', 'z', 'pending'), ...before.nodes, node('d-u', 'u', 'd', 'pending', { after: ['z-u'] }), node('c-v', 'v', 'c', 'pending', { after: ['z-u'] })]);
    const chain = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['b-u'] })]);
    const grown = planOf([...chain.nodes, node('d-u', 'u', 'd', 'pending', { after: ['c-u', 'a-u'] }), node('e-u', 'u', 'e', 'pending', { after: ['a-u'] })]);
    expect({
      'a loop box after pass 2': frozen(reviewRun({ a: 0, b: 2 }), [RUN, LOOP], false, first.order),
      'a loop box after pass 2, down': frozen(reviewRun({ a: 0, b: 2 }), [RUN, LOOP], true, first.order),
      'nodes that appear later': frozen(after, [], false, layerGraph(before).order),
      'a point moves': frozen(grown, [], false, layerGraph(chain).order),
    }).toMatchSnapshot();
  });
});
