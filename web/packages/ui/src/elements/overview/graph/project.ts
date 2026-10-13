// The pipeline graph, by layer: the plan projected onto one layer of its flow.
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
import { isPython, type FlowCallNode, type Plan, type PlanNode, type TaskState } from '@contraagent/api';
import { orderRows, push, rankLayers, isPoint } from './arrange.js';
import { boxChain, cmpPasses, indexOf, instanceOf, loopsAt, passesAt, placeOf, shortName, startsWith, type FlowIndex, type FlowTask } from './flow-index.js';
import { worstOf, worstState } from './states.js';
import {
  LOOP_SEGMENT,
  type EdgeRoute,
  type GraphEdge,
  type GraphMark,
  type GraphNode,
  type LayerGraph,
  type LayerOrder,
  type LoopBox,
  type NodeCounts,
  type RouteStep,
} from './types.js';

/** Who runs a kind node's tasks: a coding agent, Python, or both (`mixed`). */
function executorOf(ns: readonly PlanNode[]): 'agent' | 'python' | 'mixed' {
  const py = ns.filter(isPython).length;
  return py === 0 ? 'agent' : py === ns.length ? 'python' : 'mixed';
}

const CALL_STATE: Record<FlowCallNode['state'], TaskState> = { running: 'running', returned: 'done', raised: 'failed', closed: 'failed' };

/** A flow call stopped with an error: it raised, or it was closed. */
const callFailed = (c: FlowCallNode | undefined): c is FlowCallNode => c?.state === 'raised' || c?.state === 'closed';

export function taskMark(ts: readonly FlowTask[], unit: string): GraphMark {
  const ns = ts.map((t) => t.n);
  const key = (ns.find((n) => n.state === 'running') ?? ns[ns.length - 1] ?? { key: '' }).key;
  return { key, unit, state: worstState(ns), count: ns.length, keys: ns.map((n) => n.key) };
}

export interface Marks {
  byUnit: Map<string, GraphMark>;
  single: GraphMark[];
  /** A function node's flow calls, and those that raised or were closed. */
  calls?: number;
  errors?: number;
}

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
export function flowMarks(ts: readonly FlowTask[], d: number, name: string, calls: Map<string, FlowCallNode> | null): Marks {
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

export interface Draft {
  id: string;
  type: 'kind' | 'flow';
  name: string;
  loops: number[];
  tasks: FlowTask[];
}

export interface Projection {
  graph: LayerGraph;
  drafts: Map<string, Draft>;
  ix: FlowIndex;
}

export function project(plan: Plan, path: readonly string[], prev?: LayerOrder, down = false): Projection {
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
