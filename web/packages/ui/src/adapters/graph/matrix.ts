// A loop's passes: a loop box unrolled into units by (node, pass).
import type { Plan, TaskState } from '@contraagent/api';
import { arrange, type GraphOrder } from '@contraagent/elements/graph';
import { passesAt, push, type FlowTask } from './flow-index.js';
import { arranged, flowMarks, project, shapeOf, taskMark, type Draft, type Projection } from './project.js';
import { SEVERITY, worstOf } from './states.js';
import { LOOP_SEGMENT, type LayerMark, type GraphNode, type LoopBox } from './types.js';

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
  cells: (LayerMark | null)[];
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
 * each pass of the outer one. A column no task reached is left out. The columns
 * follow the order of the layer drawn left to right with `prev` (its graph's order);
 * `proj` is the layer's projection when the caller has it.
 */
export function passMatrix(plan: Plan, path: readonly string[], box: string, prev?: GraphOrder, proj: Projection = project(plan, path)): PassMatrix | null {
  const { drafts, ix } = proj;
  const graph = arranged(proj.model, arrange(shapeOf(proj.model), prev, false));
  const b = graph.boxes.find((x) => x.id === box);
  if (!b) return null;
  const d = path.length;
  const i0 = b.id.slice(LOOP_SEGMENT.length).split('.').length - 1;
  const byBox = new Map(graph.boxes.map((x) => [x.id, x]));
  const byNode = new Map(graph.nodes.map((n) => [n.id, n]));
  const rel = (t: FlowTask) => passesAt(t, d).slice(i0);
  const leaves = (x: LoopBox): string[] => x.layers.flat().flatMap((id) => (byBox.has(id) ? leaves(byBox.get(id) as LoopBox) : [id]));
  const tasksOf = (x: LoopBox): FlowTask[] => leaves(x).flatMap((id) => drafts.get(id)?.tasks ?? []);
  // Two pass lists are the same (`cmpPasses`, of one length) exactly when their JSON is.
  const passKey = (v: readonly number[]) => JSON.stringify(v);
  // Each node's tasks by their passes, in task order.
  const byPasses = new Map<string, Map<string, FlowTask[]>>();
  const tasksAt = (id: string, at: readonly number[]): readonly FlowTask[] => {
    let m = byPasses.get(id);
    if (!m) {
      m = new Map();
      for (const t of drafts.get(id)?.tasks ?? []) push(m, passKey(rel(t)), t);
      byPasses.set(id, m);
    }
    return m.get(passKey(at)) ?? [];
  };
  // The passes the tasks of a box ran after each list of earlier passes: by box, by the length of that list.
  const nextPasses = new Map<LoopBox, Map<number, Map<string, Set<number>>>>();
  const passesAfter = (x: LoopBox, prefix: readonly number[]): number[] => {
    const k = prefix.length;
    let byK = nextPasses.get(x);
    if (!byK) nextPasses.set(x, (byK = new Map<number, Map<string, Set<number>>>()));
    let byPrefix = byK.get(k);
    if (!byPrefix) {
      byPrefix = new Map();
      for (const v of tasksOf(x).map(rel)) {
        if (v.length <= k) continue;
        const key = passKey(v.slice(0, k));
        (byPrefix.get(key) ?? byPrefix.set(key, new Set()).get(key))?.add(v[k] as number);
      }
      byK.set(k, byPrefix);
    }
    return [...(byPrefix.get(passKey(prefix)) ?? [])].sort((a, c) => a - c);
  };
  const build = (x: LoopBox, prefix: number[]): ColTree[] => {
    const passes = passesAfter(x, prefix);
    return passes.flatMap((p): ColTree[] => {
      const at = [...prefix, p];
      const kids = x.layers.flat().flatMap((id): ColTree[] => {
        const inner = byBox.get(id);
        if (inner) {
          const sub = build(inner, at);
          return sub.length ? [{ type: 'loop', box: inner, kids: sub }] : [];
        }
        const node = byNode.get(id);
        return node && tasksAt(id, at).length ? [{ type: 'node', node, passes: at }] : [];
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
    for (const t of tasksAt(c.node.id, c.passes)) push(cellTasks, `${ci}\u0000${t.n.unit || ''}`, t);
  });
  const markOf = (c: MatrixColumn, ts: readonly FlowTask[], unit: string): LayerMark | null => {
    const x = drafts.get(c.node.id) as Draft;
    if (x.type === 'kind') return taskMark(ts, unit);
    const m = flowMarks(ts, d, x.name, ix.calls);
    return unit ? (m.byUnit.get(unit) ?? m.single[0] ?? null) : (m.single[0] ?? null);
  };
  const mineOf = new Map<string, FlowTask[]>();
  for (const t of mine) push(mineOf, t.n.unit || '', t);
  const rows = rowUnits.map((unit): MatrixRow => {
    const cells = columns.map((c, ci) => {
      const ts = cellTasks.get(`${ci}\u0000${unit}`);
      return ts?.length ? markOf(c, ts, unit) : null;
    });
    const passes = new Set((mineOf.get(unit) ?? []).map((t) => passesAt(t, d).slice(0, i0 + 1).join('.'))).size;
    return { unit, passes, state: worstOf(cells.filter((m): m is LayerMark => m !== null).map((m) => m.state)), cells };
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
