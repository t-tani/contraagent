import { deriveRun, isLaunched, planOutcome, type JournalRow, type Plan, type PlanNode, type TaskState } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, svg, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { keyed } from 'lit/directives/keyed.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { facts, fmtDur, kindUnit, usd } from '../../lib/format.js';
import { loopLabel, notStartedCause, passCount, passLabel, passSpread, passesRan, stateCount, statusLabel } from '../../lib/labels.js';
import { base } from '../../styles/base.js';
import { PAD, placeCard, type Box } from './place-card.js';
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
  markSel,
  parentLayer,
  passMatrix,
  resolveLayer,
  returnPath,
  selected,
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
  type Selected,
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

/** A loop: a circle that comes back round to where it started, its head at the top right. */
const loopIcon = (size = 14) =>
  html`<svg class="ic loop-ic" width=${size} height=${size} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
    <path d="M12.7,9.71 A5,5 0 1 1 11.21,4.17" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"></path>
    <path d="M12.44,5.2 L9.15,5.06 L11.73,2 z" fill="currentColor"></path>
  </svg>`;

/** Something with an inner view (a function's layer, a loop's passes): two cards, one behind the other, as a function node is drawn. */
const innerIcon = () =>
  html`<svg class="ic in-ic" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
    <rect x="3.4" y="0.7" width="7.9" height="7.9" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.2"></rect>
    <path d="M0.7,3.6 V9.7 Q0.7,11.3 2.3,11.3 H8.4" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"></path>
  </svg>`;

/** Who runs a kind node's tasks, as the Tasks list shows it: ✦ a coding agent, ⚙ Python. */
const exIcon = (python: boolean) => html`<span class="k-ic ${python ? '' : 'llm'}" aria-hidden="true">${python ? '⚙' : '✦'}</span>`;

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
 * ("1 pass: 4 | 2 passes: 1"); a nested loop's box is inside it, and a dotted edge
 * inside each box, from its last layer back to its first, is the return to its next
 * pass. A kind node names who runs its tasks (✦ and an accent: an agent task; ⚙: a
 * Python task); a function node and a loop box carry the mark of an inner view (their
 * layer, their passes). Inside a node, one mark per unit, at the same place in every
 * node, so a unit can be followed across the layer: a task in a kind node, a flow
 * call in a function node; in a loop box, the unit's latest pass, with the number of
 * passes it ran when more than 1. A mark of several tasks shows the most severe state
 * among them (failed, running, not started, waiting, skipped, done); a flow call's
 * mark counts every task of it and of the flow calls it started, and its own error
 * (raised or closed) as failed. A node's count is its tasks done of its tasks, with
 * the others by state, and a function node names its flow calls that stopped with an
 * error. A problem has a square mark (failed: red; not started: hatched), every other
 * state a round one. Above 200 marks, a node shows a bar of its counts and names its
 * failed marks. A solid edge waits for an output; a dashed edge was created after a
 * result; an edge from outside the layer starts at a named stub.
 *
 * The layout is layered: each layer of the flow in a column, an edge bending only
 * in the gaps between columns and never passing a node or a box's label, a loop's
 * return in a band past its box's content. It depends on the flow's structure only,
 * so it stays still while the run progresses; nodes that appear later are added at
 * the end of their layer.
 *
 * A click selects a mark, a node or a loop box (`sel`); a card beside it in the frame
 * (it moves with the item as the graph pans and zooms, and hides while the item is out
 * of the frame; a sheet under the frame on a narrow screen) shows its facts and links to where it leads:
 * a mark to its task detail, a kind node to its tasks, a function node to its layer,
 * a loop box to its passes. A double click, or Enter, follows the first of them.
 * Hovering or focusing a mark highlights its unit and the tasks joined to it, as the
 * selected mark does. The graph opens on the first layer with more than one node (a
 * static flow's kinds), or on a single function node whose flow call raised; a layer
 * the run does not have opens that one, with a line naming it, and the route is set
 * right in place (a function named by its qualified name alone opens its layer when
 * the run reaches it by one flow path). A loop's passes are a row per unit and a
 * column per node and pass, a nested loop's passes as a group of columns inside each
 * pass of the outer one, the units sortable by number of passes or by status; narrower
 * than the frame, they are in its middle, under a line as wide as they are. The
 * breadcrumb, shown on every layer below the top (a loop named by its file and line),
 * and Escape go back up. The graph
 * runs left to right in a frame that first shows all of it; Ctrl (or ⌘) and the
 * wheel, or the buttons, zoom; dragging pans; "Show all" goes back to the whole
 * graph. On a narrow screen it runs top to bottom instead.
 *
 * Keyboard: Tab moves between nodes; the arrow keys, Home and End move between a
 * node's marks, and a mark out of the frame is brought into it; Shift and an arrow
 * key move along an edge to an earlier or a later node, on the same unit when it is
 * there; what has the focus is selected (the focus stays on it, and Tab goes on to the
 * card's links); Enter follows the selection's first link;
 * Escape clears the selection, then goes up, back to the node it came from. In a
 * loop's passes, the arrow keys, Home, End, Page Up and Page Down move between the
 * marks.
 *
 * Every view is drawn in one frame, which keeps its height across a change of view;
 * "Graph | Table", at the right end of the row under it, changes the view. The table
 * is a row per node: its status as the node shows it ("28/30 | 1 failed"), and the
 * nodes it waits for, was created after and feeds; a row is selected as a node is,
 * with the same card (Tab moves between rows). A loop's passes are its layer's table:
 * there "Graph" opens the layer the loop is in, with its box selected.
 *
 * @fires ca-open-task - `{key, view?}`: a mark's task detail was opened (a task that did not start opens on its input, a Python task on its output)
 * @fires ca-navigate - `{sel}`: a mark, a node, a table row or a loop box was selected, or the selection cleared; `{tab: 'tasks', kind}`: a kind node's tasks (`kind` '' for a node of several kinds); `{layer, unit?}`: a function's layer, a loop's passes, a flow call's function or the breadcrumb, or Escape; `{layer, unit, sel}`: "Graph" in a loop's passes, its box selected; `{layer, unit, sel, replace: true}`: the route's layer set right
 */
@customElement('ca-pipeline-graph')
@localized()
export class CaPipelineGraph extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }

      /* One frame for every view of a layer: the graph, the table and a loop's passes. */
      .frame { position: relative; overflow: hidden; border-radius: 8px; background: var(--well); box-sizing: border-box; }
      .gframe { cursor: grab; touch-action: none; }
      .gframe.drag { cursor: grabbing; }
      .stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
      .gframe.down { touch-action: pan-y pinch-zoom; }
      /* A view's content fades in when the view changes; the frame stays. */
      .view { animation: view-in 0.1s var(--ease) both; }
      @keyframes view-in { from { opacity: 0; } }
      @media (prefers-reduced-motion: reduce) { .view { animation: none; } }
      .tools { display: flex; align-items: center; gap: 4px; justify-self: end; }
      .tools button { all: unset; cursor: pointer; min-width: 22px; height: 22px; padding: 0 7px; box-sizing: border-box; text-align: center;
        font-size: 11.5px; line-height: 22px; color: var(--text-2); border-radius: 6px; border: 1px solid var(--line); }
      .tools button:hover:not(:disabled) { color: var(--text); border-color: var(--line2); }
      .tools button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .tools button:disabled { cursor: default; opacity: 0.4; }
      /* Graph | Table: the pressed one is raised, as the header's language switch. */
      .views { display: inline-flex; margin-left: 6px; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
      .tools .views button { height: 20px; line-height: 20px; padding: 0 10px; border: 0; border-radius: 0; color: var(--text-muted); }
      .tools .views button + button { border-left: 1px solid var(--line); }
      .tools .views button[aria-pressed='true'] { background: var(--raise); color: var(--text); cursor: default; }
      .tools .views button:focus-visible { outline-offset: -2px; }

      .dag { position: relative; }
      .dag.unplaced { visibility: hidden; }
      .dag > *, .box > .in > * { position: absolute; }
      .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
      .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
      .edges path.created { stroke-dasharray: 5 4; }
      /* A loop's return to its next pass: dotted, lighter than the edges, under the box's nodes. */
      .edges path.ret, .legend svg path.ret { stroke: var(--text-2); stroke-width: 2; stroke-dasharray: 0.1 4; stroke-linecap: round; opacity: 0.8; }
      .edges path.ret-tip, .legend svg path.ret-head { fill: var(--text-2); stroke: none; opacity: 0.8; }
      .ic { display: block; flex: none; }
      .loop-ic { color: var(--text-2); }
      .in-ic { color: var(--text-muted); }
      .unset { visibility: hidden; }

      .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); padding: 3px 9px;
        border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

      .box { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: color-mix(in srgb, var(--text-muted) 5%, transparent); }
      .box .box { background: color-mix(in srgb, var(--text-muted) 6%, transparent); }
      .box > .in { position: absolute; inset: 0; pointer-events: none; }
      .box > .in > * { pointer-events: auto; }
      /* Room on the right for the mark of an inner view: the box is as wide as its label. */
      .box > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
        white-space: nowrap; justify-content: flex-start; padding-right: 22px; }
      .box > .hd .line { display: flex; align-items: center; gap: 8px; }
      .box > .hd .name { display: inline-flex; align-items: center; gap: 5px; }
      .box > .hd { cursor: pointer; }
      .box.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
      .box > .hd .spread { font-size: 11px; color: var(--text-2); font-variant-numeric: tabular-nums; }

      .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
        display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
        border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s;
        cursor: pointer; box-shadow: var(--ex, 0 0 0 0 transparent); }
      /* An agent task's node: a thin accent along its left side, the colour the timeline gives agent tasks; a Python task's stays neutral. */
      .node.agent { --ex: inset 3px 0 0 -1px color-mix(in srgb, var(--agent) 60%, transparent); }
      .node .k-ic { width: 16px; height: 16px; margin-right: 6px; border-radius: 4px; font-size: 9.5px; }
      .node .nm { display: flex; align-items: center; min-width: 0; gap: 0; }
      .node .right { display: flex; align-items: center; gap: 8px; }
      /* The mark of an inner view: at the top right of a function node and of a loop box alike. */
      .cue { display: block; line-height: 0; }
      .box > .cue { position: absolute; top: 9px; right: 10px; }
      .node.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
      .node.flow { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
      .node.cur { border-color: var(--status-running); }
      .node.flow.cur { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--status-running), 0 0 14px var(--status-running-bg); }
      .node:not(.flow).cur { box-shadow: var(--ex, 0 0 0 0 transparent), 0 0 14px var(--status-running-bg); }
      .node.fail { border-color: color-mix(in srgb, var(--status-failed) 55%, transparent); }
      .node:focus-within { border-color: var(--text-2); }
      .hd { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
      .name { all: unset; cursor: pointer; font-family: var(--mono); font-weight: 600; font-size: 12.5px; color: var(--text);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
      .name:hover { text-decoration: underline; }
      .name:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .count { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .ex { display: flex; flex-wrap: wrap; gap: 0 10px; font-size: 11px; line-height: 1.5;
        max-width: max(98px, calc(var(--cols) * var(--m) + (var(--cols) - 1) * var(--g))); }
      .ex .err { color: var(--status-failed); }
      .ex .warn { color: var(--status-attention); }
      .ex .live { color: var(--status-running); }
      .ex .mut { color: var(--text-muted); }

      .marks { display: grid; grid-template-columns: repeat(var(--cols), var(--m)); gap: var(--g); }
      .slot { width: var(--m); height: var(--m); }
      .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--status-done); opacity: 0.9;
        cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
      .mark.skipped { background: var(--status-muted); opacity: 0.55; }
      .mark.running { background: var(--status-running); opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
      .mark.pending { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line2); }
      .mark.blocked { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, color-mix(in srgb, var(--status-attention) 55%, transparent) 2px 3px);
        box-shadow: inset 0 0 0 1.5px var(--status-attention); opacity: 1; }
      .mark.failed { border-radius: 2px; background: var(--status-failed); opacity: 1; }
      .big .mark.failed::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: var(--bg);
        font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
      /* A unit that ran more than 1 pass: its number in the mark; a small mark has a hole instead. */
      .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
      .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
        font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: var(--bg); letter-spacing: -0.5px; }
      .big .mark.failed[data-n]::after, .big .mark.running[data-n]::after { color: var(--bg); }
      .big .mark.pending[data-n]::after, .big .mark.blocked[data-n]::after, .big .mark.skipped[data-n]::after { color: var(--text); }
      .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: var(--focus-width) solid var(--text); outline-offset: 1px; z-index: 2; }
      .mark.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; z-index: 2; }
      .taskchip.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 1px; }
      .hl .mark:not(.on) { opacity: 0.16; }
      .hl .mark.on { transform: scale(1.2); }
      .mx.hl .mark:not(.on) { opacity: 0.4; }
      @media (prefers-reduced-motion: reduce) {
        .mark, .node { transition: none; }
        .mark.running { animation: none; background: linear-gradient(90deg, var(--status-running) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--status-running); }
      }

      .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
      .sbar i { display: block; min-width: 2px; height: 100%; }
      .sbar .done { background: var(--status-done); opacity: 0.85; }
      .sbar .running { background: var(--status-running); }
      .sbar .pending { background: var(--line2); }
      .sbar .failed { background: var(--status-failed); }
      .sbar .blocked { background: repeating-linear-gradient(135deg, var(--status-attention-bg) 0 2px, color-mix(in srgb, var(--status-attention) 60%, transparent) 2px 3px); }
      .sbar .skipped { background: var(--status-muted); opacity: 0.5; }
      .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--text-muted); }
      .fails .taskchip { color: var(--status-failed); border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); }
      .fails .taskchip:focus-visible { outline: var(--focus-width) solid var(--text); outline-offset: 1px; }
      .hl .fails .taskchip:not(.on) { opacity: 0.4; }

      /* A loop's passes: centred in the frame, the line above as wide as the table (it adds no width of its own). */
      .mxframe { display: grid; grid-template-columns: minmax(0, 1fr); place-items: center; padding: 14px 16px; }
      /* At least wide enough for the loop's name and the sort beside it: a narrower table is stretched to it. */
      .mxblock { display: flex; flex-direction: column; width: fit-content; max-width: 100%; min-width: min(100%, 27rem); }
      .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; margin-bottom: 8px; font-size: 12px; color: var(--text-2);
        width: 0; min-width: 100%; box-sizing: border-box; }
      .mxbar .cap { color: var(--text); font-weight: 600; }
      .mxbar .sum { flex: 1 0 100%; min-width: 0; }
      .mxbar .f { white-space: nowrap; }
      .sep { color: var(--text-muted); }
      .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--text-muted); font-size: 11.5px; white-space: nowrap; }
      .mxbar select { font: inherit; font-size: 11.5px; color: var(--text); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
      .mxbar select:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .mx { overflow: auto; max-width: 100%; max-height: max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh); border-radius: 6px; border: 1px solid var(--line); }
      table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: 100%; min-width: max-content; }
      .matrix th, .matrix td { padding: 0 6px; height: ${ROW_H}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
      .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--text-muted); font-weight: 500; text-align: center; height: 22px; }
      .matrix thead th.nh { font-family: var(--mono); color: var(--text-2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
      .matrix thead th.pass { color: var(--text-2); }
      .matrix thead th.loop { font-family: var(--mono); }
      .matrix .uh, .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--panel); text-align: left; }
      .matrix thead .uh { z-index: 3; }
      .matrix thead .uh, .matrix thead .pn { background: var(--panel2); }
      .matrix tbody th { font-family: var(--mono); font-weight: 600; color: var(--text); max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
      .matrix tbody th.none { font-family: var(--sans); font-weight: 500; color: var(--text-muted); }
      .matrix .pn { text-align: right; color: var(--text-muted); font-variant-numeric: tabular-nums; }
      .matrix .pn.many { color: var(--text); font-weight: 600; }
      .matrix td.c { text-align: center; --m: 12px; }
      .matrix td.c .mark { vertical-align: middle; }
      .matrix .g0 { border-left: 1px solid var(--line2); }
      .matrix .g1 { border-left: 1px dashed var(--line); }
      .matrix tbody tr:hover td, .matrix tbody tr:hover th { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
      .matrix tbody tr.on td, .matrix tbody tr.on th { background-color: var(--accent-bg); }
      .matrix .gap td { padding: 0; border: 0; }

      .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; }
      .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; list-style: none; margin: 0; padding: 0; }
      .crumbs li { display: inline-flex; align-items: center; gap: 4px; }
      .crumbs .sep { color: var(--text-muted); }
      .crumbs button { all: unset; cursor: pointer; color: var(--accent); font-family: var(--mono); }
      .crumbs button:hover { text-decoration: underline; }
      .crumbs button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .crumbs [aria-current] { font-family: var(--mono); color: var(--text); font-weight: 600; }
      .pin { display: inline-flex; align-items: center; gap: 8px; color: var(--text-2); }
      .pin b { font-family: var(--mono); }

      /* The legend on the left, the tools at the right end of the first line, in every view. */
      .foot { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 6px 14px; margin-top: 6px; }
      .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--text-muted); }
      .legend > span { white-space: nowrap; }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .legend .mark { --m: 12px; cursor: default; animation: none; }
      .legend .mark:hover { transform: none; outline: none; }
      .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }
      .legend .k-ic { width: 14px; height: 14px; margin: 0; border-radius: 4px; font-size: 8.5px; }
      .list .k-ic { width: 16px; height: 16px; border-radius: 4px; font-size: 9.5px; }
      .matrix thead th.nh .k-ic { width: 14px; height: 14px; margin-right: 5px; border-radius: 4px; font-size: 8.5px; vertical-align: -2px; }

      .main { position: relative; min-width: 0; }
      .missing { margin-bottom: 8px; font-size: 12px; color: var(--status-attention); }
      .missing code { font-family: var(--mono); }

      /* the selection's card: beside the item, joined to it by a pointer, in the accent of the item's outline */
      .insp { position: absolute; left: 0; top: 0; z-index: 6; width: 272px; max-width: calc(100% - 16px); box-sizing: border-box;
        display: flex; flex-direction: column; gap: 9px; padding: 10px 12px 12px; border-radius: 10px;
        border: 1px solid var(--accent); background: var(--card); font-size: 12px; overflow: visible;
        box-shadow: 0 12px 32px color-mix(in srgb, var(--shadow) 55%, transparent); visibility: hidden;
        animation: insp-in 0.12s var(--ease) both; }
      .insp.placed { visibility: visible; }
      .insp .scroll { display: flex; flex-direction: column; gap: 9px; min-height: 0; overflow: auto; }
      .insp .ptr { position: absolute; width: 10px; height: 10px; background: var(--card); border: 1px solid var(--accent);
        transform: rotate(45deg); }
      .insp[data-side='right'] .ptr { left: -6px; top: calc(var(--arrow) - 5px); border-top: 0; border-right: 0; }
      .insp[data-side='left'] .ptr { right: -6px; top: calc(var(--arrow) - 5px); border-bottom: 0; border-left: 0; }
      .insp[data-side='below'] .ptr { top: -6px; left: calc(var(--arrow) - 5px); border-bottom: 0; border-right: 0; }
      .insp[data-side='above'] .ptr { bottom: -6px; left: calc(var(--arrow) - 5px); border-top: 0; border-left: 0; }
      /* a narrow screen: a sheet under the frame, naming the item */
      .insp.sheet { position: sticky; bottom: 8px; width: auto; max-width: none; margin-top: 8px; visibility: visible; }
      .insp.sheet .ptr { display: none; }
      @keyframes insp-in { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: none; } }
      .insp h4 { margin: 0; display: flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 13px; font-weight: 600;
        color: var(--text); overflow-wrap: anywhere; }
      .insp h4 .mark { --m: 11px; flex: none; cursor: default; animation: none; }
      .insp h4 .mark:hover { transform: none; outline: none; }
      .insp h4 .k-ic { width: 18px; height: 18px; margin: 0; border-radius: 5px; font-size: 10px; }
      .insp .sub { color: var(--text-2); }
      .insp dl { display: grid; grid-template-columns: fit-content(42%) minmax(0, 1fr); gap: 4px 12px; margin: 0; }
      .insp dt { color: var(--text-muted); word-break: keep-all; overflow-wrap: break-word; }
      .insp dd { margin: 0; color: var(--text); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
      .insp dd .err { color: var(--status-failed); }
      .insp dd .warn { color: var(--status-attention); }
      .insp .acts { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding-top: 2px; }
      .insp .go { all: unset; cursor: pointer; color: var(--accent); overflow-wrap: anywhere; }
      .insp .go.primary { font-weight: 600; }
      .insp .go:hover { text-decoration: underline; }
      .insp .go:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
      .insp .acts .switch { margin-left: auto; }
      .keys { grid-column: 1 / -1; font-size: 11px; color: var(--text-muted); display: none; }
      .keys span { white-space: nowrap; }
      :host(:focus-within) .keys { display: block; }
      .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--text-2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
      .switch:hover { color: var(--text); border-color: var(--line2); }
      .switch:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }

      /* The table: across the frame's content box, the name and status as wide as their content, the relations sharing the rest. */
      /* A shadow at an edge the table scrolls past: a lid over it at the end, a shadow fixed to the frame. */
      .tframe { overflow: auto; padding: 0 12px 10px;
        background:
          linear-gradient(transparent, var(--well) 70%) center bottom / 100% 28px no-repeat local,
          radial-gradient(farthest-side at 50% 100%, color-mix(in srgb, var(--text-muted) 30%, transparent), transparent) center bottom / 100% 12px no-repeat scroll,
          var(--well); }
      /* on a narrow screen it keeps room for its relations and scrolls across */
      table.list { width: 100%; min-width: 64rem; border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
      .list th, .list td { text-align: left; vertical-align: middle; padding: 6px 10px; border-bottom: 1px solid var(--line); }
      .list .fit { width: 1%; white-space: nowrap; }
      /* a header is as wide as its words, and stays at the top of the frame */
      .list thead th { position: sticky; top: 0; z-index: 2; background: var(--well); color: var(--text-muted); font-weight: 500; font-size: 11px;
        white-space: nowrap; padding-top: 10px; }
      .list tbody th { font-weight: 600; }
      .list td { color: var(--text-2); }
      .list tbody tr { cursor: pointer; }
      .list tbody tr:hover > * { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
      .list tbody tr.sel > * { background-color: var(--accent-bg); }
      .list tbody tr.sel > th { box-shadow: inset 2px 0 0 var(--accent); }
      .list .nm { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; }
      .list .nm .k-ic { margin: 0 -2px 0 0; }
      .list .nm .in-ic { margin-right: -2px; }
      .list .name { max-width: 32ch; }
      .loopchip { display: inline-flex; align-items: center; gap: 4px; font-family: var(--sans); font-weight: 400; }
      .loopchip .ic { color: var(--text-muted); }
      .loopchip:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
      .list .st .n { color: var(--text); }
      .list .st .err { color: var(--status-failed); }
      .list .st .warn { color: var(--status-attention); }
      .list .st .live { color: var(--status-running); }
      .list .st .mut { color: var(--text-muted); }
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
  /** What is selected in the layer: a node or a loop box by its id, a mark by `markSel`; '' for nothing. */
  @property() sel = '';

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
  /** The layer the route named that this run does not have (shown once the graph fell back to its opening layer). */
  @state() private missing = '';
  /** A pointer is down on the frame. */
  private pressed = false;
  /** The frame height the selection's card needs (0 without one). */
  private cardRoom = 0;
  /** What the live region says: the item just selected, and its status. */
  @state() private announced = '';
  /** The route's layer is being set right: the change that follows is not the reader's. */
  private replacing = false;

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
  /** What the layout was computed from: the structure, the orientation and the sizes; and the layer it is of. */
  private layKey = '';
  private layPath = '';
  private resize?: ResizeObserver;
  /** The scale that shows the whole graph; the reader has zoomed or panned away from it. */
  private fitK = 1;
  private moved = false;
  /** A pan in progress, and whether it went far enough to swallow the click that ends it. */
  private pan: { id: number; px: number; py: number; x: number; y: number; far: boolean } | null = null;
  private swallowClick = false;
  /** Focus is being put back, not moved by the reader. */
  private quiet = false;

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('run')) this.orders.clear();
    if (changed.has('layer') && changed.get('layer') !== undefined) {
      this.moved = false;
      this.active.clear();
      this.cell = null;
      this.scrollRow = 0;
      // The focus stays where it is on the view switch; elsewhere it goes to the new layer.
      const at = this.renderRoot instanceof ShadowRoot ? this.renderRoot.activeElement : null;
      this.refocus = at !== null && !at.closest('.views');
      if (this.replacing) this.replacing = false;
      else this.missing = '';
    }
    if (changed.has('run') && changed.get('run') !== undefined) this.missing = '';
    if (!changed.has('plan') && !changed.has('layer') && !changed.has('run') && !(changed as Map<string, unknown>).has('down')) return;
    this.auto = autoLayer(this.plan);
    this.segments = this.layer ? this.layer.split('/') : this.auto;
    // A layer the plan does not have (a stale link, a typo): the one it names when that is
    // unique, else the opening layer; either way the route is set right in place.
    if (this.layer && this.plan.nodes.length) {
      const found = resolveLayer(this.plan, this.segments);
      if (!found) {
        this.missing = this.layer;
        this.segments = this.auto;
        this.setLayer('');
      } else if (found.join('/') !== this.layer) {
        this.segments = found;
        this.setLayer(found.join('/') === this.auto.join('/') ? '' : found.join('/'));
      }
    }
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
    this.removeEventListener('keydown', this.onTabToCard);
    this.resize?.disconnect();
    this.resize = undefined;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    // Ctrl (or ⌘) and the wheel zoom; the wheel alone still scrolls the page.
    this.addEventListener('wheel', this.onWheel, { passive: false });
    this.addEventListener('click', this.onClickCapture, { capture: true });
    this.addEventListener('keydown', this.onEscape);
    this.addEventListener('keydown', this.onTabToCard);
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (!this.resize) {
      this.resize = new ResizeObserver(() => {
        this.fit();
        this.anchorCard();
      });
      this.resize.observe(this);
    }
    this.place();
    if (this.refocus || this.cameFrom) this.restoreFocus();
    this.anchorCard();
    if (changed.has('sel')) this.selectionChanged();
  }

  // ---- the selection's card ----

  /**
   * The selected item as drawn (a mark, a node, a loop box's header), what the card keeps clear of
   * (a mark's whole node), and the box it is shown in (the frame, or a loop's passes).
   */
  private anchor(): { item: HTMLElement; clear: HTMLElement; frame: HTMLElement } | null {
    const root = this.renderRoot;
    const frame = root.querySelector<HTMLElement>('.main > .frame');
    const row = frame?.querySelector<HTMLElement>('tr.sel > th');
    if (frame && row) return { item: row, clear: row, frame };
    const sel = frame?.querySelector<HTMLElement>('.mark.sel, .taskchip.sel, .node.sel, .box.sel');
    if (!frame || !sel) return null;
    // A loop box: the card points at its header, where its name is, and keeps clear of the whole box when there is room.
    const item = sel.classList.contains('box') ? (sel.querySelector<HTMLElement>(':scope > .hd') ?? sel) : sel;
    return { item, clear: item.closest<HTMLElement>('.node') ?? sel, frame };
  }

  /** Put the card beside the selected item, inside the frame; hide it while the item is out of view. Runs after every draw, pan, zoom and scroll. */
  private anchorCard(): void {
    const card = this.renderRoot.querySelector<HTMLElement>('.insp');
    const room = card && !this.down ? card.querySelector<HTMLElement>('.scroll')!.scrollHeight + 24 + 2 * PAD : 0;
    if (room !== this.cardRoom && (room > this.frameH || this.cardRoom > 0)) {
      this.cardRoom = room;
      // A loop's passes: the frame's least height holds the card.
      if (this.matrix) this.requestUpdate();
      else this.fit();
    }
    if (!card || this.down) return;
    const a = this.anchor();
    const main = this.renderRoot.querySelector<HTMLElement>('.main');
    if (!a || !main) {
      card.classList.remove('placed');
      return;
    }
    const m = main.getBoundingClientRect();
    const rel = (r: DOMRect): Box => ({ left: r.left - m.left, top: r.top - m.top, width: r.width, height: r.height });
    const item = rel(a.item.getBoundingClientRect());
    const clear = rel(a.clear.getBoundingClientRect());
    const f = rel(a.frame.getBoundingClientRect());
    // A loop's passes and the table scroll: the item hides when scrolled out of them.
    const port = a.frame.querySelector<HTMLElement>('.mx');
    const inView = placeCard(item, port ? rel(port.getBoundingClientRect()) : f, { width: 0, height: 0 }).shown;
    const scroll = card.querySelector<HTMLElement>('.scroll');
    if (scroll) scroll.style.maxHeight = `${Math.max(120, f.height - 2 * PAD - 24)}px`;
    const size = { width: card.offsetWidth, height: card.offsetHeight };
    let p = placeCard(clear, f, size, item);
    if (!p.fits && a.clear !== a.item && !a.clear.classList.contains('node')) p = placeCard(item, f, size);
    card.classList.toggle('placed', p.shown && inView);
    card.dataset['side'] = p.side;
    card.style.left = `${p.x}px`;
    card.style.top = `${p.y}px`;
    card.style.setProperty('--arrow', `${p.arrow}px`);
  }

  /** The focusable that stands for the selected item: the mark itself, or a node's or a box's name. */
  private anchorFocus(): HTMLElement | null {
    const a = this.anchor();
    if (!a) return null;
    return a.item.matches('button') ? a.item : a.item.querySelector<HTMLElement>('.name');
  }

  /**
   * After a new selection: the selected item is described by the card, the live region names it,
   * and on a narrow screen (the card is a sheet under the frame, kept in view while the frame is) the item is scrolled into view.
   */
  private selectionChanged(): void {
    for (const el of this.renderRoot.querySelectorAll('[aria-describedby="insp"]')) el.removeAttribute('aria-describedby');
    const own = this.anchorFocus();
    own?.setAttribute('aria-describedby', 'insp');
    const card = this.renderRoot.querySelector<HTMLElement>('.insp');
    const name = card?.querySelector('h4')?.textContent?.trim() ?? '';
    const status = card?.querySelector('[data-status]')?.textContent?.trim() ?? '';
    const said = name ? facts(name, status) : '';
    if (said !== this.announced) this.announced = said;
    if (this.down) this.whenReleased(() => this.revealOverSheet());
  }

  /** Run `f` now, or, while a pointer is down on the graph, once it is released (a scroll under a pressed pointer would move the click elsewhere). */
  private whenReleased(f: () => void): void {
    if (!this.pressed) return f();
    globalThis.addEventListener('pointerup', () => setTimeout(f), { once: true });
  }

  /** On a narrow screen: scroll the selected item into view when it is out of it or under the sheet. */
  private revealOverSheet(): void {
    const item = this.anchor()?.item;
    if (!item) return;
    const r = item.getBoundingClientRect();
    const sheet = this.renderRoot.querySelector<HTMLElement>('.insp')?.getBoundingClientRect();
    const bottom = Math.min(globalThis.innerHeight, sheet?.top ?? Infinity);
    if (r.top < 0 || r.bottom > bottom) item.scrollIntoView({ block: 'center' });
  }

  /** Tab on the selected item goes on to its card; Shift+Tab on the card's first link comes back to the item. */
  private readonly onTabToCard = (e: KeyboardEvent): void => {
    if (e.key !== 'Tab' || e.shiftKey || e.defaultPrevented) return;
    const own = this.anchorFocus();
    const at = this.renderRoot instanceof ShadowRoot ? this.renderRoot.activeElement : null;
    if (!own || at !== own) return;
    const first = this.renderRoot.querySelector<HTMLElement>('.insp button');
    if (!first) return;
    e.preventDefault();
    first.focus();
  };

  private onCardKey(e: KeyboardEvent): void {
    const card = e.currentTarget as HTMLElement;
    const items = [...card.querySelectorAll<HTMLElement>('button')];
    const at = this.renderRoot instanceof ShadowRoot ? this.renderRoot.activeElement : null;
    if (e.key === 'Tab' && e.shiftKey && at === items[0]) {
      const own = this.anchorFocus();
      if (!own) return;
      e.preventDefault();
      this.quiet = true;
      own.focus();
      this.quiet = false;
    } else if (e.key === 'Escape') {
      // The card goes with the selection: the focus goes back to the item first.
      this.quiet = true;
      this.anchorFocus()?.focus();
      this.quiet = false;
    }
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
    this.layPath = g.path.join('/');
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
    // Focus put back after going up a level does not select.
    this.quiet = true;
    (el ?? root.querySelector<HTMLElement>('.mark[tabindex="0"], .node .name, .crumbs button'))?.focus();
    this.quiet = false;
  }

  /** Focus moved by the reader selects what it is on. */
  private focusSelect(id: string): void {
    if (!this.quiet) this.select(id);
  }

  // ---- layers ----

  /** Set the route's layer right, in place: the reader did not go anywhere. */
  private setLayer(layer: string): void {
    this.replacing = true;
    emit(this, 'ca-navigate', { layer, unit: this.unit, sel: this.sel, replace: true });
  }

  /** Go to a layer (its segments; [] for the layer the graph opens on), with a unit highlighted or not. */
  private go(segments: readonly string[], unit = this.unit): void {
    const auto = this.auto.join('/');
    const layer = segments.join('/');
    emit(this, 'ca-navigate', { layer: layer === auto ? '' : layer, unit });
  }

  // ---- what is selected ----

  /** What `sel` names in the view shown, or null. */
  private chosen(): Selected | null {
    return selected(this.graph, this.matrix, this.sel);
  }

  /** Select a node, a loop box or a mark (by its selection id); '' clears the selection. */
  private select(id: string): void {
    if (id !== this.sel) emit(this, 'ca-navigate', { sel: id });
  }

  /** What a double click or Enter does: a mark opens its task (or its flow call's function), a function node or a loop box opens inside, a kind node its tasks. */
  private primary(s: Selected): void {
    if (s.type === 'mark') return this.open(s.mark);
    if (s.type === 'box') return this.go([...this.segments, s.box.id]);
    if (s.node.type === 'flow') return this.go([...this.graph.path, s.node.name]);
    this.tasksOf(s.node);
  }

  /** The Tasks tab, filtered to a kind node's kind. */
  private tasksOf(n: GraphNode): void {
    emit(this, 'ca-navigate', { tab: 'tasks', kind: n.kinds.length === 1 ? n.kinds[0] : '' });
  }

  /** A click on a node or a box, not on one of its marks or on a node inside it: selects it. */
  private onItemClick(e: MouseEvent, id: string): void {
    const t = e.target as HTMLElement;
    const own = t.closest('.mark, .taskchip, .node, .box');
    if (own !== e.currentTarget) return;
    e.stopPropagation();
    if (e.detail >= 2) return; // the second click of a double click
    this.select(id);
  }

  private onItemDblClick(e: MouseEvent, id: string): void {
    const own = (e.target as HTMLElement).closest('.mark, .taskchip, .node, .box');
    if (own !== e.currentTarget) return;
    e.stopPropagation();
    const s = selected(this.graph, this.matrix, id);
    if (s) this.primary(s);
  }

  /** Enter on a node's or a box's name: its primary action (Space selects it, as a click does). */
  private onNameKey(e: KeyboardEvent, id: string): void {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const s = selected(this.graph, this.matrix, id);
    if (s) this.primary(s);
  }

  private readonly onEscape = (e: KeyboardEvent): void => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    if (this.sel) {
      e.preventDefault();
      this.select('');
      return;
    }
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
      // A loop by where it is: two loops one in the other are told apart.
      ...(loop ? loop.slice(LOOP_SEGMENT.length).split('.') : []).map((line, i, lines) => {
        const id = LOOP_SEGMENT + lines.slice(0, i + 1).join('.');
        const file = this.graph.boxes.find((b) => b.id === id)?.file || this.matrix?.box.file || '';
        const known = /^\d+$/.test(line);
        return {
          name: known ? msg(str`Loop at ${this.where(line, file)}`) : msg('Loop'),
          tip: known && file ? `${file}:${line}` : '',
          to: [...path, id],
        };
      }),
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
                    ? html`<span aria-current="page" title=${l.tip || nothing}>${l.name}</span>`
                    : html`<button type="button" title=${l.tip || nothing} @click=${() => this.go(l.to)}>${l.name}</button>`}</li>`;
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
    const host = this.clientWidth;
    const down = host > 0 && host < NARROW;
    if (down !== this.down) this.down = down;
    const lay = this.lay;
    if (!lay || this.matrix) return;
    // The frame is beside the inspector, or above it on a narrow screen.
    const width = this.renderRoot.querySelector<HTMLElement>('.frame')?.clientWidth || host;
    // Top to bottom, the graph is as tall as it needs at the frame's width.
    const whole = fitView(lay.w, lay.h, width, down ? Infinity : Math.max(FRAME_MIN, FRAME_SHARE * window.innerHeight));
    this.fitK = whole.k;
    // A short graph's frame grows down to hold the selection's card; the graph stays where it is.
    const h = down ? whole.h : Math.max(whole.h, this.cardRoom);
    const y = whole.y;
    if (!this.moved) {
      if (h !== this.frameH) this.frameH = h;
      if (whole.k !== this.view.k || whole.x !== this.view.x || y !== this.view.y) this.view = { k: whole.k, x: whole.x, y };
    } else if (h > this.frameH) this.frameH = h;
  }

  /** Zoom out, zoom in, and back to the whole graph (which does nothing while the whole graph shows at its own size). */
  private zoomTools() {
    const whole = !this.moved && this.fitK >= 1;
    return html`<button type="button" aria-label=${msg('Zoom out')} title=${msg('Zoom out (Ctrl + scroll)')} @click=${() => this.zoomBy(1 / 1.25)}>−</button>
      <button type="button" aria-label=${msg('Zoom in')} title=${msg('Zoom in (Ctrl + scroll)')} @click=${() => this.zoomBy(1.25)}>+</button>
      <button type="button" ?disabled=${whole} @click=${() => this.showAll()}>${msg('Show all')}</button>`;
  }

  private showAll(): void {
    this.moved = false;
    this.fit();
    this.requestUpdate();
  }

  private zoomBy(factor: number, cx = (this.renderRoot.querySelector<HTMLElement>('.frame')?.clientWidth ?? this.clientWidth) / 2, cy = this.frameH / 2): void {
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
    this.pressed = true;
    globalThis.addEventListener('pointerup', () => (this.pressed = false), { once: true });
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

  /** The unit (or key) highlighted: the one hovered or focused, else the selected mark's, else the pinned unit. */
  private get hl(): string | null {
    const s = this.hover === null ? this.chosen() : null;
    const mine = s?.type === 'mark' ? s.mark.unit || s.mark.key : null;
    return this.hover ?? mine ?? (this.unit || null);
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
    const { outcomes } = deriveRun(this.journal, this.plan);
    const causeOf = (key: string) => {
      const t = outcomes.get(key);
      return t ? notStartedCause(t, outcomes, this.run) : '';
    };
    const m = this.matrix;
    const table = !!m || this.asTable;
    const body = m ? this.matrixView(m, causeOf) : this.asTable ? this.table() : this.dag(causeOf);
    return html`${this.crumbs()}${this.missingLine()}
      <div class="main">${body}${this.inspector(causeOf)}</div>
      <div class="foot">
        ${this.legend()}
        <div class="tools">${table ? nothing : this.zoomTools()}${this.viewSwitch(table)}</div>
        <div class="keys">${this.keyHints().map((k, i) => html`${i ? ' | ' : ''}<span>${k}</span>`)}</div>
      </div>`;
  }

  /**
   * The two views of a layer, at the same place in each: the graph, and the table (a loop's
   * passes, or a row per node). From a loop's passes, the graph is the layer the loop is in,
   * with its box selected.
   */
  private viewSwitch(table: boolean) {
    return html`<div class="views" role="group" aria-label=${msg('View')}>
      <button type="button" aria-pressed=${!table} @click=${() => this.showGraph()}>${msg('Graph')}</button>
      <button type="button" aria-pressed=${table} @click=${() => this.showTable()}>${msg('Table')}</button>
    </div>`;
  }

  private showGraph(): void {
    this.asTable = false;
    if (!this.matrix) return;
    const box = this.segments[this.segments.length - 1] ?? '';
    const up = parentLayer(this.segments, this.auto) ?? [];
    const auto = this.auto.join('/');
    emit(this, 'ca-navigate', { layer: up.join('/') === auto ? '' : up.join('/'), unit: this.unit, sel: box });
  }

  private showTable(): void {
    if (!this.matrix) this.asTable = true;
  }

  /** The layer the route named that this run does not have. */
  private missingLine() {
    if (!this.missing) return nothing;
    const segs = this.missing.split('/');
    const name = segs[segs.length - 1] || this.missing;
    return html`<div class="missing" role="status" title=${this.missing}>${msg(html`No layer <code>${name}</code> in this run`)}</div>`;
  }

  /** The keys of the view shown. */
  private keyHints(): string[] {
    const up = this.sel ? msg('Esc: clear selection') : parentLayer(this.segments, this.auto) ? msg('Esc: up a level') : '';
    const keys = this.matrix
      ? [msg('Arrow keys: marks'), msg('Enter: open'), up]
      : this.asTable
        ? [msg('Tab: next row'), msg('Enter: open'), up]
        : [msg('Tab: next node'), msg('Arrow keys: marks'), msg('Shift + arrow keys: earlier and later tasks'), msg('Enter: open'), up];
    return keys.filter(Boolean);
  }

  private dag(causeOf: (key: string) => string) {
    const graph = this.graphView(causeOf);
    const v = this.view;
    return html`<div class="frame gframe ${this.down ? 'down' : ''}" style="height:${Math.round(this.frameH)}px"
        @pointerdown=${(e: PointerEvent) => this.onPointerDown(e)} @pointermove=${(e: PointerEvent) => this.onPointerMove(e)}
        @pointerup=${(e: PointerEvent) => this.onPointerUp(e)} @pointercancel=${(e: PointerEvent) => this.onPointerUp(e)}
        @click=${(e: MouseEvent) => !(e.target as Element).closest('.node, .box, .stub, .tools') && this.select('')}>
        <div class="stage view" style="transform:translate(${v.x}px,${v.y}px) scale(${v.k})">${graph}</div>
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
          <marker id="arr-ret" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path class="ret-tip" d="M0,0.5 L8,4 L0,7.5 z"></path>
          </marker>
        </defs>
        ${(lay?.edges ?? []).map((e) => svg`<path class=${e.type} d=${edgePath(e.runs, lay?.down)} marker-end="url(#arr)"></path>`)}
        ${(lay?.returns ?? []).map((r) => svg`<path class="ret" data-box=${r.box} d=${returnPath(r, lay?.down)} marker-end="url(#arr-ret)"></path>`)}
      </svg>
      ${repeat(items(''), (id) => id, (id) => item(id, null))}
    </div>`;
  }

  private box(b: LoopBox, parent: Rect | null, item: (id: string, r: Rect | null) => unknown) {
    const r = this.lay?.at[b.id] ?? null;
    const where = msg(str`Loop at ${this.where(b.loop, b.file)}`);
    const spread = b.spread.length > 1 ? passSpread(b.spread) : '';
    const kids = (this.graph.slots[b.id] ?? []).flat().filter((id) => !isPoint(id));
    const size = r ? `;width:${r.w}px;height:${r.h}px` : '';
    return html`<section class="box ${this.sel === b.id ? 'sel' : ''}" role="group" data-box=${b.id} style=${this.at(b.id, parent) + size}
        aria-label=${facts(where, passCount(b.passes), spread)}
        @click=${(e: MouseEvent) => this.onItemClick(e, b.id)} @dblclick=${(e: MouseEvent) => this.onItemDblClick(e, b.id)}>
      <div class="hd" data-id=${`lbl:${b.id}`}>
        <span class="line">
          <button type="button" class="name" title=${facts(loopLabel(), where)} aria-pressed=${this.sel === b.id}
            @focus=${() => this.focusSelect(b.id)} @keydown=${(e: KeyboardEvent) => this.onNameKey(e, b.id)}>${loopIcon()}${loopLabel()}</button>
          <span class="count">${passCount(b.passes)}</span>
        </span>
        ${spread ? html`<span class="spread" title=${msg('Units by number of passes')}>${spread}</span>` : nothing}
      </div>
      <span class="cue" aria-hidden="true">${innerIcon()}</span>
      <div class="in">${repeat(kids, (id) => id, (id) => item(id, r))}</div>
    </section>`;
  }

  private node(n: GraphNode, parent: Rect | null, causeOf: (key: string) => string, on: Set<string> | null) {
    const c = n.counts;
    // Finished (done and skipped) only sets the frame's look; the count is of the tasks done.
    const look = c.failed || n.errors ? 'fail' : c.running ? 'cur' : c.done + c.skipped === c.total ? 'done' : '';
    const bar = asBar(n);
    const group: MarkGroup = bar
      ? { id: n.id, label: n.label, slots: slotsOf(n).filter((m): m is GraphMark => m?.state === 'failed'), grid: { cols: BAR_LIST, size: 12, gap: 4 } }
      : { id: n.id, label: n.label, slots: slotsOf(n), grid: gridOf(n, this.graph.units.length) };
    const ex = this.exceptions(n);
    const on_ = this.sel === n.id;
    const tip = n.type === 'flow' ? facts(msg(str`Function ${n.name}`), this.doneOf(c)) : facts(n.label, this.executorWord(n), this.doneOf(c));
    const icons =
      n.executor === 'mixed' ? html`${exIcon(false)}${exIcon(true)}` : n.executor ? exIcon(n.executor === 'python') : nothing;
    return html`<section class="node ${n.type} ${n.executor === 'agent' ? 'agent' : ''} ${look} ${on_ ? 'sel' : ''}" role="group" data-id=${n.id}
      aria-label=${this.nodeLabel(n)}
      style="${this.at(n.id, parent)};--cols:${group.grid.cols};--m:${group.grid.size}px;--g:${group.grid.gap}px"
      @click=${(e: MouseEvent) => this.onItemClick(e, n.id)} @dblclick=${(e: MouseEvent) => this.onItemDblClick(e, n.id)}>
      <div class="hd">
        <span class="nm">${icons}<button type="button" class="name" title=${tip} aria-pressed=${on_}
          @focus=${() => this.focusSelect(n.id)} @keydown=${(e: KeyboardEvent) => this.onNameKey(e, n.id)}>${n.label}</button></span>
        <span class="right"><span class="count" aria-hidden="true" title=${this.doneOf(c)}>${c.done}/${c.total}</span>${n.type === 'flow'
          ? html`<span class="cue" aria-hidden="true">${innerIcon()}</span>`
          : nothing}</span>
      </div>
      ${bar ? this.statusBar(n, group, causeOf, on) : this.marks(group, causeOf, on)}
      ${ex.length ? html`<div class="ex" aria-hidden="true">${ex.map(([cls, t]) => html`<span class=${cls}>${t}</span>`)}</div>` : nothing}
    </section>`;
  }

  /** Who runs a kind node's tasks, in the words the Tasks list uses. */
  private executorWord(n: Pick<GraphNode, 'executor'>): string {
    if (n.executor === 'agent') return msg('Agent task');
    if (n.executor === 'python') return msg('Python task');
    return n.executor === 'mixed' ? facts(msg('Agent task'), msg('Python task')) : '';
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
    const { name, parts } = this.markText(g.label, m, causeOf);
    const hlKey = m.unit || m.key;
    const lit = on !== null && ((m.unit !== '' && m.unit === this.hl) || m.keys.some((k) => on.has(k)));
    const id = markSel(g.id, m);
    const sel = this.sel === id ? 'sel' : '';
    const focus = (e: FocusEvent) => {
      this.hover = hlKey;
      this.active.set(g.id, i);
      this.reveal(e.currentTarget as HTMLElement);
      this.focusSelect(id);
    };
    // The tooltip names it and its status; the rest is in the inspector.
    const tip = [name, parts[0] ?? ''].filter(Boolean).join('\n');
    if (chip) {
      return html`<button type="button" class="taskchip ${lit ? 'on' : ''} ${sel}" data-i=${i} tabindex=${tabStop ? 0 : -1}
        title=${tip} aria-label=${facts(name, ...parts)} aria-pressed=${!!sel}
        @mouseenter=${() => (this.hover = hlKey)} @focus=${focus} @blur=${() => (this.hover = null)}
        @click=${() => this.select(id)} @dblclick=${() => this.open(m)}>${m.unit || m.key}</button>`;
    }
    return html`<button type="button" class="mark ${m.state} ${lit ? 'on' : ''} ${sel}" data-i=${i} data-n=${m.passes ?? nothing} tabindex=${tabStop ? 0 : -1}
      title=${tip}
      aria-label=${facts(name, ...parts)} aria-pressed=${!!sel}
      @mouseenter=${() => (this.hover = hlKey)}
      @focus=${focus}
      @blur=${() => (this.hover = null)}
      @click=${() => this.select(id)}
      @dblclick=${() => this.open(m)}></button>`;
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
        title=${h.node.type === 'flow' ? msg(str`Function ${h.node.name}`) : facts(h.node.label, this.executorWord(h.node))}
        aria-label=${h.node.type === 'flow' ? h.node.label : facts(h.node.label, this.executorWord(h.node))}>${h.node.executor && h.node.executor !== 'mixed'
          ? exIcon(h.node.executor === 'python')
          : nothing}${h.node.label}</th>`;
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
    const summary = [
      passCount(mx.box.passes),
      mx.box.spread.length > 1 ? passSpread(mx.box.spread) : '',
      units === 1 ? msg('1 unit') : msg(str`${units} units`),
    ].filter(Boolean);
    // In the graph's frame, at least as tall as the graph was (and as the card needs), the passes centred in it.
    const least = this.down ? 0 : Math.round(Math.max(this.frameH, this.cardRoom));
    return html`<div class="frame mxframe" style=${least ? `min-height:${least}px` : ''}><div class="mxblock view">
      <div class="mxbar">
        <span class="cap" title=${mx.box.file ? `${mx.box.file}:${mx.box.loop}` : nothing}>${msg(str`Loop at ${this.where(mx.box.loop, mx.box.file)}`)}</span>
        <label>${msg('Sort units')}
          <select @change=${(e: Event) => (this.sort = (e.target as HTMLSelectElement).value as MatrixSort)}>
            <option value="order" ?selected=${this.sort === 'order'}>${msg('Scheduled order')}</option>
            <option value="passes" ?selected=${this.sort === 'passes'}>${msg('Number of passes')}</option>
            <option value="state" ?selected=${this.sort === 'state'}>${msg('Status')}</option>
          </select>
        </label>
        <span class="sum">${summary.map((t, i) => html`${i ? html`<span class="sep"> | </span>` : nothing}<span class="f">${t}</span>`)}</span>
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
      </div>
    </div></div>`;
  }

  private cellMark(r: MatrixRow, m: GraphMark, ri: number, ci: number, node: GraphNode, passes: number[], tabStop: boolean, causeOf: (key: string) => string) {
    const { name, parts } = this.markText(node.label, m, causeOf, passes.map(passLabel).join(', '));
    const hlKey = m.unit || m.key;
    const id = markSel(node.id, m, passes);
    const sel = this.sel === id;
    return html`<button type="button" class="mark ${m.state} ${r.unit && r.unit === this.hl ? 'on' : ''} ${sel ? 'sel' : ''}" data-r=${ri} data-c=${ci} tabindex=${tabStop ? 0 : -1}
      title=${[name, parts[0] ?? ''].filter(Boolean).join('\n')} aria-label=${facts(name, ...parts)} aria-pressed=${sel}
      @mouseenter=${() => (this.hover = hlKey)}
      @focus=${() => {
        this.hover = hlKey;
        this.cell = [ri, ci];
        this.focusSelect(id);
      }}
      @blur=${() => (this.hover = null)}
      @click=${() => this.select(id)}
      @dblclick=${() => this.open(m)}></button>`;
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
    this.anchorCard();
  }

  private onMatrixKey(e: KeyboardEvent, rows: readonly MatrixRow[]): void {
    const t = e.target as HTMLElement;
    if (!t.classList.contains('mark')) return;
    const r = Number(t.dataset['r']);
    const c = Number(t.dataset['c']);
    if (e.key === 'Enter') {
      const m = rows[r]?.cells[c];
      e.preventDefault();
      if (m) this.open(m);
      return;
    }
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

  /** How many tasks are done (plan state done: done, and done after retrying): "5 of 6 tasks done". Skipped tasks are counted apart. */
  private doneOf(c: NodeCounts): string {
    return msg(str`${c.done} of ${c.total} tasks done`);
  }

  /** The tasks that are not done, by state, most severe first: "1 failed", "1 not started". */
  private notDone(c: NodeCounts): string[] {
    return (['failed', 'blocked', 'running', 'pending', 'skipped'] as const).filter((s) => c[s]).map((s) => this.countOf(s, c[s]));
  }

  /** A pending task waits while the run runs; once the run is over, it did not run. */
  private stateWord(s: TaskState): string {
    return statusLabel(planOutcome(s), this.live);
  }

  /** Where a loop is: `flow.py:130` (the file's name and the loop's first line), or `line 130` when the file is not known. */
  private where(line: number | string, file?: string): string {
    const name = file ? file.slice(file.lastIndexOf('/') + 1) : '';
    return name ? `${name}:${line}` : msg(str`line ${line}`);
  }

  /** How many marks are in a state, number first: "3 failed". */
  private countOf(s: TaskState, n: number): string {
    const o = planOutcome(s);
    return stateCount(o === 'waiting' && !this.live ? 'not_run' : o, n);
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
    if (c.skipped) out.push(['mut', this.countOf('skipped', c.skipped)]);
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
      n.type === 'flow' ? facts(msg(str`Function ${n.label}`), this.doneOf(c)) : facts(n.label, this.executorWord(n), this.doneOf(c)),
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
    if (e.key === 'Enter') {
      const m = slots[Number(target.dataset['i'])];
      e.preventDefault();
      if (m) this.open(m);
      return;
    }
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

  /**
   * What the view shows that needs a word: the states of the marks shown, the pass number
   * when a mark shows one, who runs the kind nodes' tasks, the kinds of edges when there is
   * more than one, a loop's return to its next pass, and the mark of a node or a box with an
   * inner view.
   */
  private legend() {
    const flat = this.asTable && !this.matrix;
    // The marks drawn: a node with a bar draws its failed marks only; the table draws none.
    const marks = flat
      ? []
      : this.matrix
        ? this.matrix.rows.flatMap((r) => r.cells)
        : this.graph.nodes.flatMap((n) => (asBar(n) ? slotsOf(n).map((m) => m && { ...m, passes: undefined }) : slotsOf(n)));
    const shown = marks.filter((m): m is GraphMark => m !== null);
    const present = new Set(shown.map((m) => m.state));
    const passes = !this.matrix && shown.some((m) => m.passes);
    const created = !this.matrix && !flat && [...this.graph.edges, ...this.graph.stubs].some((e) => e.type === 'created');
    const nodes = this.matrix ? this.matrix.columns.map((c) => c.node) : this.graph.nodes;
    const ex = new Set(nodes.flatMap((n) => (n.executor === 'mixed' ? ['agent', 'python'] : n.executor ? [n.executor] : [])));
    const loops = !this.matrix && !flat && this.graph.boxes.length > 0;
    const inner = !this.matrix && (loops || this.graph.nodes.some((n) => n.type === 'flow'));
    const line = (dash: boolean) => svg`<svg width="22" height="8" aria-hidden="true"><path d="M1,4 H21" stroke-dasharray=${dash ? '5 4' : 'none'}></path></svg>`;
    return html`<div class="legend big">
      ${LEGEND.filter((s) => present.has(s)).map((s) => html`<span aria-hidden="true"><i class="mark ${s}"></i>${this.stateWord(s)}</span>`)}
      ${passes ? html`<span aria-hidden="true"><i class="mark done" data-n="2"></i>${msg('number of passes')}</span>` : nothing}
      ${ex.has('agent') ? html`<span>${exIcon(false)}${msg('agent task')}</span>` : nothing}
      ${ex.has('python') ? html`<span>${exIcon(true)}${msg('Python task')}</span>` : nothing}
      ${created
        ? html`<span>${line(false)}${msg('waits for output')}</span><span>${line(true)}${msg('created after result')}</span>`
        : nothing}
      ${loops
        ? html`<span><svg width="24" height="12" aria-hidden="true"><path class="ret" d="M20,1.5 V5.5 Q20,9.5 16,9.5 H8 Q4,9.5 4,5.5 V5"></path>
            <path class="ret-head" d="M4,0.8 L1.4,5 L6.6,5 z"></path></svg>${msg('next pass')}</span>`
        : nothing}
      ${inner ? html`<span>${innerIcon()}${msg('has an inner view')}</span>` : nothing}
    </div>`;
  }

  // ---- the inspector ----

  /** What is selected, its facts and where it leads; with nothing selected, the layer's counts. */
  /**
   * The selection's card (none without a selection), placed by `anchorCard` once drawn; a new
   * selection is a new card, so it fades in. A live region names what was selected.
   */
  private inspector(causeOf: (key: string) => string) {
    const s = this.chosen();
    const card = s
      ? keyed(this.sel, html`<section id="insp" class="insp ${this.down ? 'sheet' : ''}" aria-label=${msg('Selected item')}
          @keydown=${(e: KeyboardEvent) => this.onCardKey(e)}>
          <span class="ptr" aria-hidden="true"></span>
          <div class="scroll">${this.inspect(s, causeOf)}</div>
        </section>`)
      : nothing;
    return html`${card}<div class="sr" role="status">${this.announced}</div>`;
  }

  private inspect(s: Selected, causeOf: (key: string) => string) {
    const row = (dt: string, dd: unknown) => html`<dt>${dt}</dt><dd>${dd}</dd>`;
    const link = (text: string, go: () => void, primary = false) =>
      html`<button type="button" class="go ${primary ? 'primary' : ''}" @click=${go}>${text}</button>`;
    const clear = html`<button type="button" class="switch" @click=${() => this.select('')}>${msg('Clear selection')}</button>`;
    const list = (xs: string[]) => (xs.length ? xs.join(', ') : msg('none'));
    if (s.type === 'box') {
      const b = s.box;
      const where = this.where(b.loop, b.file);
      return html`<h4 title=${b.file ? `${b.file}:${b.loop}` : nothing}>${loopIcon(16)}${msg(str`Loop at ${where}`)}</h4>
        <dl>
          ${row(msg('Passes'), passCount(b.passes))}
          ${b.spread.length > 1 ? row(msg('Units by number of passes'), passSpread(b.spread)) : nothing}
        </dl>
        <div class="acts">${link(msg(str`Passes of the loop at ${where}`), () => this.primary(s), true)}${clear}</div>`;
    }
    if (s.type === 'node') {
      const n = s.node;
      const c = n.counts;
      const { waits, after, feeds } = this.neighbours(n);
      const states = this.exceptions(n).map(([cls, t]) => html`<div class=${cls}>${t}</div>`);
      if (n.type === 'flow') {
        return html`<h4 title=${n.name}>${innerIcon()}${n.label}</h4>
          <div class="sub">${msg('Function')}</div>
          <dl>
            ${row(msg('Flow calls'), n.calls)}
            ${row(msg('Tasks'), html`${this.doneOf(c)}${states}`)}
            ${row(msg('Waits for'), list(waits))}
            ${after.length ? row(msg('Created after'), list(after)) : nothing}
            ${row(msg('Later tasks'), list(feeds))}
          </dl>
          <div class="acts">${link(msg(str`Inside ${n.label}`), () => this.primary(s), true)}${clear}</div>`;
      }
      return html`<h4>${n.executor && n.executor !== 'mixed' ? exIcon(n.executor === 'python') : nothing}${n.label}</h4>
        <div class="sub">${this.executorWord(n)}</div>
        <dl>
          ${row(msg('Tasks'), html`${this.doneOf(c)}${states}`)}
          ${row(msg('Waits for'), list(waits))}
          ${after.length ? row(msg('Created after'), list(after)) : nothing}
          ${row(msg('Later tasks'), list(feeds))}
        </dl>
        <div class="acts">${link(msg(str`Tasks of ${n.label}`), () => this.primary(s), true)}${clear}</div>`;
    }
    const { node, mark: m, passes } = s;
    const name = kindUnit({ kind: node.label, unit: m.unit });
    const cause = !m.flow && m.state === 'blocked' ? causeOf(m.key) : '';
    const status = html`<span data-status class=${m.state === 'failed' ? 'err' : m.state === 'blocked' ? 'warn' : ''}>${this.stateWord(m.state)}</span>`;
    const head = html`<h4 title=${m.flow ? msg(str`Flow call ${m.key}`) : m.key}><i class="mark ${m.state}" aria-hidden="true"></i>${name}</h4>`;
    const pass = passes.length ? passes.map(passLabel).join(', ') : m.passes ? passesRan(m.passes) : '';
    if (m.flow) {
      const c = m.counts;
      return html`${head}
        <dl>
          ${row(msg('Status'), status)}
          ${pass ? row(msg('Pass'), pass) : nothing}
          ${c ? row(msg('Tasks'), html`${this.doneOf(c)}${this.notDone(c).map((t) => html`<div>${t}</div>`)}`) : nothing}
          ${m.error !== undefined ? row(msg('Error'), html`<span class="err">${m.error || msg('Flow call stopped with an error')}</span>`) : nothing}
        </dl>
        <div class="acts">${link(msg(str`Inside ${shortName(m.flow)}`), () => this.primary(s), true)}${clear}</div>`;
    }
    const rows = this.journal.filter((r) => m.keys.includes(r.key));
    const ran = rows.filter(isLaunched);
    const costs = ran.map((r) => r.cost_usd).filter((x): x is number => typeof x === 'number');
    const wall = ran.reduce((a, r) => a + (r.wall_s ?? 0), 0);
    return html`${head}
      <dl>
        ${row(msg('Status'), cause ? html`${status}<div>${cause}</div>` : status)}
        ${pass ? row(msg('Pass'), pass) : nothing}
        ${m.count > 1 ? row(msg('Tasks'), msg(str`${m.count} tasks`)) : nothing}
        ${row(msg('Attempts'), ran.length || msg('none'))}
        ${row(msg('Time'), ran.length ? fmtDur(wall) : msg('none'))}
        ${row(msg('Cost'), costs.length ? usd(costs.reduce((a, x) => a + x, 0)) : '—')}
      </dl>
      <div class="acts">${link(msg('Task detail'), () => this.primary(s), true)}${node.kinds.length === 1
          ? link(msg(str`Tasks of ${node.label}`), () => this.tasksOf(node))
          : nothing}${clear}</div>`;
  }

  /**
   * The layer as a table, in the graph's frame: a row per node with its status (the graph
   * node's facts: done of all, then the others by state) and the nodes it waits for, was
   * created after and feeds. A row is selected as a node is, with the same card.
   */
  private table() {
    const nodes = this.graph.nodes;
    const flows = nodes.some((n) => n.type === 'flow');
    const created = [...this.graph.edges, ...this.graph.stubs].some((e) => e.type === 'created');
    const boxes = new Map(this.graph.boxes.map((b) => [b.id, b]));
    const list = (xs: string[]) => xs.join(', ') || msg('none');
    // The frame keeps the graph's height when the graph of this layer was drawn (left to right); else the table's own, up to the frame's limit.
    const height =
      !this.down && this.layPath === this.graph.path.join('/') && this.frameH > 0
        ? `height:${Math.round(this.frameH)}px`
        : `max-height:max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh)`;
    return html`<div class="frame tframe" style=${height} @scroll=${() => this.anchorCard()}
        @click=${(e: MouseEvent) => !(e.target as Element).closest('tbody tr') && this.select('')}>
      <table class="list view">
        <thead>
          <tr>
            <th scope="col" class="fit">${flows ? msg('Kind or function') : msg('Kind')}</th>
            <th scope="col" class="fit">${msg('Status')}</th>
            <th scope="col">${msg('Waits for')}</th>
            ${created ? html`<th scope="col">${msg('Created after')}</th>` : nothing}
            <th scope="col">${msg('Later tasks')}</th>
          </tr>
        </thead>
        <tbody>
          ${repeat(nodes, (n) => n.id, (n) => {
            const c = n.counts;
            const { waits, after, feeds } = this.neighbours(n);
            const box = n.box ? boxes.get(n.box) : undefined;
            const on = this.sel === n.id;
            const tip = n.type === 'flow' ? facts(msg(str`Function ${n.name}`), this.doneOf(c)) : facts(n.label, this.executorWord(n), this.doneOf(c));
            const icon =
              n.type === 'flow' ? innerIcon() : n.executor && n.executor !== 'mixed' ? exIcon(n.executor === 'python') : n.executor ? html`${exIcon(false)}${exIcon(true)}` : nothing;
            const where = box ? msg(str`Loop at ${this.where(box.loop, box.file)}`) : '';
            return html`<tr class=${on ? 'sel' : ''} data-id=${n.id}
                @click=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && e.detail < 2 && this.select(n.id)}
                @dblclick=${(e: MouseEvent) => !(e.target as Element).closest('.loopchip') && this.primary({ type: 'node', id: n.id, node: n })}>
              <th scope="row" class="fit">
                <span class="nm">${icon}<button type="button" class="name" title=${tip} aria-pressed=${on}
                  @focus=${() => this.focusSelect(n.id)} @keydown=${(e: KeyboardEvent) => this.onNameKey(e, n.id)}>${n.label}</button>${box
                  ? html`<button type="button" class="taskchip loopchip" title=${facts(where, passCount(box.passes))}
                      aria-label=${facts(msg(str`Passes of the loop at ${this.where(box.loop, box.file)}`), passCount(box.passes))}
                      @click=${() => this.go([...this.graph.path, box.id])}>${loopIcon(12)}${passCount(box.passes)}</button>`
                  : nothing}</span>
              </th>
              <td class="fit st">${this.statusLine(n)}</td>
              <td class="rel">${list(waits)}</td>
              ${created ? html`<td class="rel">${list(after)}</td>` : nothing}
              <td class="rel">${list(feeds)}</td>
            </tr>`;
          })}
        </tbody>
      </table>
    </div>`;
  }

  /** A node's status in one row, as its node in the graph says it: "28/30 | 1 failed | 1 not started". */
  private statusLine(n: GraphNode) {
    const c = n.counts;
    const sep = html`<span class="sep" aria-hidden="true"> | </span>`;
    return html`<span class="n" aria-hidden="true" title=${this.doneOf(c)}>${c.done}/${c.total}</span><span class="sr">${this.doneOf(c)}</span>${this.exceptions(
      n,
    ).map(([cls, t]) => html`${sep}<span class=${cls}>${t}</span>`)}`;
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
