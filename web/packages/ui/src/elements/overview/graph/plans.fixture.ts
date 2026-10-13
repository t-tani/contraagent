// Synthetic plans for the graph's tests, as a run writes them: a task's flow path
// (outermost first) with the loops around each call site, what its flow call had
// received when it was created, and its flow call. Test code only: the build leaves
// `*.fixture.ts` out.
import type { FlowCallNode, FlowFrame, Plan, PlanNode } from '@contraagent/api';

export const node = (key: string, unit: string, group: string, state: PlanNode['state'], extra: Partial<PlanNode> = {}): PlanNode => ({
  key, kind: group, unit, group, state, level: 0, ...extra,
});
export const group = (id: string, counts: Partial<Plan['groups'][number]> = {}): Plan['groups'][number] => ({
  id, label: id, total: 0, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, ...counts,
});

/** A frame of a flow path, with the loops around its call site (each at pass 1). */
export const F = (fn: string, ...loops: number[]): FlowFrame => ({ function: fn, file: 'flow.py', line: 1, loops: loops.map((line) => ({ line, pass: 1 })) });

/**
 * A task created by a flow. `pass` is the pass of the innermost loop around the
 * task's own call site; `passes`, one pass per loop around it, outermost first.
 */
export const ft = (
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
export const planOf = (nodes: PlanNode[], flow_calls?: FlowCallNode[]): Plan => {
  const groups = [...new Set(nodes.map((n) => n.group))].map((g) => group(g));
  return flow_calls ? { nodes, groups, flow_calls } : { nodes, groups };
};
export const call = (id: string, fn: string, state: FlowCallNode['state'] = 'returned'): FlowCallNode => ({
  id, parent: id.includes('.') ? id.slice(0, id.lastIndexOf('.')) : null, function: fn, flow: [], state,
});

export const RUN = 'flows.run_all';
export const LOOP = 'flows.review_loop';
export const AT = 7; // the line of review_loop's `while`

/**
 * run_all: prepare each unit (Python), then review_loop(u) for every unit as one batch,
 * then report on what they returned. review_loop: summarize, check, and while the review
 * is not ok: fix, score (Python), check. `passes[u]` is how many times u went round.
 */
export function reviewRun(passes: Record<string, number>, opts: { calls?: boolean; failed?: string } = {}): Plan {
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

export const UNITS = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta'];

/** The demo as a static flow: prepare -> summarize -> { review, write_note }, review -> report (one task, no unit). */
export function staticDemo(stateOf: (key: string) => PlanNode['state'] = (k) => (k.endsWith('zeta') ? 'blocked' : 'done'), flow?: FlowFrame[]): Plan {
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
}

/** scan(u): for each column (the outer `for`, line 30), propose it, then while not ok verify and refine it (the inner `while`, line 33). */
export const SCAN = 'flows.scan';
export function nestedLoops(): Plan {
  const outer = 30;
  const inner = 33;
  const at = (loops: number[]) => [F(RUN), F(SCAN, ...loops)];
  return planOf(
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
}

/** Plans of every shape the graph draws, by name: the input of the graph's order snapshot. */
export function shapes(): Record<string, Plan> {
  const L = [F(RUN), F(LOOP, AT)];
  const inRL = [F(RUN), F(LOOP)];
  const REFINE = 'flows.refine';
  const POLISH = 'flows.polish';
  const deep = [
    ft('draft-a', 'a', 'draft', 'done', [F(RUN), F(LOOP), F(REFINE)], { flow_call: '0.1' }),
    ft('tune-a', 'a', 'tune', 'running', [F(RUN), F(LOOP), F(REFINE), F(POLISH)], { flow_call: '0.1.1', after: ['draft-a'] }),
    ft('report', '', 'report', 'pending', [F(RUN)], { after: ['tune-a'] }),
  ];
  const at = (loops: number[]) => [F(RUN), F(SCAN, ...loops)];
  return {
    'static demo': staticDemo(),
    'static demo, running': staticDemo((k) => (k.startsWith('review') ? 'running' : 'pending')),
    'static demo under one function': staticDemo(undefined, [F('flows.pipeline')]),
    'cycle and waits inside a node': planOf([
      node('a1', 'u', 'a', 'done'),
      node('a2', 'v', 'a', 'done', { after: ['a1', 'not-yet'] }),
      node('b1', 'u', 'b', 'done', { after: ['c1'] }),
      node('c1', 'u', 'c', 'done', { after: ['b1'] }),
    ]),
    'long edge': planOf([node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['b-u'] }), node('d-u', 'u', 'd', 'done', { after: ['c-u', 'a-u'] })]),
    crossing: planOf([
      node('x1-u', 'u', 'x1', 'done'), node('x2-u', 'u', 'x2', 'done'),
      node('y1-u', 'u', 'y1', 'done', { after: ['x2-u'] }), node('y2-u', 'u', 'y2', 'done', { after: ['x1-u'] }),
    ]),
    'review loop, calls': reviewRun({ a: 0, b: 1 }, { calls: true }),
    'review loop, 2 passes': reviewRun({ a: 1, b: 2 }),
    'review loop, spread': reviewRun({ a: 1, b: 3, c: 0, d: 1, e: 2 }),
    'review loop, failed': reviewRun({ a: 1, b: 3, c: 0, d: 2 }, { failed: 'd' }),
    'review loop, calls, failed': reviewRun({ a: 0, b: 1, c: 2 }, { calls: true, failed: 'c' }),
    branch: planOf([
      ft('check-a', 'a', 'check', 'done', inRL, { flow_call: '0.1' }),
      ft('check-b', 'b', 'check', 'done', inRL, { flow_call: '0.2' }),
      ft('publish-a', 'a', 'publish', 'done', inRL, { flow_call: '0.1', created_from: ['check-a'] }),
      ft('escalate-b', 'b', 'escalate', 'running', inRL, { flow_call: '0.2', created_from: ['check-b'] }),
    ]),
    'fan-out': planOf(
      [
        ft('part-a/1', 'a/1', 'part', 'done', inRL, { flow_call: '0.1' }),
        ft('part-a/2', 'a/2', 'part', 'failed', inRL, { flow_call: '0.1' }),
        ft('part-b/1', 'b/1', 'part', 'done', inRL, { flow_call: '0.2' }),
        ft('part-b/2', 'b/2', 'part', 'done', inRL, { flow_call: '0.2' }),
        ft('merge', '', 'merge', 'blocked', [F(RUN)], { after: ['part-a/1', 'part-a/2', 'part-b/1', 'part-b/2'] }),
      ],
      [call('0', RUN, 'running'), call('0.1', LOOP, 'raised'), call('0.2', LOOP)],
    ),
    'deep, calls': planOf(deep, [call('0', RUN, 'running'), call('0.1', LOOP, 'running'), call('0.1.1', POLISH, 'running')]),
    'deep, no calls': planOf(deep),
    'nested loops': nestedLoops(),
    'nested boxes': planOf([
      ft('rank-a', 'a', 'rank', 'done', at([])),
      ft('propose-a', 'a', 'propose', 'done', at([30]), { created_from: ['rank-a'] }),
      ft('verify-a', 'a', 'verify', 'done', at([30, 33]), { after: ['propose-a'] }),
      ft('refine-a', 'a', 'refine', 'done', at([30, 33]), { after: ['verify-a', 'propose-a'] }),
      ft('report-a', 'a', 'report', 'done', at([]), { after: ['refine-a'] }),
    ]),
    'into and out of a box': planOf([
      ft('s-u', 'u', 's', 'done', inRL),
      ft('a-u', 'u', 'a', 'done', L, { after: ['s-u'] }),
      ft('b-u', 'u', 'b', 'done', L, { after: ['a-u'] }),
      ft('c-u', 'u', 'c', 'done', L, { after: ['b-u', 's-u'] }),
      ft('w-u', 'u', 'w', 'done', inRL, { after: ['b-u', 's-u', 'c-u'] }),
    ]),
    'loop of one layer': planOf([ft('a-u', 'u', 'a', 'done', L), ft('a-u~2', 'u', 'a', 'done', L, { pass: 2 })]),
  };
}
