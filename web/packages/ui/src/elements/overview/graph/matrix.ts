// A loop's passes: a loop box unrolled into units by (node, pass).
import type { Plan, TaskState } from '@contraagent/api';
import { push } from './arrange.js';
import { cmpPasses, passesAt, type FlowTask } from './flow-index.js';
import { flowMarks, project, taskMark, type Draft } from './project.js';
import { SEVERITY, worstOf } from './states.js';
import { LOOP_SEGMENT, type GraphMark, type GraphNode, type LayerOrder, type LoopBox } from './types.js';

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
