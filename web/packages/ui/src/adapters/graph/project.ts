// The pipeline graph, by layer: the plan projected onto one layer of its flow.
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
// The drawing's order is `arrange` (@contraagent/elements): a loop box is a
// cluster, an edge back to a loop's next pass does not set the layers.
import { isPython, type FlowCallNode, type Plan, type PlanNode, type TaskState, type TimeBoxRecord } from '@contraagent/api';
import type { Arrangement, EdgeStyle, GraphShape } from '@contraagent/elements/graph';
import { boxChain, cmpPasses, indexOf, instanceOf, loopsAt, passesAt, placeOf, push, shortName, startsWith, type FlowIndex, type FlowTask } from './flow-index.js';
import { worstOf, worstState } from './states.js';
import { LOOP_SEGMENT, type GraphNode, type LayerGraph, type LayerMark, type LayerModel, type LoopBox, type NodeCounts } from './types.js';

/** Who runs a kind node's tasks: a coding agent, Python, or both (`mixed`). */
function executorOf(ns: readonly PlanNode[]): 'agent' | 'python' | 'mixed' {
  const py = ns.filter(isPython).length;
  return py === 0 ? 'agent' : py === ns.length ? 'python' : 'mixed';
}

const CALL_STATE: Record<FlowCallNode['state'], TaskState> = { running: 'running', returned: 'done', raised: 'failed', closed: 'failed' };

/** A flow call stopped with an error: it raised, or it was closed. */
const callFailed = (c: FlowCallNode | undefined): c is FlowCallNode => c?.state === 'raised' || c?.state === 'closed';

export function taskMark(ts: readonly FlowTask[], unit: string): LayerMark {
  const ns = ts.map((t) => t.n);
  const key = (ns.find((n) => n.state === 'running') ?? ns[ns.length - 1] ?? { key: '' }).key;
  return { key, unit, state: worstState(ns), count: ns.length, keys: ns.map((n) => n.key) };
}

export interface Marks {
  byUnit: Map<string, LayerMark>;
  single: LayerMark[];
  /** A function node's flow calls, and those that raised or were closed. */
  calls?: number;
  errors?: number;
  /** A function node's first own flow call with a deadline of its own (`time_box`), else null. */
  timeBox?: TimeBoxRecord | null;
}

/** A kind node's marks: one per unit, and one per task without a unit. */
function kindMarks(ts: readonly FlowTask[]): Marks {
  const byUnit = new Map<string, FlowTask[]>();
  const single: LayerMark[] = [];
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
export function flowMarks(ts: readonly FlowTask[], d: number, name: string, calls: Map<string, FlowCallNode> | null): Marks {
  const markOf = (xs: readonly Instance[], unit: string): LayerMark => {
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
    const mark: LayerMark = { key: last?.id ?? '', unit, state: worstOf(states), count: keys.length, keys, flow: name, counts: taskCounts(tasks) };
    const box = last?.own ? calls?.get(last.id)?.time_box : null;
    const deadlineAt = box ? deadlineOf(box) : '';
    const withBox = deadlineAt ? { ...mark, deadlineAt } : mark;
    return failed ? { ...withBox, error: failed.error ?? '' } : withBox;
  };
  const byUnit = new Map<string, Instance[]>();
  const single: LayerMark[] = [];
  const xs = instances(ts, d, calls);
  for (const x of xs) {
    if (x.unit) push(byUnit, x.unit, x);
    else single.push(markOf([x], ''));
  }
  const errors = calls ? xs.filter((x) => x.own && callFailed(calls.get(x.id))).length : 0;
  const timeBox = xs.map((x) => (x.own ? calls?.get(x.id)?.time_box : null)).find((b) => b) ?? null;
  return { byUnit: new Map([...byUnit].map(([u, ys]) => [u, markOf(ys, u)])), single, calls: xs.length, errors, timeBox };
}

/** When a flow call's own deadline falls: its start plus `deadline_s` (UTC ISO 8601); '' when its start is not known. */
export function deadlineOf(box: TimeBoxRecord): string {
  const t = Date.parse(box.started_at);
  return Number.isNaN(t) ? '' : new Date(t + box.deadline_s * 1000).toISOString();
}

/** Tasks by state. */
function taskCounts(ts: readonly FlowTask[]): NodeCounts {
  const c: NodeCounts = { total: ts.length, done: 0, partial: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0 };
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
const withPasses = (m: LayerMark, n: number | undefined): LayerMark => (n && n > 1 ? { ...m, passes: n } : m);

export interface Draft {
  id: string;
  type: 'kind' | 'flow';
  name: string;
  loops: number[];
  tasks: FlowTask[];
}

export interface Projection {
  model: LayerModel;
  drafts: Map<string, Draft>;
  ix: FlowIndex;
}

/** The layer `path` of the plan, as the plan has it: its nodes, loop boxes, edges and stubs, not yet arranged. */
export function project(plan: Plan, path: readonly string[]): Projection {
  const ix = indexOf(plan);
  return projectTasks(ix, path, ix.tasks.filter((t) => startsWith(t.path, path)));
}

/**
 * The layer `path` of the tasks `inside` (each with that prefix): its nodes, loop boxes,
 * edges and stubs, as `project` has them. A function drawn open (`compound.ts`) is the
 * layer of the tasks of its node alone.
 */
export function projectTasks(ix: FlowIndex, path: readonly string[], inside: readonly FlowTask[]): Projection {
  const d = path.length;
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

  const boxes: LoopBox[] = [...boxParent.keys()].map((id) => {
    const spread = new Map<number, number>();
    for (const [u, ran] of boxRan.get(id) ?? []) if (u) spread.set(ran.size, (spread.get(ran.size) ?? 0) + 1);
    return {
      id,
      local: id,
      layer: [...path],
      loop: Number(id.slice(LOOP_SEGMENT.length).split('.').pop()),
      file: inside[0]?.frames[d - 1]?.file ?? '',
      parent: boxParent.get(id) ?? null,
      passes: boxLast.get(id) ?? 1,
      spread: [...spread].sort((a, b) => a[0] - b[0]),
      layers: [],
    };
  });

  const nodeOf = (x: Draft): GraphNode => {
    const m = marks.get(x.id) as Marks;
    const hasUnits = m.byUnit.size > 0;
    return {
      id: x.id,
      type: x.type,
      name: x.name,
      label: x.type === 'kind' ? (ix.labels.get(x.name) ?? x.name) : shortName(x.name),
      layer: [...path],
      kinds: [...new Set(x.tasks.map((t) => t.n.kind))],
      executor: x.type === 'flow' ? null : executorOf(x.tasks.map((t) => t.n)),
      box: boxOf.get(x.id) ?? null,
      units: hasUnits ? units.map((u) => m.byUnit.get(u) ?? null) : [],
      single: m.single,
      inOrder: inOrder.has(x.id),
      counts: taskCounts(shownOf.get(x.id) ?? []),
      calls: m.calls ?? 0,
      errors: m.errors ?? 0,
      timeBox: m.timeBox ?? null,
    };
  };
  return {
    model: {
      path: [...path],
      nodes: [...drafts.values()].map(nodeOf),
      boxes,
      fns: [],
      edges: all.map((e) => ({ from: e.from, to: e.to, tasks: e.tasks.size, type: e.type, samePass: e.samePass, back: false })),
      stubs: stubList.map((s) => ({ id: s.id, label: s.label, to: s.to, tasks: s.tasks.size, type: s.type })),
      units,
    },
    drafts,
    ix,
  };
}

/** How an edge of the layer is drawn: an `after` edge solid, a `created` one dashed. */
export const edgeStyle = (type: 'after' | 'created'): EdgeStyle => (type === 'after' ? 'solid' : 'dashed');

/** What `arrange` reads of a layer: its nodes in their loop boxes, the boxes (each a loop: it cycles), and the links. */
export function shapeOf(m: LayerModel): GraphShape {
  return {
    nodes: m.nodes.map((n) => ({ id: n.id, cluster: n.box })),
    clusters: [
      ...m.boxes.map((b) => ({ id: b.id, parent: b.parent, cycle: true })),
      ...m.fns.map((f) => ({ id: f.id, parent: f.parent, cycle: false })),
    ],
    edges: m.edges.map((e) => ({ from: e.from, to: e.to, style: edgeStyle(e.type), ranks: e.samePass })),
    stubs: m.stubs.map((s) => ({ id: s.id, to: s.to, style: edgeStyle(s.type) })),
  };
}

/** The layer arranged: its nodes in drawing order, each loop box with its layers, the edges that go back marked. */
export function arranged(m: LayerModel, a: Arrangement): LayerGraph {
  const nodes = new Map(m.nodes.map((n) => [n.id, n]));
  const layersOf = new Map(a.clusters.map((c) => [c.id, c.layers]));
  return {
    ...a,
    path: m.path,
    nodes: a.drawn.map((id) => nodes.get(id) as GraphNode),
    boxes: m.boxes.map((b) => ({ ...b, layers: layersOf.get(b.id) ?? [] })),
    fns: m.fns,
    edges: m.edges.map((e, i) => ({ ...e, back: a.back[i] ?? false })),
    stubs: m.stubs,
    units: m.units,
  };
}
