import type { FlowCallNode, FlowFrame, JournalRow, Plan, PlanNode } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import {
  alongEdge, asBar, autoLayer, barBox, barParts, edgePath, fitView, gridStep, isPoint, kpis, layerGraph, layoutGraph, markGrid, parentLayer, passMatrix,
  sortRows, splitLayer, timeline, worstState, zoomView,
  RETURN_BAND, layerCounts, markSel, resolveLayer, returnPath, selected,
  type GraphLayout, type LayerGraph, type LoopReturn, type Size,
} from './logic.js';

const node = (key: string, unit: string, group: string, state: PlanNode['state'], extra: Partial<PlanNode> = {}): PlanNode => ({
  key, kind: group, unit, group, state, level: 0, ...extra,
});
const group = (id: string, counts: Partial<Plan['groups'][number]> = {}): Plan['groups'][number] => ({
  id, label: id, total: 0, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, ...counts,
});
const row = (key: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T10:00:00Z', key, kind: 'k', stop: 'completed', ok: true, ...extra,
});

describe('kpis', () => {
  it('counts tries that ran: a refusal is no try, no session and no failure', () => {
    const k = kpis([
      row('a', { wall_s: 2 }),
      row('b', { executor: 'python', wall_s: 1 }),
      row('c', { stop: 'timeout', ok: false, wall_s: 1 }),
      row('c', { attempt: 1, rounds: 3, hops: [{}, {}] }),
      row('d', { stop: 'invalid_input', ok: false }),
    ]);
    expect(k).toEqual({
      attempts: 4, python: 1, launches: 3, bad: 1, launchWall: 3, pythonWall: 1,
      retries: 1, retriedTasks: 1, fixups: 2, fixupTasks: 1, switches: 1, switchTasks: 1,
      retriedKeys: ['c'], fixupKeys: ['c'],
    });
  });

  it('counts a retry only after a try that ran and failed: refused, then done, is no retry', () => {
    const k = kpis([row('a', { stop: 'invalid_input', ok: false }), row('a', { attempt: 1 })]);
    expect(k).toMatchObject({ attempts: 1, bad: 0, retries: 0, retriedTasks: 0, retriedKeys: [] });
  });
});

describe('timeline', () => {
  const end = Date.parse('2026-10-11T10:00:00Z');

  it('lays finished tasks on lanes by kind, in order of first start', () => {
    const tl = timeline(
      [row('a', { kind: 'late', wall_s: 10 }), row('b', { kind: 'early', wall_s: 60, executor: 'python' }), row('c', { kind: 'late', stop: 'error', ok: false })],
      [],
      end + 1000,
    );
    expect(tl?.lanes.map((l) => [l.name, l.llm, l.bars.map((b) => b.cls)])).toEqual([
      ['early', false, ['py']],
      ['late', true, ['llm', 'bad']],
    ]);
    expect(tl?.t0).toBe(end - 60e3);
    expect(tl?.span).toBe(60e3);
    expect(tl?.live).toBe(false);
  });

  it('leaves out what ended more than six hours before the newest', () => {
    const tl = timeline([row('old', { ts: '2026-10-11T03:00:00Z' }), row('new')], [], end);
    expect(tl?.hidden).toBe(1);
  });

  it('grows running tasks to now, on a span rounded up to the minute', () => {
    const tl = timeline([], [{ kind: 'k', cls: 'llm', t0: end }], end + 30e3);
    expect(tl?.span).toBe(60e3);
    const bar = tl?.lanes[0]?.bars[0];
    expect(bar && tl && barBox(bar, tl, end + 30e3)).toEqual({ left: 0, width: 50 });
    expect(tl?.lanes[0]?.llm).toBe(true);
  });

  it('stacks overlapping bars of one lane on tracks, and greys a task that never started', () => {
    const tl = timeline(
      [row('a', { wall_s: 10 }), row('a', { wall_s: 5, attempt: 1 }), row('z', { stop: 'invalid_input', ok: false, ts: '2026-10-11T10:00:20Z' })],
      [],
      end,
    );
    const lane = tl?.lanes[0];
    expect(lane?.tracks).toBe(2);
    expect(lane?.bars.map((b) => [b.cls, b.track])).toEqual([['llm', 0], ['llm', 1], ['idle', 0]]);
  });

  it('is null with nothing to draw', () => {
    expect(timeline([], [], end)).toBeNull();
  });
});

describe('worstState', () => {
  it('of nothing is done, else the most severe', () => {
    expect(worstState([])).toBe('done');
    expect(worstState([node('x', '', 'a', 'skipped'), node('y', '', 'a', 'blocked')])).toBe('blocked');
  });
});

// Synthetic plans, as a run writes them: a task's flow path (outermost first) with the
// loops around each call site, what its flow call had received when it was created, and
// its flow call. `pass` is the pass of the innermost loop around the task's own call site;
// `passes`, one pass per loop around it, outermost first.
const F = (fn: string, ...loops: number[]): FlowFrame => ({ function: fn, file: 'flow.py', line: 1, loops: loops.map((line) => ({ line, pass: 1 })) });
const ft = (
  key: string,
  unit: string,
  kind: string,
  state: PlanNode['state'],
  flow: FlowFrame[],
  { pass = 1, passes, ...extra }: Partial<PlanNode> & { pass?: number; passes?: number[] } = {},
): PlanNode => {
  const last = flow[flow.length - 1];
  const loops = last?.loops ?? [];
  const at = (i: number) => passes?.[i] ?? (i === loops.length - 1 ? pass : 1);
  const own = last && loops.length ? [...flow.slice(0, -1), { ...last, loops: loops.map((l, i) => ({ ...l, pass: at(i) })) }] : flow;
  return node(key, unit, kind, state, { flow: own, flow_call: '0', created_from: [], ...extra });
};
const planOf = (nodes: PlanNode[], flow_calls?: FlowCallNode[]): Plan => {
  const groups = [...new Set(nodes.map((n) => n.group))].map((g) => group(g));
  return flow_calls ? { nodes, groups, flow_calls } : { nodes, groups };
};
const call = (id: string, fn: string, state: FlowCallNode['state'] = 'returned'): FlowCallNode => ({
  id, parent: id.includes('.') ? id.slice(0, id.lastIndexOf('.')) : null, function: fn, flow: [], state,
});
const rows = (g: LayerGraph) => g.layers;
const byId = (g: LayerGraph) => new Map(g.nodes.map((n) => [n.id, n]));

const RUN = 'flows.run_all';
const LOOP = 'flows.review_loop';
const AT = 7; // the line of review_loop's `while`

/**
 * run_all: prepare each unit (Python), then review_loop(u) for every unit as one batch,
 * then report on what they returned. review_loop: summarize, check, and while the review
 * is not ok: fix, score (Python), check. `passes[u]` is how many times u went round.
 */
function reviewRun(passes: Record<string, number>, opts: { calls?: boolean; failed?: string } = {}): Plan {
  const nodes: PlanNode[] = [];
  const top = [F(RUN)];
  const inLoop = [F(RUN), F(LOOP)];
  const looped = [F(RUN), F(LOOP, AT)];
  const finals: string[] = [];
  const lastChecks: string[] = [];
  Object.entries(passes).forEach(([u, n], i) => {
    const c = `0.${i + 1}`;
    const bad = opts.failed === u;
    nodes.push(ft(`prepare-${u}`, u, 'prepare', 'done', top, { executor: 'python' }));
    nodes.push(ft(`summarize-${u}`, u, 'summarize', 'done', inLoop, { flow_call: c, after: [`prepare-${u}`], created_from: [`prepare-${u}`] }));
    let summary = `summarize-${u}`;
    let check = `check-${u}`;
    nodes.push(ft(check, u, 'check', 'done', inLoop, { flow_call: c, after: [summary], created_from: [summary] }));
    for (let p = 1; p <= n; p++) {
      const sfx = p === 1 ? '' : `~${p}`;
      const fix = `fix-${u}${sfx}`;
      const score = `score-${u}${sfx}`;
      const last = p === n;
      nodes.push(ft(fix, u, 'fix', bad && last ? 'failed' : 'done', looped, { flow_call: c, pass: p, after: [summary, check], created_from: [check] }));
      if (bad && last) break;
      nodes.push(ft(score, u, 'score', 'done', looped, { flow_call: c, pass: p, executor: 'python', after: [fix], created_from: [fix] }));
      const next = `check-${u}~${p + 1}`;
      nodes.push(ft(next, u, 'check', 'done', looped, { flow_call: c, pass: p, after: [fix], created_from: [score] }));
      summary = fix;
      check = next;
    }
    finals.push(summary);
    lastChecks.push(check);
  });
  const failed = opts.failed !== undefined;
  if (!failed) nodes.push(ft('report', '', 'report', 'done', top, { after: finals, created_from: lastChecks }));
  const units = Object.keys(passes);
  const calls = [call('0', RUN, failed ? 'raised' : 'returned'), ...units.map((u, i) => call(`0.${i + 1}`, LOOP, opts.failed === u ? 'raised' : 'returned'))];
  return planOf(nodes, opts.calls ? calls : undefined);
}

describe('layerGraph: a static flow', () => {
  const UNITS = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta'];
  // The demo: prepare -> summarize -> { review, write_note }, review -> report (one task, no unit).
  const demo = (stateOf: (key: string) => PlanNode['state'] = (k) => (k.endsWith('zeta') ? 'blocked' : 'done'), flow?: FlowFrame[]): Plan => {
    const extra = (x: Partial<PlanNode>): Partial<PlanNode> => (flow ? { ...x, flow, flow_call: '0' } : x);
    const nodes: PlanNode[] = [];
    for (const u of UNITS) {
      nodes.push(node(`prepare-${u}`, u, 'prepare', u === 'zeta' ? 'failed' : stateOf(`prepare-${u}`), extra({})));
      nodes.push(node(`summarize-${u}`, u, 'summarize', stateOf(`summarize-${u}`), extra({ after: [`prepare-${u}`] })));
      nodes.push(node(`review-${u}`, u, 'review', stateOf(`review-${u}`), extra({ after: [`summarize-${u}`] })));
      nodes.push(node(`write_note-${u}`, u, 'write_note', stateOf(`write_note-${u}`), extra({ after: [`summarize-${u}`] })));
    }
    nodes.push(node('report', '', 'report', 'blocked', extra({ after: UNITS.map((u) => `review-${u}`) })));
    return { groups: ['prepare', 'summarize', 'review', 'write_note', 'report'].map((g) => group(g)), nodes };
  };
  const KINDS = [['kind:prepare'], ['kind:summarize'], ['kind:review', 'kind:write_note'], ['kind:report']];

  it('opens on its kinds, laid out by their dependencies', () => {
    const plan = demo();
    expect(autoLayer(plan)).toEqual([]);
    const g = layerGraph(plan, autoLayer(plan));
    expect(rows(g)).toEqual(KINDS);
    expect(g.boxes).toEqual([]);
    expect(g.stubs).toEqual([]);
    expect(g.edges).toEqual(
      expect.arrayContaining([
        { from: 'kind:prepare', to: 'kind:summarize', tasks: 6, type: 'after', back: false },
        { from: 'kind:summarize', to: 'kind:review', tasks: 6, type: 'after', back: false },
        { from: 'kind:summarize', to: 'kind:write_note', tasks: 6, type: 'after', back: false },
        { from: 'kind:review', to: 'kind:report', tasks: 1, type: 'after', back: false },
      ]),
    );
    expect(g.edges).toHaveLength(4);
  });

  it('with a flow path of one function, lands on the same kinds below it', () => {
    const plan = demo(undefined, [F('flows.pipeline')]);
    expect(autoLayer(plan)).toEqual(['flows.pipeline']);
    expect(rows(layerGraph(plan, autoLayer(plan)))).toEqual(KINDS);
    expect(rows(layerGraph(plan, []))).toEqual([['flow:flows.pipeline']]);
  });

  it('puts a unit at the same slot in every node, and a task without a unit on its own', () => {
    const g = layerGraph(demo());
    expect(g.units).toEqual(UNITS);
    const n = byId(g);
    expect(n.get('kind:prepare')?.units[5]).toMatchObject({ unit: 'zeta', state: 'failed', key: 'prepare-zeta' });
    expect(n.get('kind:summarize')?.units[5]).toMatchObject({ unit: 'zeta', state: 'blocked' });
    expect(n.get('kind:report')?.units).toEqual([]);
    expect(n.get('kind:report')?.single).toEqual([{ key: 'report', unit: '', state: 'blocked', count: 1, keys: ['report'] }]);
    expect(n.get('kind:prepare')?.counts).toEqual({ total: 6, done: 5, failed: 1, running: 0, pending: 0, skipped: 0, blocked: 0 });
  });

  it('keeps its layout while the states change', () => {
    expect(rows(layerGraph(demo((k) => (k.startsWith('review') ? 'running' : 'pending'))))).toEqual(rows(layerGraph(demo())));
  });

  it('leaves a slot empty where a unit has no task of the node', () => {
    const plan = planOf([node('a-u', 'u', 'a', 'done'), node('a-v', 'v', 'a', 'done'), node('b-v', 'v', 'b', 'running', { after: ['a-v'] })]);
    expect(byId(layerGraph(plan)).get('kind:b')?.units).toEqual([null, { key: 'b-v', unit: 'v', state: 'running', count: 1, keys: ['b-v'] }]);
  });

  it('marks waits inside a node, ignores tasks not scheduled yet, and survives a cycle', () => {
    const plan = planOf([
      node('a1', 'u', 'a', 'done'),
      node('a2', 'v', 'a', 'done', { after: ['a1', 'not-yet'] }),
      node('b1', 'u', 'b', 'done', { after: ['c1'] }),
      node('c1', 'u', 'c', 'done', { after: ['b1'] }),
    ]);
    const g = layerGraph(plan);
    expect(byId(g).get('kind:a')?.inOrder).toBe(true);
    expect(g.edges.map((e) => `${e.from}>${e.to}${e.back ? ' back' : ''}`).sort()).toEqual(['kind:b>kind:c', 'kind:c>kind:b back']);
    expect(g.nodes.map((n) => n.id).sort()).toEqual(['kind:a', 'kind:b', 'kind:c']);
  });
});

describe('layerGraph: a generator flow', () => {
  it('opens below the top flow on the per-unit flow calls and the task that joins them', () => {
    const plan = reviewRun({ a: 0, b: 1 }, { calls: true });
    expect(autoLayer(plan)).toEqual([RUN]);
    const g = layerGraph(plan, [RUN]);
    expect(rows(g)).toEqual([['kind:prepare'], [`flow:${LOOP}`], ['kind:report']]);
    const loop = byId(g).get(`flow:${LOOP}`);
    expect(loop).toMatchObject({ type: 'flow', label: 'review_loop', name: LOOP, single: [] });
    expect(loop?.units.map((m) => [m?.unit, m?.key, m?.state, m?.flow])).toEqual([
      ['a', '0.1', 'done', LOOP],
      ['b', '0.2', 'done', LOOP],
    ]);
    // report waits for what the calls returned, and was created after their checks: one solid edge.
    expect(g.edges.filter((e) => e.to === 'kind:report')).toEqual([{ from: `flow:${LOOP}`, to: 'kind:report', tasks: 1, type: 'after', back: false }]);
  });

  it("takes a flow call's state from the plan's flow calls, else from its tasks", () => {
    const withCalls = byId(layerGraph(reviewRun({ a: 0, b: 2 }, { calls: true, failed: 'b' }), [RUN])).get(`flow:${LOOP}`);
    expect(withCalls?.units.map((m) => m?.state)).toEqual(['done', 'failed']);
    const running = reviewRun({ a: 0, b: 1 });
    const n = running.nodes.find((x) => x.key === 'check-b~2');
    if (n) n.state = 'running';
    const derived = byId(layerGraph(running, [RUN])).get(`flow:${LOOP}`);
    expect(derived?.units.map((m) => m?.state)).toEqual(['done', 'running']);
  });

  it('shows the worst of a flow call and its tasks, so a call that caught a failure and returned shows it', () => {
    // b's review_loop caught its fix's failure and returned; a check after it did not start.
    const plan = reviewRun({ a: 0, b: 2 }, { calls: true, failed: 'b' });
    const calls = (plan.flow_calls ?? []).map((c) => ({ ...c, state: 'returned' as const }));
    plan.nodes.push(ft('check-b~3', 'b', 'check', 'blocked', [F(RUN), F(LOOP, AT)], { flow_call: '0.2', pass: 2, after: ['fix-b~2'] }));
    const g = layerGraph({ ...plan, flow_calls: calls }, [RUN]);
    const fn = byId(g).get(`flow:${LOOP}`);
    expect(fn?.units.map((m) => m?.state)).toEqual(['done', 'failed']);
    expect(fn?.units[1]).toMatchObject({ counts: { failed: 1, blocked: 1 } });
    expect(fn?.units[1]?.error).toBeUndefined();
    // The node counts its tasks, not its calls: 1 failed and 1 not started among them.
    expect(fn?.counts).toMatchObject({ failed: 1, blocked: 1 });
    expect(fn?.counts.total).toBe(fn?.units.reduce((n, m) => n + (m?.count ?? 0), 0));
    expect(fn).toMatchObject({ calls: 2, errors: 0 });
    // A call that raised with every task done still shows failed, and keeps its error.
    const ok = reviewRun({ a: 0, b: 1 }, { calls: true });
    const raised = (ok.flow_calls ?? []).map((c) => (c.id === '0.2' ? { ...c, state: 'raised' as const, error: 'ValueError: no score' } : c));
    const r = byId(layerGraph({ ...ok, flow_calls: raised }, [RUN])).get(`flow:${LOOP}`);
    expect(r?.units.map((m) => [m?.state, m?.error])).toEqual([['done', undefined], ['failed', 'ValueError: no score']]);
    expect(r).toMatchObject({ errors: 1, counts: { failed: 0 } });
  });

  it('descends into a single function node whose call returned with a failed task: the layer below shows the task', () => {
    const DOCS = 'flows.docs';
    const RL = 'flows.review_loop';
    const inRL = [F(DOCS), F(RL)];
    const plan = planOf(
      [ft('summarize-a', 'a', 'summarize', 'done', inRL, { flow_call: '0.1' }), ft('summarize-b', 'b', 'summarize', 'failed', inRL, { flow_call: '0.2' })],
      [call('0', DOCS), call('0.1', RL), call('0.2', RL)],
    );
    expect(autoLayer(plan)).toEqual([DOCS, RL]);
    expect(byId(layerGraph(plan, [DOCS, RL])).get('kind:summarize')?.units.map((m) => m?.state)).toEqual(['done', 'failed']);
  });

  it('draws a loop known at pass 1 as a box that stays the same after pass 2', () => {
    const first = layerGraph(reviewRun({ a: 0, b: 1 }), [RUN, LOOP]);
    const box = `loop:${AT}`;
    expect(first.boxes).toEqual([{ id: box, loop: AT, file: 'flow.py', parent: null, passes: 1, spread: [[1, 1]], layers: [[`kind:fix@${AT}`], [`kind:score@${AT}`], [`kind:check@${AT}`]] }]);
    expect(rows(first)).toEqual([['kind:summarize'], ['kind:check'], [box]]);
    expect(byId(first).get(`kind:fix@${AT}`)?.box).toBe(box);
    const second = layerGraph(reviewRun({ a: 0, b: 2 }), [RUN, LOOP], first.order);
    expect(rows(second)).toEqual(rows(first));
    expect(second.boxes[0]).toMatchObject({ passes: 2, spread: [[2, 1]] });
    // check (the next pass's) -> fix goes back to the next pass: drawn by the box, not laid out.
    expect(second.edges.find((e) => e.from === `kind:check@${AT}` && e.to === `kind:fix@${AT}`)?.back).toBe(true);
    expect(second.routes.some((r) => r.from === `kind:check@${AT}` && r.to === `kind:fix@${AT}`)).toBe(false);
  });

  it("counts each box's passes, how many units ran each number, and each mark's passes", () => {
    const g = layerGraph(reviewRun({ a: 1, b: 3, c: 0, d: 1, e: 2 }), [RUN, LOOP]);
    expect(g.boxes[0]).toMatchObject({ passes: 3, spread: [[1, 2], [2, 1], [3, 1]] });
    // a mark shows the passes its unit's tasks of the node ran in, when more than 1.
    expect(byId(g).get(`kind:fix@${AT}`)?.units.map((m) => m?.passes ?? null)).toEqual([null, 3, null, null, 2]);
    // a unit's mark in a loop box is its latest pass.
    expect(byId(g).get(`kind:check@${AT}`)?.units.map((m) => m?.key ?? null)).toEqual(['check-a~2', 'check-b~4', null, 'check-d~2', 'check-e~3']);
  });

  it('unrolls a loop box into units by (node, pass), leaving out what no unit reached', () => {
    const plan = reviewRun({ a: 1, b: 3, c: 0, d: 2 }, { failed: 'd' });
    const m = passMatrix(plan, [RUN, LOOP], `loop:${AT}`);
    expect(m?.box.passes).toBe(2 + 1);
    // c never entered the loop: no row.
    expect(m?.rows.map((r) => [r.unit, r.passes, r.state])).toEqual([['a', 1, 'done'], ['b', 3, 'done'], ['d', 2, 'failed']]);
    expect(m?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['fix1', 'score1', 'check1', 'fix2', 'score2', 'check2', 'fix3', 'score3', 'check3']);
    expect(m?.head.map((r) => r.map((h) => (h.type === 'pass' ? `P${h.pass}x${h.span}` : h.type === 'node' ? h.node.label : 'loop')))).toEqual([
      ['P1x3', 'P2x3', 'P3x3'],
      ['fix', 'score', 'check', 'fix', 'score', 'check', 'fix', 'score', 'check'],
    ]);
    expect(m?.rows[2]?.cells.map((c) => c?.key ?? null)).toEqual(['fix-d', 'score-d', 'check-d~2', 'fix-d~2', null, null, null, null, null]);
    expect(passMatrix(plan, [RUN, LOOP], 'loop:99')).toBeNull();
    // Sorted by passes (most first) or by status (most severe first); a tie keeps the order.
    expect(sortRows(m?.rows ?? [], 'passes').map((r) => r.unit)).toEqual(['b', 'd', 'a']);
    expect(sortRows(m?.rows ?? [], 'state').map((r) => r.unit)).toEqual(['d', 'a', 'b']);
  });

  it("counts a node's tasks: those of its flow calls in a function node, each unit's latest pass in a loop box", () => {
    const plan = reviewRun({ a: 0, b: 1, c: 2 }, { calls: true, failed: 'c' });
    const fn = byId(layerGraph(plan, [RUN])).get(`flow:${LOOP}`);
    // a: summarize, check; b: those and fix, score, check; c: those and fix, score, check, fix (failed).
    expect(fn?.counts).toMatchObject({ total: 2 + 5 + 6, done: 12, failed: 1 });
    expect(fn).toMatchObject({ calls: 3, errors: 1 });
    const box = byId(layerGraph(plan, [RUN, LOOP]));
    // fix: b's pass 1 done, c's pass 2 failed (its pass 1 was done): 2 units, not 3 tasks.
    expect(box.get(`kind:fix@${AT}`)?.units.map((m) => m && [m.key, m.state])).toEqual([null, ['fix-b', 'done'], ['fix-c~2', 'failed']]);
    expect(box.get(`kind:fix@${AT}`)?.counts).toMatchObject({ total: 2, done: 1, failed: 1 });
    expect(box.get(`kind:check@${AT}`)?.units.map((m) => m?.key ?? null)).toEqual([null, 'check-b~2', 'check-c~2']);
  });

  it('a Python task in the loop is a node of the box like any other', () => {
    const g = layerGraph(reviewRun({ a: 1 }), [RUN, LOOP]);
    expect(byId(g).get(`kind:score@${AT}`)?.units[0]).toMatchObject({ key: 'score-a', state: 'done' });
  });

  it('shows both sides of a branch, each with the units that took it', () => {
    const at = [F(RUN), F(LOOP)];
    const plan = planOf([
      ft('check-a', 'a', 'check', 'done', at, { flow_call: '0.1' }),
      ft('check-b', 'b', 'check', 'done', at, { flow_call: '0.2' }),
      ft('publish-a', 'a', 'publish', 'done', at, { flow_call: '0.1', created_from: ['check-a'] }),
      ft('escalate-b', 'b', 'escalate', 'running', at, { flow_call: '0.2', created_from: ['check-b'] }),
    ]);
    const g = layerGraph(plan, autoLayer(plan));
    expect(g.path).toEqual([RUN, LOOP]);
    expect(rows(g)).toEqual([['kind:check'], ['kind:publish', 'kind:escalate']]);
    expect(g.edges.map((e) => [e.from, e.to, e.type])).toEqual([
      ['kind:check', 'kind:publish', 'created'],
      ['kind:check', 'kind:escalate', 'created'],
    ]);
    expect(byId(g).get('kind:publish')?.units.map((m) => m?.key ?? null)).toEqual(['publish-a', null]);
    expect(byId(g).get('kind:escalate')?.units.map((m) => m?.key ?? null)).toEqual([null, 'escalate-b']);
  });

  it('gives a fan-out over other units one mark per flow call above it, and its own units below', () => {
    const at = [F(RUN), F(LOOP)];
    const plan = planOf(
      [
        ft('part-a/1', 'a/1', 'part', 'done', at, { flow_call: '0.1' }),
        ft('part-a/2', 'a/2', 'part', 'failed', at, { flow_call: '0.1' }),
        ft('part-b/1', 'b/1', 'part', 'done', at, { flow_call: '0.2' }),
        ft('part-b/2', 'b/2', 'part', 'done', at, { flow_call: '0.2' }),
        ft('merge', '', 'merge', 'blocked', [F(RUN)], { after: ['part-a/1', 'part-a/2', 'part-b/1', 'part-b/2'] }),
      ],
      [call('0', RUN, 'running'), call('0.1', LOOP, 'raised'), call('0.2', LOOP)],
    );
    const top = layerGraph(plan, [RUN]);
    expect(top.units).toEqual([]);
    expect(byId(top).get(`flow:${LOOP}`)?.single.map((m) => [m.key, m.state, m.count])).toEqual([
      ['0.1', 'failed', 2],
      ['0.2', 'done', 2],
    ]);
    const below = layerGraph(plan, [RUN, LOOP]);
    expect(below.units).toEqual(['a/1', 'a/2', 'b/1', 'b/2']);
  });

  it('nests to any depth with the same rule', () => {
    const REFINE = 'flows.refine';
    const POLISH = 'flows.polish';
    // review_loop does `yield from refine(u)` (the same flow call); refine yields a batch of polish(u) (a flow call each).
    const nodes = [
      ft('draft-a', 'a', 'draft', 'done', [F(RUN), F(LOOP), F(REFINE)], { flow_call: '0.1' }),
      ft('tune-a', 'a', 'tune', 'running', [F(RUN), F(LOOP), F(REFINE), F(POLISH)], { flow_call: '0.1.1', after: ['draft-a'] }),
      ft('report', '', 'report', 'pending', [F(RUN)], { after: ['tune-a'] }),
    ];
    for (const calls of [[call('0', RUN, 'running'), call('0.1', LOOP, 'running'), call('0.1.1', POLISH, 'running')], undefined]) {
      const plan = planOf(nodes, calls);
      expect(rows(layerGraph(plan, [RUN]))).toEqual([[`flow:${LOOP}`], ['kind:report']]);
      expect(rows(layerGraph(plan, [RUN, LOOP]))).toEqual([[`flow:${REFINE}`]]);
      const third = layerGraph(plan, [RUN, LOOP, REFINE]);
      expect(rows(third)).toEqual([['kind:draft'], [`flow:${POLISH}`]]);
      expect(byId(third).get(`flow:${POLISH}`)?.units[0]).toMatchObject({ unit: 'a', state: 'running', flow: POLISH });
      expect(layerGraph(plan, [RUN, LOOP, REFINE, POLISH]).nodes.map((n) => n.id)).toEqual(['kind:tune']);
    }
    // A layer of one function node opens below it.
    expect(autoLayer(planOf(nodes.slice(0, 2)))).toEqual([RUN, LOOP, REFINE]);
  });

  it('draws a loop inside a loop as nested boxes, each counting its own passes', () => {
    // scan(u): for each column (the outer `for`, line 30), propose it, then while not ok verify and refine it (the inner `while`, line 33).
    // a: outer pass 1 needs 2 inner passes, outer pass 2 one; b: one outer pass, one inner pass.
    const SCAN = 'flows.scan';
    const outer = 30;
    const inner = 33;
    const at = (loops: number[]) => [F(RUN), F(SCAN, ...loops)];
    const plan = planOf(
      [
        ft('propose-a', 'a', 'propose', 'done', at([outer]), { flow_call: '0.1', passes: [1] }),
        ft('verify-a', 'a', 'verify', 'done', at([outer, inner]), { flow_call: '0.1', passes: [1, 1], executor: 'python', after: ['propose-a'] }),
        ft('refine-a', 'a', 'refine', 'done', at([outer, inner]), { flow_call: '0.1', passes: [1, 1], after: ['verify-a'] }),
        ft('verify-a~2', 'a', 'verify', 'done', at([outer, inner]), { flow_call: '0.1', passes: [1, 2], executor: 'python', after: ['refine-a'] }),
        ft('propose-a~2', 'a', 'propose', 'done', at([outer]), { flow_call: '0.1', passes: [2] }),
        ft('verify-a~3', 'a', 'verify', 'failed', at([outer, inner]), { flow_call: '0.1', passes: [2, 1], executor: 'python', after: ['propose-a~2'] }),
        ft('propose-b', 'b', 'propose', 'done', at([outer]), { flow_call: '0.2', passes: [1] }),
        ft('verify-b', 'b', 'verify', 'done', at([outer, inner]), { flow_call: '0.2', passes: [1, 1], executor: 'python', after: ['propose-b'] }),
      ],
      [call('0', RUN), call('0.1', SCAN), call('0.2', SCAN)],
    );
    const g = layerGraph(plan, [RUN, SCAN]);
    const outerBox = `loop:${outer}`;
    const innerBox = `loop:${outer}.${inner}`;
    const boxes = new Map(g.boxes.map((b) => [b.id, b]));
    expect(boxes.get(outerBox)).toMatchObject({ parent: null, passes: 2, spread: [[1, 1], [2, 1]] });
    // The inner loop's last pass is 2 (a's, in outer pass 1); a ran 3 inner passes in all, b 1.
    expect(boxes.get(innerBox)).toMatchObject({ parent: outerBox, passes: 2, spread: [[1, 1], [3, 1]] });
    expect(boxes.get(outerBox)?.layers).toEqual([[`kind:propose@${outer}`], [innerBox]]);
    expect(boxes.get(innerBox)?.layers).toEqual([[`kind:verify@${outer}.${inner}`], [`kind:refine@${outer}.${inner}`]]);
    expect(byId(g).get(`kind:verify@${outer}.${inner}`)?.box).toBe(innerBox);
    // a's verify mark: its latest pass (outer 2, inner 1), which failed, after 3 passes.
    expect(byId(g).get(`kind:verify@${outer}.${inner}`)?.units[0]).toMatchObject({ key: 'verify-a~3', state: 'failed', passes: 3 });

    // The outer loop's passes: each outer pass a group of columns, the inner loop's passes nested in it.
    const o = passMatrix(plan, [RUN, SCAN], outerBox);
    expect(o?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['propose1', 'verify1.1', 'refine1.1', 'verify1.2', 'propose2', 'verify2.1']);
    const label = (h: NonNullable<typeof o>['head'][number][number]) =>
      h.type === 'pass' ? `P${h.pass}x${h.span}` : h.type === 'loop' ? `loop x${h.span}` : `${h.node.label}/${h.rows}`;
    expect(o?.head.map((r) => r.map(label))).toEqual([
      ['P1x4', 'P2x2'],
      ['propose/3', 'loop x3', 'propose/3', 'loop x1'],
      ['P1x2', 'P2x1', 'P1x1'],
      ['verify/1', 'refine/1', 'verify/1', 'verify/1'],
    ]);
    expect(o?.rows.map((r) => [r.unit, r.passes, r.cells.map((c) => c?.key ?? null)])).toEqual([
      ['a', 2, ['propose-a', 'verify-a', 'refine-a', 'verify-a~2', 'propose-a~2', 'verify-a~3']],
      ['b', 1, ['propose-b', 'verify-b', null, null, null, null]],
    ]);
    // The inner loop's passes: counted within each pass of the outer loop.
    const i = passMatrix(plan, [RUN, SCAN], innerBox);
    expect(i?.columns.map((c) => `${c.node.label}${c.passes.join('.')}`)).toEqual(['verify1', 'refine1', 'verify2']);
    expect(i?.rows.map((r) => [r.unit, r.passes, r.cells.map((c) => c?.key ?? null)])).toEqual([
      ['a', 3, ['verify-a~3', 'refine-a', 'verify-a~2']],
      ['b', 1, ['verify-b', null, null]],
    ]);
    // a ran verify in inner pass 1 twice (outer passes 1 and 2): that column holds both.
    expect(i?.rows[0]?.cells[0]).toMatchObject({ count: 2, state: 'failed' });
  });

  it('draws no loop box for flow calls of one batch, whatever units their tasks have', () => {
    // run_all yields [bundle(b) for b in ...]: each call creates tasks of several units, at one call site.
    const B = 'flows.bundle';
    const inB = [F(RUN), F(B)];
    const plan = planOf(
      [
        ft('unpack-x', 'x', 'unpack', 'done', inB, { flow_call: '0.1' }),
        ft('classify-x-0', 'x-0', 'classify', 'done', inB, { flow_call: '0.1' }),
        ft('unpack-y', 'y', 'unpack', 'done', inB, { flow_call: '0.2' }),
        ft('classify-y-0', 'y-0', 'classify', 'done', inB, { flow_call: '0.2' }),
        ft('summary', '', 'summary', 'done', [F(RUN)], { after: ['unpack-x', 'unpack-y'] }),
      ],
      [call('0', RUN), call('0.1', B), call('0.2', B)],
    );
    const g = layerGraph(plan, [RUN]);
    expect(g.boxes).toEqual([]);
    expect(byId(g).get(`flow:${B}`)?.single.map((m) => m.key)).toEqual(['0.1', '0.2']);
  });

  it('opens on a failed flow call as a node, not inside it', () => {
    // docs -> review_loop(u) for each unit (no other node at the docs layer); b's loop raised.
    const DOCS = 'flows.docs';
    const RL = 'flows.review_loop';
    const inRL = [F(DOCS), F(RL)];
    const flowCalls = (failed: boolean): FlowCallNode[] => [call('0', DOCS), call('0.1', RL), call('0.2', RL, failed ? 'raised' : 'returned')];
    const build = (failed: boolean): Plan =>
      planOf(
        [
          ft('summarize-a', 'a', 'summarize', 'done', inRL, { flow_call: '0.1' }),
          ft('summarize-b', 'b', 'summarize', failed ? 'failed' : 'done', inRL, { flow_call: '0.2' }),
        ],
        flowCalls(failed),
      );
    // Without a failure, the single review_loop node opens its own layer (auto-descent).
    expect(autoLayer(build(false))).toEqual([DOCS, RL]);
    // b's review_loop raised: the graph stops on the review_loop node, which shows it failed.
    expect(autoLayer(build(true))).toEqual([DOCS]);
    expect(byId(layerGraph(build(true), [DOCS])).get(`flow:${RL}`)?.counts.failed).toBe(1);
  });

  it('draws created_from as its own edge only where there is no after edge', () => {
    const g = layerGraph(reviewRun({ a: 1 }), [RUN, LOOP]);
    const e = (from: string, to: string) => g.edges.filter((x) => x.from === from && x.to === to).map((x) => x.type);
    expect(e('kind:summarize', 'kind:check')).toEqual(['after']);
    expect(e(`kind:fix@${AT}`, `kind:check@${AT}`)).toEqual(['after']);
    expect(e(`kind:score@${AT}`, `kind:check@${AT}`)).toEqual(['created']);
  });

  it('shows an edge from outside the layer as an incoming stub, named as the nearest layer names it', () => {
    const g = layerGraph(reviewRun({ a: 0, b: 0 }), [RUN, LOOP]);
    expect(g.stubs).toEqual([{ id: 'stub:1:kind:prepare', label: 'prepare', to: 'kind:summarize', tasks: 2, type: 'after' }]);
  });

  it('appends nodes that appear later to their layer, without moving the others', () => {
    const before = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['a-u'] })]);
    const g1 = layerGraph(before);
    expect(rows(g1)).toEqual([['kind:a'], ['kind:b', 'kind:c']]);
    // z comes first in the plan and feeds c: laid out afresh, c would move up.
    const after = planOf([node('z-u', 'u', 'z', 'pending'), ...before.nodes, node('d-u', 'u', 'd', 'pending', { after: ['z-u'] })]);
    after.nodes.push(node('c-v', 'v', 'c', 'pending', { after: ['z-u'] }));
    const g2 = layerGraph(after, [], g1.order);
    expect(rows(g2)).toEqual([['kind:a', 'kind:z'], ['kind:b', 'kind:c', 'kind:d']]);
    expect(rows(layerGraph(after))).not.toEqual(rows(g2));
  });
});

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

  it('puts a point on every layer a long edge crosses, and routes it around what is between', () => {
    // a -> b -> c -> d, and a -> d: the long edge passes layers 1 and 2 beside b and c.
    const plan = planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['b-u'] }), node('d-u', 'u', 'd', 'done', { after: ['c-u', 'a-u'] })]);
    const g = layerGraph(plan);
    const long = g.routes.find((r) => r.from === 'kind:a' && r.to === 'kind:d');
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
      const into = g.routes.find((r) => r.from === 'kind:s' && r.to === `kind:c@${AT}`);
      expect(into?.steps.map((x) => (x.id.includes('|by:') ? 'beside' : isPoint(x.id) ? 'point' : x.id))).toEqual(['kind:s', 'beside', `loop:${AT}`, `kind:c@${AT}`]);
      const out = g.routes.find((r) => r.from === `kind:b@${AT}` && r.to === 'kind:w');
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

  it('draws an edge as its runs, joined by a curve where it bends', () => {
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 5 }])).toBe('M10,5 L20,5 L40,5');
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 25 }])).toBe('M10,5 L20,5 C30,5 30,25 40,25');
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 25 }], true)).toBe('M5,10 L5,20 C5,30 25,30 25,40');
    expect(edgePath([])).toBe('');
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

describe('keyboard', () => {
  it('moves along an edge to the nearest earlier or later node', () => {
    const plan = planOf([
      node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['a-u'] }),
    ]);
    const g = layerGraph(plan);
    const across = (id: string) => ({ 'kind:a': 50, 'kind:b': 10, 'kind:c': 60 })[id] ?? 0;
    expect(alongEdge(g, 'kind:a', 'later', across)).toBe('kind:c');
    expect(alongEdge(g, 'kind:b', 'earlier', across)).toBe('kind:a');
    expect(alongEdge(g, 'kind:b', 'later', across)).toBeNull();
  });

  it('does not follow an edge back to the next pass', () => {
    const g = layerGraph(reviewRun({ a: 2 }), [RUN, LOOP]);
    expect(alongEdge(g, `kind:check@${AT}`, 'later', () => 0)).toBeNull();
  });

  it('moves between the marks of a grid, past the empty cells', () => {
    const has = [
      [true, false, true],
      [false, false, false],
      [false, true, false],
      [true, false, false],
    ];
    expect(gridStep(has, 0, 0, 'ArrowRight')).toEqual([0, 2]);
    expect(gridStep(has, 0, 2, 'ArrowRight')).toBeNull();
    expect(gridStep(has, 0, 0, 'ArrowDown')).toEqual([3, 0]);
    expect(gridStep(has, 0, 2, 'ArrowDown')).toEqual([2, 1]);
    expect(gridStep(has, 3, 0, 'ArrowUp')).toEqual([0, 0]);
    expect(gridStep(has, 2, 1, 'Home')).toEqual([2, 1]);
    expect(gridStep(has, 3, 0, 'Home', true)).toEqual([0, 0]);
    expect(gridStep(has, 0, 0, 'End', true)).toEqual([3, 0]);
    expect(gridStep(has, 0, 0, 'PageDown', false, 2)).toEqual([2, 1]);
    expect(gridStep(has, 0, 0, 'x')).toBeNull();
  });
});

describe('a node of many marks', () => {
  it("shows a bar above 200 marks, with each state's share", () => {
    const many = Array.from({ length: 201 }, (_, i) => ({ key: `k${i}`, unit: `u${i}`, state: 'done' as const, count: 1, keys: [] }));
    expect(asBar({ units: many, single: [] })).toBe(true);
    expect(asBar({ units: many.slice(1), single: [] })).toBe(false);
    expect(barParts({ total: 4, done: 3, failed: 1, running: 0, pending: 0, skipped: 0, blocked: 0 }, ['done', 'failed', 'running'])).toEqual([
      { state: 'done', n: 3, pct: 75 },
      { state: 'failed', n: 1, pct: 25 },
    ]);
  });
});

describe('layer segments', () => {
  it('splits off the loop box entered at the end', () => {
    expect(splitLayer([RUN, LOOP, 'loop:7'])).toEqual({ path: [RUN, LOOP], loop: 'loop:7' });
    expect(splitLayer([RUN])).toEqual({ path: [RUN], loop: null });
  });

  it('goes up one level, to the layer the graph opens on at most', () => {
    expect(parentLayer([RUN, LOOP, 'loop:7'], [RUN])).toEqual([RUN, LOOP]);
    expect(parentLayer([RUN, LOOP], [RUN])).toEqual([]);
    expect(parentLayer([RUN], [RUN])).toBeNull();
  });
});

describe('markGrid', () => {
  it('one row up to 12 units, then 10 and 20 columns of smaller marks', () => {
    expect([0, 6, 12, 13, 100, 101, 2000].map(markGrid)).toEqual([
      { cols: 1, size: 12 },
      { cols: 6, size: 12 },
      { cols: 12, size: 12 },
      { cols: 10, size: 10 },
      { cols: 10, size: 10 },
      { cols: 20, size: 6 },
      { cols: 20, size: 6 },
    ]);
  });
});

describe('fitView', () => {
  it('shows a small graph at its own size, centred, in a frame as tall as the graph', () => {
    expect(fitView(600, 200, 1200, 600)).toEqual({ k: 1, x: 300, y: 0, h: 200 });
  });

  it('scales a wide graph down to the frame width', () => {
    expect(fitView(2400, 400, 1200, 600)).toEqual({ k: 0.5, x: 0, y: 0, h: 200 });
  });

  it('scales a tall graph down to the frame height, and centres it', () => {
    const v = fitView(600, 2000, 1200, 500);
    expect(v.k).toBe(0.25);
    expect(v.h).toBe(500);
    expect(v.x).toBe((1200 - 150) / 2);
  });
});

describe('zoomView', () => {
  it('keeps the point under the cursor still, within the limits', () => {
    const v = zoomView({ k: 1, x: 0, y: 0 }, 2, 100, 50, 0.1, 4);
    expect(v).toEqual({ k: 2, x: -100, y: -50 });
    expect(zoomView({ k: 1, x: 0, y: 0 }, 10, 0, 0, 0.1, 4).k).toBe(4);
  });
});

describe('resolveLayer', () => {
  const plan = reviewRun({ a: 1, b: 2 });
  it('keeps a layer the plan has, with its loop box', () => {
    expect(resolveLayer(plan, [RUN, LOOP])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, [RUN, LOOP, `loop:${AT}`])).toEqual([RUN, LOOP, `loop:${AT}`]);
  });
  it("finds a function named by its qualified name, or by its name, when the plan reaches it by one flow path", () => {
    expect(resolveLayer(plan, [LOOP])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, ['review_loop'])).toEqual([RUN, LOOP]);
    expect(resolveLayer(plan, ['review_loop', `loop:${AT}`])).toEqual([RUN, LOOP, `loop:${AT}`]);
  });
  it('names nothing for a layer the plan does not have', () => {
    expect(resolveLayer(plan, ['flows.gone'])).toBeNull();
    expect(resolveLayer(plan, [RUN, LOOP, 'loop:99'])).toBeNull();
    // A function the plan reaches by two flow paths names no one layer.
    const SUB = 'flows.sub';
    const two = planOf([ft('x-u', 'u', 'x', 'done', [F(RUN), F(SUB)]), ft('y-u', 'u', 'y', 'done', [F(RUN), F(LOOP), F(SUB)])]);
    expect(resolveLayer(two, [SUB])).toBeNull();
    expect(resolveLayer(two, [RUN, LOOP, SUB])).toEqual([RUN, LOOP, SUB]);
  });
});

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
