// The plan as the graph reads it: each task's flow path, its loops and passes, its
// flow call, and where it is shown at a depth of the flow path.
// A plan node's origin (`flow`, `created_from`, `flow_call`) is optional on the
// wire (absent for a task no flow created), so the readers here check it before use.
import { type FlowCallNode, type FlowFrame, type FlowLoop, type Plan, type PlanNode } from '@contraagent/api';
import { LOOP_SEGMENT } from './types.js';

/** A frame of a task's flow path as the graph reads it: its loops by first line, and their passes. */
export interface TaskFrame {
  function: string;
  file: string;
  line: number;
  loops: number[];
  passes: number[];
}

export interface FlowTask {
  n: PlanNode;
  path: string[];
  frames: TaskFrame[];
  from: string[];
  call: string;
}

export interface FlowIndex {
  tasks: FlowTask[];
  byKey: Map<string, FlowTask>;
  calls: Map<string, FlowCallNode> | null;
  unitRank: Map<string, number>;
  labels: Map<string, string>;
}

const isStr = (x: unknown): x is string => typeof x === 'string';

function readFrames(n: PlanNode): TaskFrame[] {
  const f = n.flow as unknown;
  if (!Array.isArray(f)) return [];
  const out: TaskFrame[] = [];
  for (const x of f as unknown[]) {
    const r = x as Partial<FlowFrame> | null;
    if (!r || typeof r !== 'object' || !isStr(r.function)) break;
    const read = (Array.isArray(r.loops) ? r.loops : []).filter((l): l is FlowLoop => !!l && typeof l.line === 'number');
    out.push({
      function: r.function,
      file: isStr(r.file) ? r.file : '',
      line: typeof r.line === 'number' ? r.line : 0,
      loops: read.map((l) => l.line),
      // A pass not counted (null) reads as the first.
      passes: read.map((l) => (typeof l.pass === 'number' && l.pass >= 1 ? l.pass : 1)),
    });
  }
  return out;
}

function readCalls(plan: Plan): Map<string, FlowCallNode> | null {
  const cs = plan.flow_calls as unknown;
  if (!Array.isArray(cs) || cs.length === 0) return null; // no flow call recorded
  return new Map((cs as Partial<FlowCallNode>[]).filter((c) => c && isStr(c.id) && isStr(c.function)).map((c) => [c.id as string, c as FlowCallNode]));
}

const indexes = new WeakMap<Plan, FlowIndex>();

export function indexOf(plan: Plan): FlowIndex {
  const had = indexes.get(plan);
  if (had) return had;
  const tasks = plan.nodes.map((n): FlowTask => {
    const frames = readFrames(n);
    const from = n.created_from as unknown;
    return {
      n,
      frames,
      path: frames.map((f) => f.function),
      from: Array.isArray(from) ? (from as unknown[]).filter(isStr) : [],
      call: isStr(n.flow_call) ? n.flow_call : '',
    };
  });
  const unitRank = new Map<string, number>();
  for (const n of plan.nodes) if (n.unit && !unitRank.has(n.unit)) unitRank.set(n.unit, unitRank.size);
  const ix: FlowIndex = {
    tasks,
    byKey: new Map(tasks.map((t) => [t.n.key, t])),
    calls: readCalls(plan),
    unitRank,
    labels: new Map(plan.groups.map((g) => [g.id, g.label])),
  };
  indexes.set(plan, ix);
  return ix;
}

export const startsWith = (path: readonly string[], prefix: readonly string[]) => prefix.every((p, i) => path[i] === p);

/** A function's name without its module. */
export const shortName = (fn: string): string => fn.slice(fn.lastIndexOf('.') + 1) || fn;

/** The loops around a task's call site at depth `d`, outermost first ([] outside any). */
export const loopsAt = (t: FlowTask, d: number): number[] => (d > 0 ? (t.frames[d - 1]?.loops ?? []) : []);

/** The pass of each of those loops, outermost first: the task's place in them. */
export const passesAt = (t: FlowTask, d: number): number[] => (d > 0 ? (t.frames[d - 1]?.passes ?? []) : []);

/** Two pass lists in the order the passes ran: the outer loop's first. */
export function cmpPasses(a: readonly number[], b: readonly number[]): number {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d) return d;
  }
  return 0;
}

/** The loop box ids for a loop chain, outermost first: `loop:7`, then `loop:7.9`, ... */
export const boxChain = (loops: readonly number[]): string[] => loops.map((_, i) => `${LOOP_SEGMENT}${loops.slice(0, i + 1).join('.')}`);

/** Where a task is shown at depth `d`: its kind node, or the node of the function it was created under. */
export function placeOf(t: FlowTask, d: number): { id: string; type: 'kind' | 'flow'; name: string; loops: number[] } {
  const loops = loopsAt(t, d);
  const at = loops.length ? `@${loops.join('.')}` : '';
  if (t.path.length <= d) return { id: `kind:${t.n.group}${at}`, type: 'kind', name: t.n.group, loops };
  const name = t.path[d] as string;
  return { id: `flow:${name}${at}`, type: 'flow', name, loops };
}

/**
 * The flow call a function node stands for, for a task at depth `d`: the call that
 * started at frame `d` (`own`), else the call the frame runs in (`yield from`). With
 * no flow calls in the plan, each frame of the task's call chain is taken to start one.
 */
export function instanceOf(t: FlowTask, d: number, calls: Map<string, FlowCallNode> | null): { id: string; own: boolean } {
  if (!t.call) return { id: `>${d}`, own: false };
  const parts = t.call.split('.');
  const chain = parts.map((_, i) => parts.slice(0, i + 1).join('.'));
  let owner = 0;
  let start = 0;
  if (calls) {
    for (let j = 1; j < chain.length; j++) {
      const fn = calls.get(chain[j] as string)?.function;
      const idx = fn === undefined ? -1 : t.frames.findIndex((f, i) => i > start && f.function === fn);
      if (idx < 0 || idx > d) break;
      owner = j;
      start = idx;
    }
  } else {
    owner = Math.min(d, chain.length - 1);
    start = owner;
  }
  const id = chain[owner] as string;
  return start === d ? { id, own: true } : { id: `${id}>${d}`, own: false };
}
