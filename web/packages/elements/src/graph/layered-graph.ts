// A layered graph: nodes in layers, joined by edges, in clusters; each node a
// group of marks, one per series. The views are in `views/`.
import { LitElement, adoptStyles, html, nothing, type CSSResult, type PropertyValueMap, type PropertyValues } from 'lit';
import { keyed } from 'lit/directives/keyed.js';
import { emit } from '../core/events.js';
import { withDefaults } from '../core/strings.js';
import type { CaeMarkMatrix } from '../matrix/mark-matrix.js';
import type { MarkMatrixInput, MarkMatrixStrings } from '../matrix/types.js';
import { legendStyles } from '../primitives/legend.js';
import { icon } from '../primitives/icon.js';
import type { StateStyles } from '../primitives/states.js';
import { base, markStyles } from '../styles/index.js';
import { arrange } from './arrange.js';
import { CardController } from './card.js';
import { slotsOf, type GraphHost } from './host.js';
import { layoutGraph, type GraphLayout, type Size } from './layout.js';
import { BAR_MARKS, fillNode } from './marks.js';
import { PanZoomController } from './pan-zoom.js';
import { DEFAULT_LAYERED_GRAPH_STRINGS, type LayeredGraphStrings } from './strings.js';
import { graphStyles } from './styles.js';
import type { Arrangement, DrawnGraph, GraphClusterInput, GraphInput, GraphNode, GraphOrder } from './types.js';
import { dag } from './views/dag.js';
import { foot } from './views/foot.js';
import { nodeTable } from './views/node-table.js';

/** Below this width, `direction: 'auto'` draws top to bottom, without zoom. */
export const NARROW = 640;

/** The changes `willUpdate` reads: the properties, and the private `down`. */
type Changed = PropertyValues<CaeLayeredGraph> & PropertyValueMap<{ down: boolean }>;

const EMPTY: GraphInput = { series: [], nodes: [], clusters: [], edges: [], stubs: [] };

/**
 * A layered graph: each node in a layer by the longest path to it, edges bending only
 * in the gaps between layers and never passing a node or a cluster's label; a cluster
 * of nodes in a box (a cluster in a cluster: a box in a box), with, when it `cycle`s,
 * a dotted return from its last layer to its first; an edge from outside the graph
 * from a named stub. Inside each node, one mark per series id, at the same place in
 * every node, so a series can be followed across the graph; a mark is drawn in its
 * state's look (`states`). Above `barAt` marks, a node shows a bar of its counts and
 * lists its failed marks. The order depends on the structure only, and keeps a
 * previous `order`: nodes that appear later are added at the end of their layer.
 *
 * A click selects a mark, a node or a cluster (`cae-select`); a card beside it (the
 * host's content, in the `inspector` slot) moves with it as the graph pans and zooms,
 * and hides while it is out of the frame; on a narrow screen it is a sheet under the
 * frame. A double click or Enter is the item's action (`cae-activate`), or opens its
 * inner view (`cae-drill`, for an item with `drill`). Hovering or focusing a mark
 * highlights its series and what `related` names. The frame first shows the whole
 * graph; Ctrl (or ⌘) and the wheel, or the buttons, zoom; dragging pans; "Show all"
 * goes back. "Graph | Table" changes the view (`cae-view-change`): the table is a row
 * per node, with its status and the nodes it is joined to. With `matrix`, the frame
 * shows that `<cae-mark-matrix>` as the table instead.
 *
 * Size: the element is as wide as its container. Without a height set on it, the
 * frame is as tall as the whole drawing at that width (never scaled up), up to 70% of
 * the window's height or 360 px, whichever is more, and taller when the card needs
 * it; top to bottom, as tall as the drawing. A height set on the element
 * (or given it by a flex or grid container) is shared: the `crumbs` slot and the row
 * under the frame keep theirs, and the frame takes the rest, the drawing fitted in it.
 *
 * Keyboard: Tab moves between nodes; the arrow keys, Home and End move between a
 * node's marks, and a mark out of the frame is brought into it; Shift and an arrow
 * key move along an edge to an earlier or a later node, on the same series; what has
 * the focus is selected (Tab goes on to the card); Enter is the item's action; Escape
 * clears the selection (and, with none, is left to the host).
 *
 * @tagname cae-layered-graph
 * @fires cae-select - `{id}`: a mark, a node, a cluster or a table row was selected; `{id: null}`: the selection was cleared
 * @fires cae-activate - `{id}`: an item's action (a double click or Enter)
 * @fires cae-drill - `{id}`: an item's inner view (a double click or Enter on an item with `drill`, a cluster's chip in the table, a later part of a cluster's `path`)
 * @fires cae-toggle - `{id, open}`: an item's open or close control (`toggle`) was used
 * @fires cae-view-change - `{view}`: "Graph" or "Table" was chosen
 * @slot inspector - the selected item's card: its first heading and its `[data-status]` name it to a screen reader
 * @slot crumbs - a line above the frame (where the graph is)
 * @csspart frame - the frame every view is drawn in
 * @csspart stage - what pans and zooms
 * @csspart node - each node
 * @csspart node-header - a node's first line
 * @csspart node-name - a node's name
 * @csspart mark - each mark
 * @csspart cluster - each cluster
 * @csspart cluster-label - a cluster's header
 * @csspart edge - each edge
 * @csspart stub - each stub
 * @csspart legend - the legend
 * @csspart keys - the line of key hints under the legend
 * @csspart inspector - the selected item's card
 * @csspart table - the node table
 * @csspart row - each row of the node table
 */
export class CaeLayeredGraph extends LitElement {
  static override styles = [base, markStyles, legendStyles, graphStyles];
  static override properties = {
    graph: { attribute: false },
    states: { attribute: false },
    selected: { attribute: false },
    highlight: { attribute: false },
    order: { attribute: false },
    key: {},
    direction: {},
    view: {},
    matrix: { attribute: false },
    barAt: { type: Number },
    related: { attribute: false },
    strings: { attribute: false },
    matrixStrings: { attribute: false },
    renderIcon: { attribute: false },
    iconStyles: { attribute: false },
    hover: { state: true },
    down: { state: true },
    lay: { state: true },
    announced: { state: true },
  };

  graph: GraphInput = EMPTY;
  states: StateStyles = {};
  /** The selected item's id (a mark's, a node's or a cluster's), or null. */
  selected: string | null = null;
  /** The series highlighted while no mark is hovered, focused or selected. */
  highlight: string | null = null;
  /** The order of an earlier drawing of this graph (`arrange(...).order`): its items stay where they are. */
  order: GraphOrder | undefined = undefined;
  /** The graph's identity: a new key is a new graph (the frame shows all of it again); the same key while the graph changes keeps the zoom and pan. */
  key = '';
  /** Left to right, top to bottom, or by the width (`auto`: top to bottom below `NARROW` px). */
  direction: 'auto' | 'across' | 'down' = 'auto';
  /** The node table instead of the drawing. */
  view: 'graph' | 'table' = 'graph';
  /** A mark matrix shown in the frame as the table, or null. */
  matrix: MarkMatrixInput | null = null;
  /** Above this many marks, a node shows a bar of its counts. */
  barAt = BAR_MARKS;
  /** The marks a hovered or selected series (or a mark's id, outside any series) lights; default: its own. */
  related: ((key: string) => ReadonlySet<string>) | undefined = undefined;
  strings: Partial<LayeredGraphStrings> = {};
  matrixStrings: Partial<MarkMatrixStrings> = {};
  /** Draws an icon of a node, a matrix header and the legend; default: `icon(name)`. */
  renderIcon: (name: string) => unknown = (name) => icon(name);
  /** Styles for what `renderIcon` draws, added to the element's own. */
  iconStyles: readonly CSSResult[] = [];

  /** The series (or a mark's id) under the pointer or focus. */
  private hover: string | null = null;
  /** Top to bottom. */
  private down = false;
  /** Where everything is drawn, from the sizes measured after the last render. */
  private lay: GraphLayout | null = null;
  /** What the live region says: the item just selected, and its status. */
  private announced = '';

  private arr: Arrangement = arrange(EMPTY);
  private words: LayeredGraphStrings = DEFAULT_LAYERED_GRAPH_STRINGS;
  /** The graph, its nodes with their defaults. */
  private drawn: DrawnGraph = { ...EMPTY, nodes: [] };
  private nodes = new Map<string, GraphNode>();
  private clusters = new Map<string, GraphClusterInput>();
  /** Each mark's series ('' outside any series), by its id. */
  private markSeries = new Map<string, string>();
  /** Each group's focused mark (roving tabindex): one tab stop per group. */
  private readonly active = new Map<string, number>();
  /** What the sizes were last measured for, what the layout was computed from, and the graph it is of. */
  private measured: { graph: GraphInput; key: string } | null = null;
  private layKey = '';
  private layFor: string | null = null;
  private litCache: { key: string | null; graph: GraphInput; related: unknown; on: ReadonlySet<string> | null } | null = null;
  private scrolled: Element | null = null;

  private readonly pz = new PanZoomController(this, {
    frame: () => this.renderRoot.querySelector<HTMLElement>('.frame'),
    stage: () => this.renderRoot.querySelector<HTMLElement>('.stage'),
    drawing: () => (this.lay && !this.matrix ? { w: this.lay.w, h: this.lay.h, down: this.down, room: this.card.room } : null),
    wheel: () => this.view !== 'table' && !this.matrix,
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
    // A mark matrix: the frame's least height holds the card.
    grow: () => (this.matrix ? this.requestUpdate() : this.fit()),
    pressed: () => this.pz.pressed,
    inner: () => this.matrixEl()?.renderRoot ?? null,
  });

  /** This element as its views see it (`host.ts`), its private members included. */
  private readonly h = this as unknown as GraphHost;

  private matrixEl(): CaeMarkMatrix | null {
    return this.renderRoot.querySelector<CaeMarkMatrix>('cae-mark-matrix');
  }

  protected override willUpdate(changed: Changed): void {
    if (changed.has('key') && changed.get('key') !== undefined) {
      this.pz.reset();
      this.active.clear();
    }
    if (changed.has('strings')) this.words = withDefaults(DEFAULT_LAYERED_GRAPH_STRINGS, this.strings);
    if (changed.has('direction') && this.direction !== 'auto') this.down = this.direction === 'down';
    if (changed.has('graph') || changed.has('order') || changed.has('down') || changed.has('direction')) {
      this.arr = arrange(this.graph, this.order, this.down);
      this.clusters = new Map(this.graph.clusters.map((c) => [c.id, c]));
    }
    if (changed.has('graph') || changed.has('states') || changed.has('strings')) {
      const g = this.graph;
      this.drawn = { ...g, nodes: g.nodes.map((n) => fillNode(n, this.states, this.words.progress)) };
      this.nodes = new Map(this.drawn.nodes.map((n) => [n.id, n]));
      this.markSeries = new Map(this.drawn.nodes.flatMap((n) => slotsOf(n, g.series).flatMap((s) => (s ? [[s.m.id, s.series] as const] : []))));
    }
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.addEventListener('keydown', this.onEscape);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener('keydown', this.onEscape);
  }


  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('iconStyles') && this.renderRoot instanceof ShadowRoot)
      adoptStyles(this.renderRoot, [...(this.constructor as typeof LitElement).elementStyles, ...this.iconStyles]);
    const mx = this.matrixEl();
    if (mx && mx !== this.scrolled) {
      // A scroll inside the matrix moves the selected mark: the card follows it.
      this.scrolled = mx;
      mx.renderRoot.addEventListener('scroll', () => this.card.place(), { capture: true });
    }
    this.place();
    this.card.place();
    if (changed.has('selected')) this.selectionChanged();
  }

  /**
   * Put the focus on an item without selecting it: a node (its focused mark, else its
   * name) or a cluster (its name); with null, or when it is not drawn, on the first
   * thing to focus (in the `crumbs` slot, else the first node).
   */
  /** Put the focus on an item's open or close control (`toggle`), else on the item: where it was after the item was drawn again. */
  focusToggle(id: string, tries = 4): void {
    const root = this.renderRoot;
    // A drawing of a new structure is first drawn hidden, to be measured: focus it once it is placed.
    if (root.querySelector('.dag.unplaced') && tries > 0) {
      void this.updateComplete.then(() => requestAnimationFrame(() => this.focusToggle(id, tries - 1)));
      return;
    }
    const sel = this.clusters.has(id) ? `.cluster[data-cluster="${CSS.escape(id)}"] > .cue .tog` : `.node[data-id="${CSS.escape(id)}"] .tog`;
    const el = root.querySelector<HTMLElement>(sel);
    if (el) this.card.focusQuietly(el);
    else this.focusItem(id);
  }

  focusItem(id: string | null): void {
    const root = this.renderRoot;
    let el: HTMLElement | null = null;
    if (id && this.clusters.has(id)) el = root.querySelector<HTMLElement>(`.cluster[data-cluster="${CSS.escape(id)}"] > .hd .name`);
    else if (id) el = root.querySelector<HTMLElement>(`.node[data-id="${CSS.escape(id)}"] [tabindex="0"]`);
    const crumbs = root.querySelector<HTMLSlotElement>('slot[name="crumbs"]')?.assignedElements({ flatten: true }) ?? [];
    const first = () =>
      crumbs.map((c) => (c.matches('button') ? (c as HTMLElement) : c.querySelector<HTMLElement>('button'))).find(Boolean) ??
      root.querySelector<HTMLElement>('.mark[tabindex="0"], .node .name') ??
      this.matrixEl()?.renderRoot.querySelector<HTMLElement>('.mark[tabindex="0"]') ??
      null;
    this.card.focusQuietly(el ?? first());
  }

  /** After a new selection: the card describes the item, the live region names it, and on a narrow screen the item is scrolled into view. */
  private selectionChanged(): void {
    const [name, status] = this.card.describe();
    const said = name ? [name, status].filter(Boolean).join(' | ') : '';
    if (said !== this.announced) this.announced = said;
    if (this.down) this.card.whenReleased(() => this.card.revealOverSheet());
  }

  /** Measure what was drawn when the graph or the width changed; lay it out again when the structure or a size changed. */
  private place(): void {
    const dagEl = this.renderRoot.querySelector<HTMLElement>('.dag');
    if (!dagEl) return;
    const g = this.graph;
    const seen = `${this.down}|${this.clientWidth}`;
    if (this.measured?.graph === g && this.measured.key === seen) return this.fit();
    this.measured = { graph: g, key: seen };
    const sizes = new Map<string, Size>();
    for (const el of dagEl.querySelectorAll<HTMLElement>('[data-id]')) sizes.set(el.dataset['id'] ?? '', { w: el.offsetWidth, h: el.offsetHeight });
    const a = this.arr;
    const key = JSON.stringify([this.key, a.slots, a.edgePaths.map((r) => r.steps.map((s) => s.id)), this.down, [...sizes]]);
    if (key === this.layKey) return this.fit();
    this.layKey = key;
    this.layFor = this.key;
    this.lay = layoutGraph(a, sizes, this.down);
    void this.updateComplete.then(() => this.fit());
  }

  /** Top to bottom on a narrow screen (`auto`); otherwise the whole graph in a frame, until the reader zooms or pans. */
  private fit(): void {
    if (this.direction === 'auto') {
      const w = this.clientWidth;
      const down = w > 0 && w < NARROW;
      if (down !== this.down) this.down = down;
    }
    this.pz.fit();
  }

  private readonly onEscape = (e: KeyboardEvent): void => {
    if (e.key !== 'Escape' || e.defaultPrevented || !this.selected) return;
    e.preventDefault();
    this.select(null);
  };

  private select(id: string | null): void {
    if (id !== this.selected) emit(this, 'cae-select', { id });
  }

  /** An item's action: its inner view when it has one. */
  protected act(id: string): void {
    const x = this.nodes.get(id) ?? this.clusters.get(id) ?? this.findMark(id);
    if (x?.drill) this.drill(id);
    else if (x) emit(this, 'cae-activate', { id });
  }

  private findMark(id: string): { drill?: boolean } | null {
    for (const n of this.drawn.nodes) for (const m of [...n.marks, ...n.loose]) if (m?.id === id) return m;
    for (const r of this.matrix?.rows ?? []) for (const m of r.cells) if (m?.id === id) return m;
    return null;
  }

  /** The series (or mark id) highlighted: the one hovered or focused, else the selected mark's, else `highlight`; and the marks it lights. */
  protected lit(): { key: string | null; on: ReadonlySet<string> | null } {
    const sel = this.selected;
    const mine = this.hover === null && sel !== null && this.markSeries.has(sel) ? this.markSeries.get(sel) || sel : null;
    const key = this.hover ?? mine ?? this.highlight ?? null;
    const c = this.litCache;
    if (c && c.key === key && c.graph === this.graph && c.related === this.related) return c;
    const on = key === null ? null : (this.related ?? ((k: string) => new Set([k])))(key);
    this.litCache = { key, graph: this.graph, related: this.related, on };
    return this.litCache;
  }

  private known(id: string): boolean {
    return this.nodes.has(id) || this.clusters.has(id) || !!this.findMark(id);
  }

  override render() {
    const h = this.h;
    const mx = this.matrix;
    const body = mx ? this.matrixView(mx) : this.view === 'table' ? nodeTable(h) : dag(h);
    const sel = this.selected;
    const card =
      sel && this.querySelector('[slot=inspector]') && this.known(sel)
        ? keyed(
            sel,
            html`<section id="insp" class="insp ${this.down ? 'sheet' : ''}" part="inspector" aria-label=${this.words.inspector} @keydown=${this.card.onCardKey}>
              <span class="ptr" aria-hidden="true"></span>
              <div class="scroll"><slot name="inspector"></slot></div>
            </section>`,
          )
        : nothing;
    return html`<div class="col">
      <slot name="crumbs"></slot>
      <div class="main">${body}${card}<div class="sr" role="status">${this.announced}</div></div>
      ${foot(h, mx)}
    </div>`;
  }

  /** A mark matrix in the frame, at least as tall as the drawing was (and as the card needs), centred in it. */
  private matrixView(mx: MarkMatrixInput) {
    const least = this.down ? 0 : Math.round(Math.max(this.pz.frameH, this.card.room));
    return html`<div class="frame mxframe" part="frame" style=${least ? `min-height:${least}px` : ''}>
      <cae-mark-matrix .matrix=${mx} .states=${this.states} .selected=${this.selected} .highlight=${this.highlight} .key=${this.key}
        .strings=${this.matrixStrings} .renderIcon=${this.renderIcon} .iconStyles=${this.iconStyles}></cae-mark-matrix>
    </div>`;
  }

  // What the views read and call besides the members above (`host.ts`).
  protected get laidOut(): boolean {
    return this.layFor === this.key;
  }

  protected get asTable(): boolean {
    return this.view === 'table';
  }

  protected focusSelect(id: string): void {
    if (!this.card.quiet) this.select(id);
  }

  protected drill(id: string): void {
    emit(this, 'cae-drill', { id });
  }

  protected toggle(id: string, open: boolean): void {
    emit(this, 'cae-toggle', { id, open });
  }

  protected showView(v: 'graph' | 'table'): void {
    // A mark matrix is the table: only "Graph" leaves it, and the host decides where to.
    if (this.matrix && v === 'table') return;
    if (!this.matrix) this.view = v;
    emit(this, 'cae-view-change', { view: v });
  }

}

declare global {
  interface HTMLElementTagNameMap {
    'cae-layered-graph': CaeLayeredGraph;
  }
}
