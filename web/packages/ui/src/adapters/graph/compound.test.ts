import { arrange, extentOf } from '@contraagent/elements/graph';
import { describe, expect, it } from 'vitest';
import { compound, doi, FLOW_BOX, IN_SEP, placeKey, placeStats } from './compound.js';
import { indexOf } from './flow-index.js';
import { F, ft, planOf } from './plans.fixture.js';
import { shapeOf } from './project.js';

const MAIN = 'flows.main';
const WORK = 'flows.work';
const INNER = 'flows.inner';
const TIDY = 'flows.tidy';
const py = { executor: 'python' as const };

/**
 * main: fetch (Python) → work → tidy. `work` holds a plan step and one function, `inner`;
 * `inner` holds the agent's writes (per unit) and a check. `tidy` is Python steps, all done.
 */
function nested(state: (key: string) => 'done' | 'failed' | 'pending' = () => 'done') {
  const at = (...fns: string[]) => fns.map((f) => F(f));
  return planOf([
    ft('fetch', '', 'fetch', state('fetch'), at(MAIN), py),
    ft('plan', '', 'plan', state('plan'), at(MAIN, WORK), { ...py, after: ['fetch'] }),
    ft('write-a', 'a', 'write', state('write-a'), at(MAIN, WORK, INNER), { after: ['plan'] }),
    ft('write-b', 'b', 'write', state('write-b'), at(MAIN, WORK, INNER), { after: ['plan'] }),
    ft('check-a', 'a', 'check', state('check-a'), at(MAIN, WORK, INNER), { ...py, after: ['write-a'] }),
    ft('tidy-1', '', 'tidy1', state('tidy-1'), at(MAIN, TIDY), { ...py, after: ['check-a'] }),
    ft('tidy-2', '', 'tidy2', state('tidy-2'), at(MAIN, TIDY), { ...py, after: ['tidy-1'] }),
  ]);
}

const keyOf = (layer: string[], fn: string) => placeKey(layer, `flow:${fn}`);
const WORK_KEY = keyOf([MAIN], WORK);
const INNER_KEY = keyOf([MAIN, WORK], INNER);
const TIDY_KEY = keyOf([MAIN], TIDY);

describe('compound: the layer shown with functions drawn open', () => {
  it('opens what is notable within the budget, a chain of single functions as one box named by its path', () => {
    const c = compound(nested(), [MAIN], { budget: 40 });
    expect([...c.open].sort()).toEqual([INNER_KEY, WORK_KEY].sort());
    // tidy: finished Python steps only, so it stays a node.
    expect(c.model.nodes.map((n) => n.label)).toEqual(expect.arrayContaining(['fetch', 'tidy', 'plan', 'write', 'check']));
    expect(c.model.fns).toHaveLength(1);
    const box = c.model.fns[0];
    expect(box?.id).toBe(`${FLOW_BOX}${WORK_KEY}`);
    expect(box?.parts.map((p) => p.node.label)).toEqual(['work', 'inner']);
    // Every node inside the chain is drawn in its box, with its own layer.
    const write = c.model.nodes.find((n) => n.label === 'write');
    expect(write?.box).toBe(box?.id);
    expect(write?.layer).toEqual([MAIN, WORK, INNER]);
    expect(write?.id).toBe(`${INNER_KEY}${IN_SEP}kind:write`);
    // Its marks in the run's unit order.
    expect(c.model.units).toEqual(['a', 'b']);
    expect(write?.units.map((m) => m?.unit)).toEqual(['a', 'b']);
  });

  it('joins nodes across the boxes they are drawn in, by the tasks behind them', () => {
    const c = compound(nested(), [MAIN], { budget: 40 });
    const pairs = c.model.edges.map((e) => `${e.from} > ${e.to}`);
    expect(pairs).toContain(`kind:fetch > ${WORK_KEY}${IN_SEP}kind:plan`);
    expect(pairs).toContain(`${WORK_KEY}${IN_SEP}kind:plan > ${INNER_KEY}${IN_SEP}kind:write`);
    expect(pairs).toContain(`${INNER_KEY}${IN_SEP}kind:check > flow:${TIDY}`);
    // It is laid out as one compound drawing.
    const a = arrange(shapeOf(c.model));
    expect(a.clusters.map((x) => x.id)).toContain(`${FLOW_BOX}${WORK_KEY}`);
  });

  it("keeps the reader's opens and closes over the choice", () => {
    expect(compound(nested(), [MAIN], { budget: 40, closed: new Set([WORK_KEY]) }).open.size).toBe(0);
    expect(compound(nested(), [MAIN], { budget: 40, open: new Set([TIDY_KEY]) }).open.has(TIDY_KEY)).toBe(true);
    // A place opens only inside open places.
    expect(compound(nested(), [MAIN], { budget: 40, closed: new Set([WORK_KEY]), open: new Set([INNER_KEY]) }).open.size).toBe(0);
    expect(compound(nested(), [MAIN], { budget: 40, all: true }).open.size).toBe(3);
  });

  it('opens nothing on its own over the budget, and closes again what makes the drawing too long', () => {
    expect(compound(nested(), [MAIN], { budget: 3 }).open.size).toBe(0);
    const c = compound(nested(), [MAIN], { budget: 40, maxSpan: 3 });
    expect(extentOf(arrange(shapeOf(c.model))).span).toBeLessThanOrEqual(3);
    expect(c.open.size).toBe(0);
  });

  it('opens a failure first: the more interesting of two places, when only one fits', () => {
    const OTHER = 'flows.other';
    const plan = planOf([
      ft('w1', 'a', 'w', 'done', [F(MAIN), F(WORK)]),
      ft('w2', 'b', 'w2', 'done', [F(MAIN), F(WORK)]),
      ft('o1', 'a', 'o', 'failed', [F(MAIN), F(OTHER)]),
      ft('o2', 'b', 'o2', 'done', [F(MAIN), F(OTHER)]),
    ]);
    const stats = placeStats(indexOf(plan), [MAIN]);
    const work = stats.get(WORK_KEY);
    const other = stats.get(keyOf([MAIN], OTHER));
    expect(work && other && doi(other) > doi(work)).toBe(true);
    // Two nodes now; opening one adds one more.
    expect([...compound(plan, [MAIN], { budget: 3 }).open]).toEqual([keyOf([MAIN], OTHER)]);
  });

  it('selecting inside a place makes it, and every place around it, more interesting', () => {
    const plan = nested();
    const toward = compound(plan, [MAIN], { budget: 0, sel: `${INNER_KEY}${IN_SEP}kind:write#a`, open: new Set() });
    // No budget: nothing opens, but the choice saw the selection's places.
    expect(toward.open.size).toBe(0);
    const stats = placeStats(indexOf(plan), [MAIN]);
    const s = stats.get(INNER_KEY);
    expect(s && doi(s, new Set([INNER_KEY])) > doi(s)).toBe(true);
  });

  it('draws two thousand tasks over six levels quickly', () => {
    const levels = ['flows.l0', 'flows.l1', 'flows.l2', 'flows.l3', 'flows.l4', 'flows.l5'];
    const nodes = [];
    for (let i = 0; i < 2000; i++) {
      const depth = 1 + (i % 6);
      // Two functions at each level, so no chain merges them all.
      const path = levels.slice(0, depth).map((f, j) => F(j === 0 ? f : `${f}${(i >> j) % 2}`));
      nodes.push(ft(`t${i}`, `u${i % 40}`, `k${depth}${i % 3}`, i % 97 === 0 ? 'failed' : 'done', path, i % 5 ? {} : py));
    }
    const plan = planOf(nodes);
    const t0 = performance.now();
    const c = compound(plan, [levels[0] as string], { budget: 40, maxSpan: 13 });
    const a = arrange(shapeOf(c.model));
    const ms = performance.now() - t0;
    expect(c.model.nodes.length).toBeLessThanOrEqual(60);
    expect(a.layers.length).toBeGreaterThan(0);
    // Generous for a loaded test machine; the report gives the measured time.
    expect(ms).toBeLessThan(1500);
  });
});
