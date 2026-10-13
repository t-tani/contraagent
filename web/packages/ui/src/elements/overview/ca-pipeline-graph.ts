import type { JournalRow, Plan } from '@contraagent/api';
import '@contraagent/elements/graph/define';
import { NARROW, arrange, type CaeLayeredGraph, type GraphInput, type GraphOrder } from '@contraagent/elements/graph';
import type { MarkMatrixInput } from '@contraagent/elements/matrix';
import type { StateStyles } from '@contraagent/elements/primitives';
import { localized, msg } from '@lit/localize';
import { LitElement, html, nothing, type PropertyValueMap, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
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
import { executorIcon } from '../../words/executor.js';
import { go, leavePasses, open, primary, select, tasksOf } from './pipeline-graph/actions.js';
import { crumbs, missingLine } from './pipeline-graph/crumbs.js';
import type { PipelineHost } from './pipeline-graph/host.js';
import { inspector } from './pipeline-graph/inspector.js';
import { graphStrings, matrixStrings } from './pipeline-graph/strings.js';
import { graphStyles, iconStyles } from './pipeline-graph/styles.js';

/** The changes `willUpdate` reads: the properties, and the private `down` and `sort`. */
type Changed = PropertyValues<CaPipelineGraph> & PropertyValueMap<{ down: boolean; sort: MatrixSort }>;

const EMPTY_LAYER: LayerGraph = {
  ...arrange({ nodes: [], clusters: [], edges: [], stubs: [] }),
  path: [],
  nodes: [],
  boxes: [],
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

  /** Top to bottom: the graph does not fit left to right. */
  @state() private down = false;
  /** A loop's passes: how its units are sorted. */
  @state() private sort: MatrixSort = 'order';
  /** The layer the route named that this run does not have (shown once the graph fell back to its opening layer). */
  @state() private missing = '';
  /** The route's layer to set right after this update, and that change, which is not the reader's. */
  private fixLayer: string | null = null;
  private replacing = false;

  /** The layer the graph opens on, the one shown, and what it shows. */
  private auto: string[] = [];
  private segments: string[] = [];
  private proj: Projection | null = null;
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
    const structure = changed.has('plan') || changed.has('layer') || changed.has('run') || changed.has('down');
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
      const { path } = splitLayer(this.segments);
      this.proj = project(this.plan, path);
      this.prevOrder = this.orders.get(path.join('/'));
    }
    const locale = getLocale();
    const words = structure || changed.has('journal') || changed.has('live') || locale !== this.locale;
    if (words || changed.has('sort')) this.build(words, locale);
  }

  /** The generic graph's model of the layer (`words`: its words changed), its arrangement, and a loop's passes. */
  private build(words: boolean, locale: string): void {
    const proj = this.proj;
    if (!proj) return;
    const { path, loop } = splitLayer(this.segments);
    const x = { plan: this.plan, journal: this.journal, run: this.run, live: this.live, links: this.links };
    if (words) {
      this.locale = locale;
      this.states = taskStateStyles(this.live);
      this.input = graphInput(proj.model, x);
      const a = arrange(this.input, this.prevOrder, this.down);
      this.graph = arranged(proj.model, a);
      this.orders.set(path.join('/'), a.order);
      this.lights = lightsOf(this.plan, this.links, this.graph);
    }
    const m = loop ? matrixFromPlan(this.plan, path, loop, this.graph.order, this.sort, x, proj) : null;
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
    });
    this.resize.observe(this);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.removeEventListener('keydown', this.onEscape);
    this.resize?.disconnect();
  }

  protected override updated(): void {
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
    if (s?.type === 'mark') open(this.h, s.mark);
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
    const s = parseSelection(this.graph, this.matrix, this.sel);
    const functions = this.graph.nodes.some((n) => n.type === 'flow');
    return html`<cae-layered-graph .graph=${this.input} .states=${this.states} .selected=${this.sel || null} .highlight=${this.unit || null}
        .order=${this.prevOrder} key=${this.segments.join('/')} direction=${this.down ? 'down' : 'across'} .matrix=${this.matrixIn}
        .related=${this.lights} .strings=${graphStrings(!!parentLayer(this.segments, this.auto), functions)} .matrixStrings=${matrixStrings()}
        .renderIcon=${renderIcon} .iconStyles=${iconStyles}
        @cae-select=${this.onSelect} @cae-activate=${this.onActivate} @cae-drill=${this.onDrill} @cae-view-change=${this.onView}
        @cae-sort=${(e: CustomEvent<{ id: string }>) => (this.sort = e.detail.id as MatrixSort)}>
      <div slot="crumbs">${crumbs(this.h)}${missingLine(this.missing)}</div>
      ${s ? inspector(this.h, s) : nothing}
    </cae-layered-graph>`;
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

declare global {
  interface HTMLElementTagNameMap {
    'ca-pipeline-graph': CaPipelineGraph;
  }
}
