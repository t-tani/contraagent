import {
  createExportClient,
  deriveRun,
  isRunLive,
  liveActivities,
  MonitorStore,
  hostOf,
  openExportFeed,
  runActivity,
  runIdOf,
  runRow,
  type MonitorSnapshot,
  type RunDerived,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import type { ChooseThemeDetail, FilterDetail, NavigateDetail, OpenTaskDetail, SelectRunDetail } from '../../core/events.js';
import { LOCALE_NAMES, allLocales, chooseLocale, configureLocales, getLocale, isLocale, type Locale } from '../../core/i18n.js';
import { LocalMemory, flushMemory, keepMemory, memoryOf } from '../../core/memory.js';
import { ScrollMemory } from '../../core/scroll.js';
import type { Route, RoutePatch, Tab } from '../../core/route.js';
import { Router, type RouteCause, type RouterMode } from '../../core/router.js';
import { LocaleController } from '../../controllers/locale.js';
import { ShortcutsController, isShortcutScope, type ShortcutScope } from '../../controllers/shortcuts.js';
import { ThemeController } from '../../controllers/theme.js';
import { runLine, runLineAccounts, triesLine } from '../../words/index.js';
import { stubLabel, stubTip } from '../../words/run-line.js';
import { exportTip, exportedLabel } from '../../words/export.js';
import { apiErrorLine } from '../../words/api-error.js';
import { accountsTip } from '../../words/quota.js';
import { hostFact, hostsLine, lastReport, noReportLabel } from '../../words/hosts.js';
import { pill } from '@contraagent/elements/primitives';
import { runTone, type Tone } from '../../lib/tone.js';
import { RovingFocusController, toneAttr } from '@contraagent/elements';
import '@contraagent/elements/segmented/define';
import { base } from '@contraagent/elements/styles';
import { adoptThemes, hostThemeStyles, rememberTheme, type ThemeChoice, type ThemeName } from '@contraagent/elements/themes';
import { rowToast, type CaToasts } from './ca-toasts.js';
import { monitorStyles } from './styles.js';
import { monitorTabs, moveTabIndicator, tabBar, tabId, tabStyles } from './tabs.js';
import { brand, connection, nowLine } from './header.js';
import { tabView } from './views.js';
import './ca-clock.js';
import './ca-hosts.js';
import './ca-run-picker.js';
import './ca-toasts.js';
import './ca-theme-switch.js';
import '../trends/ca-trends.js';
import { browserZone, runGroups, trendsQuery } from '../../lib/trends.js';
import { trendsTip, trendsTitle } from '../../words/trends.js';

/** Applies a typed filter to the URL after the reader stops typing, so the history is not written per key. */
const Q_DEBOUNCE_MS = 250;

/**
 * The whole monitor: header, run switcher, tabs, filters and the views, live.
 * It owns the data (`MonitorStore`) and the route (`Router`); every view below
 * it only renders what it is given and sends `ca-*` events back up.
 */
@customElement('ca-monitor')
@localized()
export class CaMonitor extends LitElement {
  static override styles = [hostThemeStyles, base, tabStyles, monitorStyles];

  /**
   * Where the monitor's API is served, such as `http://127.0.0.1:8787`; '' is
   * this page's origin. A server on another origin must allow this page's
   * (`contraagent monitor --cors-origin`). It takes effect whenever it is set,
   * before or after the element connects: a change closes the old server's
   * feeds and opens the run named by `run`, else the new server's newest run.
   * A request that gets no JSON answer (a network error, a status outside 2xx,
   * or an HTML page from a server without the API) is shown above the view,
   * with its URL and cause, and written to the console.
   */
  @property({ attribute: 'base-url' }) baseUrl = '';
  /**
   * An export to read instead of a server (`contraagent monitor export`): its `data/`
   * directory, relative to the page (`export="data/"`) or absolute. The monitor then
   * makes no request to an API and opens no feed: it reads the export's files, which
   * hold no transcripts and no processes. Set, it outranks `base-url`.
   */
  @property({ attribute: 'export' }) exportUrl = '';
  /**
   * `url`: the monitor is the page. The route lives in the address bar (Back
   * and reload return to it), and the monitor sets the page's title, `lang` and
   * theme. `memory`: for a monitor embedded in another page. The route, the
   * scroll positions and the open sections live in the element, and the page's
   * URL, history, title and `<html>` attributes stay the host's. A change after
   * connecting takes effect at once: `memory` keeps the route shown, `url`
   * reads the address bar's.
   */
  @property() history: RouterMode = 'url';
  /**
   * Where the single-key shortcuts (1 to 9 for the tabs, `r` for the runs, `/`
   * for the filter) work: `page`, anywhere in the page except in a text field;
   * `element`, only while the focus is inside the monitor; `off`, nowhere.
   * Unset: `page` with `history="url"`, `element` with `history="memory"`.
   */
  @property() shortcuts: ShortcutScope | '' = '';
  /**
   * The run to open first (in `memory` mode, or when the URL names none). A
   * change after connecting opens that run.
   */
  @property() run = '';
  /**
   * The language to show (`en`, `ja`). Unset: the reader's earlier choice, else
   * the browser's language. The header's switch changes it and remembers it.
   */
  @property() locale: Locale | '' = '';
  /**
   * The theme: `contraagent-dark`, `contraagent-light`, `system` (one of the two,
   * as the system's colour scheme), `github-dark`, `github-light`, `one-dark`,
   * `nord` or `high-contrast`. Unset: the reader's earlier choice, else
   * `contraagent-dark`. The header's control changes it and remembers it. The
   * theme shown is reflected as `data-ca-theme` (on `<html>` too, with `history="url"`).
   */
  @property() theme: ThemeChoice | '' = '';
  /** Reflects whether the run is live (the logo moves). */
  @property({ type: Boolean, reflect: true }) live = false;

  @state() private snap!: MonitorSnapshot;
  @state() private route!: Route;
  @state() private pickerOpen = false;
  /** The filter text as typed, ahead of the URL. */
  @state() private qDraft: string | null = null;

  @query('main') private main!: HTMLElement;
  @query('ca-toasts') private toasts!: CaToasts;
  @query('.runbtn') private runBtn!: HTMLButtonElement;
  @query('ca-run-picker') private picker!: HTMLElement;

  private readonly themes = new ThemeController(this, { theme: () => this.theme, pageWide: () => this.history === 'url' });

  /** One tab stop for the tab list, on the selected tab; the arrow keys, Home and End move between the tabs. */
  private readonly tabFocus = new RovingFocusController(this, {
    items: () => [...this.renderRoot.querySelectorAll<HTMLElement>('[role="tablist"] [role="tab"]')],
    layout: 'horizontal',
    wrap: true,
  });
  private store!: MonitorStore;
  private router!: Router;
  /** The `baseUrl` the store was made for, and the `history` the router was. */
  private storeBase = '';
  private routerMode: RouterMode = 'url';
  /** Stop listening to the store. */
  private readonly storeCleanups: (() => void)[] = [];
  private readonly mainScroll = new ScrollMemory('main', () => memoryOf(this));
  private pendingScroll: RouteCause | null = null;
  private qTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly cleanups: (() => void)[] = [];
  /** The scroll positions and open sections, with `history="memory"`. */
  private readonly localMemory = new LocalMemory();
  /** Closes the run picker on a click outside it; listened for on the document only while the picker is open. */
  private readonly onOutsideClick = (e: MouseEvent): void => {
    if (!e.composedPath().some((n) => n instanceof HTMLElement && (n.localName === 'ca-run-picker' || n.classList.contains('runbtn')))) this.pickerOpen = false;
  };
  private outsideClickOn = false;
  private navObserver: ResizeObserver | null = null;
  private navObserved: Element | null = null;
  private readonly language: LocaleController;
  /** Whether the elements can switch language: false when the page configured Lit Localize itself. */
  private locales = false;

  constructor() {
    super();
    this.language = new LocaleController(this, { locale: () => this.locale, pageWide: () => this.history === 'url' });
    new ShortcutsController(this, (e) => this.onKey(e), () => this.shortcutScope);
  }

  /** The first paint waits for the reader's language: its module loads when first chosen. */
  protected override async scheduleUpdate(): Promise<unknown> {
    await this.language.ready;
    return super.scheduleUpdate();
  }

  override connectedCallback(): void {
    // Set up here, not at import: a page that only imports the package keeps its own setup.
    this.locales = configureLocales();
    adoptThemes(this.ownerDocument);
    super.connectedCallback();
    this.openStore();
    this.openRouter();
    void this.store.start();
    this.cleanups.push(() => {
      this.listenOutside(false);
      this.navObserver?.disconnect();
      this.navObserver = null;
      this.navObserved = null;
    });
    this.addEventListener('ca-open-task', (e: CustomEvent<OpenTaskDetail>) => {
      this.navigate({ tab: 'stream', key: e.detail.key, ...(e.detail.view ? { view: e.detail.view } : {}) });
    });
    this.addEventListener('ca-navigate', (e: CustomEvent<NavigateDetail>) => {
      const { replace, ...patch } = e.detail;
      this.navigate(patch, { replace: replace === true });
    });
    this.addEventListener('ca-select-run', (e: CustomEvent<SelectRunDetail>) => this.navigate({ run: e.detail.run, page: '' }));
    this.addEventListener('ca-filter', (e: CustomEvent<FilterDetail>) => this.navigate(e.detail));
    this.addEventListener('ca-choose-theme', (e: CustomEvent<ChooseThemeDetail>) => {
      this.theme = e.detail.theme;
      rememberTheme(e.detail.theme);
    });
  }

  /** Where the store reads: an export's files, else the server at `baseUrl`. */
  private get source(): string {
    return this.exportUrl ? `export:${this.exportUrl}` : this.baseUrl;
  }

  /** A store for the export, else for `baseUrl`, shown and listened to; not started. */
  private openStore(): void {
    this.storeBase = this.source;
    if (this.exportUrl) {
      const client = createExportClient(new URL(this.exportUrl, this.ownerDocument.baseURI).href);
      this.store = new MonitorStore({ client, openRunFeed: openExportFeed(client), runsEveryMs: 0 });
    } else this.store = new MonitorStore({ baseUrl: this.baseUrl });
    this.show(this.store.snapshot);
    this.storeCleanups.push(
      this.store.subscribe((s) => {
        this.show(s);
        this.pickDefaultRun();
      }),
      this.store.onNewRow((row) => this.toasts?.show(...rowToast(row, this.snap.run))),
    );
  }

  private closeStore(): void {
    for (const fn of this.storeCleanups.splice(0)) fn();
    this.store.stop();
  }

  /**
   * A router for `history`, started at the `run` property's run; when it replaces
   * another router, `memory` starts at the route shown and `url` at the address bar's.
   */
  private openRouter(): void {
    this.routerMode = this.history;
    keepMemory(this, this.history === 'memory' ? this.localMemory : null);
    const at = !this.route ? (this.run ? { run: this.run } : {}) : this.history === 'memory' ? this.route : {};
    this.router = new Router(this.history, (route, cause) => this.onRoute(route, cause), at, flushMemory);
    this.router.start();
  }

  /**
   * A connection property changed while connected: a new `base-url` gets a new
   * store (the feeds of the old one close) and the run named by `run`, else the
   * newest of the new server's; a new `history` gets a new router; a new `run` opens it.
   */
  protected override willUpdate(changed: PropertyValues<this>): void {
    if (!this.isConnected || !this.store) return;
    if (this.source !== this.storeBase) {
      this.closeStore();
      this.openStore();
      this.navigate({ run: this.run }, { replace: true });
      this.store.selectRun(this.route.run);
      void this.store.start();
    }
    if (this.history !== this.routerMode) {
      this.router.stop();
      this.openRouter();
    }
    if (changed.has('run') && changed.get('run') !== undefined && this.run) this.navigate({ run: this.run });
  }

  /** Show a new snapshot of the data, and whether the run is live; write a new API failure to the console. */
  private show(snap: MonitorSnapshot): void {
    // A new failure of the API goes to the console too, as the view says it.
    if (snap.error && snap.error !== this.snap?.error) console.error(apiErrorLine(snap.error));
    this.snap = snap;
    this.live = isRunLive(snap.state, runRow(snap.runs, snap.run));
  }

  /** Where the single-key shortcuts work now: the `shortcuts` property, else by `history`. */
  private get shortcutScope(): ShortcutScope {
    return isShortcutScope(this.shortcuts) ? this.shortcuts : this.history === 'url' ? 'page' : 'element';
  }

  /** Listen for a click outside the run picker on the document (while it is open), or stop. */
  private listenOutside(on: boolean): void {
    if (on === this.outsideClickOn) return;
    this.outsideClickOn = on;
    if (on) document.addEventListener('click', this.onOutsideClick);
    else document.removeEventListener('click', this.onOutsideClick);
  }

  /** The theme shown now. */
  get shownTheme(): ThemeName {
    return this.themes.shown;
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    for (const fn of this.cleanups.splice(0)) fn();
    keepMemory(this, null);
    this.router.stop();
    this.closeStore();
    this.mainScroll.detach();
  }

  /** Go elsewhere: the route changes, and with it the URL (pushing an entry for a new place). */
  navigate(patch: RoutePatch, opts: { replace?: boolean } = {}): void {
    this.router.navigate(patch, opts);
  }

  private onRoute(route: Route, cause: RouteCause): void {
    const before = this.route;
    this.route = route;
    if (cause !== 'replace') this.qDraft = null;
    this.store.selectRun(route.run);
    // Another tab of the same trends shows what is loaded already.
    const sameTrends = before?.page === 'trends' && JSON.stringify(trendsQuery(before)) === JSON.stringify(trendsQuery(route));
    if (route.page !== 'trends') this.store.closeTrends();
    else if (!sameTrends) void this.store.loadTrends(trendsQuery(route));
    this.pickDefaultRun();
    if (cause !== 'replace') this.pendingScroll = cause;
  }

  /**
   * With no run named, open the most recent one (replacing the entry: it is a
   * default, not a step). The hosts page names none; a monitor of one host has no hosts page.
   */
  private pickDefaultRun(): void {
    const { info, runs } = this.snap;
    if (this.route.page === 'trends') return;
    if (this.route.page === 'hosts') {
      if (!info.api_version || info.hosts) return;
      this.navigate({ page: '' }, { replace: true });
    }
    const first = runs[0];
    if (!this.route.run && first) this.navigate({ run: first.run }, { replace: true });
  }

  private onKey(e: KeyboardEvent): void {
    if (e.key === 'r') {
      e.preventDefault();
      this.pickerOpen = true;
    } else if (e.key === '/') {
      e.preventDefault();
      this.renderRoot.querySelector<HTMLInputElement>('.bar input')?.focus();
    } else if (/^[1-9]$/.test(e.key) && !this.route.page) {
      const tab = monitorTabs(this.snap.info.panels)[Number(e.key) - 1];
      if (tab) this.navigate({ tab: tab.id });
    }
  }

  /** The index of the selected tab in the tab list, or -1 (a custom view the run does not have). */
  private selectedTab(): number {
    return monitorTabs(this.snap.info.panels).findIndex((t) => t.id === this.route.tab);
  }

  /** Close the run picker; the focus goes back to the button that opens it when it was in the picker. */
  private closePicker(): void {
    const inside = this.picker?.matches(':focus-within');
    this.pickerOpen = false;
    if (inside) this.runBtn?.focus();
  }

  protected override updated(): void {
    // A monitor that is the page names it, in its language.
    if (this.history === 'url' && this.snap) document.title = msg(str`${this.snap.info.title} monitor`);
    // The click on the run button that opened the picker reaches the document after this: `onOutsideClick` passes it over.
    this.listenOutside(this.isConnected && this.pickerOpen);
    this.observeNav();
    // Tab comes back into the tab list on the selected tab.
    if (this.snap && this.route) this.tabFocus.set(Math.max(0, this.selectedTab()));
    moveTabIndicator(this.renderRoot);
    if (this.main) this.mainScroll.attach(this.main);
    if (this.pendingScroll) {
      // A new place starts at the top; Back, Forward and a reload return to where the reader was.
      if (this.pendingScroll === 'push') this.mainScroll.reset();
      else this.mainScroll.restore();
      this.pendingScroll = null;
    }
  }

  /** Move the line under the selected tab when the tab bar changes size. */
  private observeNav(): void {
    const nav = this.renderRoot.querySelector('nav');
    if (!nav || typeof ResizeObserver === 'undefined') return;
    if (this.navObserved === nav) return;
    if (!this.navObserver) this.navObserver = new ResizeObserver(() => moveTabIndicator(this.renderRoot));
    else this.navObserver.disconnect();
    this.navObserver.observe(nav);
    this.navObserved = nav;
  }

  private setQ(q: string): void {
    this.qDraft = q;
    if (this.qTimer) clearTimeout(this.qTimer);
    this.qTimer = setTimeout(() => {
      this.qTimer = null;
      this.navigate({ q });
    }, Q_DEBOUNCE_MS);
  }

  /** The header's language switch: switch now, and remember it for the next visit. */
  private pickLocale(locale: Locale): void {
    this.locale = locale;
    void chooseLocale(locale);
  }

  override render() {
    if (!this.snap || !this.route) return nothing;
    const { snap, route } = this;
    const acts = liveActivities(snap.state.procs);
    const derived = deriveRun(snap.state.journal, snap.state.plan);
    const tab = this.selectedTab();
    const keys = this.shortcutScope !== 'off';
    const hub = !!snap.info.hosts;
    const hostsPage = route.page === 'hosts';
    const trendsPage = route.page === 'trends';
    return html`
      <header>
        ${brand(snap.info.title)}
        <button type="button" class="runbtn" title=${keys ? msg('Switch run (r)') : msg('Switch run')} aria-haspopup="dialog" aria-expanded=${this.pickerOpen ? 'true' : 'false'}
          @click=${() => (this.pickerOpen = !this.pickerOpen)}>
          ${hostsPage ? this.hostsLabel() : trendsPage ? this.trendsLabel() : this.runLabel(hub, derived)}
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="hdr-right">
          ${nowLine(this, acts)}
          <ca-theme-switch .value=${this.themes.choice} .system=${this.themes.system}></ca-theme-switch>
          ${this.locales
            ? html`<cae-segmented class="langs" label=${msg('Language')} .value=${getLocale()}
                .options=${allLocales.map((l) => ({ value: l, label: LOCALE_NAMES[l], lang: l }))}
                @cae-change=${(e: CustomEvent<{ value: string }>) => isLocale(e.detail.value) && this.pickLocale(e.detail.value)}></cae-segmented>`
            : nothing}
          ${snap.info.export
            ? pill({ text: exportedLabel(snap.info.export), tone: 'muted', title: exportTip(snap.info.export) })
            : connection(snap.connected)}
          <ca-clock class="clock"></ca-clock>
        </div>
        <ca-run-picker .runs=${snap.runs} current=${route.run} ?open=${this.pickerOpen} ?hub=${hub} .hosts=${snap.hosts?.hosts ?? []} page=${route.page}
          @ca-close=${() => this.closePicker()}></ca-run-picker>
      </header>
      ${hostsPage
        ? html`${this.renderApiError()}<main id="main"><ca-hosts .hosts=${snap.hosts}></ca-hosts></main>`
        : trendsPage
        ? html`${this.renderApiError()}<main id="main"><ca-trends .view=${snap.trends} days=${route.days} from=${route.from} to=${route.to}
            tz=${route.tz || browserZone()} group=${route.group} .groups=${runGroups(snap.runs)} .panels=${snap.info.panels}
            tab=${route.trendsTab} ?exported=${!!snap.info.export}></ca-trends></main>`
        : html`${this.renderTabs(derived, acts.length)} ${this.renderBar(derived)} ${this.renderApiError()}
            <main id="main" class=${route.tab === 'stream' ? 'stream' : ''} role="tabpanel" aria-labelledby=${tab >= 0 ? tabId(tab) : nothing}
              >${tabView({ snap, route, derived, q: this.qDraft ?? route.q, client: this.store.client, baseUrl: this.store.client.baseUrl })}</main>`}
      <ca-toasts></ca-toasts>
    `;
  }

  /**
   * The run button's label for a run: its status dot, its name (on a hub,
   * without the host, which follows it), no report from its host (a hub; before
   * the run line, which the button may cut), its run line.
   */
  private runLabel(hub: boolean, derived: RunDerived) {
    const { snap, route } = this;
    const summary = runRow(snap.runs, snap.run);
    const activity = runActivity(summary, !!snap.state.procs?.alive);
    const dot = runTone(activity, summary?.tasks);
    const host = hub ? (summary?.host_id ?? '') : '';
    return html`<span class="dot" data-tone=${toneAttr(dot)} aria-hidden="true"></span>
      <span class="rn" title=${host ? route.run : nothing}>${summary && host ? runIdOf(summary) : route.run || '—'}</span>
      ${host ? html`<span class="hostchip" title=${hostFact(host)}><span class="sr">${hostFact(host)}</span><span aria-hidden="true">${host}</span></span>` : nothing}
      ${activity === 'unresponsive' ? pill({ text: noReportLabel(), tone: 'attention', title: lastReport(hostOf(snap.hosts?.hosts, summary)) }) : nothing}
      ${summary?.stub ? pill({ text: stubLabel(), tone: 'muted', title: stubTip() }) : nothing}
      <span class="rs" title=${summary ? accountsTip(runLineAccounts(snap.state, summary)) : ''}>${summary ? runLine(snap.state, summary, derived) : ''}</span>`;
  }

  /** The run button's label on the trends page: its name, and what it shows. */
  private trendsLabel() {
    return html`<span class="dot" data-tone="neutral" aria-hidden="true"></span><span class="rn">${trendsTitle()}</span><span class="rs">${trendsTip()}</span>`;
  }

  /** The run button's label on the hosts page: the hosts in one line, attention while a host has no report. */
  private hostsLabel() {
    const hosts = this.snap.hosts?.hosts ?? [];
    return html`<span class="dot" data-tone=${toneAttr(hosts.some((h) => !h.up) ? 'attention' : 'neutral')} aria-hidden="true"></span>
      <span class="rn">${msg('Hosts')}</span><span class="rs">${hostsLine(hosts)}</span>`;
  }

  /** A request to the API that got no JSON answer: its URL and cause. */
  private renderApiError() {
    const { error } = this.snap;
    return html`<p class="api-error" role="alert">${error ? html`<span class="ic" aria-hidden="true">✕</span> ${apiErrorLine(error)}` : nothing}</p>`;
  }

  private renderTabs(d: RunDerived, busy: number) {
    const { state } = this.snap;
    const { tries } = d.tries;
    const tasks = d.counts;
    // A tab's count is a total: neutral, never coloured by its worst part. Only a count of what is running is.
    const badge = (id: Tab): [string | number, Tone] | null =>
      id === 'tasks'
        ? [tasks.total || '', 'neutral']
        : id === 'journal'
          ? [tries || '', 'neutral']
          : id === 'procs'
            ? [state.procs?.alive ? busy || '' : '', 'running']
            : null;
    return tabBar(monitorTabs(this.snap.info.panels), this.route.tab, badge, (id) => this.navigate({ tab: id }), 'main', this.shortcutScope !== 'off');
  }

  private renderBar(d: RunDerived) {
    const { route } = this;
    if (route.tab !== 'tasks' && route.tab !== 'journal') return nothing;
    const { counts, kinds } = d;
    const total = counts.total;
    return html`<div class="bar">
      <select title=${msg('Kind')} aria-label=${msg('Kind')} @change=${(e: Event) => this.navigate({ kind: (e.target as HTMLSelectElement).value })}>
        <option value="" ?selected=${!route.kind}>${msg('All kinds')}</option>
        ${kinds.map((k) => html`<option ?selected=${k === route.kind}>${k}</option>`)}
      </select>
      <input placeholder=${msg('Filter')} aria-label=${msg('Text filter')} size="22" title=${this.shortcutScope !== 'off' ? msg('Text filter (/)') : msg('Text filter')} .value=${this.qDraft ?? route.q}
        @input=${(e: Event) => this.setQ((e.target as HTMLInputElement).value)} />
      <span class="meta">${route.tab === 'journal'
        ? triesLine(d.tries)
        : total === 1 ? msg('1 task') : msg(str`${total} tasks`)}</span>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-monitor': CaMonitor;
  }
}
