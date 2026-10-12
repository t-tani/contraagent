import { taskOutcomes, type JournalRow, type Plan, type PlanNode, type TaskState } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, svg, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { facts, fmtDur, kindUnit } from '../../lib/format.js';
import { loopLabel, notStartedCause, passCount, passLabel, passSpread, passesRan, planStateLabel, stateCount } from '../../lib/labels.js';
import { base } from '../../styles/base.js';
import {
  LOOP_SEGMENT,
  alongEdge,
  asBar,
  autoLayer,
  barParts,
  edgePath,
  fitView,
  gridStep,
  isPoint,
  layerGraph,
  layoutGraph,
  markGrid,
  parentLayer,
  passMatrix,
  shortName,
  sortRows,
  splitLayer,
  zoomView,
  type GraphLayout,
  type GraphMark,
  type GraphNode,
  type LayerGraph,
  type NodeCounts,
  type LayerOrder,
  type LoopBox,
  type MatrixHead,
  type MatrixRow,
  type MatrixSort,
  type PassMatrix,
  type Rect,
  type Size,
  type View,
} from './logic.js';

/** The states the legend can show, in this order; it shows the ones the view has. */
const LEGEND: readonly TaskState[] = ['done', 'running', 'pending', 'failed', 'blocked', 'skipped'];
/** Below this width the graph runs top to bottom, without zoom. */
const NARROW = 640;
/** The frame is at most this share of the window's height, and at least `FRAME_MIN` px. */
const FRAME_SHARE = 0.7;
const FRAME_MIN = 360;
/** How far the view zooms: from half of the whole-graph view (or of 1) up to this. */
const ZOOM_MAX = 2.5;
/** A pointer moved this far is a pan, not a click. */
const DRAG = 4;
/** A row of a loop's passes, in px; above `WINDOW_AT` rows, only the rows in view (and `OVERSCAN` around them) are drawn. */
const ROW_H = 24;
const WINDOW_AT = 150;
const OVERSCAN = 30;
/** The failed marks a node with a bar of counts lists by name. */
const BAR_LIST = 8;

/** How a group of marks lays out. */
interface Grid {
  cols: number;
  size: number;
  gap: number;
}

/** A group of marks with one tab stop: a node's marks, or the failed marks a node with a bar lists. */
interface MarkGroup {
  id: string;
  /** The name a mark's task or flow call is called by (`label · unit`). */
  label: string;
  slots: (GraphMark | null)[];
  grid: Grid;
}

/** A node's marks in slot order: one per unit (null where the unit has none here), then those without a unit. */
const slotsOf = (n: Pick<GraphNode, 'units' | 'single'>): (GraphMark | null)[] => [...n.units, ...n.single];

/** A group's grid: the layer's, so a unit sits at one place in every node; a group without units lays out its own few marks. */
function gridOf(n: Pick<GraphNode, 'units' | 'single'>, units: number): Grid {
  const slots = slotsOf(n);
  const g = n.units.length ? markGrid(units) : markGrid(slots.length);
  return { cols: Math.min(g.cols, Math.max(1, slots.length)), size: g.size, gap: g.size >= 10 ? 4 : 2 };
}

/**
 * The run as a graph of its flow, one layer at a time. A layer shows the kinds of
 * the tasks its function created (a kind node each, joined to the ones it waits for)
 * and the functions it called (a function node each, holding their tasks); nodes
 * created in one loop are drawn in a loop box, with its last pass ("up to 3
 * passes") and, when its units ran different numbers of passes, how many ran each
 * ("1 pass: 4 | 2 passes: 1"); a nested loop's box is inside it, and a mark on the
 * box's edge stands for the return to its next pass. Inside a node, one mark per
 * unit, at the same place in every node, so a unit can be followed across the
 * layer: a task in a kind node, a flow call in a function node; in a loop box, the
 * unit's latest pass, with the number of passes it ran when more than 1. A mark of
 * several tasks shows the most severe state among them (failed, running, not
 * started, waiting, skipped, done); a flow call's mark counts every task of it and
 * of the flow calls it started, and its own error (raised or closed) as failed. A
 * node's count is its tasks done of its tasks, with the others by state, and a
 * function node names its flow calls that stopped with an error. A problem
 * has a square mark (failed: red; not started: hatched), every other state a round
 * one. Above 200 marks, a node shows a bar of its counts and names its failed
 * marks. A solid edge waits for an output; a dashed edge was created after a
 * result; an edge from outside the layer starts at a named stub.
 *
 * The layout is layered: each layer of the flow in a column, an edge bending only
 * in the gaps between columns and never passing a node or a box's label. It depends
 * on the flow's structure only, so it stays still while the run progresses; nodes
 * that appear later are added at the end of their layer.
 *
 * The graph opens on the first layer with more than one node (a static flow's
 * kinds), or on a single function node whose flow call raised. Clicking a
 * function's name, or one of its marks, enters it (the mark's unit stays
 * highlighted); clicking a loop box's name shows its passes: a row per unit and a
 * column per node and pass, a nested loop's passes as a group of columns inside
 * each pass of the outer one, the units sortable by number of passes or by status.
 * The breadcrumb, shown on every layer below the top, and Escape go back up.
 * Hovering or focusing a mark highlights its unit and the tasks joined to it. The
 * graph runs left to right in a frame that first shows all of it; Ctrl (or ⌘) and
 * the wheel, or the buttons, zoom; dragging pans; "Show all" goes back to the whole
 * graph. On a narrow screen it runs top to bottom instead.
 *
 * Keyboard: Tab moves between nodes; the arrow keys, Home and End move between a
 * node's marks, and a mark out of the frame is brought into it; Shift and an arrow
 * key move along an edge to an earlier or a later node, on the same unit when it is
 * there; Enter opens the task or enters the function; Escape goes up, back to the
 * node it came from. In a loop's passes, the arrow keys, Home, End, Page Up and Page
 * Down move between the marks. "Show as table" gives the same counts as a table.
 *
 * @fires ca-open-task - `{key, view?}`: a task's mark was clicked (a task that did not start opens on its input, a Python task on its output)
 * @fires ca-navigate - `{tab: 'tasks', kind?}`: a kind's name was clicked; `{layer, unit?}`: a function, a loop box, a flow call's mark or the breadcrumb was clicked, or Escape was pressed
 */
@customElement('ca-pipeline-graph')
@localized()
export class CaPipelineGraph extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }

      .frame { position: relative; overflow: hidden; border-radius: 8px; background: rgba(0, 0, 0, 0.12); cursor: grab; touch-action: none; }
      .frame.drag { cursor: grabbing; }
      .stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
      .frame.down { touch-action: pan-y pinch-zoom; }
      .tools { display: flex; gap: 4px; margin-left: auto; }
      .tools button { all: unset; cursor: pointer; min-width: 22px; height: 22px; padding: 0 7px; box-sizing: border-box; text-align: center;
        font-size: 11.5px; line-height: 22px; color: var(--fg2); border-radius: 6px; border: 1px solid var(--line); }
      .tools button:hover:not(:disabled) { color: var(--fg); border-color: var(--line2); }
      .tools button:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }
      .tools button:disabled { cursor: default; opacity: 0.4; }

      .dag { position: relative; }
      .dag.unplaced { visibility: hidden; }
      .dag > *, .box > .in > * { position: absolute; }
      .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
      .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
      .edges path.created { stroke-dasharray: 5 4; }
      .unset { visibility: hidden; }

      .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--mut); padding: 3px 9px;
        border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

      .box { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: rgba(148, 163, 184, 0.045); }
      .box .box { background: rgba(148, 163, 184, 0.06); }
      .box > .in { position: absolute; inset: 0; pointer-events: none; }
      .box > .in > * { pointer-events: auto; }
      .box > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
        white-space: nowrap; justify-content: flex-start; }
      .box > .hd .line { display: flex; align-items: baseline; gap: 8px; }
      .box > .hd .spread { font-size: 11px; color: var(--fg2); font-variant-numeric: tabular-nums; }
      /* The next-pass mark sits on the box's edge, where no edge crosses it: below its first layer
         (left to right), or beside its last (top to bottom). */
      .ret { position: absolute; left: 14px; bottom: -8px; display: grid; place-items: center; width: 22px; height: 15px;
        border-radius: 8px; background: var(--card); border: 1px solid var(--line2); color: var(--fg2); }
      .down .ret { left: auto; right: -12px; bottom: 14px; transform: rotate(90deg); }
      .ret svg { display: block; }

      .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
        display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
        border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s; }
      .node.flow { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
      .node.done { border-color: rgba(52, 211, 153, 0.32); }
      .node.cur { border-color: var(--live); }
      .node.flow.cur { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--live), 0 0 14px rgba(34, 211, 238, 0.12); }
      .node:not(.flow).cur { box-shadow: 0 0 14px rgba(34, 211, 238, 0.12); }
      .node.fail { border-color: rgba(248, 113, 113, 0.55); }
      .node:focus-within { border-color: var(--fg2); }
      .hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .name { all: unset; cursor: pointer; font-family: var(--mono); font-weight: 600; font-size: 12.5px; color: var(--fg);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
      .name:hover { text-decoration: underline; }
      .name:focus-visible { outline: 2px solid var(--live); outline-offset: 2px; border-radius: 3px; }
      .count { font-size: 11px; color: var(--mut); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .ex { display: flex; flex-wrap: wrap; gap: 0 10px; font-size: 11px; line-height: 1.5;
        max-width: max(98px, calc(var(--cols) * var(--m) + (var(--cols) - 1) * var(--g))); }
      .ex .err { color: var(--err); }
      .ex .warn { color: var(--warn); }
      .ex .live { color: var(--live); }
      .ex .mut { color: var(--mut); }

      .marks { display: grid; grid-template-columns: repeat(var(--cols), var(--m)); gap: var(--g); }
      .slot { width: var(--m); height: var(--m); }
      .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--ok); opacity: 0.9;
        cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
      .mark.skipped { opacity: 0.4; }
      .mark.running { background: var(--live); opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
      .mark.pending { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .mark.blocked { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, rgba(251, 191, 36, 0.55) 2px 3px);
        box-shadow: inset 0 0 0 1.5px var(--warn); opacity: 1; }
      .mark.failed { border-radius: 2px; background: var(--err); opacity: 1; }
      .big .mark.failed::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: #fff;
        font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
      /* A unit that ran more than 1 pass: its number in the mark; a small mark has a hole instead. */
      .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
      .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
        font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: #04241a; letter-spacing: -0.5px; }
      .big .mark.failed[data-n]::after { color: #fff; }
      .big .mark.running[data-n]::after { color: #03222a; }
      .big .mark.pending[data-n]::after, .big .mark.blocked[data-n]::after, .big .mark.skipped[data-n]::after { color: var(--fg); }
      .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: 2px solid var(--fg); outline-offset: 1px; z-index: 2; }
      .hl .mark:not(.on) { opacity: 0.16; }
      .hl .mark.on { transform: scale(1.2); }
      .mx.hl .mark:not(.on) { opacity: 0.4; }
      @media (prefers-reduced-motion: reduce) {
        .mark, .node { transition: none; }
        .mark.running { animation: none; background: linear-gradient(90deg, var(--live) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--live); }
      }

      .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
      .sbar i { display: block; min-width: 2px; height: 100%; }
      .sbar .done { background: var(--ok); opacity: 0.85; }
      .sbar .running { background: var(--live); }
      .sbar .pending { background: var(--line2); }
      .sbar .failed { background: var(--err); }
      .sbar .blocked { background: repeating-linear-gradient(135deg, var(--warn-a) 0 2px, rgba(251, 191, 36, 0.6) 2px 3px); }
      .sbar .skipped { background: var(--ok); opacity: 0.35; }
      .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--mut); }
      .fails .taskchip { color: var(--err); border-color: rgba(248, 113, 113, 0.45); }
      .fails .taskchip:focus-visible { outline: 2px solid var(--fg); outline-offset: 1px; }
      .hl .fails .taskchip:not(.on) { opacity: 0.4; }

      .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; color: var(--fg2); }
      .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--mut); font-size: 11.5px; }
      .mxbar select { font: inherit; font-size: 11.5px; color: var(--fg); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
      .mxbar select:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }
      .mx { overflow: auto; width: fit-content; max-width: 100%; max-height: max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh); border-radius: 8px; background: rgba(0, 0, 0, 0.12); }
      table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: max-content; }
      .matrix th, .matrix td { padding: 0 6px; height: ${ROW_H}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
      .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--mut); font-weight: 500; text-align: center; height: 22px; }
      .matrix thead th.nh { font-family: var(--mono); color: var(--fg2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
      .matrix thead th.pass { color: var(--fg2); }
      .matrix thead th.loop { font-family: var(--mono); }
      .matrix .uh, .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--panel); text-align: left; }
      .matrix thead .uh { z-index: 3; }
      .matrix thead .uh, .matrix thead .pn { background: var(--panel2); }
      .matrix tbody th { font-family: var(--mono); font-weight: 600; color: var(--fg); max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
      .matrix tbody th.none { font-family: var(--sans); font-weight: 500; color: var(--mut); }
      .matrix .pn { text-align: right; color: var(--mut); font-variant-numeric: tabular-nums; }
      .matrix .pn.many { color: var(--fg); font-weight: 600; }
      .matrix td.c { text-align: center; --m: 12px; }
      .matrix td.c .mark { vertical-align: middle; }
      .matrix .g0 { border-left: 1px solid var(--line2); }
      .matrix .g1 { border-left: 1px dashed var(--line); }
      .matrix tbody tr:hover td, .matrix tbody tr:hover th { background-color: rgba(148, 163, 184, 0.06); }
      .matrix tbody tr.on td, .matrix tbody tr.on th { background-color: var(--live-a); }
      .matrix .gap td { padding: 0; border: 0; }

      .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; }
      .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; list-style: none; margin: 0; padding: 0; }
      .crumbs li { display: inline-flex; align-items: center; gap: 4px; }
      .crumbs .sep { color: var(--mut); }
      .crumbs button { all: unset; cursor: pointer; color: var(--live); font-family: var(--mono); }
      .crumbs button:hover { text-decoration: underline; }
      .crumbs button:focus-visible { outline: 2px solid var(--live); outline-offset: 2px; border-radius: 3px; }
      .crumbs [aria-current] { font-family: var(--mono); color: var(--fg); font-weight: 600; }
      .pin { display: inline-flex; align-items: center; gap: 8px; color: var(--fg2); }
      .pin b { font-family: var(--mono); }

      .foot { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-top: 6px; }
      .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--mut); }
      .legend > span { white-space: nowrap; }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .legend .mark { --m: 12px; cursor: default; animation: none; }
      .legend .mark:hover { transform: none; outline: none; }
      .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }
      .keys { flex-basis: 100%; font-size: 11px; color: var(--mut); display: none; }
      .keys span { white-space: nowrap; }
      :host(:focus-within) .keys { display: block; }
      .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--fg2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
      .switch:hover { color: var(--fg); border-color: var(--line2); }
      .switch:focus-visible { outline: 2px solid var(--live); outline-offset: 1px; }

      table.list { width: 100%; border-collapse: collapse; font-size: 12px; }
      .list th, .list td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); }
      .list td.n { text-align: right; font-variant-numeric: tabular-nums; }
      /* a header is as wide as its words: a narrow count column never breaks its header inside a word */
      .list thead th { color: var(--mut); font-weight: 500; font-size: 11px; white-space: nowrap; }
      .list tbody th { font-family: var(--mono); font-weight: 600; }
    `,
  ];

  @property({ attribute: false }) plan: Plan = { nodes: [], groups: [] };
  /** The finished attempts: they tell why a task did not start. */
  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The run id: paths in a cause are shown relative to it. */
  @property() run = '';
  /** The run is running: tasks still pending are waiting; once it is over, they did not run. */
  @property({ type: Boolean }) live = false;
  /** The layer shown: its segments (function names, then `loop:<line>` for a loop's passes) joined by `/`; '' for the layer the graph opens on. */
  @property() layer = '';
  /** The unit highlighted while nothing is hovered or focused. */
  @property() unit = '';

  /** The unit (or, for a mark without a unit, its task or flow call key) under the pointer or focus. */
  @state() private hover: string | null = null;
  @state() private asTable = false;
  /** Top to bottom: the graph does not fit left to right. */
  @state() private down = false;
  /** Where everything is drawn, from the sizes measured after the last render. */
  @state() private lay: GraphLayout | null = null;
  /** The zoom and pan of the graph in its frame, and the frame's height. */
  @state() private view: View = { k: 1, x: 0, y: 0 };
  @state() private frameH = 0;
  /** A loop's passes: how its units are sorted, and the first row in view. */
  @state() private sort: MatrixSort = 'order';
  @state() private scrollRow = 0;

  /** The layer the graph opens on, the one shown, and what it shows. */
  private auto: string[] = [];
  private segments: string[] = [];
  private graph: LayerGraph = { path: [], nodes: [], layers: [], boxes: [], edges: [], stubs: [], units: [], slots: {}, routes: [], order: { layers: [], boxes: {} } };
  private matrix: PassMatrix | null = null;
  /** Each layer's order, so nodes stay where they are while the plan grows. */
  private orders = new Map<string, LayerOrder>();
  private byKey = new Map<string, PlanNode>();
  /** The tasks that wait for each task, by key. */
  private waiters = new Map<string, string[]>();
  /** Each group's focused mark (roving tabindex): one tab stop per group; in a loop's passes, the focused cell. */
  private readonly active = new Map<string, number>();
  private cell: [number, number] | null = null;
  private refocus = false;
  /** After going up a level: the node (or box) it came from, to focus. */
  private cameFrom = '';
  /** What the layout was computed from: the structure, the orientation and the sizes. */
  private layKey = '';
  private resize?: ResizeObserver;
  /** The scale that shows the whole graph; the reader has zoomed or panned away from it. */
  private fitK = 1;
  private moved = false;
  /** A pan in progress, and whether it went far enough to swallow the click that ends it. */
  private pan: { id: number; px: number; py: number; x: number; y: number; far: boolean } | null = null;
  private swallowClick = false;

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('run')) this.orders.clear();
    if (changed.has('layer') && changed.get('layer') !== undefined) {
      this.moved = false;
      this.active.clear();
      this.cell = null;
      this.scrollRow = 0;
      this.refocus = this.renderRoot instanceof ShadowRoot && this.renderRoot.activeElement !== null;
    }
    if (!changed.has('plan') && !changed.has('layer') && !changed.has('run') && !(changed as Map<string, unknown>).has('down')) return;
    this.auto = autoLayer(this.plan);
    this.segments = this.layer ? this.layer.split('/') : this.auto;
    const { path, loop } = splitLayer(this.segments);
    const key = path.join('/');
    this.graph = layerGraph(this.plan, path, this.orders.get(key), this.down);
    this.orders.set(key, this.graph.order);
    this.matrix = loop ? passMatrix(this.plan, path, loop, this.graph.order) : null;
    if (changed.has('plan')) {
      this.byKey = new Map(this.plan.nodes.map((n) => [n.key, n]));
      this.waiters = new Map();
      for (const n of this.plan.nodes) for (const d of n.after ?? []) (this.waiters.get(d) ?? this.waiters.set(d, []).get(d))?.push(n.key);
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener('wheel', this.onWheel);
    this.removeEventListener('click', this.onClickCapture, { capture: true });
    this.removeEventListener('keydown', this.onEscape);
    this.resize?.disconnect();
    this.resize = undefined;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    // Ctrl (or ⌘) and the wheel zoom; the wheel alone still scrolls the page.
    this.addEventListener('wheel', this.onWheel, { passive: false });
    this.addEventListener('click', this.onClickCapture, { capture: true });
    this.addEventListener('keydown', this.onEscape);
  }

  protected override updated(): void {
    if (!this.resize) {
      this.resize = new ResizeObserver(() => this.fit());
      this.resize.observe(this);
    }
    this.place();
    if (this.refocus || this.cameFrom) this.restoreFocus();
  }

  /** Measure what was drawn and, when the structure, the orientation or a size changed, lay it out again. */
  private place(): void {
    const dag = this.renderRoot.querySelector<HTMLElement>('.dag');
    if (!dag) return;
    const sizes = new Map<string, Size>();
    for (const el of dag.querySelectorAll<HTMLElement>('[data-id]')) sizes.set(el.dataset['id'] ?? '', { w: el.offsetWidth, h: el.offsetHeight });
    const g = this.graph;
    const key = JSON.stringify([g.path, g.slots, g.routes.map((r) => r.steps.map((s) => s.id)), this.down, [...sizes]]);
    if (key === this.layKey) return this.fit();
    this.layKey = key;
    this.lay = layoutGraph(g, sizes, this.down);
    void this.updateComplete.then(() => this.fit());
  }

  private restoreFocus(): void {
    const from = this.cameFrom;
    this.refocus = false;
    this.cameFrom = '';
    const root = this.renderRoot;
    let el: HTMLElement | null = null;
    if (from.startsWith(LOOP_SEGMENT)) el = root.querySelector<HTMLElement>(`.box[data-box="${CSS.escape(from)}"] > .hd .name`);
    else if (from) {
      const n = this.graph.nodes.find((x) => x.type === 'flow' && x.name === from);
      if (n) el = root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(n.id)}"] [tabindex="0"]`);
    }
    (el ?? root.querySelector<HTMLElement>('.mark[tabindex="0"], .node .name, .crumbs button'))?.focus();
  }

  // ---- layers ----

  /** Go to a layer (its segments; [] for the layer the graph opens on), with a unit highlighted or not. */
  private go(segments: readonly string[], unit = this.unit): void {
    const auto = this.auto.join('/');
    const layer = segments.join('/');
    emit(this, 'ca-navigate', { layer: layer === auto ? '' : layer, unit });
  }

  private readonly onEscape = (e: KeyboardEvent): void => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    const up = parentLayer(this.segments, this.auto);
    if (!up) return;
    e.preventDefault();
    this.refocus = true;
    this.cameFrom = this.segments[this.segments.length - 1] ?? '';
    this.go(up);
  };

  /**
   * Where the layer is: "Pipeline", then every level down to the one shown, auto-descended
   * levels included; a nested loop's box is a level below the box it is in.
   */
  private crumbs() {
    const segs = this.segments;
    const pinned = this.unit;
    if (!segs.length && !pinned) return nothing;
    const { path, loop } = splitLayer(segs);
    const levels = [
      ...path.map((fn, i) => ({ name: shortName(fn), tip: fn, to: path.slice(0, i + 1) })),
      ...(loop ? loop.slice(LOOP_SEGMENT.length).split('.') : []).map((line, i, lines) => ({
        name: loopLabel(),
        tip: /^\d+$/.test(line) ? msg(str`Loop at ${this.where(line, this.matrix?.box.file || this.graph.boxes[0]?.file)}`) : msg('Loop'),
        to: [...path, LOOP_SEGMENT + lines.slice(0, i + 1).join('.')],
      })),
    ];
    return html`<div class="bar">
      ${segs.length
        ? html`<nav aria-label=${msg('Pipeline layer')}>
            <ol class="crumbs">
              <li><button type="button" @click=${() => this.go([])}>${msg('Pipeline')}</button></li>
              ${levels.map((l, i) => {
                const last = i === levels.length - 1;
                return html`<li><span class="sep" aria-hidden="true">›</span>
                  ${last
                    ? html`<span aria-current="page" title=${l.tip}>${l.name}</span>`
                    : html`<button type="button" title=${l.tip} @click=${() => this.go(l.to)}>${l.name}</button>`}</li>`;
              })}
            </ol>
          </nav>`
        : nothing}
      ${pinned
        ? html`<span class="pin">${msg(str`Unit: ${pinned}`)}
            <button type="button" class="switch" @click=${() => emit(this, 'ca-navigate', { unit: '' })}>${msg('Clear highlight')}</button></span>`
        : nothing}
    </div>`;
  }

  // ---- frame: fit, zoom, pan ----

  /** Top to bottom on a narrow screen; otherwise the whole graph in a frame, until the reader zooms or pans. */
  private fit(): void {
    const width = this.clientWidth;
    const down = width > 0 && width < NARROW;
    if (down !== this.down) this.down = down;
    const lay = this.lay;
    if (!lay || this.matrix) return;
    // Top to bottom, the graph is as tall as it needs at the frame's width.
    const whole = fitView(lay.w, lay.h, width, down ? Infinity : Math.max(FRAME_MIN, FRAME_SHARE * window.innerHeight));
    this.fitK = whole.k;
    if (!this.moved) {
      if (whole.h !== this.frameH) this.frameH = whole.h;
      if (whole.k !== this.view.k || whole.x !== this.view.x || whole.y !== this.view.y) this.view = { k: whole.k, x: whole.x, y: whole.y };
    }
  }

  /** Zoom out, zoom in, and back to the whole graph (which does nothing while the whole graph shows at its own size). */
  private tools() {
    const whole = !this.moved && this.fitK >= 1;
    return html`<div class="tools">
      <button type="button" aria-label=${msg('Zoom out')} title=${msg('Zoom out (Ctrl + scroll)')} @click=${() => this.zoomBy(1 / 1.25)}>−</button>
      <button type="button" aria-label=${msg('Zoom in')} title=${msg('Zoom in (Ctrl + scroll)')} @click=${() => this.zoomBy(1.25)}>+</button>
      <button type="button" ?disabled=${whole} @click=${() => this.showAll()}>${msg('Show all')}</button>
    </div>`;
  }

  private showAll(): void {
    this.moved = false;
    this.fit();
    this.requestUpdate();
  }

  private zoomBy(factor: number, cx = this.clientWidth / 2, cy = this.frameH / 2): void {
    this.moved = true;
    this.view = zoomView(this.view, factor, cx, cy, Math.min(1, this.fitK) / 2, ZOOM_MAX);
  }

  private readonly onWheel = (e: WheelEvent): void => {
    if (this.asTable || this.matrix || !(e.ctrlKey || e.metaKey)) return;
    const frame = this.renderRoot.querySelector<HTMLElement>('.frame');
    if (!frame) return;
    e.preventDefault();
    const r = frame.getBoundingClientRect();
    this.zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  };

  private onPointerDown(e: PointerEvent): void {
    // On a narrow screen a touch scrolls the page; a mouse still pans.
    if (e.button !== 0 || (e.target as HTMLElement).closest('.tools') || (this.down && e.pointerType !== 'mouse')) return;
    this.pan = { id: e.pointerId, px: e.clientX, py: e.clientY, x: this.view.x, y: this.view.y, far: false };
  }

  private onPointerMove(e: PointerEvent): void {
    const p = this.pan;
    if (!p || p.id !== e.pointerId) return;
    const dx = e.clientX - p.px;
    const dy = e.clientY - p.py;
    if (!p.far && Math.hypot(dx, dy) < DRAG) return;
    if (!p.far) {
      p.far = true;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      (e.currentTarget as HTMLElement).classList.add('drag');
    }
    this.moved = true;
    this.view = { ...this.view, x: p.x + dx, y: p.y + dy };
  }

  private onPointerUp(e: PointerEvent): void {
    const p = this.pan;
    if (!p || p.id !== e.pointerId) return;
    this.pan = null;
    (e.currentTarget as HTMLElement).classList.remove('drag');
    if (p.far) this.swallowClick = true;
  }

  /** The click that ends a pan opens nothing. */
  private readonly onClickCapture = (e: Event): void => {
    if (!this.swallowClick) return;
    this.swallowClick = false;
    e.stopPropagation();
    e.preventDefault();
  };

  /** Bring a focused mark into the frame when zoom or pan left it outside. */
  private reveal(el: HTMLElement): void {
    const frame = this.renderRoot.querySelector<HTMLElement>('.frame');
    if (!frame) return;
    const f = frame.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const pad = 24;
    let dx = 0;
    let dy = 0;
    if (r.left < f.left + pad) dx = f.left + pad - r.left;
    else if (r.right > f.right - pad) dx = f.right - pad - r.right;
    if (r.top < f.top + pad) dy = f.top + pad - r.top;
    else if (r.bottom > f.bottom - pad) dy = f.bottom - pad - r.bottom;
    if (dx || dy) {
      this.moved = true;
      this.view = { ...this.view, x: this.view.x + dx, y: this.view.y + dy };
    }
  }

  // ---- highlight ----

  /** The unit (or key) highlighted: the one hovered or focused, else the pinned unit. */
  private get hl(): string | null {
    return this.hover ?? (this.unit || null);
  }

  /** The tasks to highlight: the unit's own, and every task joined to them upstream or downstream (a task without a unit, another unit's). */
  private lit(): Set<string> | null {
    const hl = this.hl;
    if (hl === null) return null;
    const seeds = this.plan.nodes.filter((n) => (n.unit ? n.unit === hl : n.key === hl)).map((n) => n.key);
    const on = new Set(seeds);
    const walk = (next: (key: string) => readonly string[]) => {
      const seen = new Set(seeds);
      const queue = [...seeds];
      for (let k = queue.pop(); k !== undefined; k = queue.pop()) {
        for (const x of next(k)) {
          if (seen.has(x)) continue;
          seen.add(x);
          on.add(x);
          queue.push(x);
        }
      }
    };
    walk((k) => this.waiters.get(k) ?? []);
    walk((k) => this.byKey.get(k)?.after ?? []);
    return on;
  }

  // ---- render ----

  override render() {
    if (!this.plan.nodes.length) {
      return html`<div class="blank" style="padding:24px">${this.live ? msg('No tasks scheduled yet') : msg('No tasks scheduled')}</div>`;
    }
    const outcomes = taskOutcomes(this.journal, this.plan);
    const causeOf = (key: string) => {
      const t = outcomes.get(key);
      return t ? notStartedCause(t, outcomes, this.run) : '';
    };
    const m = this.matrix;
    const body = m ? this.matrixView(m, causeOf) : this.asTable ? this.table() : this.dag(causeOf);
    return html`${this.crumbs()}${body}
      <div class="foot">
        ${this.asTable && !m ? nothing : this.legend()}
        ${this.asTable || m ? nothing : this.tools()}
        ${m
          ? nothing
          : html`<button type="button" class="switch" @click=${() => (this.asTable = !this.asTable)}>
              ${this.asTable ? msg('Show as graph') : msg('Show as table')}
            </button>`}
        ${this.asTable && !m ? nothing : html`<div class="keys">${this.keyHints().map((k, i) => html`${i ? ' | ' : ''}<span>${k}</span>`)}</div>`}
      </div>`;
  }

  /** The keys of the view shown. */
  private keyHints(): string[] {
    const up = parentLayer(this.segments, this.auto) ? msg('Esc: up a level') : '';
    const keys = this.matrix
      ? [msg('Arrow keys: marks'), msg('Enter: open'), up]
      : [msg('Tab: next node'), msg('Arrow keys: marks'), msg('Shift + arrow keys: earlier and later tasks'), msg('Enter: open'), up];
    return keys.filter(Boolean);
  }

  private dag(causeOf: (key: string) => string) {
    const graph = this.graphView(causeOf);
    const v = this.view;
    return html`<div class="frame ${this.down ? 'down' : ''}" style="height:${Math.round(this.frameH)}px"
        @pointerdown=${(e: PointerEvent) => this.onPointerDown(e)} @pointermove=${(e: PointerEvent) => this.onPointerMove(e)}
        @pointerup=${(e: PointerEvent) => this.onPointerUp(e)} @pointercancel=${(e: PointerEvent) => this.onPointerUp(e)}>
        <div class="stage" style="transform:translate(${v.x}px,${v.y}px) scale(${v.k})">${graph}</div>
      </div>`;
  }

  /** Where an item is drawn, from its parent's corner (a loop box's, inside its border), or hidden until laid out. */
  private at(id: string, parent: Rect | null): string {
    const r = this.lay?.at[id];
    if (!r) return 'left:0;top:0';
    const dx = parent ? parent.x + 1 : 0;
    const dy = parent ? parent.y + 1 : 0;
    return `left:${r.x - dx}px;top:${r.y - dy}px`;
  }

  private graphView(causeOf: (key: string) => string) {
    const on = this.lit();
    const g = this.graph;
    const lay = this.lay;
    const nodes = new Map(g.nodes.map((n) => [n.id, n]));
    const boxes = new Map(g.boxes.map((b) => [b.id, b]));
    const stubs = new Map(g.stubs.map((s) => [s.id, s]));
    const items = (container: string): string[] => (g.slots[container] ?? []).flat().filter((id) => !isPoint(id));
    const item = (id: string, parent: Rect | null): unknown => {
      const b = boxes.get(id);
      if (b) return this.box(b, parent, (x, r) => item(x, r));
      const s = stubs.get(id);
      if (s) return html`<span class="stub" data-id=${s.id} style=${this.at(s.id, parent)} title=${msg('Outside this layer')}>${s.label}</span>`;
      const n = nodes.get(id);
      return n ? this.node(n, parent, causeOf, on) : nothing;
    };
    // Unplaced until a layout of this structure exists: the first render only measures.
    const placed = !!lay && g.nodes.every((n) => lay.at[n.id]);
    const w = lay?.w ?? 0;
    const h = lay?.h ?? 0;
    return html`<div class="dag ${this.down ? 'down' : ''} ${on ? 'hl' : ''} ${placed ? '' : 'unplaced'}" style="width:${w}px;height:${h}px"
      @mouseleave=${() => (this.hover = null)}>
      <svg class="edges" aria-hidden="true" width=${w} height=${h}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0,0.5 L8,4 L0,7.5 z" fill="var(--line2)" stroke="none"></path>
          </marker>
        </defs>
        ${(lay?.edges ?? []).map((e) => svg`<path class=${e.type} d=${edgePath(e.runs, lay?.down)} marker-end="url(#arr)"></path>`)}
      </svg>
      ${repeat(items(''), (id) => id, (id) => item(id, null))}
    </div>`;
  }

  private box(b: LoopBox, parent: Rect | null, item: (id: string, r: Rect | null) => unknown) {
    const r = this.lay?.at[b.id] ?? null;
    const enter = () => this.go([...this.segments, b.id]);
    const where = msg(str`Loop at ${this.where(b.loop, b.file)}`);
    const spread = b.spread.length > 1 ? passSpread(b.spread) : '';
    const kids = (this.graph.slots[b.id] ?? []).flat().filter((id) => !isPoint(id));
    const size = r ? `;width:${r.w}px;height:${r.h}px` : '';
    return html`<section class="box" role="group" data-box=${b.id} style=${this.at(b.id, parent) + size}
        aria-label=${facts(where, passCount(b.passes), spread)}>
      <div class="hd" data-id=${`lbl:${b.id}`}>
        <span class="line">
          <button type="button" class="name" title=${where} aria-label=${msg('Show the passes of the loop')} @click=${enter}>${loopLabel()}</button>
          <span class="count">${passCount(b.passes)}</span>
        </span>
        ${spread ? html`<span class="spread" title=${msg('Units by number of passes')}>${spread}</span>` : nothing}
      </div>
      <span class="ret" title=${msg('Next pass')} aria-hidden="true">
        <svg width="14" height="10" viewBox="0 0 14 10"><path d="M11.5,3.5 A4.5,3.6 0 1 1 7,0.9" fill="none" stroke="currentColor" stroke-width="1.4"></path>
          <path d="M6,0 L8.6,1 L6.4,2.9 z" fill="currentColor"></path></svg>
      </span>
      <div class="in">${repeat(kids, (id) => id, (id) => item(id, r))}</div>
    </section>`;
  }

  private node(n: GraphNode, parent: Rect | null, causeOf: (key: string) => string, on: Set<string> | null) {
    const c = n.counts;
    const fin = c.done + c.skipped;
    const look = c.failed || n.errors ? 'fail' : c.running ? 'cur' : fin === c.total ? 'done' : '';
    const bar = asBar(n);
    const group: MarkGroup = bar
      ? { id: n.id, label: n.label, slots: slotsOf(n).filter((m): m is GraphMark => m?.state === 'failed'), grid: { cols: BAR_LIST, size: 12, gap: 4 } }
      : { id: n.id, label: n.label, slots: slotsOf(n), grid: gridOf(n, this.graph.units.length) };
    const ex = this.exceptions(n);
    const name =
      n.type === 'flow'
        ? html`<button type="button" class="name" title=${facts(msg(str`Function ${n.name}`), msg(str`${n.calls} flow calls`))}
            aria-label=${msg(str`Open ${n.label}`)} @click=${() => this.go([...this.graph.path, n.name])}>${n.label}</button>`
        : html`<button type="button" class="name" aria-label=${msg(str`Show the tasks of ${n.label}`)}
            @click=${() => emit(this, 'ca-navigate', n.kinds.length === 1 ? { tab: 'tasks', kind: n.kinds[0] } : { tab: 'tasks' })}>${n.label}</button>`;
    return html`<section class="node ${n.type} ${look}" role="group" data-id=${n.id} aria-label=${this.nodeLabel(n)}
      style="${this.at(n.id, parent)};--cols:${group.grid.cols};--m:${group.grid.size}px;--g:${group.grid.gap}px">
      <div class="hd">${name}<span class="count" aria-hidden="true" title=${this.doneOf(c)}>${fin}/${c.total}</span></div>
      ${bar ? this.statusBar(n, group, causeOf, on) : this.marks(group, causeOf, on)}
      ${ex.length ? html`<div class="ex" aria-hidden="true">${ex.map(([cls, t]) => html`<span class=${cls}>${t}</span>`)}</div>` : nothing}
    </section>`;
  }

  /** A node with too many marks to draw: a bar of its counts, and its failed marks by name. */
  private statusBar(n: GraphNode, g: MarkGroup, causeOf: (key: string) => string, on: Set<string> | null) {
    const parts = barParts(n.counts, LEGEND);
    const shown = g.slots.slice(0, BAR_LIST);
    const more = g.slots.length - shown.length;
    const active = Math.min(this.active.get(g.id) ?? 0, Math.max(0, shown.length - 1));
    return html`<div class="sbar" role="img" aria-label=${this.stateCounts(n.counts)}>
        ${parts.map((p) => html`<i class=${p.state} style="width:${p.pct}%" title=${this.countOf(p.state, p.n)}></i>`)}
      </div>
      ${shown.length
        ? html`<div class="fails" @keydown=${(e: KeyboardEvent) => this.onKey(e, { ...g, slots: shown, grid: { ...g.grid, cols: shown.length } })}>
            ${shown.map((m, i) => (m ? this.mark(g, m, i, i === active, causeOf, on, true) : nothing))}
            ${more > 0 ? html`<span>${msg(str`+${more}`)}</span>` : nothing}
          </div>`
        : nothing}`;
  }

  /** A group's marks, with one tab stop. */
  private marks(g: MarkGroup, causeOf: (key: string) => string, on: Set<string> | null) {
    const active = Math.min(this.active.get(g.id) ?? firstMark(g.slots), g.slots.length - 1);
    return html`<div class="marks ${g.grid.size >= 10 ? 'big' : ''}" @keydown=${(e: KeyboardEvent) => this.onKey(e, g)}>
      ${g.slots.map((m, i) => (m ? this.mark(g, m, i, i === active, causeOf, on) : html`<span class="slot"></span>`))}
    </div>`;
  }

  /** What a mark says: its name, state, passes, attempts, tasks and time, for its tooltip and its label. */
  private markText(label: string, m: GraphMark, causeOf: (key: string) => string, pass = ''): { name: string; parts: string[]; id: string } {
    const t = m.flow ? undefined : this.byKey.get(m.key);
    const name = kindUnit({ kind: label, unit: m.unit });
    const cause = !m.flow && m.state === 'blocked' ? causeOf(m.key) : '';
    const state = cause ? msg(str`Not started: ${cause}`) : this.stateWord(m.state);
    const attempts = t?.attempts ?? 1;
    const tries = attempts > 1 ? msg(str`${attempts} attempts`) : '';
    const passes = m.passes ? passesRan(m.passes) : '';
    const many = m.flow || m.count > 1 ? msg(str`${m.count} tasks`) : '';
    // A flow call's tasks that are not done, and its own error: what its state comes from.
    const not = m.counts ? this.notDone(m.counts) : [];
    const error = m.error === undefined ? [] : [msg('Flow call stopped with an error'), m.error];
    const time = !m.flow && (m.state === 'done' || m.state === 'failed') && t?.wall_s ? fmtDur(t.wall_s) : '';
    return { name, parts: [state, pass, passes, tries, many, ...not, ...error, time].filter(Boolean), id: m.flow ? msg(str`Flow call ${m.key}`) : m.key };
  }

  /** Open a mark: a task (on its input when it did not start, a Python task on its output), or a flow call's function. */
  private open(m: GraphMark): void {
    if (m.flow) return this.go([...this.graph.path, m.flow], m.unit || this.unit);
    const t = this.byKey.get(m.key);
    emit(this, 'ca-open-task', m.state === 'blocked' ? { key: m.key, view: 'input' } : t?.executor === 'python' ? { key: m.key, view: 'output' } : { key: m.key });
  }

  private mark(g: MarkGroup, m: GraphMark, i: number, tabStop: boolean, causeOf: (key: string) => string, on: Set<string> | null, chip = false) {
    const { name, parts, id } = this.markText(g.label, m, causeOf);
    const hlKey = m.unit || m.key;
    const lit = on !== null && ((m.unit !== '' && m.unit === this.hl) || m.keys.some((k) => on.has(k)));
    const focus = (e: FocusEvent) => {
      this.hover = hlKey;
      this.active.set(g.id, i);
      this.reveal(e.currentTarget as HTMLElement);
    };
    if (chip) {
      return html`<button type="button" class="taskchip ${lit ? 'on' : ''}" data-i=${i} tabindex=${tabStop ? 0 : -1}
        title=${[name, ...parts, id].join('\n')} aria-label=${facts(name, ...parts)}
        @mouseenter=${() => (this.hover = hlKey)} @focus=${focus} @blur=${() => (this.hover = null)} @click=${() => this.open(m)}>${m.unit || m.key}</button>`;
    }
    return html`<button type="button" class="mark ${m.state} ${lit ? 'on' : ''}" data-i=${i} data-n=${m.passes ?? nothing} tabindex=${tabStop ? 0 : -1}
      title=${[name, ...parts, id].join('\n')}
      aria-label=${facts(name, ...parts)}
      @mouseenter=${() => (this.hover = hlKey)}
      @focus=${focus}
      @blur=${() => (this.hover = null)}
      @click=${() => this.open(m)}></button>`;
  }

  // ---- a loop's passes ----

  /** A loop's passes: a row per unit, a column per node and pass, the nested loops' passes as nested groups of columns. */
  private matrixView(mx: PassMatrix, causeOf: (key: string) => string) {
    const rows = sortRows(mx.rows, this.sort);
    const cols = mx.columns;
    const hl = this.hl;
    // Where a group of columns starts: 0 at a pass of the loop shown, 1 at a pass of a loop in it, ...
    const starts = cols.map((c, i) => {
      const p = cols[i - 1]?.passes;
      if (!p) return -1;
      const k = c.passes.findIndex((x, j) => x !== p[j]);
      return k < 0 ? (c.passes.length !== p.length ? Math.min(c.passes.length, p.length) : -1) : k;
    });
    const groupCls = (ci: number) => (starts[ci] === 0 ? 'g0' : (starts[ci] ?? -1) > 0 ? 'g1' : '');
    const headRows = mx.head.length;
    // The rows in view (all of them up to `WINDOW_AT`).
    const many = rows.length > WINDOW_AT;
    const from = many ? Math.max(0, this.scrollRow - OVERSCAN) : 0;
    const to = many ? Math.min(rows.length, this.scrollRow + 2 * OVERSCAN + 20) : rows.length;
    const cur = this.cell && this.cell[0] < rows.length ? this.cell : this.firstCell(rows);
    const units = mx.rows.filter((r) => r.unit).length;
    // A header cell's class: where a group of columns starts.
    const headCls = (col: number) => (col === 0 || starts[col] === 0 ? 'g0' : (starts[col] ?? -1) > 0 ? 'g1' : '');
    const headCell = (h: MatrixHead, col: number, level: number) => {
      const style = `top:${level * 22}px`;
      if (h.type === 'pass')
        return html`<th scope="colgroup" colspan=${h.span} class="pass ${headCls(col)}" style=${style}
          title=${h.box.id === mx.box.id ? msg(str`Loop at ${this.where(h.box.loop, h.box.file)}`) : msg(str`Nested loop at ${this.where(h.box.loop, h.box.file)}`)}>${passLabel(h.pass)}</th>`;
      if (h.type === 'loop')
        return html`<th scope="colgroup" colspan=${h.span} class="loop ${headCls(col)}" style=${style}
          title=${msg(str`Nested loop at ${this.where(h.box.loop, h.box.file)}`)}>${loopLabel()}</th>`;
      return html`<th scope="col" rowspan=${h.rows} class="nh ${headCls(col)}" style=${style}
        title=${h.node.type === 'flow' ? msg(str`Function ${h.node.name}`) : h.node.label}>${h.node.label}</th>`;
    };
    // The column each cell of a header row starts at: a cell under one that spans down starts after it.
    const firstCols = (level: number) => {
      const out: number[] = [];
      let c = 0;
      for (const h of mx.head[level] ?? []) {
        while (spannedAt(mx.head, level, c)) c++;
        out.push(c);
        c += h.span;
      }
      return out;
    };
    return html`<div class="mxbar">
        <span>${facts(msg(str`Loop at ${this.where(mx.box.loop, mx.box.file)}`), passCount(mx.box.passes), mx.box.spread.length > 1 ? passSpread(mx.box.spread) : '', units === 1 ? msg('1 unit') : msg(str`${units} units`))}</span>
        <label>${msg('Sort units')}
          <select @change=${(e: Event) => (this.sort = (e.target as HTMLSelectElement).value as MatrixSort)}>
            <option value="order" ?selected=${this.sort === 'order'}>${msg('Scheduled order')}</option>
            <option value="passes" ?selected=${this.sort === 'passes'}>${msg('Number of passes')}</option>
            <option value="state" ?selected=${this.sort === 'state'}>${msg('Status')}</option>
          </select>
        </label>
      </div>
      <div class="mx ${hl ? 'hl' : ''}" @scroll=${(e: Event) => this.onMatrixScroll(e)} @mouseleave=${() => (this.hover = null)}>
        <table class="matrix big" role="grid" aria-rowcount=${rows.length + headRows} aria-colcount=${cols.length + 2}
          aria-label=${facts(msg(str`Loop at ${this.where(mx.box.loop, mx.box.file)}`), passCount(mx.box.passes))}>
          <thead>
            ${mx.head.map((hr, level) => {
              const fc = firstCols(level);
              return html`<tr>
                ${level === 0
                  ? html`<th scope="col" rowspan=${headRows} class="uh" style="top:0">${msg('Unit')}</th>
                      <th scope="col" rowspan=${headRows} class="pn" style="top:0" title=${msg('Passes of this loop')}>${msg('Passes')}</th>`
                  : nothing}
                ${hr.map((h, i) => headCell(h, fc[i] ?? 0, level))}
              </tr>`;
            })}
          </thead>
          <tbody @keydown=${(e: KeyboardEvent) => this.onMatrixKey(e, rows)}>
            ${from > 0 ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + 2} style="height:${from * ROW_H}px"></td></tr>` : nothing}
            ${repeat(
              rows.slice(from, to),
              (r) => r.unit,
              (r, k) => {
                const ri = from + k;
                return html`<tr class=${r.unit && r.unit === hl ? 'on' : ''} aria-rowindex=${ri + headRows + 1}>
                  ${r.unit
                    ? html`<th scope="row" title=${r.unit}>${r.unit}</th>`
                    : html`<th scope="row" class="none" title=${msg('Tasks that run once per run, not once per unit')}>${msg('No unit')}</th>`}
                  <td class="pn ${r.passes > 1 ? 'many' : ''}">${r.passes}</td>
                  ${r.cells.map((m, ci) => {
                    const col = cols[ci];
                    const focusable = !!m && cur !== null && cur[0] === ri && cur[1] === ci;
                    return html`<td class="c ${groupCls(ci)}" role="gridcell">${m && col ? this.cellMark(r, m, ri, ci, col.node, col.passes, focusable, causeOf) : nothing}</td>`;
                  })}
                </tr>`;
              },
            )}
            ${to < rows.length ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + 2} style="height:${(rows.length - to) * ROW_H}px"></td></tr>` : nothing}
          </tbody>
        </table>
      </div>`;
  }

  private cellMark(r: MatrixRow, m: GraphMark, ri: number, ci: number, node: GraphNode, passes: number[], tabStop: boolean, causeOf: (key: string) => string) {
    const { name, parts, id } = this.markText(node.label, m, causeOf, passes.map(passLabel).join(', '));
    const hlKey = m.unit || m.key;
    return html`<button type="button" class="mark ${m.state} ${r.unit && r.unit === this.hl ? 'on' : ''}" data-r=${ri} data-c=${ci} tabindex=${tabStop ? 0 : -1}
      title=${[name, ...parts, id].join('\n')} aria-label=${facts(name, ...parts)}
      @mouseenter=${() => (this.hover = hlKey)}
      @focus=${() => {
        this.hover = hlKey;
        this.cell = [ri, ci];
      }}
      @blur=${() => (this.hover = null)}
      @click=${() => this.open(m)}></button>`;
  }

  /** The first mark of the sorted rows, as (row, column). */
  private firstCell(rows: readonly MatrixRow[]): [number, number] | null {
    for (let i = 0; i < rows.length; i++) {
      const j = rows[i]?.cells.findIndex((c) => c !== null) ?? -1;
      if (j >= 0) return [i, j];
    }
    return null;
  }

  private onMatrixScroll(e: Event): void {
    const top = Math.floor((e.currentTarget as HTMLElement).scrollTop / ROW_H);
    if (Math.abs(top - this.scrollRow) >= OVERSCAN / 2) this.scrollRow = top;
  }

  private onMatrixKey(e: KeyboardEvent, rows: readonly MatrixRow[]): void {
    const t = e.target as HTMLElement;
    if (!t.classList.contains('mark')) return;
    const r = Number(t.dataset['r']);
    const c = Number(t.dataset['c']);
    const has = rows.map((row) => row.cells.map((x) => x !== null));
    const next = gridStep(has, r, c, e.key, e.ctrlKey || e.metaKey);
    if (!next) return;
    e.preventDefault();
    this.cell = next;
    const box = this.renderRoot.querySelector<HTMLElement>('.mx');
    if (box && rows.length > WINDOW_AT) {
      // Bring the row into view first: only the rows in view are drawn.
      const y = next[0] * ROW_H;
      if (y < box.scrollTop + ROW_H * 2 || y > box.scrollTop + box.clientHeight - ROW_H * 3) box.scrollTop = Math.max(0, y - box.clientHeight / 2);
      this.scrollRow = Math.floor(box.scrollTop / ROW_H);
    }
    this.requestUpdate();
    void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(`.matrix .mark[data-r="${next[0]}"][data-c="${next[1]}"]`)?.focus());
  }

  /** How many tasks are in each state, in words: "2 done | 1 failed". */
  private stateCounts(c: NodeCounts): string {
    return facts(...LEGEND.filter((s) => c[s]).map((s) => this.countOf(s, c[s])));
  }

  /** How many tasks finished: "5 of 6 tasks done". */
  private doneOf(c: NodeCounts): string {
    return msg(str`${c.done + c.skipped} of ${c.total} tasks done`);
  }

  /** The tasks that are not done, by state, most severe first: "1 failed", "1 not started". */
  private notDone(c: NodeCounts): string[] {
    return (['failed', 'blocked', 'running', 'pending'] as const).filter((s) => c[s]).map((s) => this.countOf(s, c[s]));
  }

  /** A pending task waits while the run runs; once the run is over, it did not run. */
  private stateWord(s: TaskState): string {
    return s === 'pending' && !this.live ? msg('not run') : planStateLabel(s);
  }

  /** Where a loop is: `flow.py:130` (the file's name and the loop's first line), or `line 130` when the file is not known. */
  private where(line: number | string, file?: string): string {
    const name = file ? file.slice(file.lastIndexOf('/') + 1) : '';
    return name ? `${name}:${line}` : msg(str`line ${line}`);
  }

  /** How many marks are in a state, number first: "3 failed". */
  private countOf(s: TaskState, n: number): string {
    switch (s) {
      case 'blocked':
        return stateCount('not_started', n);
      case 'pending':
        return stateCount(this.live ? 'waiting' : 'not_run', n);
      default:
        return stateCount(s, n);
    }
  }

  /** What a node needs a word for: its tasks that are not done, by state, and its flow calls that stopped with an error. */
  private exceptions(n: GraphNode): [string, string][] {
    const c = n.counts;
    const out: [string, string][] = [];
    if (c.failed) out.push(['err', this.countOf('failed', c.failed)]);
    if (n.errors) out.push(['err', n.errors === 1 ? msg('1 flow call stopped with an error') : msg(str`${n.errors} flow calls stopped with an error`)]);
    if (c.blocked) out.push(['warn', this.countOf('blocked', c.blocked)]);
    if (c.running) out.push(['live', this.countOf('running', c.running)]);
    if (c.pending) out.push(['mut', this.countOf('pending', c.pending)]);
    return out;
  }

  /** The names of the nodes `n` waits for, was created after, and feeds. */
  private neighbours(n: GraphNode): { waits: string[]; after: string[]; feeds: string[] } {
    const g = this.graph;
    const label = (id: string) => {
      const x = g.nodes.find((y) => y.id === id);
      return !x ? id : x.box ? msg(str`${x.label} in the loop`) : x.label;
    };
    const into = (type: 'after' | 'created') => [
      ...g.stubs.filter((s) => s.to === n.id && s.type === type).map((s) => s.label),
      ...g.edges.filter((e) => e.to === n.id && e.type === type).map((e) => label(e.from)),
    ];
    return { waits: into('after'), after: into('created'), feeds: [...new Set(g.edges.filter((e) => e.from === n.id).map((e) => label(e.to)))] };
  }

  /** The node for a screen reader: its counts, and the nodes it waits for, was created after and feeds. */
  private nodeLabel(n: GraphNode): string {
    const c = n.counts;
    const { waits, after, feeds } = this.neighbours(n);
    return [
      n.type === 'flow' ? facts(msg(str`Function ${n.label}`), this.doneOf(c)) : facts(n.label, this.doneOf(c)),
      ...this.exceptions(n).map(([, t]) => t),
      waits.length ? msg(str`Waits for ${waits.join(', ')}`) : '',
      after.length ? msg(str`Created after ${after.join(', ')}`) : '',
      feeds.length ? msg(str`Later tasks: ${feeds.join(', ')}`) : '',
    ]
      .filter(Boolean)
      .join('. ');
  }

  /** Arrow keys, Home and End within a group's marks, skipping empty slots; Shift and an arrow key along an edge to another node. */
  private onKey(e: KeyboardEvent, g: MarkGroup): void {
    const target = e.target as HTMLElement;
    if (!target.classList.contains('mark') && !target.classList.contains('taskchip')) return;
    if (e.shiftKey && e.key.startsWith('Arrow')) return this.alongEdge(e, g);
    const { slots } = g;
    const cur = this.active.get(g.id) ?? firstMark(slots);
    const step: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: g.grid.cols, ArrowUp: -g.grid.cols };
    let next: number;
    if (e.key === 'Home') next = firstMark(slots);
    else if (e.key === 'End') next = slots.length - 1 - [...slots].reverse().findIndex((m) => m !== null);
    else if (step[e.key] !== undefined) {
      const d = step[e.key] as number;
      next = cur + d;
      while (next >= 0 && next < slots.length && !slots[next]) next += Math.sign(d);
      if (next < 0 || next >= slots.length) return;
    } else return;
    e.preventDefault();
    this.active.set(g.id, next);
    this.requestUpdate();
    const marks = e.currentTarget as HTMLElement;
    void this.updateComplete.then(() => marks.querySelector<HTMLElement>(`[data-i="${next}"]`)?.focus());
  }

  /** To the node an edge joins: a later one (Shift and → or ↓) or an earlier one (Shift and ← or ↑), on the same unit when it has a mark there. */
  private alongEdge(e: KeyboardEvent, g: MarkGroup): void {
    const dir = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 'later' : 'earlier';
    const lay = this.lay;
    const across = (id: string) => {
      const r = lay?.at[id];
      return !r ? 0 : lay?.down ? r.x + r.w / 2 : r.y + r.h / 2;
    };
    const to = alongEdge(this.graph, g.id, dir, across);
    e.preventDefault();
    if (!to) return;
    const n = this.graph.nodes.find((x) => x.id === to);
    if (!n) return;
    const unit = g.slots[this.active.get(g.id) ?? firstMark(g.slots)]?.unit ?? '';
    const slots = asBar(n) ? slotsOf(n).filter((m) => m?.state === 'failed') : slotsOf(n);
    const same = unit ? slots.findIndex((m) => m?.unit === unit) : -1;
    const i = same >= 0 ? same : (this.active.get(n.id) ?? firstMark(slots));
    this.active.set(n.id, i);
    this.requestUpdate();
    void this.updateComplete.then(() => {
      const node = this.renderRoot.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(to)}"]`);
      (node?.querySelector<HTMLElement>(`[data-i="${i}"]`) ?? node?.querySelector<HTMLElement>('.name'))?.focus();
    });
  }

  /** The states of the marks shown, the pass number when a mark shows one, and the kinds of edges when there is more than one. */
  private legend() {
    // The marks drawn: a node with a bar draws its failed marks only.
    const marks = this.matrix
      ? this.matrix.rows.flatMap((r) => r.cells)
      : this.graph.nodes.flatMap((n) => (asBar(n) ? slotsOf(n).map((m) => m && { ...m, passes: undefined }) : slotsOf(n)));
    const shown = marks.filter((m): m is GraphMark => m !== null);
    const present = new Set(shown.map((m) => m.state));
    const passes = !this.matrix && shown.some((m) => m.passes);
    const created = !this.matrix && [...this.graph.edges, ...this.graph.stubs].some((e) => e.type === 'created');
    const line = (dash: boolean) => svg`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${dash ? '5 4' : 'none'}></path></svg>`;
    return html`<div class="legend big">
      ${LEGEND.filter((s) => present.has(s)).map((s) => html`<span aria-hidden="true"><i class="mark ${s}"></i>${this.stateWord(s)}</span>`)}
      ${passes ? html`<span aria-hidden="true"><i class="mark done" data-n="2"></i>${msg('number of passes')}</span>` : nothing}
      ${created
        ? html`<span>${line(false)}${msg('waits for output')}</span><span>${line(true)}${msg('created after result')}</span>`
        : nothing}
    </div>`;
  }

  /** The same counts as a table: a row per node with the nodes it waits for and feeds. */
  private table() {
    const nodes = this.graph.nodes;
    const flows = nodes.some((n) => n.type === 'flow');
    const created = [...this.graph.edges, ...this.graph.stubs].some((e) => e.type === 'created');
    const boxes = new Map(this.graph.boxes.map((b) => [b.id, b]));
    return html`<table class="list">
      <thead>
        <tr>
          <th>${flows ? msg('Kind or function') : msg('Kind')}</th><th>${msg('Done')}</th><th>${msg('Failed')}</th><th>${msg('Not started')}</th>
          <th>${msg('Running')}</th><th>${this.live ? msg('Waiting') : msg('Not run')}</th><th>${msg('Waits for')}</th>
          ${created ? html`<th>${msg('Created after')}</th>` : nothing}<th>${msg('Later tasks')}</th>
        </tr>
      </thead>
      <tbody>
        ${nodes.map((n) => {
          const c = n.counts;
          const { waits, after, feeds } = this.neighbours(n);
          const box = n.box ? boxes.get(n.box) : undefined;
          const name = n.type === 'flow' ? html`<button type="button" class="name" @click=${() => this.go([...this.graph.path, n.name])}>${n.label}</button>` : n.label;
          return html`<tr>
            <th scope="row">${name}${box
              ? html` <button type="button" class="switch" title=${msg('Show the passes of the loop')} @click=${() => this.go([...this.segments, box.id])}>${facts(loopLabel(), passCount(box.passes))}</button>`
              : nothing}</th>
            <td class="n">${c.done + c.skipped}/${c.total}</td><td class="n">${c.failed}</td><td class="n">${c.blocked}</td>
            <td class="n">${c.running}</td><td class="n">${c.pending}</td>
            <td>${waits.join(', ') || msg('none')}</td>
            ${created ? html`<td>${after.join(', ') || msg('none')}</td>` : nothing}<td>${feeds.join(', ') || msg('none')}</td>
          </tr>`;
        })}
      </tbody>
    </table>`;
  }
}

/** The first slot that holds a mark. */
function firstMark(slots: readonly (GraphMark | null)[]): number {
  return Math.max(0, slots.findIndex((m) => m !== null));
}

/** A header row's column `c` is under a cell of an earlier row that spans down past it. */
function spannedAt(head: readonly MatrixHead[][], level: number, c: number): boolean {
  for (let l = 0; l < level; l++) {
    let x = 0;
    for (const h of head[l] ?? []) {
      if (c >= x && c < x + h.span && l + h.rows > level) return true;
      x += h.span;
    }
  }
  return false;
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-pipeline-graph': CaPipelineGraph;
  }
}
