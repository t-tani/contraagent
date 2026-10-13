// Where the monitor is: one typed value, kept in the URL. Pure: parsing and
// formatting only; `router.ts` binds it to the browser's history.

export const BUILTIN_TABS = ['overview', 'tasks', 'journal', 'outputs', 'definitions', 'procs', 'stream'] as const;
export type BuiltinTab = (typeof BUILTIN_TABS)[number];
/** A built-in view, or a panel the pipeline registered (`panel:<name>`). */
export type Tab = BuiltinTab | `panel:${string}`;

/** What the task view shows next to (or instead of) the transcript. */
export const TASK_VIEWS = ['transcript', 'input', 'output', 'definition'] as const;
export type TaskView = (typeof TASK_VIEWS)[number];

export interface Route {
  /** The run; '' until one is picked. */
  run: string;
  tab: Tab;
  /** stream tab: the task key whose transcript is open (null: the latest, `latestTask`). */
  key: string | null;
  /** stream tab: what the task view shows. */
  view: TaskView;
  /** stream tab: the round shown, 1-based (null: follow the latest). */
  round: number | null;
  /** definitions tab: the selected kind (null: the default one). */
  def: string | null;
  /** tasks and journal tabs: only this kind (kept, and out of the URL, while another tab is shown). */
  kind: string;
  /** journal tab: only this stop ('bad': every attempt that did not complete). */
  stop: string;
  /** tasks and journal tabs: a text filter. */
  q: string;
  /** overview tab: the pipeline graph's layer, its segments joined by `/` ('': the layer the graph opens on). */
  layer: string;
  /** overview tab: the unit highlighted in the pipeline graph. */
  unit: string;
  /** overview tab: what is selected in the pipeline graph's layer (a node, a loop box or a mark; '' for nothing). */
  sel: string;
}

export type RoutePatch = Partial<Route>;

export const DEFAULT_ROUTE: Route = {
  run: '',
  tab: 'overview',
  key: null,
  view: 'transcript',
  round: null,
  def: null,
  kind: '',
  stop: '',
  q: '',
  layer: '',
  unit: '',
  sel: '',
};

const isTab = (t: string): t is Tab => (BUILTIN_TABS as readonly string[]).includes(t) || /^panel:.+/.test(t);
const isTaskView = (v: string): v is TaskView => (TASK_VIEWS as readonly string[]).includes(v);

export function parseRoute(search: string): Route {
  const p = new URLSearchParams(search);
  const tab = p.get('tab') ?? '';
  const view = p.get('view') ?? '';
  const round = Number(p.get('round'));
  return {
    run: p.get('run') ?? '',
    tab: isTab(tab) ? tab : 'overview',
    key: p.get('key') || null,
    view: isTaskView(view) ? view : 'transcript',
    round: Number.isInteger(round) && round > 0 ? round : null,
    def: p.get('def') || null,
    kind: p.get('kind') ?? '',
    stop: p.get('stop') ?? '',
    q: p.get('q') ?? '',
    layer: p.get('layer') ?? '',
    unit: p.get('unit') ?? '',
    sel: p.get('sel') ?? '',
  };
}

/** The query string for a route: only what differs from the defaults, and only what its tab uses. */
export function formatRoute(r: Route): string {
  const p = new URLSearchParams();
  if (r.run) p.set('run', r.run);
  if (r.tab !== 'overview') p.set('tab', r.tab);
  if (r.tab === 'stream') {
    if (r.key) p.set('key', r.key);
    if (r.view !== 'transcript') p.set('view', r.view);
    if (r.round != null) p.set('round', String(r.round));
  }
  if (r.tab === 'definitions' && r.def) p.set('def', r.def);
  if (r.tab === 'overview' && r.layer) p.set('layer', r.layer);
  if (r.tab === 'overview' && r.unit) p.set('unit', r.unit);
  if (r.tab === 'overview' && r.sel) p.set('sel', r.sel);
  // The filters of the Tasks and History tabs: kept while another tab is shown (going back finds them), named in the URL only on their tabs.
  const filtered = r.tab === 'tasks' || r.tab === 'journal';
  if (filtered && r.kind) p.set('kind', r.kind);
  if (r.tab === 'journal' && r.stop) p.set('stop', r.stop);
  if (filtered && r.q) p.set('q', r.q);
  const s = p.toString();
  return s ? `?${s}` : '';
}

/** Apply a patch. Leaving a task (another key, run) forgets its view and round; another run forgets every selection. */
export function applyPatch(r: Route, patch: RoutePatch): Route {
  const next = { ...r, ...patch };
  if (patch.run !== undefined && patch.run !== r.run) {
    Object.assign(next, { key: null, def: null, round: null, layer: '', unit: '', sel: '', ...patch });
  }
  // A selection belongs to its layer.
  if (patch.layer !== undefined && patch.layer !== r.layer && patch.sel === undefined) next.sel = '';
  if (patch.key !== undefined && patch.key !== r.key) {
    if (patch.view === undefined) next.view = 'transcript';
    if (patch.round === undefined) next.round = null;
  }
  return next;
}

/**
 * Whether going from `a` to `b` is a move to another place (a new history entry,
 * so Back returns) or only a refinement of this one (the entry is replaced, so
 * typing in a filter, highlighting a unit or selecting in the graph does not fill the history).
 */
export function isNewPlace(a: Route, b: Route): boolean {
  const place = (r: Route) => formatRoute({ ...r, kind: '', stop: '', q: '', unit: '', sel: '' });
  return place(a) !== place(b);
}
