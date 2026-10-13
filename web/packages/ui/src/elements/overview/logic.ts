// The overview's arithmetic, apart from its templates: progress, the pipeline
// graph by layer, the KPI counts and the timeline layout. Pure.
import { isLaunched, isPython, type JournalRow, type Plan, type PlanGroup, type PlanNode, type RunSummary, type TaskState } from '@contraagent/api';
import type { FlowCallNode, FlowFrame, FlowLoop } from './flow-types.js';

// --- progress by kind ---------------------------------------------------------

export interface Progress {
  total: number;
  done: number;
  pct: number;
}

export function progress(plan: Plan): Progress {
  const total = plan.groups.reduce((a, g) => a + g.total, 0);
  const done = plan.groups.reduce((a, g) => a + g.done + g.skipped, 0);
  return { total, done, pct: Math.round((100 * done) / Math.max(1, total)) };
}

/** Tries (journal rows that ran) and rows of tasks that never started: the one way the UI counts them. */
export function tryCounts(journal: readonly JournalRow[]): { tries: number; notStarted: number } {
  const tries = journal.filter(isLaunched).length;
  return { tries, notStarted: journal.length - tries };
}

/** How a run's tasks ended, from the plan: for a run that is over, in place of a progress bar. */
export function result(plan: Plan): { done: number; failed: number; notStarted: number; left: number } {
  const count = (...states: PlanNode['state'][]) => plan.nodes.filter((n) => states.includes(n.state)).length;
  return { done: count('done', 'skipped'), failed: count('failed'), notStarted: count('blocked'), left: count('pending', 'running') };
}

/** How long a run took, wall clock: from its start to its last activity (null when unknown). */
export function elapsedS(r: Pick<RunSummary, 'started_at' | 'last_ts'> | undefined): number | null {
  const a = Date.parse(r?.started_at ?? '');
  const b = Date.parse(r?.last_ts ?? '');
  return Number.isNaN(a) || Number.isNaN(b) ? null : Math.max(0, (b - a) / 1000);
}

// --- the pipeline graph, by layer ---------------------------------------------------
//
// The run as a graph of what its flow's code did, one layer at a time. A layer is
// a prefix of the flow path (the names of the functions a task was created in,
// outermost first). At a layer, a task created in the layer's own function is
// shown in a kind node (its plan group); a task created deeper is shown in the
// node of the function the layer's function called on the way (a function node).
// The same rule applies at every depth. Nodes whose call sites sit in the same
// loop of the layer's function are drawn in one loop box, a nested loop's box
// inside it; each box counts its own loop's passes (`flow[].loops[].pass`). Edges
// are the tasks' `after` (data) and `created_from` (created after those results),
// projected onto the layer's nodes; an edge from a task outside the layer is an
// incoming stub. Inside each node, one mark per unit, in the same unit order
// everywhere in the layer.
//
// The drawing is a layered (Sugiyama) layout of the compound graph, by container
// (the layer's top level, then each loop box, a box being one item of its parent):
// layers by longest path, with the edges that go back to a loop's next pass left
// out; a point (`~...`) on every layer a long edge crosses, so no edge runs over a
// node; crossings reduced by barycentre sweeps; then coordinates from the measured
// sizes (`layoutGraph`), every edge routed through those points and bending only in
// the gaps between layers. The order depends on structure only, never on states,
// and keeps a previous order: nodes that appear later are appended to their layer.

const SEVERITY: Record<TaskState, number> = { failed: 5, running: 4, blocked: 3, pending: 2, skipped: 1, done: 0 };

/** The state a mark of several tasks shows: the most severe of them. */
export const worstState = (nodes: readonly PlanNode[]): TaskState =>
  nodes.reduce<TaskState>((a, n) => (SEVERITY[n.state] > SEVERITY[a] ? n.state : a), 'done');

const worstOf = (states: readonly TaskState[]): TaskState => states.reduce<TaskState>((a, s) => (SEVERITY[s] > SEVERITY[a] ? s : a), 'done');

/** A layer segment that enters a loop box: `loop:<line>`, `loop:<outer>.<inner>` for a nested one. */
export const LOOP_SEGMENT = 'loop:';

/** One mark of a node: a unit's tasks (a kind node), or a unit's flow calls (a function node). */
export interface GraphMark {
  /** The task it opens (the running one, else the last), or the flow call it stands for. */
  key: string;
  unit: string;
  state: TaskState;
  /** The tasks it stands for. */
  count: number;
  keys: string[];
  /** A function node's mark: the function (`module.qualname`) it enters. */
  flow?: string;
  /** In a loop box: the passes its unit's tasks (or flow calls) of this node ran in, when more than 1. */
  passes?: number;
  /** A function node's mark: its tasks by state (those of the flow calls it started included). */
  counts?: NodeCounts;
  /** A function node's mark whose flow call raised or was closed: what it raised (`<type>: <message>`), '' when not recorded. */
  error?: string;
}

export type NodeCounts = Pick<PlanGroup, 'total' | 'done' | 'failed' | 'running' | 'pending' | 'skipped' | 'blocked'>;

export interface GraphNode {
  id: string;
  /** `kind`: tasks created in the layer's own function; `flow`: tasks created in a function it called. */
  type: 'kind' | 'flow';
  /** The plan group's id, or the function's `module.qualname`. */
  name: string;
  label: string;
  /** The kinds of its tasks. */
  kinds: string[];
  /** A kind node: who runs its tasks (`mixed` when its kinds differ); null for a function node. */
  executor: 'agent' | 'python' | 'mixed' | null;
  /** The loop box it is drawn in (its innermost), or null. */
  box: string | null;
  /** One slot per unit of the layer, in the layer's unit order: null where the unit has no mark here. Empty for a node without units. */
  units: (GraphMark | null)[];
  /** Its marks without a unit. */
  single: GraphMark[];
  /** Its tasks also wait for each other. */
  inOrder: boolean;
  /** Its tasks by state (in a function node, those of the flow calls they started included); in a loop box, each unit's latest pass. */
  counts: NodeCounts;
  /** A function node: its flow calls (in a loop box, each unit's latest pass); 0 for a kind node. */
  calls: number;
  /** A function node: those of its flow calls that raised or were closed. */
  errors: number;
}

/** The nodes created by one loop of the layer's function; a nested loop is a box inside it. */
export interface LoopBox {
  /** `loop:<line>`, `loop:<outer>.<inner>` for a nested loop. */
  id: string;
  /** The loop's first line. */
  loop: number;
  /** The file the loop is in (the layer's function's file, as recorded); '' when not known. */
  file: string;
  /** The loop box this one is nested in, or null when it is at the layer's top level. */
  parent: string | null;
  /** Its last pass: the most passes of this loop (never a nested loop's) in one run of it. */
  passes: number;
  /** How many units ran each number of passes of it, fewest first: `[[1, 4], [2, 1]]`. */
  spread: [passes: number, units: number][];
  /** Its items (node ids and nested loop box ids) by layer, each layer in drawing order. */
  layers: string[][];
}

export interface GraphEdge {
  from: string;
  to: string;
  /** Tasks of `to` joined to a task of `from`. */
  tasks: number;
  /** `after`: waits for its output; `created`: created after its result (and does not wait for its output). */
  type: 'after' | 'created';
  /** It goes back to a loop's next pass (or otherwise closes a cycle): the loop box stands for it, it is not drawn. */
  back: boolean;
}

/** An edge from a task outside the layer, named by the node it is in at the nearest layer that holds both. */
export interface GraphStub {
  id: string;
  label: string;
  to: string;
  tasks: number;
  type: 'after' | 'created';
}

/** One place an edge passes: a slot (`id`) of a container (`in`: '' for the layer's top level, else a loop box id). */
export interface RouteStep {
  id: string;
  in: string;
}

/**
 * A drawn edge (or a stub's), as the slots it passes from its source to its target:
 * a point (`~...`) on every layer it crosses, and a loop box's id where it leaves or
 * enters that box.
 */
export interface EdgeRoute {
  from: string;
  to: string;
  type: 'after' | 'created';
  steps: RouteStep[];
}

/** Where a layer's items are: what `layerGraph` keeps when it is given it back. */
export interface LayerOrder {
  /** The top level's layers: nodes, loop boxes and stubs. */
  layers: string[][];
  boxes: Record<string, string[][]>;
}

export interface LayerGraph {
  /** The layer: function names, outermost first. */
  path: string[];
  /** Every node, in drawing order. */
  nodes: GraphNode[];
  /** Node and loop box ids by layer, each layer in drawing order. */
  layers: string[][];
  boxes: LoopBox[];
  edges: GraphEdge[];
  stubs: GraphStub[];
  /** The units with a mark in this layer, in the order the run first scheduled them. */
  units: string[];
  /** Each container's slots by layer, in drawing order: '' for the top level, a loop box's id for its inside. */
  slots: Record<string, string[][]>;
  /** The drawn edges and the stubs' edges, with the slots they pass. */
  routes: EdgeRoute[];
  order: LayerOrder;
}

/** A frame of a task's flow path as the graph reads it: its loops by first line, and their passes. */
interface TaskFrame {
  function: string;
  file: string;
  line: number;
  loops: number[];
  passes: number[];
}

interface FlowTask {
  n: PlanNode;
  path: string[];
  frames: TaskFrame[];
  from: string[];
  call: string;
}

interface FlowIndex {
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

function indexOf(plan: Plan): FlowIndex {
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

const startsWith = (path: readonly string[], prefix: readonly string[]) => prefix.every((p, i) => path[i] === p);

/** Who runs a kind node's tasks: a coding agent, Python, or both (`mixed`). */
function executorOf(ns: readonly PlanNode[]): 'agent' | 'python' | 'mixed' {
  const py = ns.filter(isPython).length;
  return py === 0 ? 'agent' : py === ns.length ? 'python' : 'mixed';
}

/** A function's name without its module. */
export const shortName = (fn: string): string => fn.slice(fn.lastIndexOf('.') + 1) || fn;

/** The loops around a task's call site at depth `d`, outermost first ([] outside any). */
const loopsAt = (t: FlowTask, d: number): number[] => (d > 0 ? (t.frames[d - 1]?.loops ?? []) : []);

/** The pass of each of those loops, outermost first: the task's place in them. */
const passesAt = (t: FlowTask, d: number): number[] => (d > 0 ? (t.frames[d - 1]?.passes ?? []) : []);

/** Two pass lists in the order the passes ran: the outer loop's first. */
function cmpPasses(a: readonly number[], b: readonly number[]): number {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0);
    if (d) return d;
  }
  return 0;
}

/** The loop box ids for a loop chain, outermost first: `loop:7`, then `loop:7.9`, ... */
export const boxChain = (loops: readonly number[]): string[] => loops.map((_, i) => `${LOOP_SEGMENT}${loops.slice(0, i + 1).join('.')}`);

/** Where a task is shown at depth `d`: its kind node, or the node of the function it was created under. */
function placeOf(t: FlowTask, d: number): { id: string; type: 'kind' | 'flow'; name: string; loops: number[] } {
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
function instanceOf(t: FlowTask, d: number, calls: Map<string, FlowCallNode> | null): { id: string; own: boolean } {
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

const CALL_STATE: Record<FlowCallNode['state'], TaskState> = { running: 'running', returned: 'done', raised: 'failed', closed: 'failed' };

/** A flow call stopped with an error: it raised, or it was closed. */
const callFailed = (c: FlowCallNode | undefined): c is FlowCallNode => c?.state === 'raised' || c?.state === 'closed';

function taskMark(ts: readonly FlowTask[], unit: string): GraphMark {
  const ns = ts.map((t) => t.n);
  const key = (ns.find((n) => n.state === 'running') ?? ns[ns.length - 1] ?? { key: '' }).key;
  return { key, unit, state: worstState(ns), count: ns.length, keys: ns.map((n) => n.key) };
}

interface Marks {
  byUnit: Map<string, GraphMark>;
  single: GraphMark[];
  /** A function node's flow calls, and those that raised or were closed. */
  calls?: number;
  errors?: number;
}

const push = <K, V>(m: Map<K, V[]>, k: K, v: V): void => {
  const xs = m.get(k);
  if (xs) xs.push(v);
  else m.set(k, [v]);
};

/** A kind node's marks: one per unit, and one per task without a unit. */
function kindMarks(ts: readonly FlowTask[]): Marks {
  const byUnit = new Map<string, FlowTask[]>();
  const single: GraphMark[] = [];
  for (const t of ts) {
    if (t.n.unit) push(byUnit, t.n.unit, t);
    else single.push(taskMark([t], ''));
  }
  return { byUnit: new Map([...byUnit].map(([u, xs]) => [u, taskMark(xs, u)])), single };
}

interface Instance {
  id: string;
  own: boolean;
  tasks: FlowTask[];
  /** The one unit of its tasks, or '' when they have several (or none). */
  unit: string;
}

function instances(ts: readonly FlowTask[], d: number, calls: Map<string, FlowCallNode> | null): Instance[] {
  const by = new Map<string, Instance>();
  for (const t of ts) {
    const { id, own } = instanceOf(t, d, calls);
    const x = by.get(id) ?? by.set(id, { id, own, tasks: [], unit: '' }).get(id);
    x?.tasks.push(t);
  }
  for (const x of by.values()) {
    const us = new Set(x.tasks.map((t) => t.n.unit || ''));
    x.unit = us.size === 1 ? ([...us][0] as string) : '';
  }
  return [...by.values()];
}

/**
 * A function node's marks: its flow calls, one mark per unit when a call's tasks share one unit, else one per call.
 * A call's state is the most severe of its own (raised or closed: failed) and its tasks' (those of the calls it
 * started included), so a call that caught a task's failure and returned still shows it.
 */
function flowMarks(ts: readonly FlowTask[], d: number, name: string, calls: Map<string, FlowCallNode> | null): Marks {
  const markOf = (xs: readonly Instance[], unit: string): GraphMark => {
    const own = xs.map((x) => (x.own ? calls?.get(x.id) : undefined));
    const states = xs.map((x, i): TaskState => {
      const c = own[i];
      const tasks = worstState(x.tasks.map((t) => t.n));
      return c && CALL_STATE[c.state] ? worstOf([CALL_STATE[c.state], tasks]) : tasks;
    });
    const tasks = xs.flatMap((x) => x.tasks);
    const keys = tasks.map((t) => t.n.key);
    const last = xs.find((_, i) => states[i] === 'running') ?? xs[xs.length - 1];
    const failed = own.find(callFailed);
    const mark: GraphMark = { key: last?.id ?? '', unit, state: worstOf(states), count: keys.length, keys, flow: name, counts: taskCounts(tasks) };
    return failed ? { ...mark, error: failed.error ?? '' } : mark;
  };
  const byUnit = new Map<string, Instance[]>();
  const single: GraphMark[] = [];
  const xs = instances(ts, d, calls);
  for (const x of xs) {
    if (x.unit) push(byUnit, x.unit, x);
    else single.push(markOf([x], ''));
  }
  const errors = calls ? xs.filter((x) => x.own && callFailed(calls.get(x.id))).length : 0;
  return { byUnit: new Map([...byUnit].map(([u, ys]) => [u, markOf(ys, u)])), single, calls: xs.length, errors };
}

/** Tasks by state. */
function taskCounts(ts: readonly FlowTask[]): NodeCounts {
  const c: NodeCounts = { total: ts.length, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0 };
  for (const t of ts) c[t.n.state] += 1;
  return c;
}

/** The tasks of each unit's latest pass, by the passes of the loops around them at depth `d` (tasks without a unit count as one unit). */
function latestPass(ts: readonly FlowTask[], d: number): FlowTask[] {
  const most = new Map<string, number[]>();
  for (const t of ts) {
    const u = t.n.unit || '';
    const had = most.get(u);
    if (!had || cmpPasses(passesAt(t, d), had) > 0) most.set(u, passesAt(t, d));
  }
  return ts.filter((t) => cmpPasses(passesAt(t, d), most.get(t.n.unit || '') ?? []) === 0);
}

/** How many passes each unit's tasks in a node ran in (distinct pass lists at depth `d`). */
function passesByUnit(ts: readonly FlowTask[], d: number): Map<string, number> {
  const seen = new Map<string, Set<string>>();
  for (const t of ts) {
    const u = t.n.unit || '';
    (seen.get(u) ?? seen.set(u, new Set()).get(u))?.add(passesAt(t, d).join('.'));
  }
  return new Map([...seen].map(([u, s]) => [u, s.size]));
}

/** A mark with its pass count, when it is more than 1. */
const withPasses = (m: GraphMark, n: number | undefined): GraphMark => (n && n > 1 ? { ...m, passes: n } : m);

// ---- the order: layers, long-edge points, crossing reduction ----

const pairKey = (a: string, b: string) => `${a}\u0000${b}`;

/**
 * Each id's layer by longest path. Edges that close a cycle (found depth first, in
 * `ids` order) are left out; `fixed` ids keep their layer.
 */
function rankLayers(ids: readonly string[], edges: readonly (readonly [string, string])[], fixed: ReadonlyMap<string, number>): Map<string, number> {
  const known = new Set(ids);
  const all = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const [a, b] of edges) if (a !== b && known.has(a) && known.has(b) && !all.get(a)?.includes(b)) all.get(a)?.push(b);
  const back = new Set<string>();
  const seen = new Map<string, 1 | 2>();
  for (const root of ids) {
    if (seen.has(root)) continue;
    seen.set(root, 1);
    const stack: [string, number][] = [[root, 0]];
    while (stack.length) {
      const top = stack[stack.length - 1] as [string, number];
      const ss = all.get(top[0]) ?? [];
      if (top[1] < ss.length) {
        const s = ss[top[1]++] as string;
        const st = seen.get(s);
        if (st === 1) back.add(pairKey(top[0], s));
        else if (!st) {
          seen.set(s, 1);
          stack.push([s, 0]);
        }
      } else {
        seen.set(top[0], 2);
        stack.pop();
      }
    }
  }
  const succ = new Map<string, string[]>(ids.map((id) => [id, []]));
  const pred = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const [a, ss] of all) {
    for (const b of ss) {
      if (back.has(pairKey(a, b))) continue;
      succ.get(a)?.push(b);
      pred.get(b)?.push(a);
    }
  }
  // Longest path, in topological order (Kahn's).
  const indeg = new Map(ids.map((id) => [id, pred.get(id)?.length ?? 0]));
  const queue = ids.filter((id) => !indeg.get(id));
  const layer = new Map<string, number>();
  for (let q = queue.shift(); q !== undefined; q = queue.shift()) {
    layer.set(q, fixed.get(q) ?? Math.max(0, ...(pred.get(q) ?? []).map((p) => (layer.get(p) ?? 0) + 1)));
    for (const s of succ.get(q) ?? []) {
      indeg.set(s, (indeg.get(s) ?? 0) - 1);
      if (!indeg.get(s)) queue.push(s);
    }
  }
  return layer;
}

/** Pairs (a, b) between adjacent layers that cross, for the order `pos`. */
function crossings(rows: readonly string[][], links: readonly (readonly [string, string])[], pos: ReadonlyMap<string, number>, layerOf: ReadonlyMap<string, number>): number {
  let n = 0;
  const by = new Map<number, [number, number][]>();
  for (const [a, b] of links) {
    const l = layerOf.get(a);
    if (l === undefined) continue;
    push(by, l, [pos.get(a) ?? 0, pos.get(b) ?? 0]);
  }
  for (const ls of by.values())
    for (let i = 0; i < ls.length; i++)
      for (let j = i + 1; j < ls.length; j++) {
        const [a1, b1] = ls[i] as [number, number];
        const [a2, b2] = ls[j] as [number, number];
        if ((a1 - a2) * (b1 - b2) < 0) n++;
      }
  return rows.length ? n : 0;
}

/** True for a point where an edge crosses a layer. */
export const isPoint = (id: string): boolean => id.startsWith('~');

/**
 * The order within each layer that reduces crossings: barycentre sweeps, down and
 * up, four times, keeping the best. `links` join a slot to one in the next layer.
 * With `keep`, those ids keep their order (a previous layout's, new ones after
 * them) and only the other slots (the points) move between them.
 */
function orderRows(rows: string[][], links: readonly (readonly [string, string])[], keep: boolean): string[][] {
  const layerOf = new Map<string, number>();
  rows.forEach((row, i) => row.forEach((id) => layerOf.set(id, i)));
  const pred = new Map<string, string[]>();
  const succ = new Map<string, string[]>();
  for (const [a, b] of links) {
    push(succ, a, b);
    push(pred, b, a);
  }
  const pos = new Map<string, number>();
  const fix = (row: readonly string[]) => row.forEach((id, i) => pos.set(id, i));
  const cur = rows.map((r) => [...r]);
  cur.forEach(fix);
  const score = () => crossings(cur, links, pos, layerOf);
  let best = cur.map((r) => [...r]);
  let bestN = score();
  const sortRow = (row: string[], near: Map<string, string[]>): string[] => {
    const bc = new Map<string, number>();
    for (const id of row) {
      const ps = (near.get(id) ?? []).map((p) => pos.get(p)).filter((x): x is number => x !== undefined);
      bc.set(id, ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : (pos.get(id) ?? 0));
    }
    const at = (id: string) => bc.get(id) ?? 0;
    if (!keep) return [...row].sort((a, b) => at(a) - at(b) || (pos.get(a) ?? 0) - (pos.get(b) ?? 0));
    // The kept ids stay in their order; each point goes before the first kept id it is left of.
    const fixed = row.filter((id) => !isPoint(id));
    const points = row.filter(isPoint).sort((a, b) => at(a) - at(b) || (pos.get(a) ?? 0) - (pos.get(b) ?? 0));
    const out: string[] = [];
    let p = 0;
    for (const id of fixed) {
      while (p < points.length && at(points[p] as string) < at(id)) out.push(points[p++] as string);
      out.push(id);
    }
    return [...out, ...points.slice(p)];
  };
  for (let sweep = 0; sweep < 4; sweep++) {
    const down = sweep % 2 === 0;
    const order = down ? cur.map((_, i) => i).slice(1) : cur.map((_, i) => i).reverse().slice(1);
    for (const i of order) {
      const row = sortRow(cur[i] as string[], down ? pred : succ);
      cur[i] = row;
      fix(row);
    }
    const n = score();
    if (n < bestN) {
      bestN = n;
      best = cur.map((r) => [...r]);
    }
  }
  return score() <= bestN ? cur : best;
}

interface Draft {
  id: string;
  type: 'kind' | 'flow';
  name: string;
  loops: number[];
  tasks: FlowTask[];
}

interface Projection {
  graph: LayerGraph;
  drafts: Map<string, Draft>;
  ix: FlowIndex;
}

function project(plan: Plan, path: readonly string[], prev?: LayerOrder, down = false): Projection {
  const ix = indexOf(plan);
  const d = path.length;
  const inside = ix.tasks.filter((t) => startsWith(t.path, path));
  const drafts = new Map<string, Draft>();
  const nodeOfKey = new Map<string, string>();
  for (const t of inside) {
    const p = placeOf(t, d);
    const x = drafts.get(p.id) ?? drafts.set(p.id, { ...p, tasks: [] }).get(p.id);
    x?.tasks.push(t);
    nodeOfKey.set(t.n.key, p.id);
  }
  const marks = new Map<string, Marks>();
  const shownOf = new Map<string, FlowTask[]>(); // node id -> the tasks it counts
  const boxOf = new Map<string, string>(); // node id -> its innermost loop box
  const boxParent = new Map<string, string | null>(); // loop box -> the box it nests in
  for (const x of drafts.values()) {
    const chain = boxChain(x.loops);
    const inner = chain[chain.length - 1] ?? null;
    chain.forEach((box, i) => boxParent.set(box, chain[i - 1] ?? null));
    if (inner) boxOf.set(x.id, inner);
    // In a loop box, a unit's mark is its latest pass, and counts the passes it ran in.
    const shown = inner ? latestPass(x.tasks, d) : x.tasks;
    shownOf.set(x.id, shown);
    const m = x.type === 'kind' ? kindMarks(shown) : flowMarks(shown, d, x.name, ix.calls);
    if (inner) {
      const per = passesByUnit(x.tasks, d);
      m.byUnit = new Map([...m.byUnit].map(([u, mk]) => [u, withPasses(mk, per.get(u))]));
    }
    marks.set(x.id, m);
  }
  const units = [...new Set([...marks.values()].flatMap((m) => [...m.byUnit.keys()]))].sort(
    (a, b) => (ix.unitRank.get(a) ?? 0) - (ix.unitRank.get(b) ?? 0),
  );

  // Each box's own loop: its last pass, and the passes each unit ran of it (its
  // distinct passes, those of the loops around it included).
  const boxLast = new Map<string, number>();
  const boxRan = new Map<string, Map<string, Set<string>>>();
  for (const x of drafts.values()) {
    const chain = boxChain(x.loops);
    for (const t of x.tasks) {
      const ps = passesAt(t, d);
      chain.forEach((box, i) => {
        boxLast.set(box, Math.max(boxLast.get(box) ?? 1, ps[i] ?? 1));
        const per = boxRan.get(box) ?? boxRan.set(box, new Map()).get(box);
        const u = t.n.unit || '';
        (per?.get(u) ?? per?.set(u, new Set()).get(u))?.add(ps.slice(0, i + 1).join('.'));
      });
    }
  }

  // The loop boxes an id sits in, innermost first (for a box id, itself first).
  const boxPath = (id: string): string[] => {
    const out: string[] = [];
    let b: string | null = id.startsWith(LOOP_SEGMENT) ? id : (boxOf.get(id) ?? null);
    while (b) {
      out.push(b);
      b = boxParent.get(b) ?? null;
    }
    return out;
  };
  // The direct child of `container` (a box, or '' for the layer's top level) that holds a node `id`.
  const itemIn = (id: string, container: string): string | undefined => {
    const bp = boxPath(id);
    if (container === '') return bp[bp.length - 1] ?? id;
    const i = bp.indexOf(container);
    return i < 0 ? undefined : i === 0 ? id : bp[i - 1];
  };
  // The deepest loop box holding both ends of an edge (the layer's top level when none).
  const commonBox = (a: string, b: string): string => {
    const bp = boxPath(a);
    return bp.find((x) => boxPath(b).includes(x)) ?? '';
  };
  // The container a slot is in: a stub's is the top level.
  const containerOf = (id: string): string => (id.startsWith('stub:') ? '' : (boxOf.get(id) ?? ''));

  // Edges, projected onto the layer's nodes; from outside it, stubs. An edge whose
  // every task joins a later pass of a loop around both ends goes back to the next pass.
  const inOrder = new Set<string>();
  const pairs = new Map<string, { from: string; to: string; type: 'after' | 'created'; tasks: Set<string>; samePass: boolean }>();
  const stubs = new Map<string, { id: string; label: string; to: string; type: 'after' | 'created'; tasks: Set<string> }>();
  const outside = (o: FlowTask): { id: string; label: string } => {
    let c = 0;
    while (c < d && o.path[c] === path[c]) c++;
    const p = placeOf(o, c);
    return { id: `stub:${c}:${p.id}`, label: p.type === 'kind' ? (ix.labels.get(p.name) ?? p.name) : shortName(p.name) };
  };
  for (const t of inside) {
    const to = nodeOfKey.get(t.n.key) as string;
    const link = (dep: string, type: 'after' | 'created') => {
      const from = nodeOfKey.get(dep);
      if (from === to) {
        if (type === 'after') inOrder.add(to);
        return;
      }
      if (from !== undefined) {
        const o = ix.byKey.get(dep) as FlowTask;
        const a = loopsAt(o, d);
        const b = loopsAt(t, d);
        let k = 0;
        while (k < a.length && a[k] === b[k]) k++;
        const same = cmpPasses(passesAt(o, d).slice(0, k), passesAt(t, d).slice(0, k)) === 0;
        const key = `${from}\u0000${to}\u0000${type}`;
        const e = pairs.get(key) ?? pairs.set(key, { from, to, type, tasks: new Set(), samePass: false }).get(key);
        e?.tasks.add(t.n.key);
        if (e && same) e.samePass = true;
        return;
      }
      const o = ix.byKey.get(dep);
      if (!o) return; // not in the plan yet
      const s = outside(o);
      const k = `${s.id}\u0000${to}\u0000${type}`;
      (stubs.get(k) ?? stubs.set(k, { ...s, to, type, tasks: new Set() }).get(k))?.tasks.add(t.n.key);
    };
    for (const dep of t.n.after ?? []) link(dep, 'after');
    for (const dep of t.from) link(dep, 'created');
  }
  // A created_from edge is drawn only where no after edge joins the same two.
  const all = [...pairs.values()].filter((e) => e.type === 'after' || !pairs.has(`${e.from}\u0000${e.to}\u0000after`));
  const stubList = [...stubs.values()].filter((s) => s.type === 'after' || !stubs.has(`${s.id}\u0000${s.to}\u0000after`));

  // Layers, by container: the layer's top level, then each loop box (its own nodes
  // and the loop boxes nested in it). Each box is one item of its parent.
  const containers = ['', ...boxParent.keys()];
  const kidsOf = new Map<string, string[]>(containers.map((c) => [c, []]));
  for (const id of drafts.keys()) {
    for (const c of containers) {
      const it = itemIn(id, c);
      if (it !== undefined && !kidsOf.get(c)?.includes(it)) kidsOf.get(c)?.push(it);
    }
  }
  const lay = new Map<string, Map<string, number>>();
  for (const c of containers) {
    const kids = kidsOf.get(c) ?? [];
    const prevRows = c === '' ? prev?.layers : prev?.boxes[c];
    const fixed = new Map<string, number>();
    prevRows?.forEach((row, i) => row.forEach((id) => kids.includes(id) && fixed.set(id, i)));
    // An edge back to a loop's next pass does not set the layers.
    const es = all
      .filter((e) => e.samePass && commonBox(e.from, e.to) === c)
      .map((e) => [itemIn(e.from, c) as string, itemIn(e.to, c) as string] as const);
    lay.set(c, rankLayers(kids, es, fixed));
  }
  // Stubs, in the top level: in the layer before the first they lead to (a new first layer when that is the first).
  const top = lay.get('') as Map<string, number>;
  const stubIds = [...new Set(stubList.map((s) => s.id))];
  const prevTop = new Map<string, number>();
  prev?.layers.forEach((row, i) => row.forEach((id) => prevTop.set(id, i)));
  const stubAt = new Map(
    stubIds.map((id) => [id, prevTop.get(id) ?? Math.min(...stubList.filter((s) => s.id === id).map((s) => top.get(itemIn(s.to, '') as string) ?? 0)) - 1]),
  );
  if ([...stubAt.values()].some((l) => l < 0)) {
    for (const [id, l] of top) top.set(id, l + 1);
    for (const [id, l] of stubAt) stubAt.set(id, l + 1);
  }
  for (const [id, l] of stubAt) top.set(id, l);
  const layerOf = (c: string, id: string): number => lay.get(c)?.get(id) ?? 0;
  const lastLayer = (c: string): number => Math.max(0, ...(lay.get(c)?.values() ?? []));

  // Every edge whose ends are not in a later layer than its start goes back: not drawn.
  const isBack = (from: string, to: string): boolean => {
    const c = commonBox(from, to);
    return layerOf(c, itemIn(from, c) as string) >= layerOf(c, itemIn(to, c) as string);
  };
  const edges: GraphEdge[] = all.map((e) => ({ from: e.from, to: e.to, tasks: e.tasks.size, type: e.type, back: isBack(e.from, e.to) }));

  // Each container's rows: its items by layer, a previous order kept, new items after it.
  const rows = new Map<string, string[][]>();
  for (const c of containers) {
    const prevRows = c === '' ? prev?.layers : prev?.boxes[c];
    const kept = (prevRows ?? []).flat();
    const ids = [...(c === '' ? [...stubIds] : []), ...(kidsOf.get(c) ?? [])];
    ids.sort((a, b) => {
      const ka = kept.indexOf(a);
      const kb = kept.indexOf(b);
      return (ka < 0 ? Infinity : ka) - (kb < 0 ? Infinity : kb);
    });
    const r: string[][] = Array.from({ length: lastLayer(c) + 1 }, () => []);
    for (const id of ids) r[layerOf(c, id)]?.push(id);
    rows.set(c, r);
  }

  // Routes: the drawn edges through points on the layers they cross. The points of
  // edges from one place (of one type) are shared, so their lines run as one.
  const routes: EdgeRoute[] = [];
  const points = new Set<string>();
  const point = (c: string, origin: string, type: string, l: number): RouteStep => {
    const id = `~${c}|${origin}|${type}|${l}`;
    if (!points.has(id)) {
      points.add(id);
      rows.get(c)?.[l]?.push(id);
    }
    return { id, in: c };
  };
  // A point beside a box, in its layer of the container around it: an edge that leaves or
  // enters the box through its side, between two of its layers, passes there.
  const byPoint = (c: string, box: string, origin: string, type: string): RouteStep => {
    const l = layerOf(c, box);
    const id = `~${c}|by:${box}|${origin}|${type}|${l}`;
    if (!points.has(id)) {
      points.add(id);
      rows.get(c)?.[l]?.push(id);
    }
    return { id, in: c };
  };
  // An edge enters a box at its near side only to reach the box's first layer (and,
  // top to bottom, not even then: the box's label is on that side); else through its
  // side, next to the layer it goes to. It leaves at the far side only from the box's
  // last layer, else through its side. So it runs inside a box only where it starts or ends.
  const route = (from: string, to: string, type: 'after' | 'created'): RouteStep[] => {
    const c = from.startsWith('stub:') ? '' : commonBox(from, to);
    let curIn = containerOf(from);
    let cur = from;
    const steps: RouteStep[] = [{ id: from, in: curIn }];
    // Out of the boxes around the source, up to the common container.
    while (curIn !== c) {
      const up = boxParent.get(curIn) ?? '';
      steps.push({ id: curIn, in: up });
      if (layerOf(curIn, cur) < lastLayer(curIn)) steps.push(byPoint(up, curIn, cur, type));
      cur = curIn;
      curIn = up;
    }
    // Across the common container, then into the boxes around the target.
    const target = itemIn(to, c) as string;
    for (let l = layerOf(c, cur) + 1; l < layerOf(c, target); l++) steps.push(point(c, cur, type, l));
    const bp = boxPath(to);
    const inward = bp.slice(0, c === '' ? bp.length : bp.indexOf(c)).reverse();
    const origin = `>${c}:${cur}`;
    let k = c;
    for (const box of inward) {
      const n = itemIn(to, box) as string;
      if (layerOf(box, n) > 0 || down) steps.push(byPoint(k, box, origin, type));
      steps.push({ id: box, in: k });
      k = box;
    }
    steps.push({ id: to, in: k });
    return steps;
  };
  for (const e of edges) if (!e.back) routes.push({ from: e.from, to: e.to, type: e.type, steps: route(e.from, e.to, e.type) });
  for (const s of stubList) routes.push({ from: s.id, to: s.to, type: s.type, steps: route(s.id, s.to, s.type) });

  // The order within each layer.
  const slots: Record<string, string[][]> = {};
  for (const c of containers) {
    const links: [string, string][] = [];
    const lv = new Map((rows.get(c) ?? []).flatMap((r, i) => r.map((id) => [id, i] as const)));
    for (const r of routes)
      for (let i = 1; i < r.steps.length; i++) {
        const a = r.steps[i - 1] as RouteStep;
        const b = r.steps[i] as RouteStep;
        if (a.in === c && b.in === c && lv.get(a.id) !== lv.get(b.id)) links.push([a.id, b.id]);
      }
    const hasPrev = c === '' ? !!prev : !!prev?.boxes[c];
    // A point beside a box is right after it.
    slots[c] = orderRows(rows.get(c) ?? [], links, hasPrev).map((row) => {
      const by = row.filter((id) => id.includes('|by:'));
      const rest = row.filter((id) => !id.includes('|by:'));
      return rest.flatMap((id) => [id, ...by.filter((p) => p.includes(`|by:${id}|`))]);
    });
  }
  const real = (r: readonly string[][]) => r.map((row) => row.filter((id) => !isPoint(id)));
  const boxes: LoopBox[] = [...boxParent.keys()].map((id) => {
    const spread = new Map<number, number>();
    for (const [u, ran] of boxRan.get(id) ?? []) if (u) spread.set(ran.size, (spread.get(ran.size) ?? 0) + 1);
    return {
      id,
      loop: Number(id.slice(LOOP_SEGMENT.length).split('.').pop()),
      file: inside[0]?.frames[d - 1]?.file ?? '',
      parent: boxParent.get(id) ?? null,
      passes: boxLast.get(id) ?? 1,
      spread: [...spread].sort((a, b) => a[0] - b[0]),
      layers: real(slots[id] ?? []).filter((r) => r.length),
    };
  });
  const outerRows = real(slots[''] ?? []).map((row) => row.filter((id) => !id.startsWith('stub:')));

  const nodeOf = (x: Draft): GraphNode => {
    const m = marks.get(x.id) as Marks;
    const hasUnits = m.byUnit.size > 0;
    return {
      id: x.id,
      type: x.type,
      name: x.name,
      label: x.type === 'kind' ? (ix.labels.get(x.name) ?? x.name) : shortName(x.name),
      kinds: [...new Set(x.tasks.map((t) => t.n.kind))],
      executor: x.type === 'flow' ? null : executorOf(x.tasks.map((t) => t.n)),
      box: boxOf.get(x.id) ?? null,
      units: hasUnits ? units.map((u) => m.byUnit.get(u) ?? null) : [],
      single: m.single,
      inOrder: inOrder.has(x.id),
      counts: taskCounts(shownOf.get(x.id) ?? []),
      calls: m.calls ?? 0,
      errors: m.errors ?? 0,
    };
  };
  const byBox = new Map(boxes.map((b) => [b.id, b]));
  // Every node id, in drawing order: expand each loop box to the nodes nested in it.
  const expand = (ids: readonly string[]): string[] => ids.flatMap((id) => (id.startsWith(LOOP_SEGMENT) ? expand((byBox.get(id)?.layers ?? []).flat()) : [id]));
  return {
    graph: {
      path: [...path],
      nodes: expand(outerRows.flat()).map((id) => nodeOf(drafts.get(id) as Draft)),
      layers: outerRows.filter((r) => r.length),
      boxes,
      edges,
      stubs: stubList.map((s) => ({ id: s.id, label: s.label, to: s.to, tasks: s.tasks.size, type: s.type })),
      units,
      slots,
      routes,
      order: { layers: real(slots[''] ?? []), boxes: Object.fromEntries(boxes.map((b) => [b.id, real(slots[b.id] ?? [])])) },
    },
    drafts,
    ix,
  };
}

/**
 * The layer `path` of the plan's flow. Pass the `order` of the last graph of this layer as
 * `prev` to keep its nodes in place; `down` routes the edges for a drawing top to bottom
 * (a box's label is then on the side its edges come in).
 */
export function layerGraph(plan: Plan, path: readonly string[] = [], prev?: LayerOrder, down = false): LayerGraph {
  return project(plan, path, prev, down).graph;
}

/**
 * The layer the graph opens on: from the top, down while a layer has a single
 * node and it is a function's. It stops at a single function node whose flow call
 * raised or was closed, so a run that failed inside a flow opens on the node that
 * shows it, not inside it. A failed or not started task does not stop it: the layer
 * below shows that task's own mark. A static flow lands on its kinds.
 */
export function autoLayer(plan: Plan): string[] {
  const ix = indexOf(plan);
  const path: string[] = [];
  // The failure sites: flow calls that raised or were closed with no raised descendant.
  // The graph stops on the node that shows one, not inside it. A plan with no flow calls
  // cannot tell its failure sites, so it descends as if there were none.
  const raised = new Set<string>();
  if (ix.calls) for (const c of ix.calls.values()) if (c.state === 'raised' || c.state === 'closed') raised.add(c.id);
  const isSite = (id: string): boolean => raised.has(id) && ![...raised].some((r) => r !== id && r.startsWith(`${id}.`));
  for (;;) {
    let only: { id: string; name: string } | null = null;
    let one = true;
    const mine: FlowTask[] = [];
    for (const t of ix.tasks) {
      if (!startsWith(t.path, path)) continue;
      const p = placeOf(t, path.length);
      if (p.type === 'kind' || (only && only.id !== p.id)) {
        one = false;
        break;
      }
      only = p;
      mine.push(t);
    }
    // Stop before entering a single function node that is itself a failure site.
    const atSite = mine.some((t) => isSite(instanceOf(t, path.length, ix.calls).id));
    if (!one || !only || atSite) return path;
    path.push(only.name);
  }
}

/** A layer's segments: its path, and the loop box entered at its end (null when none). */
export function splitLayer(segments: readonly string[]): { path: string[]; loop: string | null } {
  const last = segments[segments.length - 1];
  return last?.startsWith(LOOP_SEGMENT) ? { path: segments.slice(0, -1), loop: last } : { path: [...segments], loop: null };
}

/**
 * The layer `segments` names, as the plan has it: the segments themselves when the
 * plan has that layer (a prefix of a task's flow path, and the loop box after it);
 * else, when the last function is named by its `module.qualname` (or, failing that,
 * its name) and the plan reaches it by one flow path only, that flow path, with the
 * loop box when the layer there has it. Null when the plan has no such layer.
 */
export function resolveLayer(plan: Plan, segments: readonly string[]): string[] | null {
  const { path, loop } = splitLayer(segments);
  const ix = indexOf(plan);
  const hasLoop = (p: readonly string[]) => !loop || layerGraph(plan, p).boxes.some((b) => b.id === loop);
  if (ix.tasks.some((t) => startsWith(t.path, path))) return hasLoop(path) ? [...segments] : null;
  const name = path[path.length - 1];
  if (name === undefined) return null;
  const found = (match: (fn: string) => boolean): string[][] => {
    const by = new Map<string, string[]>();
    for (const t of ix.tasks) t.path.forEach((fn, i) => match(fn) && by.set(t.path.slice(0, i + 1).join('/'), t.path.slice(0, i + 1)));
    return [...by.values()];
  };
  const exact = found((fn) => fn === name);
  const named = exact.length ? exact : found((fn) => shortName(fn) === name);
  const only = named.length === 1 ? (named[0] as string[]) : null;
  return only && hasLoop(only) ? (loop ? [...only, loop] : only) : null;
}

/** One level up from `segments`: null at the top (the layer the graph opens on, `auto`), [] for that layer. */
export function parentLayer(segments: readonly string[], auto: readonly string[]): string[] | null {
  if (segments.length <= auto.length) return null;
  const up = segments.slice(0, -1);
  return up.length <= auto.length ? [] : up;
}

// ---- a loop's passes: units by (node, pass) ----

/** A column of a loop's passes: one node, in one pass of each loop from the unrolled box down to the node's own box. */
export interface MatrixColumn {
  node: GraphNode;
  /** The passes, the unrolled box's loop first. */
  passes: number[];
}

/** A header cell over the columns: a pass of a loop, a nested loop, or a node. */
export type MatrixHead =
  | { type: 'pass'; box: LoopBox; pass: number; span: number; rows: number }
  | { type: 'loop'; box: LoopBox; span: number; rows: number }
  | { type: 'node'; node: GraphNode; passes: number[]; span: number; rows: number };

export interface MatrixRow {
  /** The unit, or '' for the tasks without one. */
  unit: string;
  /** How many passes of the unrolled loop it ran (in every run of the loop). */
  passes: number;
  /** The most severe state of its marks. */
  state: TaskState;
  /** One per column: its mark, or null where it has none. */
  cells: (GraphMark | null)[];
}

/** A loop box with its passes unrolled: a row per unit, a column per (node, pass), nested loops as nested column groups. */
export interface PassMatrix {
  box: LoopBox;
  columns: MatrixColumn[];
  /** The header rows, outermost first; a node's cell spans down to the last. */
  head: MatrixHead[][];
  /** The units that have a task in the box, in the layer's order; the tasks without a unit last. */
  rows: MatrixRow[];
}

type ColTree = { type: 'pass'; box: LoopBox; pass: number; kids: ColTree[] } | { type: 'loop'; box: LoopBox; kids: ColTree[] } | { type: 'node'; node: GraphNode; passes: number[] };

/**
 * The loop box `box` of layer `path` with its passes unrolled; null when the layer has
 * no such box. Each task is in the column of its node and of its passes of the box's
 * loop and of every loop nested in it, so an inner loop's passes are counted within
 * each pass of the outer one. A column no task reached is left out.
 */
export function passMatrix(plan: Plan, path: readonly string[], box: string, prev?: LayerOrder): PassMatrix | null {
  const { graph, drafts, ix } = project(plan, path, prev);
  const b = graph.boxes.find((x) => x.id === box);
  if (!b) return null;
  const d = path.length;
  const i0 = b.id.slice(LOOP_SEGMENT.length).split('.').length - 1;
  const byBox = new Map(graph.boxes.map((x) => [x.id, x]));
  const byNode = new Map(graph.nodes.map((n) => [n.id, n]));
  const rel = (t: FlowTask) => passesAt(t, d).slice(i0);
  const leaves = (x: LoopBox): string[] => x.layers.flat().flatMap((id) => (byBox.has(id) ? leaves(byBox.get(id) as LoopBox) : [id]));
  const tasksOf = (x: LoopBox): FlowTask[] => leaves(x).flatMap((id) => drafts.get(id)?.tasks ?? []);
  const same = (a: readonly number[], p: readonly number[]) => a.length === p.length && cmpPasses(a, p) === 0;
  const build = (x: LoopBox, prefix: number[]): ColTree[] => {
    const k = prefix.length;
    const passes = [...new Set(tasksOf(x).map(rel).filter((v) => v.length > k && cmpPasses(v.slice(0, k), prefix) === 0).map((v) => v[k] as number))].sort((a, c) => a - c);
    return passes.flatMap((p): ColTree[] => {
      const at = [...prefix, p];
      const kids = x.layers.flat().flatMap((id): ColTree[] => {
        const inner = byBox.get(id);
        if (inner) {
          const sub = build(inner, at);
          return sub.length ? [{ type: 'loop', box: inner, kids: sub }] : [];
        }
        const node = byNode.get(id);
        return node && drafts.get(id)?.tasks.some((t) => same(rel(t), at)) ? [{ type: 'node', node, passes: at }] : [];
      });
      return kids.length ? [{ type: 'pass', box: x, pass: p, kids }] : [];
    });
  };
  const tree = build(b, []);
  const columns: MatrixColumn[] = [];
  const width = (t: ColTree): number => (t.type === 'node' ? 1 : t.kids.reduce((a, k) => a + width(k), 0));
  const depthOf = (t: ColTree): number => (t.type === 'node' ? 1 : 1 + Math.max(0, ...t.kids.map(depthOf)));
  const rowsN = Math.max(1, ...tree.map(depthOf));
  const head: MatrixHead[][] = Array.from({ length: rowsN }, () => []);
  const walk = (t: ColTree, level: number): void => {
    const row = head[level] as MatrixHead[];
    if (t.type === 'node') {
      row.push({ type: 'node', node: t.node, passes: t.passes, span: 1, rows: rowsN - level });
      columns.push({ node: t.node, passes: t.passes });
      return;
    }
    row.push(t.type === 'pass' ? { type: 'pass', box: t.box, pass: t.pass, span: width(t), rows: 1 } : { type: 'loop', box: t.box, span: width(t), rows: 1 });
    for (const k of t.kids) walk(k, level + 1);
  };
  for (const t of tree) walk(t, 0);

  const mine = tasksOf(b);
  const unitsIn = new Set(mine.map((t) => t.n.unit || ''));
  const rowUnits = [...graph.units.filter((u) => unitsIn.has(u)), ...(unitsIn.has('') ? [''] : [])];
  const cellTasks = new Map<string, FlowTask[]>(); // `${column}\0${unit}`
  columns.forEach((c, ci) => {
    for (const t of drafts.get(c.node.id)?.tasks ?? []) if (same(rel(t), c.passes)) push(cellTasks, `${ci}\u0000${t.n.unit || ''}`, t);
  });
  const markOf = (c: MatrixColumn, ts: readonly FlowTask[], unit: string): GraphMark | null => {
    const x = drafts.get(c.node.id) as Draft;
    if (x.type === 'kind') return taskMark(ts, unit);
    const m = flowMarks(ts, d, x.name, ix.calls);
    return unit ? (m.byUnit.get(unit) ?? m.single[0] ?? null) : (m.single[0] ?? null);
  };
  const rows = rowUnits.map((unit): MatrixRow => {
    const cells = columns.map((c, ci) => {
      const ts = cellTasks.get(`${ci}\u0000${unit}`);
      return ts?.length ? markOf(c, ts, unit) : null;
    });
    const passes = new Set(mine.filter((t) => (t.n.unit || '') === unit).map((t) => passesAt(t, d).slice(0, i0 + 1).join('.'))).size;
    return { unit, passes, state: worstOf(cells.filter((m): m is GraphMark => m !== null).map((m) => m.state)), cells };
  });
  return { box: b, columns, head, rows };
}

/** How a loop's units are sorted: as scheduled, most passes first, or the most severe state first. */
export type MatrixSort = 'order' | 'passes' | 'state';

/** `rows` sorted by `by`; a tie keeps the scheduled order. */
export function sortRows(rows: readonly MatrixRow[], by: MatrixSort): MatrixRow[] {
  const ix = new Map(rows.map((r, i) => [r, i]));
  const key = (r: MatrixRow) => (by === 'passes' ? -r.passes : by === 'state' ? -SEVERITY[r.state] : 0);
  return [...rows].sort((a, b) => key(a) - key(b) || (ix.get(a) ?? 0) - (ix.get(b) ?? 0));
}

/**
 * Where a key moves in a grid of marks (`has[r][c]`: a mark there), from (`r`, `c`):
 * left and right to the next mark in the row, up and down to the nearest row with a
 * mark in the column, Home and End to the row's first and last, with Ctrl to the
 * first and last row's, PageUp and PageDown `page` rows. Null when it does not move.
 */
export function gridStep(has: readonly (readonly boolean[])[], r: number, c: number, key: string, ctrl = false, page = 10): [number, number] | null {
  const at = (i: number, j: number) => has[i]?.[j] === true;
  const first = (i: number) => (has[i] ?? []).findIndex(Boolean);
  const last = (i: number) => (has[i] ?? []).lastIndexOf(true);
  const rowWith = (from: number, step: number, col: number): number => {
    for (let i = from; i >= 0 && i < has.length; i += step) if (at(i, col)) return i;
    return -1;
  };
  const near = (i: number): [number, number] | null => {
    // The mark of row i nearest to column c.
    const row = has[i] ?? [];
    let best = -1;
    row.forEach((x, j) => x && (best < 0 || Math.abs(j - c) < Math.abs(best - c)) && (best = j));
    return best < 0 ? null : [i, best];
  };
  switch (key) {
    case 'ArrowRight':
    case 'ArrowLeft': {
      const s = key === 'ArrowRight' ? 1 : -1;
      for (let j = c + s; j >= 0 && j < (has[r]?.length ?? 0); j += s) if (at(r, j)) return [r, j];
      return null;
    }
    case 'ArrowDown':
    case 'ArrowUp': {
      const s = key === 'ArrowDown' ? 1 : -1;
      const i = rowWith(r + s, s, c);
      if (i >= 0) return [i, c];
      for (let k = r + s; k >= 0 && k < has.length; k += s) if (first(k) >= 0) return near(k);
      return null;
    }
    case 'Home': {
      const i = ctrl ? has.findIndex((row) => row.some(Boolean)) : r;
      return i < 0 || first(i) < 0 ? null : [i, first(i)];
    }
    case 'End': {
      let i = r;
      if (ctrl) for (i = has.length - 1; i >= 0 && last(i) < 0; i--);
      return i < 0 || last(i) < 0 ? null : [i, last(i)];
    }
    case 'PageDown':
    case 'PageUp': {
      const s = key === 'PageDown' ? 1 : -1;
      const target = Math.max(0, Math.min(has.length - 1, r + s * page));
      for (let k = target; k !== r; k -= s) if (first(k) >= 0) return near(k);
      return null;
    }
    default:
      return null;
  }
}

// ---- what is selected ----

/**
 * A mark's selection id: its node, the passes of its column in a loop's passes
 * (`|1.2`), and its unit, or its key for a mark without one (`kind:review@7#gamma`).
 */
export const markSel = (node: string, m: Pick<GraphMark, 'unit' | 'key'>, passes: readonly number[] = []): string =>
  `${node}${passes.length ? `|${passes.join('.')}` : ''}#${m.unit || m.key}`;

/** What a selection id names: a mark (with its node, and its column's passes in a loop's passes), a node or a loop box. */
export type Selected =
  | { type: 'mark'; id: string; node: GraphNode; mark: GraphMark; passes: number[] }
  | { type: 'node'; id: string; node: GraphNode }
  | { type: 'box'; id: string; box: LoopBox };

/**
 * What `sel` names in a layer's graph, or, with `matrix`, in a loop's passes (a mark
 * there names its column's passes); null when it names nothing there.
 */
export function selected(g: LayerGraph, matrix: PassMatrix | null, sel: string): Selected | null {
  if (!sel) return null;
  const hash = sel.indexOf('#');
  if (hash < 0) {
    const node = g.nodes.find((n) => n.id === sel);
    if (node) return { type: 'node', id: sel, node };
    const box = g.boxes.find((b) => b.id === sel);
    return box ? { type: 'box', id: sel, box } : null;
  }
  const [nodeId = '', pass] = sel.slice(0, hash).split('|');
  const who = sel.slice(hash + 1);
  const is = (m: GraphMark | null | undefined): m is GraphMark => !!m && (m.unit ? m.unit === who : m.key === who);
  if (pass !== undefined) {
    if (!matrix) return null;
    const ci = matrix.columns.findIndex((c) => c.node.id === nodeId && c.passes.join('.') === pass);
    const col = matrix.columns[ci];
    const mark = matrix.rows.map((r) => r.cells[ci]).find(is);
    return col && mark ? { type: 'mark', id: sel, node: col.node, mark, passes: col.passes } : null;
  }
  const node = g.nodes.find((n) => n.id === nodeId);
  const mark = node ? [...node.units, ...node.single].find(is) : undefined;
  return node && mark ? { type: 'mark', id: sel, node, mark, passes: [] } : null;
}

/** The tasks of a layer's nodes by state, added up. */
export function layerCounts(nodes: readonly Pick<GraphNode, 'counts'>[]): NodeCounts {
  const c: NodeCounts = { total: 0, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0 };
  for (const n of nodes) for (const k of Object.keys(c) as (keyof NodeCounts)[]) c[k] += n.counts[k];
  return c;
}

// ---- marks ----

/** How a node lays out its unit marks: as many columns as units up to 12, then 10, then 20; smaller marks as they grow. */
export function markGrid(units: number): { cols: number; size: number } {
  if (units <= 12) return { cols: Math.max(1, units), size: 12 };
  if (units <= 100) return { cols: 10, size: 10 };
  return { cols: 20, size: 6 };
}

/** Above this many marks, a node shows a bar of its counts and lists its failed marks. */
export const BAR_MARKS = 200;

/** A node shows its marks as a bar of counts. */
export const asBar = (n: Pick<GraphNode, 'units' | 'single'>): boolean => n.units.filter((m) => m !== null).length + n.single.length > BAR_MARKS;

/** A node's bar: each state's share of its marks, in `order`, the states it has only. */
export function barParts(c: NodeCounts, order: readonly TaskState[]): { state: TaskState; n: number; pct: number }[] {
  return order.filter((s) => c[s] > 0).map((s) => ({ state: s, n: c[s], pct: (100 * c[s]) / Math.max(1, c.total) }));
}

/**
 * The node joined to `from` along a drawn edge: a later one (`later`, that waits for
 * it or was created after it) or an earlier one; of several, the one nearest across
 * the flow (`across`), then the first in drawing order. Null when there is none.
 */
export function alongEdge(g: LayerGraph, from: string, dir: 'later' | 'earlier', across: (id: string) => number): string | null {
  const rank = new Map(g.nodes.map((n, i) => [n.id, i]));
  const ids = [...new Set(g.edges.filter((e) => !e.back && (dir === 'later' ? e.from === from : e.to === from)).map((e) => (dir === 'later' ? e.to : e.from)))];
  const at = across(from);
  ids.sort((a, b) => Math.abs(across(a) - at) - Math.abs(across(b) - at) || (rank.get(a) ?? 0) - (rank.get(b) ?? 0));
  return ids[0] ?? null;
}

// ---- the drawing: coordinates and edge lines ----

export interface Size {
  w: number;
  h: number;
}

/** A rectangle in the drawing. */
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A straight stretch of an edge along the flow, from `a` to `b`, `at` across it; an edge bends between two. */
export interface Run {
  a: number;
  b: number;
  at: number;
}

export interface GraphLayout {
  /** The drawing's size, its margin included. */
  w: number;
  h: number;
  /** Every node, stub and loop box, by id. */
  at: Record<string, Rect>;
  /** Every route, with its runs. */
  edges: { from: string; to: string; type: 'after' | 'created'; runs: Run[] }[];
  /** Each loop box's return to its next pass. */
  returns: LoopReturn[];
  down: boolean;
}

/**
 * A loop box's return to its next pass, along the flow (`u`) and across it (`v`): from
 * the far side of its last layer's outermost item (`from`, at `v0`) out to a band
 * past its content (`band`), back along the band, and in to its first layer's
 * outermost item (`to`, at `v1`). Left to right the band is under the nodes; top to
 * bottom, on their right.
 */
export interface LoopReturn {
  box: string;
  from: number;
  v0: number;
  to: number;
  v1: number;
  band: number;
}

/** The spaces of a drawing; left to right unless `down`. */
export interface LayoutSpace {
  /** Between two layers, at the top level and in a loop box. */
  gap: number;
  boxGap: number;
  /** Between two items of a layer, and next to a point an edge passes. */
  sep: number;
  pointSep: number;
  /** A loop box's padding, and the space under its label. */
  pad: number;
  /** The space after a box's content, across the flow: the band its return to the next pass runs in. */
  padEnd: number;
  margin: number;
}

/** The band past a loop box's content that its return to the next pass runs in, and the return's corner radius. */
export const RETURN_BAND = 24;
const RETURN_R = 6;

export const SPACE: Record<'across' | 'down', LayoutSpace> = {
  across: { gap: 56, boxGap: 40, sep: 16, pointSep: 12, pad: 12, padEnd: RETURN_BAND, margin: 16 },
  down: { gap: 40, boxGap: 32, sep: 16, pointSep: 12, pad: 10, padEnd: RETURN_BAND, margin: 16 },
};

/** Tops (across the flow) nearest to `want` that keep the order and each gap: weighted isotonic regression (pool adjacent violators). */
function placeRow(want: readonly number[], gaps: readonly number[], weight: readonly number[]): number[] {
  const off: number[] = [0];
  for (let i = 1; i < want.length; i++) off.push((off[i - 1] as number) + (gaps[i - 1] as number));
  const blocks: { sum: number; w: number; n: number }[] = [];
  want.forEach((v, i) => {
    const w = weight[i] ?? 1;
    blocks.push({ sum: w * (v - (off[i] as number)), w, n: 1 });
    while (blocks.length > 1) {
      const b = blocks[blocks.length - 1] as { sum: number; w: number; n: number };
      const a = blocks[blocks.length - 2] as { sum: number; w: number; n: number };
      if (a.sum / a.w <= b.sum / b.w) break;
      blocks.splice(-2, 2, { sum: a.sum + b.sum, w: a.w + b.w, n: a.n + b.n });
    }
  });
  const out: number[] = [];
  for (const b of blocks) for (let k = 0; k < b.n; k++) out.push(b.sum / b.w + (off[out.length] as number));
  return out;
}

/**
 * Where everything of a layer's graph is drawn, from the sizes of its nodes, its stubs
 * and its loop boxes' labels (`lbl:<box id>`): left to right, or top to bottom when
 * `down`. Each container is laid out inside out, a box being one item of its parent:
 * its layers side by side, an item at the start of its layer; across the flow, each
 * item as near as its order allows to the items it is joined to (sweeps of weighted
 * isotonic regression), so chains run straight. An edge runs along its points and
 * bends only in the gap between two layers; it enters and leaves a box where its
 * point inside is, and never passes a node or a box's label.
 */
export function layoutGraph(g: LayerGraph, sizes: ReadonlyMap<string, Size>, down = false): GraphLayout {
  const S = SPACE[down ? 'down' : 'across'];
  const len = (s: Size) => (down ? s.h : s.w);
  const brd = (s: Size) => (down ? s.w : s.h);
  const boxIds = new Set(g.boxes.map((b) => b.id));
  const label = (box: string): Size => sizes.get(`lbl:${box}`) ?? { w: 0, h: 0 };
  // A box's padding: along the flow, and across it. Its label is in a band at its top: across
  // the flow left to right; along it top to bottom, where a gap under the label lets edges in.
  const padOf = (box: string) =>
    down
      ? { u0: label(box).h + S.pad + S.gap / 2, u1: S.pad, v0: S.pad, v1: S.padEnd, minU: 0, minV: label(box).w + 2 * S.pad }
      : { u0: S.pad, u1: S.pad, v0: label(box).h + S.pad, v1: S.padEnd, minU: label(box).w + 2 * S.pad, minV: 0 };
  const extent = new Map<string, { u: number; v: number }>(); // a box's size, along and across
  const slotSize = (id: string): { u: number; v: number } => {
    if (boxIds.has(id)) return extent.get(id) ?? { u: 0, v: 0 };
    if (isPoint(id)) return { u: 0, v: 0 };
    const s = sizes.get(id) ?? { w: 0, h: 0 };
    return { u: len(s), v: brd(s) };
  };
  interface Local {
    rows: string[][];
    start: number[];
    width: number[];
    top: Map<string, number>;
    u: number;
    v: number;
  }
  const local = new Map<string, Local>();
  const layerIn = new Map<string, Map<string, number>>();
  const depth = (c: string) => (c === '' ? 0 : c.split('.').length);
  const containers = ['', ...g.boxes.map((b) => b.id)].sort((a, b) => depth(b) - depth(a));
  // Where an edge meets a slot, across the flow from the slot's top: a node's middle,
  // a point, or (a box) where the edge's step inside it is.
  const attach = (ri: number, si: number): number => {
    const steps = g.routes[ri]?.steps ?? [];
    const s = steps[si] as RouteStep;
    if (isPoint(s.id)) return 0;
    if (!boxIds.has(s.id)) return slotSize(s.id).v / 2;
    const inner = steps[si - 1]?.in === s.id ? si - 1 : si + 1;
    const step = steps[inner] as RouteStep;
    return padOf(s.id).v0 + (local.get(s.id)?.top.get(step.id) ?? 0) + attach(ri, inner);
  };
  for (const c of containers) {
    const rows = (g.slots[c] ?? []).map((r) => [...r]);
    layerIn.set(c, new Map(rows.flatMap((r, i) => r.map((id) => [id, i] as const))));
    const width = rows.map((r) => Math.max(0, ...r.map((id) => slotSize(id).u)));
    const gap = c === '' ? S.gap : S.boxGap;
    const start: number[] = [];
    width.forEach((_, i) => start.push(i ? (start[i - 1] as number) + (width[i - 1] as number) + gap : 0));
    // The joins inside this container: slot a of layer l to slot b of layer l + 1.
    const links: { a: string; b: string; oa: number; ob: number }[] = [];
    g.routes.forEach((r, ri) =>
      r.steps.forEach((s, si) => {
        const p = r.steps[si - 1];
        if (si && p && p.in === c && s.in === c && layerIn.get(c)?.get(p.id) !== layerIn.get(c)?.get(s.id)) links.push({ a: p.id, b: s.id, oa: attach(ri, si - 1), ob: attach(ri, si) });
      }),
    );
    // Points sit close to each other and to a node, further from a box (its next-pass mark is on its edge).
    const sepOf = (a: string, b: string | undefined) =>
      b === undefined ? 0 : boxIds.has(a) || boxIds.has(b) || !(isPoint(a) || isPoint(b)) ? S.sep : S.pointSep;
    const top = new Map<string, number>();
    for (const r of rows) {
      let v = 0;
      r.forEach((id, i) => {
        top.set(id, v);
        v += slotSize(id).v + sepOf(id, r[i + 1]);
      });
    }
    const place = (r: string[], want: (id: string) => number[]) => {
      const desired = r.map((id) => {
        const xs = want(id);
        return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : (top.get(id) ?? 0);
      });
      const gaps = r.map((id, i) => slotSize(id).v + sepOf(id, r[i + 1]));
      // The nodes first, as if the points between them were fixed in size; then the points, around the nodes.
      const real = r.map((id, i) => (isPoint(id) ? -1 : i)).filter((i) => i >= 0);
      const span = (i: number, j: number) => gaps.slice(i, j).reduce((a, b) => a + b, 0);
      const at = placeRow(
        real.map((i) => desired[i] as number),
        real.map((i, k) => (k + 1 < real.length ? span(i, real[k + 1] as number) : 0)),
        real.map(() => 1),
      );
      real.forEach((i, k) => (desired[i] = at[k] as number));
      placeRow(desired, gaps, r.map((id) => (isPoint(id) ? 1 : 1e6))).forEach((v, i) => top.set(r[i] as string, Math.round(v * 100) / 100));
    };
    // A node lines up with the nodes it is joined to, when it has any on that side, else with the points;
    // a point lines up with whatever it is joined to, so a chain runs straight and a long edge goes round it.
    const near = (id: string, ls: { other: string; at: number }[]) => {
      const real = isPoint(id) ? ls : ls.filter((x) => !isPoint(x.other));
      return (real.length ? real : ls).map((x) => x.at);
    };
    const fromPrev = (id: string) => near(id, links.filter((l) => l.b === id).map((l) => ({ other: l.a, at: (top.get(l.a) ?? 0) + l.oa - l.ob })));
    const fromNext = (id: string) => near(id, links.filter((l) => l.a === id).map((l) => ({ other: l.b, at: (top.get(l.b) ?? 0) + l.ob - l.oa })));
    for (let sweep = 0; sweep < 8; sweep++) {
      const order = rows.map((_, i) => i);
      if (sweep % 2) order.reverse();
      for (const i of order) place(rows[i] as string[], sweep % 2 ? fromNext : fromPrev);
    }
    for (const r of rows) place(r, (id) => [...fromPrev(id), ...fromNext(id)]);
    const lo = top.size ? Math.min(...top.values()) : 0;
    for (const [id, v] of top) top.set(id, v - lo);
    const u = (start[start.length - 1] ?? 0) + (width[width.length - 1] ?? 0);
    const v = Math.max(0, ...rows.flat().map((id) => (top.get(id) ?? 0) + slotSize(id).v));
    local.set(c, { rows, start, width, top, u, v });
    if (c !== '') {
      const p = padOf(c);
      extent.set(c, { u: Math.max(p.u0 + u + p.u1, p.minU), v: Math.max(p.v0 + v + p.v1, p.minV) });
    }
  }

  // Inside out, then outside in: each container's place in the drawing.
  const at: Record<string, Rect> = {};
  const origin = new Map<string, { u: number; v: number }>();
  const rect = (u: number, v: number, s: { u: number; v: number }): Rect => (down ? { x: v, y: u, w: s.v, h: s.u } : { x: u, y: v, w: s.u, h: s.v });
  const put = (c: string, ou: number, ov: number) => {
    origin.set(c, { u: ou, v: ov });
    const l = local.get(c) as Local;
    l.rows.forEach((r, i) =>
      r.forEach((id) => {
        if (isPoint(id)) return;
        const u = ou + (l.start[i] as number);
        const v = ov + (l.top.get(id) ?? 0);
        at[id] = rect(u, v, slotSize(id));
        if (boxIds.has(id)) {
          const p = padOf(id);
          put(id, u + p.u0, v + p.v0);
        }
      }),
    );
  };
  put('', S.margin, S.margin);
  const whole = local.get('') as Local;
  const U = whole.u + 2 * S.margin;
  const V = whole.v + 2 * S.margin;

  // A container's layer l: where it starts and ends along the flow, in the drawing.
  const col = (c: string, l: number): [number, number] => {
    const lc = local.get(c) as Local;
    const o = origin.get(c) ?? { u: 0, v: 0 };
    const c0 = o.u + (lc.start[l] ?? 0);
    return [c0, c0 + (lc.width[l] ?? 0)];
  };
  const layer = (c: string, id: string) => layerIn.get(c)?.get(id) ?? 0;
  const byOf = (s: RouteStep | undefined): string => (s && isPoint(s.id) ? (/\|by:([^|]*)\|/.exec(s.id)?.[1] ?? '') : '');
  const edges = g.routes.map((r, ri) => {
    const vOf = (si: number): number => {
      const s = r.steps[si] as RouteStep;
      const o = origin.get(s.in) ?? { u: 0, v: 0 };
      return o.v + (local.get(s.in)?.top.get(s.id) ?? 0) + attach(ri, si);
    };
    const runs: Run[] = r.steps.map((s, si): Run => {
      const prev = r.steps[si - 1];
      const next = r.steps[si + 1];
      const [c0, c1] = col(s.in, layer(s.in, s.id));
      const v = vOf(si);
      if (si === 0) return { a: c0 + slotSize(s.id).u, b: c1, at: v };
      if (si === r.steps.length - 1) return { a: c0, b: c0, at: v };
      if (isPoint(s.id)) {
        const box = byOf(s);
        // Beside a box: from where it left the box's side, or up to where it goes in.
        if (box && prev?.id === box) return { a: col(box, layer(box, r.steps[si - 2]?.id ?? '') + 1)[0], b: c1, at: v };
        if (box && next?.id === box) {
          const ln = layer(box, r.steps[si + 2]?.id ?? '');
          const gap = ln > 0 ? col(box, ln - 1)[1] : (at[box] ? (down ? at[box].y : at[box].x) : c0) + label(box).h + S.pad;
          return { a: c0, b: gap, at: v };
        }
        return { a: c0, b: c1, at: v };
      }
      const p = padOf(s.id);
      const inner = local.get(s.id) as Local;
      // Out of a box: at its far side, or through its side after the layer it leaves.
      if (prev?.in === s.id) {
        if (byOf(next) === s.id) {
          const u = col(s.id, layer(s.id, prev.id) + 1)[0];
          return { a: u, b: u, at: vOf(si + 1) };
        }
        return { a: c0 + p.u0 + inner.u, b: c1, at: v };
      }
      // Into a box: at its near side, or through its side before the layer it goes to.
      if (byOf(prev) === s.id) {
        const u = col(s.id, layer(s.id, next?.id ?? ''))[0];
        return { a: u, b: u, at: vOf(si + 1) };
      }
      return { a: c0, b: c0 + p.u0, at: v };
    });
    return { from: r.from, to: r.to, type: r.type, runs };
  });
  // Each box's return to its next pass: from its last layer's item that reaches furthest
  // across the flow, along the band past the content, to its first layer's.
  const returns = g.boxes.flatMap((b): LoopReturn[] => {
    const l = local.get(b.id);
    const o = origin.get(b.id);
    if (!l || !o) return [];
    const outer = (row: readonly string[] | undefined) => {
      const ids = (row ?? []).filter((id) => !isPoint(id));
      let best: { u: number; v: number } | null = null;
      for (const id of ids) {
        const s = slotSize(id);
        const v = (l.top.get(id) ?? 0) + s.v;
        if (!best || v > best.v) best = { u: s.u, v };
      }
      return best;
    };
    const real = l.rows.map((r, i) => (r.some((id) => !isPoint(id)) ? i : -1)).filter((i) => i >= 0);
    const fi = real[0] ?? 0;
    const li = real[real.length - 1] ?? 0;
    const last = outer(l.rows[li]);
    const first = outer(l.rows[fi]);
    if (!last || !first) return [];
    // An item's middle along the flow, as wide as its layer; one layer: either side of its middle.
    let from = o.u + (l.start[li] ?? 0) + (l.width[li] ?? 0) / 2;
    let to = o.u + (l.start[fi] ?? 0) + (l.width[fi] ?? 0) / 2;
    if (from - to < 4 * RETURN_R) {
      const d = Math.max(2 * RETURN_R, Math.min(28, Math.min(last.u, first.u) / 4));
      from = (from + to) / 2 + d;
      to = from - 2 * d;
    }
    return [{ box: b.id, from, v0: o.v + last.v, to, v1: o.v + first.v, band: o.v + l.v + RETURN_BAND / 2 }];
  });
  return { w: down ? V : U, h: down ? U : V, at, edges, returns, down };
}

/**
 * A loop box's return as an SVG path: out from its last layer to the band, back along
 * it with rounded corners, and in to its first layer, stopping `gap` short of each item.
 */
export function returnPath(r: LoopReturn, down = false, gap = 3): string {
  const r2 = (n: number) => Math.round(n * 2) / 2;
  const pt = (u: number, v: number) => (down ? `${r2(v)},${r2(u)}` : `${r2(u)},${r2(v)}`);
  const k = Math.max(0, Math.min(RETURN_R, (r.from - r.to) / 2, r.band - r.v0 - gap, r.band - r.v1 - gap));
  return [
    `M${pt(r.from, r.v0 + gap)}`,
    `L${pt(r.from, r.band - k)}`,
    `Q${pt(r.from, r.band)} ${pt(r.from - k, r.band)}`,
    `L${pt(r.to + k, r.band)}`,
    `Q${pt(r.to, r.band)} ${pt(r.to, r.band - k)}`,
    `L${pt(r.to, r.v1 + gap)}`,
  ].join(' ');
}

/** An edge's line as an SVG path: its runs, joined by a curve in each gap where it bends. */
export function edgePath(runs: readonly Run[], down = false): string {
  const r2 = (n: number) => Math.round(n * 2) / 2;
  const pt = (u: number, v: number) => (down ? `${r2(v)},${r2(u)}` : `${r2(u)},${r2(v)}`);
  const first = runs[0];
  if (!first) return '';
  let d = `M${pt(first.a, first.at)}`;
  runs.forEach((r, i) => {
    if (r.b !== r.a) d += ` L${pt(r.b, r.at)}`;
    const next = runs[i + 1];
    if (!next) return;
    if (Math.abs(next.at - r.at) < 0.5) {
      if (next.a !== r.b) d += ` L${pt(next.a, next.at)}`;
      return;
    }
    const m = (r.b + next.a) / 2;
    d += ` C${pt(m, r.at)} ${pt(m, next.at)} ${pt(next.a, next.at)}`;
  });
  return d;
}


/** A view of the graph: its scale and where its top left corner sits in the frame. */
export interface View {
  k: number;
  x: number;
  y: number;
}

/**
 * The frame's height and the view that shows the whole graph: scaled down to fit the
 * frame's width and at most `maxH` of height, never scaled up, and centred.
 */
export function fitView(graphW: number, graphH: number, frameW: number, maxH: number): View & { h: number } {
  if (graphW <= 0 || graphH <= 0 || frameW <= 0) return { k: 1, x: 0, y: 0, h: Math.max(0, graphH) };
  const byWidth = Math.min(1, frameW / graphW);
  const h = Math.min(graphH * byWidth, maxH);
  const k = Math.min(byWidth, h / graphH);
  return { k, x: (frameW - graphW * k) / 2, y: (h - graphH * k) / 2, h };
}

/** `v` scaled by `factor` about the point (`cx`, `cy`) of the frame, within `min` and `max`. */
export function zoomView(v: View, factor: number, cx: number, cy: number, min: number, max: number): View {
  const k = Math.min(max, Math.max(min, v.k * factor));
  const r = k / v.k;
  return { k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r };
}

// --- KPIs -----------------------------------------------------------------------

/**
 * The run's figures, from the journal. Only tries that ran count: a task
 * refused before launch (`invalid_input`) has a row but is not a try, not an
 * agent session and not a failed attempt; tasks are counted by `outcomeCounts`.
 */
export interface Kpis {
  /** Tries that ran. */
  attempts: number;
  python: number;
  /** Agent sessions: tries an agent ran. */
  launches: number;
  /** Tries that ran and failed. */
  bad: number;
  launchWall: number;
  pythonWall: number;
  /** Tries after a task's first, and the tasks they belong to. */
  retries: number;
  retriedTasks: number;
  /** The keys of the tasks that were retried / had fix-ups (to open one directly when it is the only one). */
  retriedKeys: string[];
  fixupKeys: string[];
  /** Fix-ups (sessions resumed with check errors), and the tasks that had any. */
  fixups: number;
  fixupTasks: number;
  /** Model switches after a rate limit, and the tasks that switched. */
  switches: number;
  switchTasks: number;
}

export function kpis(journal: readonly JournalRow[]): Kpis {
  const ran = journal.filter(isLaunched);
  const py = ran.filter(isPython);
  const llm = ran.filter((e) => !isPython(e));
  const wall = (xs: readonly JournalRow[]) => xs.reduce((a, e) => a + (e.wall_s || 0), 0);
  const keys = (xs: readonly JournalRow[]) => [...new Set(xs.map((e) => e.key))];
  const tasks = (xs: readonly JournalRow[]) => keys(xs).length;
  const retried = ran.filter((e) => (e.attempt ?? 0) > 0);
  const fixed = ran.filter((e) => (e.rounds || 1) > 1);
  const switched = ran.filter((e) => (e.hops || []).length > 1);
  return {
    attempts: ran.length,
    python: py.length,
    launches: llm.length,
    bad: ran.filter((e) => !e.ok).length,
    launchWall: wall(llm),
    pythonWall: wall(py),
    retries: retried.length,
    retriedTasks: tasks(retried),
    retriedKeys: keys(retried),
    fixupKeys: keys(fixed),
    fixups: fixed.reduce((a, e) => a + (e.rounds || 1) - 1, 0),
    fixupTasks: tasks(fixed),
    switches: switched.reduce((a, e) => a + (e.hops || []).length - 1, 0),
    switchTasks: tasks(switched),
  };
}

// --- timeline -------------------------------------------------------------------

/** Finished tasks older than this before the newest are left out. */
export const TIMELINE_WINDOW_MS = 6 * 3600e3;
const STEP_MS = 60e3;

/** Something running now, as the timeline draws it. */
export interface LiveBar {
  kind: string;
  cls: 'llm' | 'py';
  /** Epoch ms it started. */
  t0: number;
}

export interface TimelineBar {
  /** `py`, `llm`, `bad` (ran and failed), `idle` (a task that never started) for a finished row; `run` for a running one. */
  cls: 'py' | 'llm' | 'bad' | 'idle' | 'run';
  start: number;
  end: number;
  live: boolean;
  /** Which of its lane's stacked tracks it is drawn on: overlapping bars (a retry beside its failed try) get their own. */
  track: number;
  row?: JournalRow;
}

export interface TimelineLane {
  name: string;
  /** Any of its bars is an agent launch. */
  llm: boolean;
  bars: TimelineBar[];
  /** How many tracks its bars are stacked on (at least 1). */
  tracks: number;
}

export interface Timeline {
  t0: number;
  span: number;
  lanes: TimelineLane[];
  /** Finished tasks left out of the window. */
  hidden: number;
  live: boolean;
}

interface Placed extends Omit<TimelineBar, 'track'> {
  lane: string;
  liveCls?: 'llm' | 'py';
}

/** Every finished task as a bar on its kind's lane, running ones growing to `now`. Null when there is nothing to draw. */
export function timeline(journal: readonly JournalRow[], live: readonly LiveBar[], now: number): Timeline | null {
  const bars: Placed[] = [];
  for (const e of journal) {
    if (!e.ts) continue;
    const end = Date.parse(e.ts);
    if (Number.isNaN(end)) continue;
    const cls = !isLaunched(e) ? 'idle' : !e.ok ? 'bad' : isPython(e) ? 'py' : 'llm';
    bars.push({ lane: e.kind || '?', cls, start: end - (e.wall_s || 0) * 1000, end, live: false, row: e });
  }
  if (!bars.length && !live.length) return null;
  for (const a of live) bars.push({ lane: a.kind, cls: 'run', start: a.t0, end: now, live: true, liveCls: a.cls });
  const newest = Math.max(...bars.filter((x) => !x.live).map((x) => x.end), ...live.map((a) => a.t0));
  const vis = bars.filter((x) => x.end >= newest - TIMELINE_WINDOW_MS);
  const t0 = Math.min(...vis.map((x) => x.start));
  const t1 = live.length ? t0 + Math.ceil((now - t0 + 20e3) / STEP_MS) * STEP_MS : newest;
  const names: string[] = [];
  for (const x of [...vis].sort((a, b) => a.start - b.start)) if (!names.includes(x.lane)) names.push(x.lane);
  const lanes = names.map((name) => {
    const mine = vis.filter((x) => x.lane === name).sort((a, b) => a.start - b.start);
    // Each bar on the first track whose last bar has ended: overlapping bars do not hide each other.
    const ends: number[] = [];
    const bars = mine.map(({ cls, start, end, live: isLive, row }): TimelineBar => {
      let track = ends.findIndex((e) => e <= start);
      if (track < 0) track = ends.push(end) - 1;
      else ends[track] = end;
      return row ? { cls, start, end, live: isLive, track, row } : { cls, start, end, live: isLive, track };
    });
    return { name, llm: mine.some((x) => x.cls === 'llm' || x.liveCls === 'llm'), bars, tracks: Math.max(1, ends.length) };
  });
  return { t0, span: Math.max(1, t1 - t0), lanes, hidden: bars.length - vis.length, live: live.length > 0 };
}

/** A bar's left edge and width, in percent of the span; a live bar grows to `now`. */
export function barBox(b: TimelineBar, tl: Pick<Timeline, 't0' | 'span'>, now: number): { left: number; width: number } {
  const left = ((b.start - tl.t0) / tl.span) * 100;
  const end = b.live ? now : b.end;
  const w = ((end - b.start) / tl.span) * 100;
  return { left, width: Math.max(0.4, b.live ? Math.min(100 - left, w) : w) };
}
