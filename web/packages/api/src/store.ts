// The monitor's data, live: the run list, the selected run's feed folded into a
// `RunState`, and a change notification. No UI framework: a Lit controller, a
// React hook or plain code can subscribe alike.
import { ApiError, createMonitorClient, type MonitorClient } from './client.js';
import type { RunFeedOpener } from './export.js';
import { openRunFeed, type FeedOptions, type Unsubscribe } from './feed.js';
import { emptyRunState, reduceRun, rowId, type RunAction, type RunState } from './run-state.js';
import { isRunPanel } from './panels.js';
import type { Hosts, Info, JournalRow, JsonObject, RunFeedMessage, RunSummary, Trends, TrendsQuery } from './types.js';

export interface MonitorSnapshot {
  info: Info;
  runs: RunSummary[];
  /** The hosts behind the runs, on a hub (`Info.hosts`); null elsewhere and until they arrive. */
  hosts: Hosts | null;
  /** The run whose feed is open; '' for none. */
  run: string;
  state: RunState;
  /** The feed is connected. */
  connected: boolean;
  /** Journal rows (by `rowId`) that arrived in the last few seconds, after the replay. */
  fresh: ReadonlySet<string>;
  /** The run list has been answered: `runs` is the server's, not the empty start. */
  runsLoaded: boolean;
  /** Why the last request for `info`, `runs` or (on a hub) `hosts` got no answer; null while all are answered. */
  error: ApiError | null;
  /** The trends of the period last asked for (`loadTrends`); null until one is asked for. */
  trends: TrendsView | null;
}

/** The trends of one period, and the trend panels' bodies over it. */
export interface TrendsView {
  query: TrendsQuery;
  /** null until the first answer for this query. */
  data: Trends | null;
  /** Each trend panel's body (`Panel(scope="trends")`), by name, as it arrives. */
  panels: Readonly<Record<string, JsonObject>>;
  loading: boolean;
  /** Why the last request for the trends got no answer. */
  error: ApiError | null;
}

export interface StoreOptions {
  baseUrl?: string;
  client?: MonitorClient;
  feed?: FeedOptions;
  /** Opens a run's feed instead of the server's `/events` (an export's: `openExportFeed`). */
  openRunFeed?: RunFeedOpener;
  /** How often the run list (and on a hub, the host list) is refreshed; 0: never (an export). */
  runsEveryMs?: number;
  /** Feed messages are folded in batches this far apart. */
  batchMs?: number;
  /** How long a new journal row counts as fresh. */
  freshMs?: number;
}

const DEFAULT_INFO: Info = { title: 'contraagent', panels: [], api_version: '' };

/** A client given in the options may throw something else: it counts as no response from `url`. */
const asApiError = (e: unknown, url: string): ApiError => (e instanceof ApiError ? e : new ApiError(url, 'network'));

export class MonitorStore {
  readonly client: MonitorClient;
  private snap: MonitorSnapshot = {
    info: DEFAULT_INFO,
    runs: [],
    hosts: null,
    run: '',
    state: emptyRunState(),
    connected: false,
    fresh: new Set(),
    runsLoaded: false,
    error: null,
    trends: null,
  };
  /** The trends asked for last (`loadTrends`), kept fresh with the run list; null: none. */
  private trendsQuery: TrendsQuery | null = null;
  /** Counts the trend requests: an answer to an older one is dropped. */
  private trendsAsked = 0;
  /** Why the last request for `info`, for `runs`, and for `hosts` got no answer. */
  private infoError: ApiError | null = null;
  private runsError: ApiError | null = null;
  private hostsError: ApiError | null = null;
  private infoLoaded = false;
  private stopped = false;
  private readonly listeners = new Set<(s: MonitorSnapshot) => void>();
  private readonly rowListeners = new Set<(row: JournalRow) => void>();
  private closeFeed: Unsubscribe | null = null;
  private queue: RunAction[] = [];
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private readonly opts: Required<Pick<StoreOptions, 'runsEveryMs' | 'batchMs' | 'freshMs'>> & StoreOptions;

  constructor(opts: StoreOptions = {}) {
    this.opts = { runsEveryMs: 5000, batchMs: 50, freshMs: 4000, ...opts };
    this.client = opts.client ?? createMonitorClient(opts.baseUrl === undefined ? {} : { baseUrl: opts.baseUrl });
  }

  get snapshot(): MonitorSnapshot {
    return this.snap;
  }

  /** Called on every change, with the new snapshot. */
  subscribe(fn: (s: MonitorSnapshot) => void): Unsubscribe {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** Called for each journal row that arrives after the replay: a task that just finished. */
  onNewRow(fn: (row: JournalRow) => void): Unsubscribe {
    this.rowListeners.add(fn);
    return () => this.rowListeners.delete(fn);
  }

  /**
   * Load the title, panels and run list, and keep the run list fresh. A request
   * that gets no answer sets `error`; the title and panels are asked for again
   * with each refresh until they arrive.
   */
  async start(): Promise<void> {
    this.stopped = false;
    await this.refresh();
    if (!this.stopped && this.opts.runsEveryMs > 0) this.pollTimer ??= setInterval(() => void this.refresh(), this.opts.runsEveryMs);
  }

  private async refresh(): Promise<void> {
    if (!this.infoLoaded) await this.loadInfo();
    await this.refreshRuns();
    if (this.trendsQuery) await this.fetchTrends(this.trendsQuery);
  }

  /**
   * Load the trends of `query` (`/api/trends`) and the trend panels over it, and keep them
   * fresh with the run list until `closeTrends`. The trends of another query stay shown
   * until the new ones arrive (`loading`).
   */
  async loadTrends(query: TrendsQuery): Promise<void> {
    const same = this.snap.trends && JSON.stringify(this.snap.trends.query) === JSON.stringify(query);
    this.trendsQuery = query;
    this.set({ trends: { query, data: same ? this.snap.trends!.data : (this.snap.trends?.data ?? null), panels: same ? this.snap.trends!.panels : {}, loading: true, error: null } });
    await this.fetchTrends(query);
  }

  /** Stop keeping the trends fresh (the page left them). */
  closeTrends(): void {
    this.trendsQuery = null;
  }

  private async fetchTrends(query: TrendsQuery): Promise<void> {
    const asked = ++this.trendsAsked;
    const names = this.snap.info.panels.filter((p) => p.scope === 'trends').map((p) => p.name);
    const [trends, ...bodies] = await Promise.allSettled([
      this.client.trends(query),
      ...names.map((n) => this.client.trendsPanel(n, query)),
    ]);
    if (asked !== this.trendsAsked || this.stopped) return;
    const panels: Record<string, JsonObject> = {};
    bodies.forEach((b, i) => (panels[names[i]!] = b.status === 'fulfilled' ? b.value : { error: String(b.reason) }));
    this.set({
      trends: {
        query,
        data: trends.status === 'fulfilled' ? trends.value : (this.snap.trends?.data ?? null),
        panels,
        loading: false,
        error: trends.status === 'fulfilled' ? null : asApiError(trends.reason, `${this.client.baseUrl}/api/trends`),
      },
    });
  }

  private async loadInfo(): Promise<void> {
    try {
      const before = this.panelNames();
      const info = await this.client.info();
      if (this.stopped) return;
      this.infoLoaded = true;
      this.infoError = null;
      this.set({ info });
      // A run opened before the panel list arrived listens for no panel: open it again.
      if (this.snap.run && this.panelNames() !== before) this.reopen();
    } catch (e) {
      this.infoError = asApiError(e, `${this.client.baseUrl}/api/info`);
    }
  }

  /** Fetch the run list, and on a hub the host list beside it: both refresh together, so a run's host reads the same in both. */
  async refreshRuns(): Promise<void> {
    const [runs, hosts] = await Promise.allSettled([this.client.runs(), this.snap.info.hosts ? this.client.hosts() : Promise.resolve(null)]);
    if (this.stopped) return;
    // A failed request keeps the last list.
    const patch: Partial<MonitorSnapshot> = {};
    if (runs.status === 'fulfilled') {
      patch.runs = runs.value;
      patch.runsLoaded = true;
      this.runsError = null;
    } else this.runsError = asApiError(runs.reason, `${this.client.baseUrl}/api/runs`);
    if (hosts.status === 'fulfilled') {
      patch.hosts = hosts.value;
      this.hostsError = null;
    } else this.hostsError = asApiError(hosts.reason, `${this.client.baseUrl}/api/hosts`);
    const error = this.infoError ?? this.runsError ?? this.hostsError;
    // The same failure again keeps the same `error`.
    if (error?.message !== this.snap.error?.message) patch.error = error;
    if (Object.keys(patch).length) this.set(patch);
  }

  private panelNames(): string {
    return this.snap.info.panels.filter(isRunPanel).map((p) => p.name).join('\n');
  }

  /** Open the current run's feed again (the server replays it from the start). */
  private reopen(): void {
    const run = this.snap.run;
    this.closeFeed?.();
    this.closeFeed = null;
    this.selectRun(run);
  }

  /** Open `run`'s feed (closing the previous one); '' closes it. */
  selectRun(run: string): void {
    if (run === this.snap.run && (this.closeFeed || !run)) return;
    this.closeFeed?.();
    this.closeFeed = null;
    this.queue = [];
    this.set({ run, state: emptyRunState(), connected: false, fresh: new Set() });
    if (!run) return;
    const panels = this.snap.info.panels.filter(isRunPanel).map((p) => p.name);
    const on = {
      open: () => {
        this.push({ event: 'connected' });
        this.set({ connected: true });
      },
      error: () => this.set({ connected: false }),
      message: (msg: RunFeedMessage) => this.push(msg),
    };
    this.closeFeed = this.opts.openRunFeed
      ? this.opts.openRunFeed(run, panels, on)
      : openRunFeed(run, panels, on, { ...(this.opts.baseUrl === undefined ? {} : { baseUrl: this.opts.baseUrl }), ...this.opts.feed });
  }

  /** Close the feed and stop refreshing; an answer that arrives later is dropped. */
  stop(): void {
    this.stopped = true;
    this.closeFeed?.();
    this.closeFeed = null;
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = null;
  }

  private push(a: RunAction): void {
    this.queue.push(a);
    this.flushTimer ??= setTimeout(() => this.flush(), this.opts.batchMs);
  }

  private flush(): void {
    this.flushTimer = null;
    const batch = this.queue;
    this.queue = [];
    // Rows that arrive once the replay is over are new: announce them and mark them fresh.
    let ready = this.snap.state.ready;
    const fresh: JournalRow[] = [];
    for (const a of batch) {
      if (a.event === 'connected') ready = false;
      else if (a.event === 'ready') ready = true;
      else if (a.event === 'journal' && ready) fresh.push(a.data);
    }
    const state = reduceRun(this.snap.state, batch);
    if (!fresh.length) {
      this.set({ state });
      return;
    }
    const ids = new Set(this.snap.fresh);
    for (const row of fresh) ids.add(rowId(row));
    this.set({ state, fresh: ids });
    for (const row of fresh) for (const fn of this.rowListeners) fn(row);
    setTimeout(() => {
      const left = new Set(this.snap.fresh);
      for (const row of fresh) left.delete(rowId(row));
      this.set({ fresh: left });
    }, this.opts.freshMs);
  }

  private set(patch: Partial<MonitorSnapshot>): void {
    this.snap = { ...this.snap, ...patch };
    for (const fn of this.listeners) fn(this.snap);
  }
}
