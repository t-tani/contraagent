import { describe, expect, it } from 'vitest';
import { layerGraph } from './layer.js';
import { passMatrix } from './matrix.js';
import { AT, LOOP, RUN, node, planOf, reviewRun } from './plans.fixture.js';
import { layerCounts, markSel, selected } from './selection.js';
import type { LayerGraph } from './types.js';

const byId = (g: LayerGraph) => new Map(g.nodes.map((n) => [n.id, n]));

describe('what is selected', () => {
  const plan = reviewRun({ a: 1, b: 2 });
  const g = layerGraph(plan, [RUN, LOOP]);
  it('names a node, a loop box or a mark of the layer', () => {
    expect(selected(g, null, 'kind:summarize')).toMatchObject({ type: 'node', node: { id: 'kind:summarize' } });
    expect(selected(g, null, `loop:${AT}`)).toMatchObject({ type: 'box', box: { id: `loop:${AT}` } });
    const fix = g.nodes.find((n) => n.id === `kind:fix@${AT}`);
    const mark = fix?.units.find((m) => m?.unit === 'b');
    expect(markSel(`kind:fix@${AT}`, mark ?? { unit: 'b', key: '' })).toBe(`kind:fix@${AT}#b`);
    expect(selected(g, null, `kind:fix@${AT}#b`)).toMatchObject({ type: 'mark', mark: { unit: 'b', key: 'fix-b~2', passes: 2 }, passes: [] });
    expect(selected(g, null, 'kind:gone')).toBeNull();
    expect(selected(g, null, `kind:fix@${AT}#zz`)).toBeNull();
    expect(selected(g, null, '')).toBeNull();
  });
  it("names a mark of a loop's passes by its column", () => {
    const m = passMatrix(plan, [RUN, LOOP], `loop:${AT}`);
    expect(selected(g, m, `kind:fix@${AT}|2#b`)).toMatchObject({ type: 'mark', mark: { key: 'fix-b~2' }, passes: [2] });
    expect(selected(g, m, `kind:fix@${AT}|1#b`)).toMatchObject({ mark: { key: 'fix-b' }, passes: [1] });
    expect(selected(g, m, `kind:fix@${AT}|2#a`)).toBeNull();
    expect(selected(g, null, `kind:fix@${AT}|2#b`)).toBeNull();
  });
  it("adds up the layer's tasks by state", () => {
    expect(layerCounts(g.nodes)).toMatchObject({ total: g.nodes.reduce((a, n) => a + n.counts.total, 0) });
    expect(layerCounts([])).toMatchObject({ total: 0, done: 0 });
  });
  it('tells who runs a kind node: an agent, Python or both; a function node, neither', () => {
    const top = layerGraph(plan, [RUN]);
    expect(byId(top).get('kind:prepare')?.executor).toBe('python');
    expect(byId(top).get(`flow:${LOOP}`)?.executor).toBeNull();
    expect(byId(g).get('kind:summarize')?.executor).toBe('agent');
    const mixed = planOf([node('a-1', '1', 'g', 'done', { executor: 'python' }), node('b-1', '1', 'g', 'done')]);
    expect(layerGraph(mixed).nodes[0]?.executor).toBe('mixed');
  });
});
