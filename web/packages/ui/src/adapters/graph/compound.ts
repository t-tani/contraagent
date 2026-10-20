// The pipeline graph as one drawing of several layers: the layer shown, with some of
// its functions drawn open, each a cluster that holds its own layer, recursively (a
// compound graph, laid out by `arrange` as a layered drawing of nested clusters).
//
// Which functions are open is a degree-of-interest choice (Furnas 1986, "Generalized
// fisheye views"; Card & Nation 2002, "Degree-of-interest trees"): each function node
// has an a-priori interest (its tasks, and whether any failed, runs or did not run,
// and whether the selection is in it) less its distance from the layer shown, and the
// most interesting open first while the drawing stays within a budget of nodes. The
// reader's own opens and closes outrank it.
//
// A function whose layer holds only it as a function (and kinds beside it) opens into
// the cluster of the function around it rather than into a cluster of its own, which
// is then named by the path of both ("topic_work › write_batches"): a chain of single
// calls is one box, as an editor's compact folders show a chain of single folders.
import { isPython, type FlowCallNode, type Plan } from '@contraagent/api';
import { cmpPasses, indexOf, loopsAt, passesAt, placeOf, push, shortName, startsWith, type FlowIndex, type FlowTask } from './flow-index.js';
import { arrange, extentOf } from '@contraagent/elements/graph';
import { projectTasks, shapeOf, stronger, type Projection } from './project.js';
import type { EdgeType, FlowBox, GraphEdge, GraphNode, GraphStub, LayerModel, LoopBox, NodeCounts } from './types.js';

/** Between a function's place and the id of an item drawn inside it. */
export const IN_SEP = '::';
/** The prefix of a function drawn open: `fx::<place>`. */
export const FLOW_BOX = 'fx::';

/** Where a function node is, across every layer: its layer and its id there (`<layer>/<id>`). */
export const placeKey = (layer: readonly string[], id: string): string => `${layer.join('/')}/${id}`;

/** What a function's place holds, for choosing what to open. */
export interface PlaceStats {
  key: string;
  /** The layer it is in, and its node's id there. */
  layer: string[];
  id: string;
  name: string;
  /** Levels below the layer shown (0: a node of that layer). */
  depth: number;
  /** The loops of its layer's function around it, outermost first, and that function's file. */
  loops: number[];
  file: string;
  /** Its tasks by state. */
  counts: NodeCounts;
  tasks: number;
  /** Its agent tasks. */
  agent: number;
  failed: number;
  running: number;
  /** Tasks not done that will not run on their own: not started, and (once the run is over) pending. */
  stuck: number;
  /** A flow call in it stopped with an error. */
  errors: boolean;
  /** The ids of the nodes its own layer would draw. */
  kids: Set<string>;
  /** The places of the functions in its layer. */
  fns: Set<string>;
  /** The place it is in (null: a node of the layer shown). */
  parent: string | null;
}

export interface OpenChoice {
  /** Places the reader opened and closed: they outrank the choice. */
  open?: ReadonlySet<string>;
  closed?: ReadonlySet<string>;
  /** Open every function (bar `closed`). */
  all?: boolean;
  /** The most nodes the drawing holds before it stops opening functions on its own. */
  budget: number;
  /** Places of interest: the selection's, and those around it (`towardOf`); with `sel`, those of that selection. */
  toward?: ReadonlySet<string>;
  sel?: string;
  /** The run is live: a pending task is waiting, not stuck. */
  live?: boolean;
  /** The most layers the drawing may span (left to right, or top to bottom) before it closes again what it opened on its own. */
  maxSpan?: number;
}

/** A failed or closed flow call (`raised`, `closed`). */
const stopped = (c: FlowCallNode | undefined) => c?.state === 'raised' || c?.state === 'closed';

/** Every function place under the layer `focus`, with what it holds. */
export function placeStats(ix: FlowIndex, focus: readonly string[], live = false): Map<string, PlaceStats> {
  const d0 = focus.length;
  const out = new Map<string, PlaceStats>();
  const raised = new Set<string>();
  if (ix.calls) for (const c of ix.calls.values()) if (stopped(c)) raised.add(c.id);
  for (const t of ix.tasks) {
    if (!startsWith(t.path, focus)) continue;
    const st = t.n.state;
    const callErr = !!t.call && [...raised].some((r) => t.call === r || t.call.startsWith(`${r}.`));
    let parent: string | null = null;
    for (let d = d0; d < t.path.length; d++) {
      const p = placeOf(t, d);
      const layer = t.path.slice(0, d);
      const key = placeKey(layer, p.id);
      let s = out.get(key);
      if (!s) {
        const counts: NodeCounts = { total: 0, done: 0, partial: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, cancelled: 0 };
        const file = d > 0 ? (t.frames[d - 1]?.file ?? '') : '';
        s = { key, layer, id: p.id, name: p.name, depth: d - d0, loops: p.loops, file, counts, tasks: 0, agent: 0, failed: 0, running: 0, stuck: 0, errors: false, kids: new Set(), fns: new Set(), parent };
        out.set(key, s);
      }
      s.tasks += 1;
      s.counts.total += 1;
      s.counts[st] += 1;
      if (!isPython(t.n)) s.agent += 1;
      if (st === 'failed') s.failed += 1;
      else if (st === 'running') s.running += 1;
      else if (st === 'blocked' || (st === 'pending' && !live)) s.stuck += 1;
      if (callErr) s.errors = true;
      const next = placeOf(t, d + 1);
      s.kids.add(next.id);
      if (next.type === 'flow') s.fns.add(placeKey(t.path.slice(0, d + 1), next.id));
      parent = key;
    }
  }
  return out;
}

/** A place's interest, before its distance: more tasks, and a failure, running work or a selection in it, more. */
export function interest(s: PlaceStats, toward: ReadonlySet<string> = new Set()): number {
  return Math.log2(1 + s.tasks) + (s.failed || s.errors ? 4 : 0) + (s.running ? 3 : 0) + (s.stuck ? 1.5 : 0) + (toward.has(s.key) ? 6 : 0);
}

/**
 * Whether a place is worth opening on its own: it holds agent tasks, a failure, running
 * work, work that will not run, or the selection. A place of finished Python steps says
 * all it has in its node's count. (Furnas's threshold: only what is interesting enough is shown.)
 */
export const notable = (s: PlaceStats, toward: ReadonlySet<string> = new Set()): boolean =>
  s.agent > 0 || s.failed > 0 || s.errors || s.running > 0 || s.stuck > 0 || toward.has(s.key);

/** Its degree of interest: its interest less its distance from the layer shown. */
export const doi = (s: PlaceStats, toward?: ReadonlySet<string>): number => interest(s, toward) - 1.5 * s.depth;

/**
 * The places to draw open: the reader's own, then, while the drawing stays within
 * `budget` nodes, the rest in order of their degree of interest (a place's own
 * functions become candidates once it is open), those `notable` only. A place opens only
 * inside open places.
 */
export function chooseOpen(stats: ReadonlyMap<string, PlaceStats>, rootIds: number, c: OpenChoice): { open: Set<string>; auto: string[] } {
  const open = new Set<string>();
  const auto: string[] = [];
  const closed = c.closed ?? new Set<string>();
  const forced = c.open ?? new Set<string>();
  let visible = rootIds;
  const cands = new Set([...stats.values()].filter((s) => s.parent === null).map((s) => s.key));
  while (cands.size) {
    let best: PlaceStats | null = null;
    let bestScore = -Infinity;
    for (const k of cands) {
      const s = stats.get(k) as PlaceStats;
      const score = forced.has(k) ? Infinity : doi(s, c.toward);
      if (score > bestScore) {
        best = s;
        bestScore = score;
      }
    }
    if (!best) break;
    cands.delete(best.key);
    if (closed.has(best.key)) continue;
    const cost = best.kids.size - 1;
    if (!forced.has(best.key) && !c.all && (visible + cost > c.budget || !notable(best, c.toward))) continue;
    open.add(best.key);
    if (!forced.has(best.key)) auto.push(best.key);
    visible += cost;
    for (const f of best.fns) cands.add(f);
  }
  return { open, auto };
}

/** The places of interest for a selection: the place it is in or names, and every place around it. */
export function towardOf(sel: string, stats: ReadonlyMap<string, PlaceStats>): Set<string> {
  const out = new Set<string>();
  let key: string | null = null;
  if (sel.startsWith(FLOW_BOX)) key = sel.slice(FLOW_BOX.length).split('#')[0] ?? null;
  else if (sel.includes(IN_SEP)) key = sel.slice(0, sel.lastIndexOf(IN_SEP));
  for (let k = key; k !== null && stats.has(k); k = stats.get(k)?.parent ?? null) out.add(k);
  return out;
}

export interface Compound {
  model: LayerModel;
  /** The places drawn open. */
  open: Set<string>;
  stats: Map<string, PlaceStats>;
}

/**
 * The layer `focus` of the plan with the places `chooseOpen` picks drawn open: a node
 * per kind and per closed function, a cluster per open function (or one per chain of
 * single functions), the loop boxes of every layer drawn, and the edges between the
 * nodes the tasks are drawn in, whatever layer they are in.
 */
export function compound(plan: Plan, focus: readonly string[], choice: OpenChoice): Compound {
  const ix = indexOf(plan);
  const d0 = focus.length;
  const inside = ix.tasks.filter((t) => startsWith(t.path, focus));
  const stats = placeStats(ix, focus, choice.live);
  const rootIds = new Set(inside.map((t) => placeOf(t, d0).id)).size;
  const toward = choice.sel ? towardOf(choice.sel, stats) : choice.toward;
  const { open, auto } = chooseOpen(stats, rootIds, { ...choice, toward });
  let model = assemble(ix, focus, inside, stats, open);
  // Too long a drawing: close again what was opened last on its own (the least interesting,
  // and inside what was opened before it), until it spans `maxSpan` layers.
  const span = (m: LayerModel) => extentOf(arrange(shapeOf(m))).span;
  if (choice.maxSpan && !choice.all) {
    while (auto.length && span(model) > choice.maxSpan) {
      open.delete(auto.pop() as string);
      model = assemble(ix, focus, inside, stats, open);
    }
  }
  return { model, open, stats };
}

/** The layer `focus` with the places `open` drawn open (`compound`). */
function assemble(ix: FlowIndex, focus: readonly string[], inside: readonly FlowTask[], stats: ReadonlyMap<string, PlaceStats>, open: ReadonlySet<string>): LayerModel {
  const d0 = focus.length;
  // Each task's container (the open place it is drawn in, '' for the layer shown) and its
  // depth; and each container's tasks: every task under it, those of the places open in it too.
  const containerOf = new Map<string, { key: string; depth: number }>();
  const byContainer = new Map<string, FlowTask[]>([['', []]]);
  for (const t of inside) {
    let d = d0;
    let key = '';
    byContainer.get('')?.push(t);
    while (d < t.path.length) {
      const k = placeKey(t.path.slice(0, d), placeOf(t, d).id);
      if (!open.has(k)) break;
      key = k;
      push(byContainer, k, t);
      d++;
    }
    containerOf.set(t.n.key, { key, depth: d });
  }

  // Each container's layer, projected from its tasks.
  const proj = new Map<string, Projection>();
  const layerOfC = new Map<string, string[]>();
  for (const [k, ts] of byContainer) {
    const s = stats.get(k);
    const layer = s ? [...s.layer, s.name] : [...focus];
    layerOfC.set(k, layer);
    proj.set(k, projectTasks(ix, layer, ts));
  }
  const prefix = (k: string, id: string) => (k === '' ? id : `${k}${IN_SEP}${id}`);

  // Where an open place's content goes: into the cluster of the place around it when that place's
  // layer holds it as its only function, outside any loop box; else into a cluster of its own.
  const ownNode = (k: string): GraphNode | undefined => {
    const s = stats.get(k);
    const p = s ? proj.get(s.parent ?? '') : undefined;
    return p?.model.nodes.find((n) => n.id === s?.id);
  };
  const merges = (k: string): boolean => {
    const s = stats.get(k);
    if (!s || s.parent === null) return false;
    const p = proj.get(s.parent);
    if (!p) return false;
    const fns = p.model.nodes.filter((n) => n.type === 'flow');
    return fns.length === 1 && fns[0]?.id === s.id && !fns[0]?.box;
  };
  const clusterOf = (k: string): string => (merges(k) ? clusterOf((stats.get(k) as PlaceStats).parent as string) : `${FLOW_BOX}${k}`);

  const nodes: GraphNode[] = [];
  const boxes: LoopBox[] = [];
  const fns = new Map<string, FlowBox>();
  const unitsSeen = new Set<string>();
  for (const k of [...proj.keys()].sort((a, b) => (a === '' ? -1 : b === '' ? 1 : (stats.get(a)?.depth ?? 0) - (stats.get(b)?.depth ?? 0)))) {
    const p = proj.get(k) as Projection;
    const layer = layerOfC.get(k) as string[];
    const home = k === '' ? null : clusterOf(k);
    if (k !== '') {
      const own = ownNode(k);
      const s = stats.get(k) as PlaceStats;
      const node = own ? { ...own, id: prefix(s.parent ?? '', own.id) } : undefined;
      const part = { id: `${FLOW_BOX}${k}`, key: k, node: node as GraphNode };
      if (home === `${FLOW_BOX}${k}`) {
        const parentBox = own?.box ? prefix(s.parent ?? '', own.box) : s.parent !== null ? clusterOf(s.parent) : null;
        fns.set(home, { id: home, parent: parentBox, parts: [part] });
      } else fns.get(home as string)?.parts.push(part);
    }
    for (const b of p.model.boxes) {
      boxes.push({ ...b, id: prefix(k, b.id), parent: b.parent ? prefix(k, b.parent) : home, layer });
    }
    for (const n of p.model.nodes) {
      if (n.type === 'flow' && open.has(placeKey(layer, n.id))) continue;
      nodes.push({ ...n, id: prefix(k, n.id), box: n.box ? prefix(k, n.box) : home, layer });
    }
    for (const u of p.model.units) unitsSeen.add(u);
  }
  // Every node's marks in one unit order, the run's.
  const units = [...unitsSeen].sort((a, b) => (ix.unitRank.get(a) ?? 0) - (ix.unitRank.get(b) ?? 0));
  const unitsOf = new Map<string, string[]>([...proj].map(([k, p]) => [k, p.model.units]));
  for (const n of nodes) {
    const k = n.id.includes(IN_SEP) ? n.id.slice(0, n.id.lastIndexOf(IN_SEP)) : '';
    const local = unitsOf.get(k) ?? [];
    if (!n.units.length) continue;
    const by = new Map(local.map((u, i) => [u, n.units[i] ?? null]));
    n.units = units.map((u) => by.get(u) ?? null);
  }

  // Edges between the nodes the tasks are drawn in; from outside the layer shown, stubs.
  const drawnOf = (t: FlowTask): string => {
    const c = containerOf.get(t.n.key) as { key: string; depth: number };
    return prefix(c.key, placeOf(t, c.depth).id);
  };
  const layerAt = (t: FlowTask): string[] => t.path.slice(0, (containerOf.get(t.n.key) as { depth: number }).depth);
  const inOrder = new Set<string>();
  const pairs = new Map<string, { from: string; to: string; type: EdgeType; tasks: Set<string>; samePass: boolean }>();
  const stubs = new Map<string, { id: string; label: string; to: string; type: EdgeType; tasks: Set<string> }>();
  for (const t of inside) {
    const to = drawnOf(t);
    const link = (dep: string, type: EdgeType) => {
      const o = ix.byKey.get(dep);
      if (!o) return;
      if (startsWith(o.path, focus)) {
        const from = drawnOf(o);
        if (from === to) {
          if (type !== 'created') inOrder.add(to);
          return;
        }
        // The loops that matter are those of the deepest layer both are drawn in.
        const la = layerAt(o);
        const lb = layerAt(t);
        let d = 0;
        while (d < la.length && d < lb.length && la[d] === lb[d]) d++;
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
      let c = 0;
      while (c < d0 && o.path[c] === focus[c]) c++;
      const p = placeOf(o, c);
      const s = { id: `stub:${c}:${p.id}`, label: p.type === 'kind' ? (ix.labels.get(p.name) ?? p.name) : shortName(p.name) };
      const sk = `${s.id}\u0000${to}\u0000${type}`;
      (stubs.get(sk) ?? stubs.set(sk, { ...s, to, type, tasks: new Set() }).get(sk))?.tasks.add(t.n.key);
    };
    for (const dep of t.n.given_from ?? []) link(dep, 'given');
    for (const dep of t.n.after ?? []) link(dep, 'after');
    for (const dep of t.from) link(dep, 'created');
  }
  for (const n of nodes) n.inOrder = inOrder.has(n.id);
  const edges: GraphEdge[] = [...pairs.values()]
    .filter((e) => !stronger(e.type).some((x) => pairs.has(`${e.from}\u0000${e.to}\u0000${x}`)))
    .map((e) => ({ from: e.from, to: e.to, tasks: e.tasks.size, type: e.type, samePass: e.samePass, back: false }));
  const stubList: GraphStub[] = [...stubs.values()]
    .filter((s) => !stronger(s.type).some((x) => stubs.has(`${s.id}\u0000${s.to}\u0000${x}`)))
    .map((s) => ({ id: s.id, label: s.label, to: s.to, tasks: s.tasks.size, type: s.type }));

  return { path: [...focus], nodes, boxes, fns: [...fns.values()], edges, stubs: stubList, units };
}
