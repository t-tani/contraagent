// What the pipeline graph's views read from `ca-pipeline-graph` and call on it. Each
// view is a function of the element (`GraphHost`) that renders into its shadow root,
// so the element's styles and the selectors stay as they are.
import { deriveRun, type JournalRow, type Plan } from '@contraagent/api';
import type { ReactiveControllerHost } from 'lit';
import { notStartedCause } from '../../../words/index.js';
import type { CardController } from '../graph/card.js';
import type { TaskLinks } from '../graph/highlight.js';
import type { GraphLayout } from '../graph/layout.js';
import { markGrid } from '../graph/marks.js';
import type { MatrixSort, PassMatrix } from '../graph/matrix.js';
import type { PanZoomController } from '../graph/pan-zoom.js';
import { selected } from '../graph/selection.js';
import type { GraphMark, GraphNode, LayerGraph } from '../graph/types.js';

/** A row of a loop's passes, in px; above `WINDOW_AT` rows, only the rows in view (and `OVERSCAN` around them) are drawn. */
export const ROW_H = 24;
export const WINDOW_AT = 150;
export const OVERSCAN = 30;
/** The failed marks a node with a bar of counts lists by name. */
export const BAR_LIST = 8;

/**
 * The element as its views see it: what it shows, the state the views change
 * (each change renders the element again) and its controllers.
 */
export interface GraphHost {
  readonly el: ReactiveControllerHost & HTMLElement;
  readonly root: ParentNode;
  readonly plan: Plan;
  readonly journal: readonly JournalRow[];
  /** The run id: paths in a cause are shown relative to it. */
  readonly run: string;
  readonly live: boolean;
  /** The route's selection and pinned unit. */
  readonly sel: string;
  readonly unit: string;
  /** The layer shown (its segments), and the layer the graph opens on. */
  readonly segments: readonly string[];
  readonly auto: readonly string[];
  readonly graph: LayerGraph;
  /** A loop's passes, when the layer shown is a loop. */
  readonly matrix: PassMatrix | null;
  readonly links: TaskLinks;
  /** Where everything is drawn, and the layer it was drawn for. */
  readonly lay: GraphLayout | null;
  readonly layPath: string;
  /** Top to bottom: a narrow screen. */
  readonly down: boolean;
  /** The table view of the layer. */
  asTable: boolean;
  /** The unit (or key) under the pointer or focus. */
  hover: string | null;
  /** A loop's passes: how its units are sorted, the first row in view, and the focused cell. */
  sort: MatrixSort;
  scrollRow: number;
  cell: [number, number] | null;
  /** Each group's focused mark (roving tabindex): one tab stop per group. */
  readonly active: Map<string, number>;
  readonly pz: PanZoomController;
  readonly card: CardController;
}

/** How a group of marks lays out. */
export interface Grid {
  cols: number;
  size: number;
  gap: number;
}

/** A group of marks with one tab stop: a node's marks, or the failed marks a node with a bar lists. */
export interface MarkGroup {
  id: string;
  /** The name a mark's task or flow call is called by (`label · unit`). */
  label: string;
  slots: (GraphMark | null)[];
  grid: Grid;
}

/** A node's marks in slot order: one per unit (null where the unit has none here), then those without a unit. */
export const slotsOf = (n: Pick<GraphNode, 'units' | 'single'>): (GraphMark | null)[] => [...n.units, ...n.single];

/** A group's grid: the layer's, so a unit sits at one place in every node; a group without units lays out its own few marks. */
export function gridOf(n: Pick<GraphNode, 'units' | 'single'>, units: number): Grid {
  const slots = slotsOf(n);
  const g = markGrid(n.units.length ? units : slots.length);
  return { cols: Math.min(g.cols, Math.max(1, slots.length)), size: g.size, gap: g.size >= 10 ? 4 : 2 };
}

/** The first slot that holds a mark. */
export function firstMark(slots: readonly (GraphMark | null)[]): number {
  return Math.max(0, slots.findIndex((m) => m !== null));
}

/** The unit (or, for a mark without a unit, its key) highlighted: the one hovered or focused, else the selected mark's, else the pinned unit. */
export function highlighted(h: GraphHost): string | null {
  const s = h.hover === null ? selected(h.graph, h.matrix, h.sel) : null;
  const mine = s?.type === 'mark' ? s.mark.unit || s.mark.key : null;
  return h.hover ?? mine ?? (h.unit || null);
}

/** Why a task did not start, in words ('' when it is not known). */
export function causeOf(h: GraphHost, key: string): string {
  const { outcomes } = deriveRun(h.journal, h.plan);
  const t = outcomes.get(key);
  return t ? notStartedCause(t, outcomes, h.run) : '';
}
