// What the pipeline graph says about its nodes and marks. Pure: each depends only on
// its arguments (`live`: the run is running, so a pending task waits rather than did
// not run).
import { planOutcome, type PlanNode, type TaskState } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, fmtDur, kindUnit, listText } from '../../../words/format.js';
import { passesRan, stateCount, taskStatusLabel } from '../../../words/index.js';
import type { GraphMark, GraphNode, LayerGraph, NodeCounts } from '../graph/types.js';

/** The states the legend can show, in this order; it shows the ones the view has. */
export const LEGEND: readonly TaskState[] = ['done', 'running', 'pending', 'failed', 'blocked', 'skipped'];

/** A pending task waits while the run runs; once the run is over, it did not run. */
export function stateWord(s: TaskState, live: boolean): string {
  return taskStatusLabel(planOutcome(s), live);
}

/** How many marks are in a state, number first: "3 failed". */
export function countOf(s: TaskState, n: number, live: boolean): string {
  const o = planOutcome(s);
  return stateCount(o === 'waiting' && !live ? 'not_run' : o, n);
}

/** How many tasks are in each state, in words: "2 done | 1 failed". */
export function stateCounts(c: NodeCounts, live: boolean): string {
  return facts(...LEGEND.filter((s) => c[s]).map((s) => countOf(s, c[s], live)));
}

/** How many tasks are done (plan state done: done, and done after retrying): "5 of 6 tasks done". Skipped tasks are counted apart. */
export function doneOf(c: NodeCounts): string {
  return msg(str`${c.done} of ${c.total} tasks done`);
}

/** The tasks that are not done, by state, most severe first: "1 failed", "1 not started". */
export function notDone(c: NodeCounts, live: boolean): string[] {
  return (['failed', 'blocked', 'running', 'pending', 'skipped'] as const).filter((s) => c[s]).map((s) => countOf(s, c[s], live));
}

/** A fact's class: failed, not started, running, or muted (waiting, not run, skipped). */
export type ExceptionClass = 'err' | 'warn' | 'live' | 'mut';

/** What a node needs a word for: its tasks that are not done, by state, and its flow calls that stopped with an error. */
export function exceptions(n: Pick<GraphNode, 'counts' | 'errors'>, live: boolean): [ExceptionClass, string][] {
  const c = n.counts;
  const out: [ExceptionClass, string][] = [];
  if (c.failed) out.push(['err', countOf('failed', c.failed, live)]);
  if (n.errors) out.push(['err', n.errors === 1 ? msg('1 flow call stopped with an error') : msg(str`${n.errors} flow calls stopped with an error`)]);
  if (c.blocked) out.push(['warn', countOf('blocked', c.blocked, live)]);
  if (c.running) out.push(['live', countOf('running', c.running, live)]);
  if (c.pending) out.push(['mut', countOf('pending', c.pending, live)]);
  if (c.skipped) out.push(['mut', countOf('skipped', c.skipped, live)]);
  return out;
}

/** Where a loop is: `flow.py:130` (the file's name and the loop's first line), or `line 130` when the file is not known. */
export function where(line: number | string, file?: string): string {
  const name = file ? file.slice(file.lastIndexOf('/') + 1) : '';
  return name ? `${name}:${line}` : msg(str`line ${line}`);
}

/** Who runs a kind node's tasks, in the words the Tasks list uses. */
export function executorWord(n: Pick<GraphNode, 'executor'>): string {
  if (n.executor === 'agent') return msg('Agent task');
  if (n.executor === 'python') return msg('Python task');
  return n.executor === 'mixed' ? facts(msg('Agent task'), msg('Python task')) : '';
}

/** A node's tooltip: what it is, and its tasks done. */
export function nodeTip(n: GraphNode): string {
  return n.type === 'flow' ? facts(msg(str`Function ${n.name}`), doneOf(n.counts)) : facts(n.label, executorWord(n), doneOf(n.counts));
}

/** The names of the nodes `n` waits for, was created after, and feeds. */
export function neighbours(n: GraphNode, g: Pick<LayerGraph, 'nodes' | 'edges' | 'stubs'>): { waits: string[]; after: string[]; feeds: string[] } {
  const label = (id: string) => {
    const x = g.nodes.find((y) => y.id === id);
    return !x ? id : x.box ? msg(str`${x.label} in the loop`) : x.label;
  };
  const into = (type: 'after' | 'created') => [
    ...g.stubs.filter((s) => s.to === n.id && s.type === type).map((s) => s.label),
    ...g.edges.filter((e) => e.to === n.id && e.type === type).map((e) => label(e.from)),
  ];
  return { waits: into('after'), after: into('created'), feeds: [...new Set(g.edges.filter((e) => e.from === n.id).map((e) => label(e.to)))] };
}

/** The node for a screen reader: its counts, and the nodes it waits for, was created after and feeds. */
export function nodeLabel(n: GraphNode, g: Pick<LayerGraph, 'nodes' | 'edges' | 'stubs'>, live: boolean): string {
  const c = n.counts;
  const { waits, after, feeds } = neighbours(n, g);
  return [
    n.type === 'flow' ? facts(msg(str`Function ${n.label}`), doneOf(c)) : facts(n.label, executorWord(n), doneOf(c)),
    ...exceptions(n, live).map(([, t]) => t),
    waits.length ? msg(str`Waits for ${listText(waits)}`) : '',
    after.length ? msg(str`Created after ${listText(after)}`) : '',
    feeds.length ? msg(str`Later tasks: ${listText(feeds)}`) : '',
  ]
    .filter(Boolean)
    .join('. ');
}

/** What a mark's words come from: its task (none for a flow call's mark), why a task did not start, and the run being live. */
export interface MarkContext {
  task: PlanNode | undefined;
  causeOf: (key: string) => string;
  live: boolean;
}

/** What a mark says: its name, state, passes, attempts, tasks and time, for its tooltip and its label. */
export function markText(label: string, m: GraphMark, x: MarkContext, pass = ''): { name: string; parts: string[]; id: string } {
  const t = m.flow ? undefined : x.task;
  const name = kindUnit({ kind: label, unit: m.unit });
  const cause = !m.flow && m.state === 'blocked' ? x.causeOf(m.key) : '';
  const state = cause ? msg(str`Not started: ${cause}`) : stateWord(m.state, x.live);
  const attempts = t?.attempts ?? 1;
  const tries = attempts > 1 ? msg(str`${attempts} attempts`) : '';
  const passes = m.passes ? passesRan(m.passes) : '';
  const many = m.flow || m.count > 1 ? msg(str`${m.count} tasks`) : '';
  // A flow call's tasks that are not done, and its own error: what its state comes from.
  const not = m.counts ? notDone(m.counts, x.live) : [];
  const error = m.error === undefined ? [] : [msg('Flow call stopped with an error'), m.error];
  const time = !m.flow && (m.state === 'done' || m.state === 'failed') && t?.wall_s ? fmtDur(t.wall_s) : '';
  return { name, parts: [state, pass, passes, tries, many, ...not, ...error, time].filter(Boolean), id: m.flow ? msg(str`Flow call ${m.key}`) : m.key };
}
