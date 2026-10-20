// A layer of the run's flow as `<cae-layered-graph>` takes it, and a loop's passes
// as `<cae-mark-matrix>` takes them: the pipeline graph's words on the generic model.
import { deriveRun, type Forecast, type JournalRow, type Plan } from '@contraagent/api';
import type { GraphClusterInput, GraphInput, GraphMark, GraphNodeInput, GraphOrder } from '@contraagent/elements/graph';
import type { MarkMatrixInput, MatrixHeadCell, MatrixMark } from '@contraagent/elements/matrix';
import type { Fact } from '@contraagent/elements/primitives';
import { msg, str } from '@lit/localize';
import { facts, listText } from '../../words/format.js';
import { loopLabel, notStartedCause, passCount, passLabel, passSpread } from '../../words/index.js';
import { expectedByNode } from '../forecast.js';
import { expectedPill } from '../../words/forecast.js';
import type { TaskLinks } from './highlight.js';
import { passMatrix, sortRows, type MatrixSort, type PassMatrix } from './matrix.js';
import { edgeStyle, project, type Projection } from './project.js';
import { markSel } from './selection.js';
import type { GraphNode, LayerMark, LayerModel, LoopBox } from './types.js';
import { doneOf, exceptions, executorWord, markText, nodeLabel, nodeTip, where, type ExceptionClass, type MarkContext } from './words.js';

/** What the words of the marks read: the run's tasks, why a task did not start, and the run being live. */
export interface GraphWordsContext {
  plan: Plan;
  journal: readonly JournalRow[];
  /** The run id: paths in a cause are shown relative to it. */
  run: string;
  live: boolean;
  links: TaskLinks;
  /** The run's forecast: a kind node shows the tasks it is expected to have beyond its own. */
  forecast?: Forecast | null;
}

/** A note's tone by the class of a node's fact. */
const NOTE_TONE: Record<ExceptionClass, Fact['tone']> = { err: 'failed', warn: 'attention', live: 'running', mut: 'muted' };


/** Why a task did not start, in words ('' when it is not known). */
export function causeOf(x: Pick<GraphWordsContext, 'plan' | 'journal' | 'run'>): (key: string) => string {
  return (key) => {
    const { outcomes } = deriveRun(x.journal, x.plan);
    const t = outcomes.get(key);
    return t ? notStartedCause(t, outcomes, x.run) : '';
  };
}

const markContext = (x: GraphWordsContext): ((m: LayerMark) => MarkContext) => {
  const cause = causeOf(x);
  return (m) => ({ task: x.links.byKey.get(m.key), causeOf: cause, live: x.live });
};

/** Where a loop is, as its box and its passes name it: "Loop at flow.py:12". */
const loopAt = (b: Pick<LoopBox, 'loop' | 'file'>): string => msg(str`Loop at ${where(b.loop, b.file)}`);

/** The executors' icons, as `executorIcon` draws them: `agent`, `python`. */
const iconsOf = (n: GraphNode): string[] => (n.executor === 'mixed' ? ['agent', 'python'] : n.executor ? [n.executor] : []);

/**
 * The layer as the generic graph takes it: a node per kind or function (an agent
 * task's node with an accent, a function node with an inner view), a cluster per
 * loop box (it cycles: its return is the loop's next pass), a solid edge per
 * `after` and a dashed one per `created_from`, and the units as the series. Its
 * nodes are in the plan's order, as `arrange` reads them. With `open`, a function node
 * can be drawn open (`toggle`), and each function drawn open (`LayerModel.fns`) is a
 * cluster named by its path, each part a link to its own layer.
 */
export function graphInput(m: LayerModel, x: GraphWordsContext, open = false): GraphInput {
  const ctx = markContext(x);
  const mark = (n: GraphNode, mk: LayerMark): GraphMark => {
    const { name, parts } = markText(n.label, mk, ctx(mk));
    return {
      id: markSel(n.id, mk),
      state: mk.state,
      label: facts(name, ...parts),
      tip: [name, parts[0] ?? ''].filter(Boolean).join('\n'),
      ...(mk.passes ? { badge: String(mk.passes) } : {}),
      name: mk.unit || mk.key,
      drill: !!mk.flow,
    };
  };
  const expected = expectedByNode(x.forecast, m);
  const nodes = m.nodes.map((n): GraphNodeInput => {
    const c = n.counts;
    const more = expected.get(n.id);
    const pill = more ? expectedPill(more) : null;
    return {
      id: n.id,
      label: n.label,
      tip: nodeTip(n),
      summary: pill ? facts(nodeLabel(n, m, x.live), pill.label) : nodeLabel(n, m, x.live),
      ...(pill ? { expected: pill } : {}),
      cluster: n.box,
      icons: iconsOf(n),
      accent: n.executor === 'agent',
      drill: n.type === 'flow',
      marks: n.units.map((mk) => mk && mark(n, mk)),
      loose: n.single.map((mk) => mark(n, mk)),
      counts: c,
      progress: { done: c.done, total: c.total, label: doneOf(c) },
      notes: exceptions(n, x.live).map(([cls, text]) => ({ text, tone: NOTE_TONE[cls] })),
      // Finished (done and skipped) only sets the frame's look; the count is of the tasks done.
      look: c.failed || n.errors ? 'failed' : c.running ? 'running' : c.done + c.skipped === c.total ? 'done' : undefined,
      // A function can be drawn open, where the layer is drawn with its functions (not in a loop's passes).
      ...(n.type === 'flow' && open ? { toggle: 'closed' as const } : {}),
    };
  });
  // A function drawn open: a cluster named by its path, its count and what is not done under its name.
  const fns = m.fns.map((f): GraphClusterInput => {
    const first = (f.parts[0] as (typeof f.parts)[number]).node;
    const label = f.parts.map((p) => p.node.label).join(' › ');
    const c = first.counts;
    const notes = exceptions(first, x.live).map(([, text]) => text);
    return {
      id: f.id,
      parent: f.parent,
      label,
      tip: first.name,
      note: `${c.done}/${c.total}`,
      ...(notes.length ? { detail: facts(...notes) } : {}),
      summary: facts(label, nodeLabel(first, m, x.live)),
      chipLabel: msg(str`Inside ${label}`),
      chipTip: facts(msg('Function'), label),
      drill: true,
      cycle: false,
      toggle: 'open',
      path: f.parts.map((p) => ({ id: p.id, label: p.node.label, tip: p.node.name })),
    };
  });
  const clusters = m.boxes.map((b): GraphClusterInput => {
    const at = loopAt(b);
    const spread = b.spread.length > 1 ? passSpread(b.spread) : '';
    const passes = passCount(b.passes);
    return {
      id: b.id,
      parent: b.parent,
      label: loopLabel(),
      tip: facts(loopLabel(), at),
      note: passes,
      ...(spread ? { detail: spread, detailTip: msg('Units by number of passes') } : {}),
      summary: facts(at, passes, spread),
      chipLabel: facts(msg(str`Passes of the loop at ${where(b.loop, b.file)}`), passes),
      chipTip: facts(at, passes),
      drill: true,
      cycle: true,
    };
  });
  return {
    series: m.units,
    nodes,
    clusters: [...clusters, ...fns],
    edges: m.edges.map((e) => ({ from: e.from, to: e.to, style: edgeStyle(e.type), weight: e.tasks, ranks: e.samePass })),
    stubs: m.stubs.map((s) => ({ id: s.id, label: s.label, to: s.to, style: edgeStyle(s.type), weight: s.tasks })),
  };
}

/** The layer `path` of the plan, as the generic graph takes it, and its projection (for the card's facts and a loop's passes). */
export function graphFromPlan(plan: Plan, path: readonly string[], x: Omit<GraphWordsContext, 'plan'>): { input: GraphInput; proj: Projection } {
  const proj = project(plan, path);
  return { input: graphInput(proj.model, { ...x, plan }), proj };
}

/** How a loop's units can be sorted, and the words for each. */
export const matrixSorts = (): { id: MatrixSort; label: string }[] => [
  { id: 'order', label: msg('Scheduled order') },
  { id: 'passes', label: msg('Number of passes') },
  { id: 'state', label: msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' }) },
];

/**
 * A loop's passes as the generic mark matrix takes them: a row per unit (sorted by
 * `sort`), a column per node and pass under a group per pass (a nested loop's passes
 * as groups inside each pass of the outer one).
 */
export function matrixInput(mx: PassMatrix, sort: MatrixSort, x: GraphWordsContext): MarkMatrixInput {
  const ctx = markContext(x);
  const box = mx.box;
  const caption = loopAt(box);
  const units = mx.rows.filter((r) => r.unit).length;
  const cell = (ci: number, mk: LayerMark): MatrixMark => {
    const col = mx.columns[ci];
    const label = col?.node.label ?? '';
    const passes = col?.passes ?? [];
    const { name, parts } = markText(label, mk, ctx(mk), listText(passes.map(passLabel)));
    return { id: markSel(col?.node.id ?? '', mk, passes), state: mk.state, label: facts(name, ...parts), tip: [name, parts[0] ?? ''].filter(Boolean).join('\n'), drill: !!mk.flow };
  };
  const head = mx.head.map((row) =>
    row.map((hd): MatrixHeadCell => {
      if (hd.type === 'pass')
        return {
          id: `${hd.box.id}|${hd.pass}`,
          label: passLabel(hd.pass),
          tip: hd.box.id === box.id ? loopAt(hd.box) : msg(str`Nested loop at ${where(hd.box.loop, hd.box.file)}`),
          span: hd.span,
          rows: hd.rows,
          type: 'group',
        };
      if (hd.type === 'loop')
        return { id: hd.box.id, label: loopLabel(), tip: msg(str`Nested loop at ${where(hd.box.loop, hd.box.file)}`), code: true, span: hd.span, rows: hd.rows, type: 'group' };
      const n = hd.node;
      const flow = n.type === 'flow';
      return {
        id: `${n.id}|${hd.passes.join('.')}`,
        label: n.label,
        tip: flow ? msg(str`Function ${n.name}`) : facts(n.label, executorWord(n)),
        summary: flow ? n.label : facts(n.label, executorWord(n)),
        icons: n.executor && n.executor !== 'mixed' ? [n.executor] : [],
        span: hd.span,
        rows: hd.rows,
        type: 'column',
      };
    }),
  );
  return {
    caption,
    ...(box.file ? { captionTip: `${box.file}:${box.loop}` } : {}),
    label: facts(caption, passCount(box.passes)),
    facts: [passCount(box.passes), box.spread.length > 1 ? passSpread(box.spread) : '', units === 1 ? msg('1 unit') : msg(str`${units} units`)].filter(Boolean),
    head,
    columns: mx.columns.map((c) => ({ id: `${c.node.id}|${c.passes.join('.')}`, groups: c.passes.map((_, k) => c.passes.slice(0, k + 1).join('.')) })),
    rows: sortRows(mx.rows, sort).map((r) => ({
      id: r.unit,
      label: r.unit || msg('No unit'),
      tip: r.unit || msg('Tasks that run once per run, not once per unit'),
      muted: !r.unit,
      value: r.passes,
      strong: r.passes > 1,
      cells: r.cells.map((mk, ci) => mk && cell(ci, mk)),
    })),
    value: { label: msg('Passes'), tip: msg('Passes of this loop') },
    sorts: matrixSorts(),
    sort,
  };
}

/** The loop box `box` of layer `path` with its passes unrolled (`passMatrix`), as the generic mark matrix takes it; null when the layer has no such box. */
export function matrixFromPlan(
  plan: Plan,
  path: readonly string[],
  box: string,
  prev: GraphOrder | undefined,
  sort: MatrixSort,
  x: Omit<GraphWordsContext, 'plan'>,
  proj?: Projection,
): { input: MarkMatrixInput; matrix: PassMatrix } | null {
  const matrix = passMatrix(plan, path, box, prev, proj);
  return matrix && { input: matrixInput(matrix, sort, { ...x, plan }), matrix };
}
