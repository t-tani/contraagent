import type { JournalRow, Plan } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, html, type PropertyValueMap, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import { getLocale } from '../../core/i18n.js';
import { facts } from '../../words/format.js';
import { CardController } from './graph/card.js';
import { taskLinks, type TaskLinks } from './graph/highlight.js';
import { autoLayer, layerGraph, parentLayer, resolveLayer, splitLayer } from './graph/layer.js';
import { layoutGraph, type GraphLayout, type Size } from './graph/layout.js';
import { passMatrix, type MatrixSort, type PassMatrix } from './graph/matrix.js';
import { PanZoomController } from './graph/pan-zoom.js';
import type { LayerGraph, LayerOrder } from './graph/types.js';
import { go, restoreFocus, select } from './pipeline-graph/actions.js';
import { crumbs, missingLine } from './pipeline-graph/crumbs.js';
import { dag } from './pipeline-graph/dag.js';
import type { GraphHost } from './pipeline-graph/host.js';
import { inspector } from './pipeline-graph/inspector.js';
import { matrixView } from './pipeline-graph/matrix.js';
import { graphStyles } from './pipeline-graph/styles.js';
import { table } from './pipeline-graph/table.js';
import { foot } from './pipeline-graph/tools.js';

/** Below this width the graph runs top to bottom, without zoom. */
const NARROW = 640;

/** The changes `willUpdate` reads: the properties, and the private `down`. */
type Changed = PropertyValues<CaPipelineGraph> & PropertyValueMap<{ down: boolean }>;

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
  static override styles = graphStyles;

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
  /** A loop's passes: how its units are sorted, and the first row in view. */
  @state() private sort: MatrixSort = 'order';
  @state() private scrollRow = 0;
  /** The layer the route named that this run does not have (shown once the graph fell back to its opening layer). */
  @state() private missing = '';
  /** What the live region says: the item just selected, and its status. */
  @state() private announced = '';
  /** The route's layer to set right after this update, and that change, which is not the reader's. */
  private fixLayer: string | null = null;
  private replacing = false;

  /** The layer the graph opens on, the one shown, and what it shows. */
  private auto: string[] = [];
  private segments: string[] = [];
  private graph: LayerGraph = { path: [], nodes: [], layers: [], boxes: [], edges: [], stubs: [], units: [], slots: {}, routes: [], order: { layers: [], boxes: {} } };
  private matrix: PassMatrix | null = null;
  /** Each layer's order, so nodes stay where they are while the plan grows. */
  private orders = new Map<string, LayerOrder>();
  private links: TaskLinks = taskLinks([]);
  /** Each group's focused mark (roving tabindex): one tab stop per group; in a loop's passes, the focused cell. */
  private readonly active = new Map<string, number>();
  private cell: [number, number] | null = null;
  private refocus = false;
  /** After going up a level: the node (or box) it came from, to focus. */
  private cameFrom = '';
  /** What the sizes were last measured for (the graph, and what changes a node's size), what the layout was computed from, and the layer it is of. */
  private measured: { graph: LayerGraph; key: string } | null = null;
  private layKey = '';
  private layPath = '';

  private readonly pz = new PanZoomController(this, {
    frame: () => this.renderRoot.querySelector<HTMLElement>('.frame'),
    stage: () => this.renderRoot.querySelector<HTMLElement>('.stage'),
    drawing: () => (this.lay && !this.matrix ? { w: this.lay.w, h: this.lay.h, down: this.down, room: this.card.room } : null),
    wheel: () => !this.asTable && !this.matrix,
    down: () => this.down,
    onMove: () => this.card.place(),
    onResize: () => {
      this.fit();
      this.card.place();
    },
  });

  private readonly card: CardController = new CardController(this, {
    docked: () => this.down,
    frameH: () => this.pz.frameH,
    // A loop's passes: the frame's least height holds the card.
    grow: () => (this.matrix ? this.requestUpdate() : this.fit()),
    pressed: () => this.pz.pressed,
  });

  private readonly h: GraphHost = this.viewHost();

  protected override willUpdate(changed: Changed): void {
    if (changed.has('run')) this.orders.clear();
    if (changed.has('layer') && changed.get('layer') !== undefined) {
      this.pz.reset();
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
    if (!changed.has('plan') && !changed.has('layer') && !changed.has('run') && !changed.has('down')) return;
    this.auto = autoLayer(this.plan);
    this.segments = this.layer ? this.layer.split('/') : this.auto;
    // A layer the plan does not have (a stale link, a typo): the one it names when that is
    // unique, else the opening layer; either way the route is set right in place, once this update is done.
    if (this.layer && this.plan.nodes.length) {
      const found = resolveLayer(this.plan, this.segments);
      if (!found) {
        this.missing = this.layer;
        this.segments = this.auto;
        this.fixLayer = '';
      } else if (found.join('/') !== this.layer) {
        this.segments = found;
        this.fixLayer = found.join('/') === this.auto.join('/') ? '' : found.join('/');
      }
    }
    const { path, loop } = splitLayer(this.segments);
    const key = path.join('/');
    this.graph = layerGraph(this.plan, path, this.orders.get(key), this.down);
    this.orders.set(key, this.graph.order);
    this.matrix = loop ? passMatrix(this.plan, path, loop, this.graph.order) : null;
    if (changed.has('plan')) this.links = taskLinks(this.plan.nodes);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.addEventListener('keydown', this.onEscape);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener('keydown', this.onEscape);
  }

  protected override updated(changed: Changed): void {
    if (this.fixLayer !== null) {
      // Set the route's layer right, in place: the reader did not go anywhere.
      const layer = this.fixLayer;
      this.fixLayer = null;
      this.replacing = true;
      emit(this, 'ca-navigate', { layer, unit: this.unit, sel: this.sel, replace: true });
    }
    this.place();
    if (this.refocus || this.cameFrom) {
      const from = this.cameFrom;
      this.refocus = false;
      this.cameFrom = '';
      restoreFocus(this.h, from);
    }
    this.card.place();
    if (changed.has('sel')) this.selectionChanged();
  }

  /** After a new selection: the card describes the item, the live region names it, and on a narrow screen the item is scrolled into view. */
  private selectionChanged(): void {
    const [name, status] = this.card.describe();
    const said = name ? facts(name, status) : '';
    if (said !== this.announced) this.announced = said;
    if (this.down) this.card.whenReleased(() => this.card.revealOverSheet());
  }

  /**
   * Measure what was drawn when the graph or what sets a node's size (the orientation, the
   * run being live, the language, the width) changed; lay it out again when the structure or a size changed.
   */
  private place(): void {
    const dag = this.renderRoot.querySelector<HTMLElement>('.dag');
    if (!dag) return;
    const g = this.graph;
    const seen = `${this.down}|${this.live}|${getLocale()}|${this.clientWidth}`;
    if (this.measured?.graph === g && this.measured.key === seen) return this.fit();
    this.measured = { graph: g, key: seen };
    const sizes = new Map<string, Size>();
    for (const el of dag.querySelectorAll<HTMLElement>('[data-id]')) sizes.set(el.dataset['id'] ?? '', { w: el.offsetWidth, h: el.offsetHeight });
    const key = JSON.stringify([g.path, g.slots, g.routes.map((r) => r.steps.map((s) => s.id)), this.down, [...sizes]]);
    if (key === this.layKey) return this.fit();
    this.layKey = key;
    this.layPath = g.path.join('/');
    this.lay = layoutGraph(g, sizes, this.down);
    void this.updateComplete.then(() => this.fit());
  }

  /** Top to bottom on a narrow screen; otherwise the whole graph in a frame, until the reader zooms or pans. */
  private fit(): void {
    const w = this.clientWidth;
    const down = w > 0 && w < NARROW;
    if (down !== this.down) this.down = down;
    this.pz.fit();
  }

  private readonly onEscape = (e: KeyboardEvent): void => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    if (this.sel) {
      e.preventDefault();
      select(this.h, '');
      return;
    }
    const up = parentLayer(this.segments, this.auto);
    if (!up) return;
    e.preventDefault();
    this.refocus = true;
    this.cameFrom = this.segments[this.segments.length - 1] ?? '';
    go(this.h, up);
  };

  override render() {
    if (!this.plan.nodes.length) {
      return html`<div class="blank" style="padding:24px">${this.live ? msg('No tasks scheduled yet') : msg('No tasks scheduled')}</div>`;
    }
    const h = this.h;
    const body = this.matrix ? matrixView(h, this.matrix) : this.asTable ? table(h) : dag(h);
    return html`${crumbs(h)}${missingLine(this.missing)}
      <div class="main">${body}${inspector(h, this.announced)}</div>
      ${foot(h)}`;
  }

  /** This element as its views see it (`pipeline-graph/host.ts`), its private members included. */
  private viewHost(): GraphHost {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- the getters below read the element, not the object they are on
    const el = this;
    return {
      el,
      get root() { return el.renderRoot; },
      get plan() { return el.plan; },
      get journal() { return el.journal; },
      get run() { return el.run; },
      get live() { return el.live; },
      get sel() { return el.sel; },
      get unit() { return el.unit; },
      get segments() { return el.segments; },
      get auto() { return el.auto; },
      get graph() { return el.graph; },
      get matrix() { return el.matrix; },
      get links() { return el.links; },
      get lay() { return el.lay; },
      get layPath() { return el.layPath; },
      get down() { return el.down; },
      get asTable() { return el.asTable; },
      set asTable(v) { el.asTable = v; },
      get hover() { return el.hover; },
      set hover(v) { el.hover = v; },
      get sort() { return el.sort; },
      set sort(v) { el.sort = v; },
      get scrollRow() { return el.scrollRow; },
      set scrollRow(v) { el.scrollRow = v; },
      get cell() { return el.cell; },
      set cell(v) { el.cell = v; },
      active: el.active,
      pz: el.pz,
      card: el.card,
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-pipeline-graph': CaPipelineGraph;
  }
}
