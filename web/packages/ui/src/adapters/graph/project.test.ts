import type { FlowCallNode, Plan } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { autoLayer, layerGraph } from './layer.js';
import { shapeOf } from './project.js';
import { AT, F, LOOP, RUN, UNITS, call, ft, node, planOf, reviewRun, staticDemo } from './plans.fixture.js';
import type { LayerGraph } from './types.js';

const rows = (g: LayerGraph) => g.layers;
const byId = (g: LayerGraph) => new Map(g.nodes.map((n) => [n.id, n]));

describe('layerGraph: a static flow', () => {
  const demo = staticDemo;
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
        { from: 'kind:prepare', to: 'kind:summarize', tasks: 6, type: 'after', samePass: true, back: false },
        { from: 'kind:summarize', to: 'kind:review', tasks: 6, type: 'after', samePass: true, back: false },
        { from: 'kind:summarize', to: 'kind:write_note', tasks: 6, type: 'after', samePass: true, back: false },
        { from: 'kind:review', to: 'kind:report', tasks: 1, type: 'after', samePass: true, back: false },
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
    expect(n.get('kind:prepare')?.counts).toEqual({ total: 6, done: 5, partial: 0, failed: 1, running: 0, pending: 0, skipped: 0, blocked: 0, cancelled: 0 });
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
    expect(g.edges.filter((e) => e.to === 'kind:report')).toEqual([{ from: `flow:${LOOP}`, to: 'kind:report', tasks: 1, type: 'after', samePass: true, back: false }]);
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

  it('marks a function node whose flow calls have a deadline of their own, and each call with when it falls', () => {
    const plan = reviewRun({ a: 0, b: 1 }, { calls: true });
    const box = { started_at: '2026-10-14T01:00:00+00:00', deadline_s: 600, grace_s: 60, slack_s: 150, finishing_kinds: ['report'] };
    const boxed = (plan.flow_calls ?? []).map((c) => (c.id === '0.2' ? { ...c, time_box: box } : c));
    const fn = byId(layerGraph({ ...plan, flow_calls: boxed }, [RUN])).get(`flow:${LOOP}`);
    expect(fn?.timeBox).toEqual(box);
    expect(fn?.units.map((m) => m?.deadlineAt)).toEqual([undefined, '2026-10-14T01:10:00.000Z']);
    expect(byId(layerGraph(plan, [RUN])).get(`flow:${LOOP}`)?.timeBox).toBeNull();
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
    expect(first.boxes).toEqual([
      { id: box, local: box, layer: [RUN, LOOP], loop: AT, file: 'flow.py', parent: null, passes: 1, spread: [[1, 1]], layers: [[`kind:fix@${AT}`], [`kind:score@${AT}`], [`kind:check@${AT}`]] },
    ]);
    expect(rows(first)).toEqual([['kind:summarize'], ['kind:check'], [box]]);
    expect(byId(first).get(`kind:fix@${AT}`)?.box).toBe(box);
    const second = layerGraph(reviewRun({ a: 0, b: 2 }), [RUN, LOOP], first.order);
    expect(rows(second)).toEqual(rows(first));
    expect(second.boxes[0]).toMatchObject({ passes: 2, spread: [[2, 1]] });
    // check (the next pass's) -> fix goes back to the next pass: drawn by the box, not laid out.
    expect(second.edges.find((e) => e.from === `kind:check@${AT}` && e.to === `kind:fix@${AT}`)?.back).toBe(true);
    expect(second.edgePaths.some((r) => r.from === `kind:check@${AT}` && r.to === `kind:fix@${AT}`)).toBe(false);
  });

  it("counts each box's passes, how many units ran each number, and each mark's passes", () => {
    const g = layerGraph(reviewRun({ a: 1, b: 3, c: 0, d: 1, e: 2 }), [RUN, LOOP]);
    expect(g.boxes[0]).toMatchObject({ passes: 3, spread: [[1, 2], [2, 1], [3, 1]] });
    // a mark shows the passes its unit's tasks of the node ran in, when more than 1.
    expect(byId(g).get(`kind:fix@${AT}`)?.units.map((m) => m?.passes ?? null)).toEqual([null, 3, null, null, 2]);
    // a unit's mark in a loop box is its latest pass.
    expect(byId(g).get(`kind:check@${AT}`)?.units.map((m) => m?.key ?? null)).toEqual(['check-a~2', 'check-b~4', null, 'check-d~2', 'check-e~3']);
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
    // In the order of their ends, whichever task made its edge first.
    expect(g.edges.map((e) => [e.from, e.to, e.type])).toEqual([
      ['kind:check', 'kind:escalate', 'created'],
      ['kind:check', 'kind:publish', 'created'],
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

  it('draws data, order and creation apart, each pair of nodes by the strongest that joins them', () => {
    const plan = planOf([
      node('a-u', 'u', 'a', 'done'),
      // given a's output (and waiting for it): data
      node('b-u', 'u', 'b', 'done', { after: ['a-u'], given_from: ['a-u'], created_from: ['a-u'] }),
      // waits for a, not given its output: order only
      node('c-u', 'u', 'c', 'done', { after: ['a-u'] }),
      // created after b's result only
      node('d-u', 'u', 'd', 'pending', { created_from: ['b-u'] }),
      // one task of e is given c's output, another only waits for c: the pair is data
      node('e-u', 'u', 'e', 'done', { given_from: ['c-u'] }),
      node('e-v', 'v', 'e', 'done', { after: ['c-u'] }),
    ]);
    const g = layerGraph(plan);
    const types = Object.fromEntries(g.edges.map((e) => [`${e.from} > ${e.to}`, e.type]));
    expect(types).toEqual({
      'kind:a > kind:b': 'given',
      'kind:a > kind:c': 'after',
      'kind:b > kind:d': 'created',
      'kind:c > kind:e': 'given',
    });
    const style = Object.fromEntries(shapeOf(g).edges.map((e) => [`${e.from} > ${e.to}`, e.style]));
    expect(style).toEqual({ 'kind:a > kind:b': 'solid', 'kind:a > kind:c': 'dotted', 'kind:b > kind:d': 'dashed', 'kind:c > kind:e': 'solid' });
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
