// The monitor's data, live: the run list, the selected run's feed folded into a
// `RunState`, and a change notification. No UI framework: a Lit controller, a
// React hook or plain code can subscribe alike.
import { ApiError, createMonitorClient, type MonitorClient } from './client.js';
import { openRunFeed, type FeedOptions, type Unsubscribe } from './feed.js';
import { emptyRunState, reduceRun, rowId, type RunAction, type RunState } from './run-state.js';
import type { Info, JournalRow, RunSummary } from './types.js';

export interface MonitorSnapshot {
  info: Info;
  runs: RunSummary[];
  /** The run whose feed is open; '' for none. */
  run: string;
  state: RunState;
  /** The feed is connected. */
  connected: boolean;
  /** Journal rows (by `rowId`) that arrived in the last few seconds, after the replay. */
  fresh: ReadonlySet<string>;
  /** The run list has been answered: `runs` is the server's, not the empty start. */
  runsLoaded: boolean;
  /** Why the last request for `info` or `runs` got no answer; null while both are answered. */
  error: ApiError | null;
}

export interface StoreOptions {
  baseUrl?: string;
  client?: MonitorClient;
  feed?: FeedOptions;
  /** How often the run list is refreshed. */
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
    run: '',
    state: emptyRunState(),
    connected: false,
    fresh: new Set(),
    runsLoaded: false,
    error: null,
  };
  /** Why the last request for `info`, and for `runs`, got no answer. */
  private infoError: ApiError | null = null;
  private runsError: ApiError | null = null;
  private infoLoaded = false;
  private stopped = false;
  /** The message last written to the console, so a poll that fails the same way does not repeat it. */
  private logged = '';
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
   * that gets no answer sets `error` and is written to the console; the title
   * and panels are asked for again with each refresh until they arrive.
   */
  async start(): Promise<void> {
    this.stopped = false;
    await this.refresh();
    if (!this.stopped) this.pollTimer ??= setInterval(() => void this.refresh(), this.opts.runsEveryMs);
  }

  private async refresh(): Promise<void> {
    if (!this.infoLoaded) await this.loadInfo();
    await this.refreshRuns();
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

  async refreshRuns(): Promise<void> {
    try {
      const runs = await this.client.runs();
      if (this.stopped) return;
      this.runsError = null;
      this.set({ runs, runsLoaded: true });
    } catch (e) {
      // The last list stays.
      this.runsError = asApiError(e, `${this.client.baseUrl}/api/runs`);
    }
    if (!this.stopped) this.report();
  }

  /** Set `error` from the last answers, and write a new one to the console. */
  private report(): void {
    const error = this.infoError ?? this.runsError;
    if (error && error.message !== this.logged) console.error(error);
    this.logged = error?.message ?? '';
    if (error?.message !== this.snap.error?.message) this.set({ error });
  }

  private panelNames(): string {
    return this.snap.info.panels.map((p) => p.name).join('\n');
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
    this.closeFeed = openRunFeed(
      run,
      this.snap.info.panels.map((p) => p.name),
      {
        open: () => {
          this.push({ event: 'connected' });
          this.set({ connected: true });
        },
        error: () => this.set({ connected: false }),
        message: (msg) => this.push(msg),
      },
      { ...(this.opts.baseUrl === undefined ? {} : { baseUrl: this.opts.baseUrl }), ...this.opts.feed },
    );
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
