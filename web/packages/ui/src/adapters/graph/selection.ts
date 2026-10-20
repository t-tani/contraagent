// What a selection id names in a layer's graph or in a loop's passes.
import type { PassMatrix } from './matrix.js';
import type { LayerMark, GraphNode, LayerGraph, LoopBox, NodeCounts } from './types.js';

/**
 * A mark's selection id: its node, the passes of its column in a loop's passes
 * (`|1.2`), and its unit, or its key for a mark without one (`kind:review@7#gamma`).
 */
export const markSel = (node: string, m: Pick<LayerMark, 'unit' | 'key'>, passes: readonly number[] = []): string =>
  `${node}${passes.length ? `|${passes.join('.')}` : ''}#${m.unit || m.key}`;

/** What a selection id names: a mark (with its node, and its column's passes in a loop's passes), a node or a loop box. */
export type Selected =
  | { type: 'mark'; id: string; node: GraphNode; mark: LayerMark; passes: number[] }
  | { type: 'node'; id: string; node: GraphNode }
  | { type: 'box'; id: string; box: LoopBox };

/**
 * What `sel` names in a layer's graph, or, with `matrix`, in a loop's passes (a mark
 * there names its column's passes); null when it names nothing there.
 */
export function parseSelection(g: LayerGraph, matrix: PassMatrix | null, sel: string): Selected | null {
  if (!sel) return null;
  const hash = sel.indexOf('#');
  if (hash < 0) {
    const node = g.nodes.find((n) => n.id === sel);
    if (node) return { type: 'node', id: sel, node };
    const box = g.boxes.find((b) => b.id === sel);
    if (box) return { type: 'box', id: sel, box };
    // A function drawn open, or a part of its path: its node, as it is drawn closed.
    const part = g.fns.flatMap((f) => f.parts).find((p) => p.id === sel);
    return part ? { type: 'node', id: sel, node: part.node } : null;
  }
  const [nodeId = '', pass] = sel.slice(0, hash).split('|');
  const who = sel.slice(hash + 1);
  const is = (m: LayerMark | null | undefined): m is LayerMark => !!m && (m.unit ? m.unit === who : m.key === who);
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
  const c: NodeCounts = { total: 0, done: 0, partial: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, cancelled: 0 };
  for (const n of nodes) for (const k of Object.keys(c) as (keyof NodeCounts)[]) c[k] += n.counts[k];
  return c;
}
