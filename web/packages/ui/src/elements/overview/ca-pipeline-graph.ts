import type { JournalRow, Plan } from '@contraagent/api';
import '@contraagent/elements/graph/define';
import { NARROW, arrange, extentOf, type CaeLayeredGraph, type GraphInput, type GraphOrder } from '@contraagent/elements/graph';
import type { MarkMatrixInput } from '@contraagent/elements/matrix';
import type { StateStyles } from '@contraagent/elements/primitives';
import { localized, msg } from '@lit/localize';
import { LitElement, html, nothing, type PropertyValueMap, type PropertyValues } from 'lit';
import { customElement } from 'lit/decorators.js';
import { compound, FLOW_BOX, IN_SEP, placeKey, placeStats, type PlaceStats } from '../../adapters/graph/compound.js';
import { indexOf, startsWith } from '../../adapters/graph/flow-index.js';
import { related, taskLinks, type TaskLinks } from '../../adapters/graph/highlight.js';
import { graphInput, matrixFromPlan } from '../../adapters/graph/input.js';
import { autoLayer, parentLayer, resolveLayer, splitLayer } from '../../adapters/graph/layer.js';
import type { MatrixSort, PassMatrix } from '../../adapters/graph/matrix.js';
import { arranged, project, type Projection } from '../../adapters/graph/project.js';
import { markSel, parseSelection } from '../../adapters/graph/selection.js';
import type { LayerGraph, LayerMark } from '../../adapters/graph/types.js';
import { taskStateStyles } from '../../adapters/graph/words.js';
import { emit } from '../../core/events.js';
import { getLocale } from '../../core/i18n.js';
import { flushMemory, RememberedSet } from '../../core/memory.js';
import { executorIcon } from '../../words/executor.js';
import { go, leavePasses, open, primary, select, tasksOf } from './pipeline-graph/actions.js';
import { crumbs, missingLine, openControls, type OpenMode } from './pipeline-graph/crumbs.js';
import type { PipelineHost } from './pipeline-graph/host.js';
import { inspector } from './pipeline-graph/inspector.js';
import { outline, outlineTree, type OutlineHost, type OutlineItem } from './pipeline-graph/outline.js';
import { graphStrings, matrixStrings } from './pipeline-graph/strings.js';
import { graphStyles, iconStyles } from './pipeline-graph/styles.js';

/** The changes `willUpdate` reads: the properties, and the private `down`, `sort`, `rev` and `budget`. */
type Changed = PropertyValues<CaPipelineGraph> & PropertyValueMap<{ down: boolean; sort: MatrixSort; rev: number; budget: number }>;

/** The most nodes the drawing holds before it stops opening functions on its own, for a frame `w` px wide. */
export const budgetFor = (w: number): number => Math.max(14, Math.min(60, Math.round(w / 34)));

/** The most layers the drawing spans before it closes again what it opened on its own, for a frame `w` px wide: about one screen. */
export const spanFor = (w: number): number => Math.max(8, Math.min(16, Math.round(w / 105)));

/**
 * A drawing `span` layers long, left to right in a frame `w` px wide, would be scaled below
 * this to fit: it is drawn top to bottom instead, where the frame grows with it. About
 * a node and the gap after it, per layer.
 */
const LEGIBLE = 0.6;
const LAYER_PX = 180;
export const tooWide = (span: number, w: number): boolean => w > 0 && w / (span * LAYER_PX) < LEGIBLE;

/** From this width the outline is a column beside the graph (about this wide, with its gap); below it, a part above it that opens. */
const OUTLINE_WIDE = 1500;
const OUTLINE_COLUMN = 300;

/** The entries of the opened set that are a mode, not a place. */
const MODE_ALL = '*all';
const MODE_NONE = '*none';

const EMPTY_LAYER: LayerGraph = {
  ...arrange({ nodes: [], clusters: [], edges: [], stubs: [] }),
  path: [],
  nodes: [],
  boxes: [],
  fns: [],
  edges: [],
  stubs: [],
  units: [],
};

/**
 * The run as a graph of its flow, one layer at a time (`<cae-layered-graph>` draws
 * it). A layer shows the kinds of the tasks its function created (a kind node each,
 * joined to the ones it waits for) and the functions it called (a function node each,
 * holding their tasks); nodes created in one loop are drawn in a loop box, with its
 * last pass ("up to 3 passes") and, when its units ran different numbers of passes,
 * how many ran each ("1 pass: 4 | 2 passes: 1"); a nested loop's box is inside it, and
 * a dotted edge inside each box, from its last layer back to its first, is the return
 * to its next pass. A kind node names who runs its tasks (✦ and an accent: an agent
 * task; ⚙: a Python task); a function node and a loop box carry the mark of an inner
 * view (their layer, their passes). Inside a node, one mark per unit, at the same place
 * in every node, so a unit can be followed across the layer: a task in a kind node, a
 * flow call in a function node; in a loop box, the unit's latest pass, with the number
 * of passes it ran when more than 1. A mark of several tasks shows the most severe
 * state among them (failed, running, not started, waiting, skipped, done); a flow
 * call's mark counts every task of it and of the flow calls it started, and its own
 * error (raised or closed) as failed. A node's count is its tasks done of its tasks,
 * with the others by state, and a function node names its flow calls that stopped
 * with an error. A problem has a square mark (failed: red; not started: hatched),
 * every other state a round one. Above 200 marks, a node shows a bar of its counts and
 * names its failed marks. A solid edge waits for an output; a dashed edge was created
 * after a result; an edge from outside the layer starts at a named stub.
 *
 * A click selects a mark, a node or a loop box (`sel`); the card beside it shows its
 * facts and links to where it leads: a mark to its task detail, a kind node to its
 * tasks, a function node to its layer, a loop box to its passes. A double click, or
 * Enter, follows the first of them. Hovering or focusing a mark highlights its unit
 * and the tasks joined to it, as the selected mark does. The graph opens on the first
 * layer with more than one node (a static flow's kinds), or on a single function node
 * whose flow call raised; a layer the run does not have opens that one, with a line
 * naming it, and the route is set right in place (a function named by its qualified
 * name alone opens its layer when the run reaches it by one flow path). A loop's
 * passes are a row per unit and a column per node and pass, a nested loop's passes as
 * a group of columns inside each pass of the outer one, the units sortable by number
 * of passes or by status (`<cae-mark-matrix>`). The breadcrumb, shown on every layer
 * below the top (a loop named by its file and line), and Escape go back up. On a
 * narrow screen the graph runs top to bottom. "Graph | Table" changes the view; in a
 * loop's passes, "Graph" opens the layer the loop is in, with its box selected.
 *
 * @fires ca-open-task - `{key, view?}`: a mark's task detail was opened (a task that did not start opens on its input, a Python task on its output)
 * @fires ca-navigate - `{sel}`: a mark, a node, a table row or a loop box was selected, or the selection cleared; `{tab: 'tasks', kind}`: a kind node's tasks (`kind` '' for a node of several kinds); `{layer, unit?}`: a function's layer, a loop's passes, a flow call's function or the breadcrumb, or Escape; `{layer, unit, sel}`: "Graph" in a loop's passes, its box selected; `{layer, unit, sel, replace: true}`: the route's layer set right
 */
@customElement('ca-pipeline-graph')
@localized()
export class CaPipelineGraph extends LitElement {
  static override styles = graphStyles;
  static override properties = {
    plan: { attribute: false },
    journal: { attribute: false },
    run: {},
    live: { type: Boolean },
    layer: {},
    unit: {},
    sel: {},
    down: { state: true },
    sort: { state: true },
    missing: { state: true },
    rev: { state: true },
    budget: { state: true },
    wide: { state: true },
  };

  plan: Plan = { nodes: [], groups: [] };
  /** The finished attempts: they tell why a task did not start. */
  journal: JournalRow[] = [];
  /** The run id: paths in a cause are shown relative to it. */
  run = '';
  /** The run is running: tasks still pending are waiting; once it is over, they did not run. */
  live = false;
  /** The layer shown: its segments (function names, then `loop:<line>` for a loop's passes) joined by `/`; '' for the layer the graph opens on. */
  layer = '';
  /** The unit highlighted while nothing is hovered or focused. */
  unit = '';
  /** What is selected in the layer: a node or a loop box by its id, a mark by `markSel`; '' for nothing. */
  sel = '';

  /** Top to bottom: the frame is narrow. */
  private down = false;
  /** Top to bottom: the drawing is too long to read left to right in the frame. */
  private tall = false;
  /** A loop's passes: how its units are sorted. */
  private sort: MatrixSort = 'order';
  /** The layer the route named that this run does not have (shown once the graph fell back to its opening layer). */
  private missing = '';
  /** The route's layer to set right after this update, and that change, which is not the reader's. */
  private fixLayer: string | null = null;
  private replacing = false;

  /** The layer the graph opens on, the one shown, and what it shows. */
  private auto: string[] = [];
  private segments: string[] = [];
  /** The layer alone, for a loop's passes; null when the layer is drawn with its functions. */
  private proj: Projection | null = null;
  /** The layer as it is drawn: alone, or with its functions drawn open. */
  private model: Projection['model'] | null = null;
  private graph: LayerGraph = EMPTY_LAYER;
  private input: GraphInput = { series: [], nodes: [], clusters: [], edges: [], stubs: [] };
  /** The order the layer was last drawn in, before this update: the graph keeps it. */
  private prevOrder: GraphOrder | undefined = undefined;
  private matrix: PassMatrix | null = null;
  private matrixIn: MarkMatrixInput | null = null;
  /** Each layer's order, so nodes stay where they are while the plan grows. */
  private orders = new Map<string, GraphOrder>();
  private links: TaskLinks = taskLinks([]);
  private states: StateStyles = taskStateStyles(false);
  /** The locale the words were last made in. */
  private locale = '';
  /** The functions the reader opened and closed (and the mode: all or none opened), kept per run in the page's memory. */
  private opened: RememberedSet | null = null;
  private closed: RememberedSet | null = null;
  private memRun: string | null = null;
  /** A change to them: the layer is drawn again. */
  private rev = 0;
  /** The most nodes the drawing holds before it stops opening functions on its own (`budgetFor` the frame). */
  private budget = 40;
  /** The places drawn open, and what each place holds. */
  private shownOpen = new Set<string>();
  private stats = new Map<string, PlaceStats>();
  /** After this update, the focus goes on this item's open or close control. */
  private focusToggle = '';
  /** The outline: the flow's places from its top, as a tree; the items the reader folded or unfolded. */
  private flowStats = new Map<string, PlaceStats>();
  private tree: OutlineItem[] = [];
  private folds = new Map<string, boolean>();
  /** The frame is wide enough for the outline as a column. */
  private wide = true;
  private readonly oh: OutlineHost = this.outlineHost();
  /** What a hovered or selected mark lights, for this layer. */
  private lights: (key: string) => ReadonlySet<string> = () => new Set();
  /** After this update, the focus goes into the new layer: on the item it came from (`cameFrom`), else the first. */
  private refocus = false;
  private cameFrom = '';
  private resize?: ResizeObserver;

  private readonly h: PipelineHost = this.partsHost();

  protected override willUpdate(changed: Changed): void {
    if (changed.has('run')) this.orders.clear();
    if (changed.has('layer') && changed.get('layer') !== undefined) {
      // The focus stays where it is on the view switch; elsewhere it goes to the new layer.
      const at = this.renderRoot instanceof ShadowRoot ? this.renderRoot.activeElement : null;
      const inner = at?.shadowRoot?.activeElement;
      this.refocus = at !== null && !inner?.closest('.views');
      if (this.replacing) this.replacing = false;
      else this.missing = '';
    }
    if (changed.has('run') && changed.get('run') !== undefined) this.missing = '';
    if (changed.has('plan')) this.links = taskLinks(this.plan.nodes);
    if (changed.has('plan') || changed.has('live')) {
      this.flowStats = placeStats(indexOf(this.plan), [], this.live);
      this.tree = outlineTree(this.flowStats);
    }
    if (changed.has('run')) this.folds.clear();
    // A selection the drawing does not show (an outline's item, a link) opens the functions around it.
    const hidden = changed.has('sel') && !!this.sel && !splitLayer(this.segments).loop && !parseSelection(this.graph, this.matrix, this.sel);
    const structure =
      changed.has('plan') || changed.has('layer') || changed.has('run') || changed.has('down') || changed.has('rev') || changed.has('budget') || hidden;
    if (structure) {
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
      if (loop) {
        // A loop's passes: its layer drawn alone.
        this.proj = project(this.plan, path);
        this.model = this.proj.model;
      } else {
        const mem = this.memory();
        const mode = this.openMode();
        const c = compound(this.plan, path, {
          open: new Set(mem.opened.values().filter((k) => !k.startsWith('*'))),
          closed: new Set(mem.closed.values()),
          all: mode === 'all',
          budget: mode === 'none' ? 0 : this.budget,
          maxSpan: spanFor(this.graphWidth()),
          sel: this.sel,
          live: this.live,
        });
        this.proj = null;
        this.model = c.model;
        this.shownOpen = c.open;
        this.stats = c.stats;
      }
      this.prevOrder = this.orders.get(path.join('/'));
    }
    const locale = getLocale();
    const words = structure || changed.has('journal') || changed.has('live') || locale !== this.locale;
    if (words || changed.has('sort')) this.build(words, locale);
  }

  /** The generic graph's model of the layer (`words`: its words changed), its arrangement, and a loop's passes. */
  private build(words: boolean, locale: string): void {
    const model = this.model;
    if (!model) return;
    const proj = this.proj;
    const { path, loop } = splitLayer(this.segments);
    const x = { plan: this.plan, journal: this.journal, run: this.run, live: this.live, links: this.links };
    if (words) {
      this.locale = locale;
      this.states = taskStateStyles(this.live);
      this.input = graphInput(model, x, !loop);
      let a = arrange(this.input, this.prevOrder, this.down);
      // Too long to read left to right in this frame: top to bottom.
      this.tall = !this.down && !loop && tooWide(extentOf(a).span, this.graphWidth());
      if (this.tall) a = arrange(this.input, this.prevOrder, true);
      this.graph = arranged(model, a);
      this.orders.set(path.join('/'), a.order);
      this.lights = lightsOf(this.plan, this.links, this.graph);
    }
    const m = loop && proj ? matrixFromPlan(this.plan, path, loop, this.graph.order, this.sort, x, proj) : null;
    this.matrix = m?.matrix ?? null;
    this.matrixIn = m?.input ?? null;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this.addEventListener('keydown', this.onEscape);
    // Top to bottom on a narrow screen.
    this.resize = new ResizeObserver(() => {
      const w = this.clientWidth;
      const down = w > 0 && w < NARROW;
      if (down !== this.down) this.down = down;
      const budget = w > 0 ? budgetFor(this.graphWidth()) : this.budget;
      if (budget !== this.budget) this.budget = budget;
      const wide = w === 0 || w >= OUTLINE_WIDE;
      if (wide !== this.wide) this.wide = wide;
    });
    this.resize.observe(this);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener('keydown', this.onEscape);
    this.resize?.disconnect();
  }

  /** The reader's opens and closes of this run's functions. */
  private memory(): { opened: RememberedSet; closed: RememberedSet } {
    if (!this.opened || !this.closed || this.memRun !== this.run) {
      this.memRun = this.run;
      this.opened = new RememberedSet(`graph-open:${this.run}`, this);
      this.closed = new RememberedSet(`graph-closed:${this.run}`, this);
    }
    return { opened: this.opened, closed: this.closed };
  }

  /** Which functions are drawn open: those chosen (`auto`), every one, or only those the reader opened. */
  private openMode(): OpenMode {
    const { opened } = this.memory();
    return opened.has(MODE_ALL) ? 'all' : opened.has(MODE_NONE) ? 'none' : 'auto';
  }

  private setMode(mode: OpenMode): void {
    const { opened, closed } = this.memory();
    opened.clear();
    closed.clear();
    if (mode === 'all') opened.set(MODE_ALL, true);
    if (mode === 'none') opened.set(MODE_NONE, true);
    // The reader's choice is written at once: a reload right after keeps it.
    flushMemory();
    this.rev++;
  }

  /** A function node's place, by its id in the drawing. */
  private placeOfNode(id: string): string | null {
    const n = this.graph.nodes.find((x) => x.id === id);
    if (!n || n.type !== 'flow') return null;
    const local = id.includes(IN_SEP) ? id.slice(id.lastIndexOf(IN_SEP) + IN_SEP.length) : id;
    return placeKey(n.layer, local);
  }

  /** Open or close a function: `id` is its node (to open) or its cluster (to close). */
  private toggle(id: string, open: boolean): void {
    const key = id.startsWith(FLOW_BOX) ? id.slice(FLOW_BOX.length) : this.placeOfNode(id);
    if (!key) return;
    const { opened, closed } = this.memory();
    opened.set(key, open);
    closed.set(key, !open);
    flushMemory();
    // The focus stays on the control: the cluster's once open, the node's once closed.
    this.focusToggle = open ? `${FLOW_BOX}${key}` : this.nodeIdOf(key);
    this.rev++;
  }

  /** The id a place's node will have once drawn closed. */
  private nodeIdOf(key: string): string {
    const s = this.stats.get(key);
    if (!s) return '';
    const parent = s.parent;
    return parent === null || !this.shownOpen.has(parent) ? s.id : `${parent}${IN_SEP}${s.id}`;
  }

  private readonly onToggle = (e: CustomEvent<{ id: string; open: boolean }>): void => this.toggle(e.detail.id, e.detail.open);

  protected override updated(): void {
    if (this.focusToggle) {
      const id = this.focusToggle;
      this.focusToggle = '';
      const el = this.renderRoot.querySelector<CaeLayeredGraph>('cae-layered-graph');
      if (el) void el.updateComplete.then(() => el.focusToggle(id));
    }
    if (this.fixLayer !== null) {
      // Set the route's layer right, in place: the reader did not go anywhere.
      const layer = this.fixLayer;
      this.fixLayer = null;
      this.replacing = true;
      emit(this, 'ca-navigate', { layer, unit: this.unit, sel: this.sel, replace: true });
    }
    if (this.refocus || this.cameFrom) {
      const from = this.cameFrom;
      this.refocus = false;
      this.cameFrom = '';
      // The node (or loop box) it came from, else the first item; it does not select.
      const id = from.startsWith('loop:') ? from : (this.graph.nodes.find((n) => n.type === 'flow' && n.name === from)?.id ?? null);
      const el = this.renderRoot.querySelector<CaeLayeredGraph>('cae-layered-graph');
      if (el) void el.updateComplete.then(() => el.focusItem(from ? id : null));
    }
  }

  private readonly onEscape = (e: KeyboardEvent): void => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    const up = parentLayer(this.segments, this.auto);
    if (!up) return;
    e.preventDefault();
    this.refocus = true;
    this.cameFrom = this.segments[this.segments.length - 1] ?? '';
    go(this.h, up);
  };

  private readonly onSelect = (e: CustomEvent<{ id: string | null }>): void => select(this.h, e.detail.id ?? '');

  private readonly onActivate = (e: CustomEvent<{ id: string }>): void => {
    const s = parseSelection(this.graph, this.matrix, e.detail.id);
    if (s?.type === 'mark') open(this.h, s.mark, s.node);
    else if (s?.type === 'node') tasksOf(this.h, s.node);
  };

  private readonly onDrill = (e: CustomEvent<{ id: string }>): void => {
    const s = parseSelection(this.graph, this.matrix, e.detail.id);
    if (s) primary(this.h, s);
  };

  private readonly onView = (e: CustomEvent<{ view: 'graph' | 'table' }>): void => {
    if (e.detail.view === 'graph' && this.matrix) leavePasses(this.h);
  };

  override render() {
    if (!this.plan.nodes.length) {
      return html`<div class="blank" style="padding:24px">${this.live ? msg('No tasks scheduled yet') : msg('No tasks scheduled')}</div>`;
    }
    const graph = this.renderGraph();
    if (!this.tree.length) return graph;
    // The outline: a column beside the graph, or, on a narrow frame, a part above it that opens.
    return this.wide
      ? html`<div class="whole">${outline(this.oh, this.tree)}<div class="g">${graph}</div></div>`
      : html`<details class="odet"><summary>${msg('Outline of the flow')}</summary>${outline(this.oh, this.tree)}</details>${graph}`;
  }

  private renderGraph() {
    const s = parseSelection(this.graph, this.matrix, this.sel);
    const functions = this.graph.nodes.some((n) => n.type === 'flow');
    return html`<cae-layered-graph .graph=${this.input} .states=${this.states} .selected=${this.sel || null} .highlight=${this.unit || null}
        .order=${this.prevOrder} key=${this.segments.join('/')} direction=${this.down || this.tall ? 'down' : 'across'} .matrix=${this.matrixIn}
        .related=${this.lights} .strings=${graphStrings(!!parentLayer(this.segments, this.auto), functions)} .matrixStrings=${matrixStrings()}
        .renderIcon=${renderIcon} .iconStyles=${iconStyles}
        @cae-select=${this.onSelect} @cae-activate=${this.onActivate} @cae-drill=${this.onDrill} @cae-view-change=${this.onView} @cae-toggle=${this.onToggle}
        @cae-sort=${(e: CustomEvent<{ id: string }>) => (this.sort = e.detail.id as MatrixSort)}>
      <div slot="crumbs">${crumbs(this.h, splitLayer(this.segments).loop ? null : openControls(this.openMode(), (m) => this.setMode(m)))}${missingLine(this.missing)}</div>
      ${s ? inspector(this.h, s) : nothing}
    </cae-layered-graph>`;
  }

  /** The graph's own width: the element's, less the outline's column beside it. */
  private graphWidth(): number {
    const w = this.clientWidth || 1200;
    return this.tree.length && w >= OUTLINE_WIDE ? w - OUTLINE_COLUMN : w;
  }

  /** The place keys on the way to the layer shown (the functions of its path). */
  private currentKeys(): Set<string> {
    const { path } = splitLayer(this.segments);
    const out = new Set<string>();
    for (const s of this.flowStats.values()) {
      const d = s.layer.length;
      if (d < path.length && startsWith(path, s.layer) && path[d] === s.name) out.add(s.key);
    }
    return out;
  }

  /** The place (or loop item) the selection is, or is in: '' for none. */
  private selectedItem(): string {
    const sel = this.sel;
    if (!sel) return '';
    if (sel.startsWith(FLOW_BOX)) return sel.slice(FLOW_BOX.length);
    const id = sel.split('#')[0] ?? '';
    const node = this.graph.nodes.find((n) => n.id === id);
    if (node?.type === 'flow') return this.placeOfNode(id) ?? '';
    const box = this.graph.boxes.find((b) => b.id === id);
    return box ? `${box.layer.join('/')}|${box.local}` : '';
  }

  /** The id an outline item is drawn with, once its places are open; and those places. */
  private drawnId(item: OutlineItem): { id: string; open: string[] } | null {
    const { path } = splitLayer(this.segments);
    if (item.layer.length < path.length || !startsWith(item.layer, path)) return null;
    // The place whose layer the item is in, and every place around it, down from the layer shown.
    const places: string[] = [];
    for (let s = this.flowStats.get(item.type === 'fn' ? (this.flowStats.get(item.id)?.parent ?? '') : this.containerKey(item) ?? ''); s && s.layer.length >= path.length; s = this.flowStats.get(s.parent ?? '')) places.unshift(s.key);
    const inner = places[places.length - 1] ?? '';
    if (item.type === 'fn') {
      const s = this.flowStats.get(item.id);
      if (!s) return null;
      if (this.shownOpen.has(item.id)) return { id: `${FLOW_BOX}${item.id}`, open: places };
      return { id: inner ? `${inner}${IN_SEP}${s.id}` : s.id, open: places };
    }
    return { id: inner ? `${inner}${IN_SEP}${item.name}` : item.name, open: places };
  }

  /** The place whose layer a loop item is in ('' when it is the layer shown, null when none is known). */
  private containerKey(item: OutlineItem): string | null {
    const { path } = splitLayer(this.segments);
    if (item.layer.length === path.length) return '';
    for (const s of this.flowStats.values()) if ([...s.layer, s.name].join('/') === item.layer.join('/')) return s.key;
    return null;
  }

  private outlineHost(): OutlineHost {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- the methods below read the element
    const el = this;
    return {
      get live() { return el.live; },
      expanded(id) {
        const own = el.folds.get(id);
        if (own !== undefined) return own;
        // Unfolded by default: the top items, and those on the way to the layer shown, to what is open and to the selection.
        const want = new Set([...el.currentKeys(), ...el.shownOpen, el.selectedItem()]);
        const has = (it: OutlineItem): boolean => want.has(it.id) || it.kids.some(has);
        const it = findItem(el.tree, id);
        return !!it && (el.tree.includes(it) || has(it));
      },
      expand(id, on) {
        el.folds.set(id, on);
        el.requestUpdate();
      },
      current: (id) => el.currentKeys().has(id),
      here: (id) => {
        const { path } = splitLayer(el.segments);
        const s = el.flowStats.get(id);
        return !!s && s.layer.length === path.length - 1 && startsWith(path, [...s.layer, s.name]);
      },
      selected: (id) => !!id && el.selectedItem() === id,
      pick(item) {
        const at = el.drawnId(item);
        if (!at) {
          // Outside the layer shown: its layer, with it selected.
          const local = item.type === 'fn' ? (el.flowStats.get(item.id)?.id ?? '') : item.name;
          emit(el, 'ca-navigate', { layer: item.layer.join('/') === el.auto.join('/') ? '' : item.layer.join('/'), unit: el.unit, sel: local });
          return;
        }
        const { opened, closed } = el.memory();
        let more = false;
        for (const k of at.open) {
          if (!el.shownOpen.has(k)) more = true;
          opened.set(k, true);
          closed.set(k, false);
        }
        if (more) el.rev++;
        select(el.h, at.id);
      },
      enter(item) {
        // A chain: the layer of its last function, where its content is.
        const last = item.parts[item.parts.length - 1] ?? item;
        go(el.h, [...last.layer, last.name]);
      },
    };
  }

  /** This element as its parts see it (`pipeline-graph/host.ts`), its private members included. */
  private partsHost(): PipelineHost {
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- the getters below read the element, not the object they are on
    const el = this;
    return {
      el,
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
    };
  }
}

/** An executor's icon: `agent` or `python`. */
const renderIcon = (name: string) => executorIcon(name === 'python');

/**
 * What a hovered or selected mark lights in a layer: for a unit (or the key of a mark
 * without one), the marks of the tasks joined to its tasks upstream or downstream.
 */
function lightsOf(plan: Plan, links: TaskLinks, g: LayerGraph): (key: string) => ReadonlySet<string> {
  const marks: [string, LayerMark][] = g.nodes.flatMap((n) =>
    [...n.units, ...n.single].filter((m): m is LayerMark => m !== null).map((m): [string, LayerMark] => [markSel(n.id, m), m]),
  );
  const keyOf = new Map(marks.map(([id, m]) => [id, m.key]));
  const memo = new Map<string, ReadonlySet<string>>();
  return (key) => {
    const had = memo.get(key);
    if (had) return had;
    const on = related(plan.nodes, links, keyOf.get(key) ?? key);
    const lit = new Set(marks.filter(([, m]) => m.keys.some((k) => on.has(k))).map(([id]) => id));
    memo.set(key, lit);
    return lit;
  };
}

/** The outline item `id`, wherever it is in the tree. */
function findItem(items: readonly OutlineItem[], id: string): OutlineItem | undefined {
  for (const it of items) {
    if (it.id === id) return it;
    const k = findItem(it.kids, id);
    if (k) return k;
  }
  return undefined;
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-pipeline-graph': CaPipelineGraph;
  }
}
