import {
  deriveRun,
  elapsedS,
  isBad,
  isRunLive,
  latestTask,
  liveActivities,
  MonitorStore,
  runAccounts,
  runRelative,
  runRow,
  spendOf,
  type JournalRow,
  type MonitorSnapshot,
  type RunSummary,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import type { ChooseThemeDetail, FilterDetail, NavigateDetail, OpenTaskDetail, SelectRunDetail } from '../../core/events.js';
import { LOCALE_NAMES, allLocales, chooseLocale, getLocale, isLocale, preferredLocale, setLocale, type Locale } from '../../core/i18n.js';
import { ClockController } from '../../core/clock.js';
import { flushMemory } from '../../core/memory.js';
import { facts, fmtDur, kindUnit, usd } from '../../words/format.js';
import { modelSwitch, stateCount, stopLabel } from '../../words/index.js';
import { ScrollMemory } from '../../core/scroll.js';
import { runTone } from '../../lib/tone.js';
import type { Route, RoutePatch, Tab } from '../../core/route.js';
import { Router, type RouteCause, type RouterMode } from '../../core/router.js';
import { accountsLine, accountsTip } from '../../words/quota.js';
import { base } from '../../styles/base.js';
import { hostThemeStyles } from '../../styles/theme-sheet.js';
import { isThemeChoice, preferredTheme, prefersLight, rememberTheme, resolveTheme, type ThemeChoice, type ThemeName } from '../../styles/themes.js';
import { taskChip } from '../shared/task-chip.js';
import type { CaToasts } from './ca-toasts.js';
import './ca-run-picker.js';
import './ca-toasts.js';
import './ca-theme-switch.js';
import '../overview/ca-overview.js';
import '../lists/ca-task-table.js';
import '../lists/ca-journal-table.js';
import '../lists/ca-contracts.js';
import '../lists/ca-definitions.js';
import '../lists/ca-procs-view.js';
import '../lists/ca-panel-view.js';
import '../task/ca-task-view.js';

interface TabInfo {
  id: Tab;
  label: string;
  icon: string;
  tip?: string;
  panel: boolean;
}

/** The built-in tabs, in the current locale (call at render time). */
const builtinTabs = (): Omit<TabInfo, 'panel'>[] => [
  { id: 'overview', label: msg('Overview'), icon: '◎' },
  { id: 'tasks', label: msg('Tasks', { id: 'tab-tasks', desc: 'Tab: the list of tasks' }), icon: '≡' },
  { id: 'journal', label: msg('History'), icon: '▤', tip: 'journal.jsonl' },
  { id: 'outputs', label: msg('Outputs'), icon: '▣' },
  { id: 'definitions', label: msg('Definitions'), icon: '⌘' },
  { id: 'procs', label: msg('Processes'), icon: '⚙' },
  { id: 'stream', label: msg('Task detail'), icon: '✦' },
];

/** Applies a typed filter to the URL after the reader stops typing, so the history is not written per key. */
const Q_DEBOUNCE_MS = 250;

/** The wall clock in the header: its own element, so the second tick repaints nothing else. */
@customElement('ca-clock')
@localized()
export class CaClock extends LitElement {
  constructor() {
    super();
    new ClockController(this);
  }
  protected override createRenderRoot() {
    return this;
  }
  override render() {
    return new Date().toLocaleTimeString(getLocale(), { hour12: false });
  }
}

/**
 * The whole monitor: header, run switcher, tabs, filters and the views, live.
 * It owns the data (`MonitorStore`) and the route (`Router`); every view below
 * it only renders what it is given and sends `ca-*` events back up.
 */
@customElement('ca-monitor')
@localized()
export class CaMonitor extends LitElement {
  static override styles = [
    hostThemeStyles,
    base,
    css`
      :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: 13px/1.5 var(--sans); color: var(--text);
        background: var(--backdrop); }
      header { flex: none; display: flex; gap: 14px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--line);
        background: color-mix(in srgb, var(--bg) 75%, transparent); backdrop-filter: blur(10px); position: relative; z-index: 20; }
      .brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
      .brand svg { width: 22px; height: 22px; }
      .logo-core { fill: var(--accent); transform-origin: 12px 12px; }
      .logo-ring { stroke: var(--accent); opacity: 0.5; transform-origin: 12px 12px; }
      :host([live]) .logo-core { animation: core-beat 1.8s var(--ease) infinite; }
      :host([live]) .logo-ring { animation: turn 7s linear infinite; }
      .runbtn { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 52vw; cursor: pointer; padding: 6px 13px;
        border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--text); transition: border-color 0.2s, background 0.2s; }
      .runbtn:hover { border-color: var(--line2); background: var(--panel2); }
      .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
      .rs { color: var(--text-muted); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .chev { color: var(--text-muted); }
      .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
      .nowline { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; max-width: 40vw;
        display: inline-flex; align-items: center; gap: 4px; }
      .clock { font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); }
      .langs { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
      .langs button { background: none; border: 0; padding: 2px 9px; font-size: 11px; color: var(--text-muted); cursor: pointer; }
      .langs button:hover { color: var(--text-2); }
      .langs button[aria-pressed='true'] { background: var(--raise); color: var(--text); }
      .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--status-running); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
      .live-dot.off { background: var(--line2); animation: none; box-shadow: none; }

      nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
      nav::-webkit-scrollbar { display: none; }
      .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--text-muted); cursor: pointer;
        font-weight: 500; white-space: nowrap; transition: color 0.2s; }
      .tab:hover { color: var(--text-2); }
      .tab.sel { color: var(--text); }
      .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
      .tab.sel .tab-ic { opacity: 1; color: var(--accent); }
      .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); font-variant-numeric: tabular-nums; }
      .badge.running { background: var(--status-running-bg); color: var(--status-running); }
      .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
      .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
        background: var(--accent); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
      .tab-ind.init { transition: none; }
      .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }

      .bar { flex: none; display: flex; gap: 8px; padding: 8px 18px; border-top: 1px solid var(--line); align-items: center; flex-wrap: wrap; }
      .bar select, .bar input { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 8px;
        padding: 5px 9px; outline: none; font: inherit; font-size: 12px; }
      .bar input:focus, .bar select:focus { border-color: var(--focus); box-shadow: 0 0 0 calc(var(--focus-width) - 2px) var(--focus); }

      main { border-top: 1px solid var(--line); flex: 1 1 auto; min-height: 0; overflow: auto; padding: 16px 18px 48px; }
      main.stream { display: flex; flex-direction: column; overflow: hidden; padding-bottom: 16px; }
      @media (max-width: 760px) {
        header { flex-wrap: wrap; gap: 8px; padding: 8px 12px; }
        .runbtn { max-width: calc(100vw - 130px); }
        .hdr-right { width: 100%; margin-left: 0; }
        .nowline { max-width: none; flex: 1; }
        nav { padding: 4px 8px 0; }
        main { padding: 12px 12px 40px; }
      }
    `,
  ];

  /** Where the monitor's API is served; '' is this page's origin. */
  @property({ attribute: 'base-url' }) baseUrl = '';
  /** `url`: the route lives in the address bar (Back and reload return to it); `memory`: for a monitor embedded in another page. */
  @property() history: RouterMode = 'url';
  /** The run to open first (in `memory` mode, or when the URL names none). */
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
  /** Whether the system asks for a light colour scheme (what `system` follows). */
  @state() private light = prefersLight();

  @query('main') private main!: HTMLElement;
  @query('ca-toasts') private toasts!: CaToasts;

  private store!: MonitorStore;
  private router!: Router;
  private readonly mainScroll = new ScrollMemory('main');
  private pendingScroll: RouteCause | null = null;
  private qTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly cleanups: (() => void)[] = [];

  override connectedCallback(): void {
    super.connectedCallback();
    void setLocale(isLocale(this.locale) ? this.locale : preferredLocale());
    this.applyTheme();
    const scheme = globalThis.matchMedia?.('(prefers-color-scheme: light)');
    if (scheme) {
      const onScheme = (e: MediaQueryListEvent) => (this.light = e.matches);
      scheme.addEventListener('change', onScheme);
      this.cleanups.push(() => scheme.removeEventListener('change', onScheme));
    }
    this.store = new MonitorStore({ baseUrl: this.baseUrl });
    this.snap = this.store.snapshot;
    this.cleanups.push(
      this.store.subscribe((s) => {
        this.snap = s;
        this.pickDefaultRun();
      }),
      this.store.onNewRow((row) => this.announce(row)),
    );
    this.router = new Router(this.history, (route, cause) => this.onRoute(route, cause), this.run ? { run: this.run } : {}, flushMemory);
    this.router.start();
    void this.store.start();
    const onKey = (e: KeyboardEvent) => this.onKey(e);
    const onClick = (e: MouseEvent) => {
      if (this.pickerOpen && !e.composedPath().some((n) => n instanceof HTMLElement && (n.localName === 'ca-run-picker' || n.classList.contains('runbtn'))))
        this.pickerOpen = false;
    };
    const onResize = () => this.moveTabIndicator();
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onClick);
    addEventListener('resize', onResize);
    this.cleanups.push(
      () => document.removeEventListener('keydown', onKey),
      () => document.removeEventListener('click', onClick),
      () => removeEventListener('resize', onResize),
    );
    this.addEventListener('ca-open-task', (e: CustomEvent<OpenTaskDetail>) => {
      this.navigate({ tab: 'stream', key: e.detail.key, ...(e.detail.view ? { view: e.detail.view } : {}) });
    });
    this.addEventListener('ca-navigate', (e: CustomEvent<NavigateDetail>) => {
      const { replace, ...patch } = e.detail;
      this.navigate(patch, { replace: replace === true });
    });
    this.addEventListener('ca-select-run', (e: CustomEvent<SelectRunDetail>) => this.navigate({ run: e.detail.run }));
    this.addEventListener('ca-filter', (e: CustomEvent<FilterDetail>) => this.navigate(e.detail));
    this.addEventListener('ca-choose-theme', (e: CustomEvent<ChooseThemeDetail>) => {
      this.theme = e.detail.theme;
      rememberTheme(e.detail.theme);
    });
  }

  /** The reader's choice: the `theme` property, else the choice remembered from an earlier visit. */
  private themeChoice(): ThemeChoice {
    return isThemeChoice(this.theme) ? this.theme : preferredTheme();
  }

  /** The theme shown now. */
  get shownTheme(): ThemeName {
    return resolveTheme(this.themeChoice(), this.light);
  }

  /** Show the theme: on this element, and on the page when the monitor is the page. */
  private applyTheme(): void {
    const name = this.shownTheme;
    if (this.getAttribute('data-ca-theme') !== name) this.setAttribute('data-ca-theme', name);
    if (this.history === 'url' && document.documentElement.getAttribute('data-ca-theme') !== name)
      document.documentElement.setAttribute('data-ca-theme', name);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    for (const fn of this.cleanups.splice(0)) fn();
    this.router.stop();
    this.store.stop();
    this.mainScroll.detach();
  }

  /** Go elsewhere: the route changes, and with it the URL (pushing an entry for a new place). */
  navigate(patch: RoutePatch, opts: { replace?: boolean } = {}): void {
    this.router.navigate(patch, opts);
  }

  private onRoute(route: Route, cause: RouteCause): void {
    this.route = route;
    if (cause !== 'replace') this.qDraft = null;
    this.store.selectRun(route.run);
    this.pickDefaultRun();
    if (cause !== 'replace') this.pendingScroll = cause;
  }

  /** With no run named, open the most recent one (replacing the entry: it is a default, not a step). */
  private pickDefaultRun(): void {
    const first = this.snap.runs[0];
    if (!this.route.run && first) this.navigate({ run: first.run }, { replace: true });
  }

  private announce(row: JournalRow): void {
    const name = kindUnit(row);
    const reason = runRelative(row.reason, this.snap.run).slice(0, 110);
    if (row.stop === 'invalid_input') this.toasts?.show('attention', msg(str`${name}: not started`), reason);
    else if (isBad(row)) this.toasts?.show('failed', msg(str`${name}: ${stopLabel(row.stop)}`), reason);
    else if ((row.hops || []).length > 1) this.toasts?.show('agent', msg(str`${name}: model switch`), modelSwitch(row.hops, row.wall_s).slice(0, 110));
    else this.toasts?.show('done', msg(str`${name}: done`), facts(fmtDur(row.wall_s), row.model));
  }

  private tabs(): TabInfo[] {
    return [
      ...builtinTabs().map((t) => ({ ...t, panel: false })),
      ...this.snap.info.panels.map((p) => ({
        id: `panel:${p.name}` as Tab,
        label: p.title || p.name,
        icon: p.icon || '▤',
        tip: p.description ? msg(str`${p.description} (custom view)`) : msg('Custom view'),
        panel: true,
      })),
    ];
  }

  private onKey(e: KeyboardEvent): void {
    const t = e.composedPath()[0];
    if ((t instanceof HTMLElement && t.matches('input, select, textarea')) || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'r') {
      e.preventDefault();
      this.pickerOpen = true;
    } else if (e.key === '/') {
      e.preventDefault();
      this.renderRoot.querySelector<HTMLInputElement>('.bar input')?.focus();
    } else if (/^[1-9]$/.test(e.key)) {
      const tab = this.tabs()[Number(e.key) - 1];
      if (tab) this.navigate({ tab: tab.id });
    }
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('snap' as keyof CaMonitor)) {
      this.live = isRunLive(this.snap.state, runRow(this.snap.runs, this.snap.run));
      document.title = msg(str`${this.snap.info.title} monitor`);
    }
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('locale') && isLocale(this.locale) && this.locale !== getLocale()) void setLocale(this.locale);
    // A page that is the monitor speaks its language; an embedded monitor leaves the host's <html lang> alone.
    if (this.history === 'url') document.documentElement.lang = getLocale();
    // Its own text is in its language either way (line breaking between Japanese phrases reads it).
    this.lang = getLocale();
    this.applyTheme();
    this.moveTabIndicator();
    if (this.main) this.mainScroll.attach(this.main);
    if (this.pendingScroll) {
      // A new place starts at the top; Back, Forward and a reload return to where the reader was.
      if (this.pendingScroll === 'push') this.mainScroll.reset();
      else this.mainScroll.restore();
      this.pendingScroll = null;
    }
  }

  private moveTabIndicator(): void {
    const sel = this.renderRoot.querySelector<HTMLElement>('.tab.sel');
    const ind = this.renderRoot.querySelector<HTMLElement>('.tab-ind');
    if (!sel || !ind) return;
    ind.style.left = `${sel.offsetLeft + 10}px`;
    ind.style.width = `${Math.max(12, sel.offsetWidth - 20)}px`;
    if (ind.classList.contains('init')) requestAnimationFrame(() => ind.classList.remove('init'));
  }

  private setQ(q: string): void {
    this.qDraft = q;
    if (this.qTimer) clearTimeout(this.qTimer);
    this.qTimer = setTimeout(() => {
      this.qTimer = null;
      this.navigate({ q });
    }, Q_DEBOUNCE_MS);
  }

  /** The header's run line: tasks that ended well out of all tasks (not attempts), how long the run took, running. */
  private runLine(summary: RunSummary): string {
    const took = elapsedS(summary);
    // The live journal is fresher than the run list (polled); before the replay is in, the run list's figure.
    const spent = this.snap.state.ready ? spendOf(this.snap.state.journal)?.cost : summary.cost_usd;
    const cost = spent !== null && spent !== undefined ? usd(spent) : '';
    const usage = accountsLine(this.accounts(summary));
    const tail = facts(took == null ? '' : msg(str`took ${fmtDur(took)}`), cost, usage, summary.running ? msg('running') : '');
    if (!this.snap.state.ready) return tail; // the feed is still replaying: no count yet rather than a wrong one
    const c = deriveRun(this.snap.state.journal, this.snap.state.plan).counts;
    return facts(msg(str`${c.doneTotal} of ${c.total} tasks done`), tail);
  }

  /** Each account's latest subscription reading, busiest weekly first: from the live journal once replayed, else the run list's. */
  private accounts(summary: RunSummary) {
    return this.snap.state.ready ? runAccounts(this.snap.state.journal) : (summary.quota ?? []);
  }

  /** The history bar's count, as the overview counts: "23 attempts | 4 not started". */
  private triesLine(): string {
    const { tries, notStarted } = deriveRun(this.snap.state.journal, this.snap.state.plan).tries;
    return facts(tries === 1 ? msg('1 attempt') : msg(str`${tries} attempts`), notStarted ? stateCount('not_started', notStarted) : '');
  }

  /** The header's language switch: switch now, and remember it for the next visit. */
  private pickLocale(locale: Locale): void {
    this.locale = locale;
    void chooseLocale(locale);
  }

  override render() {
    if (!this.snap || !this.route) return nothing;
    const { snap, route } = this;
    const summary = runRow(snap.runs, snap.run);
    const acts = liveActivities(snap.state.procs);
    const t = summary?.tasks;
    const dot = runTone(!!summary?.running, t);
    return html`
      <header>
        <div class="brand">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle class="logo-ring" cx="12" cy="12" r="9.5" fill="none" stroke-width="1.5" stroke-dasharray="4 3" />
            <circle class="logo-core" cx="12" cy="12" r="4" />
          </svg>
          <span>${snap.info.title}</span>
        </div>
        <button type="button" class="runbtn" title=${msg('Switch run (r)')} @click=${() => (this.pickerOpen = !this.pickerOpen)}>
          <span class="dot ${dot}" aria-hidden="true"></span>
          <span class="rn">${route.run || '—'}</span>
          <span class="rs" title=${summary ? accountsTip(this.accounts(summary)) : ''}>${summary ? this.runLine(summary) : ''}</span>
          <span class="chev" aria-hidden="true">▾</span>
        </button>
        <div class="hdr-right">
          <span class="nowline">${acts.length
            ? msg(html`Running ${acts.slice(0, 3).map((a) => taskChip(this, kindUnit(a), { key: a.key }))}${acts.length > 3 ? html` <span>+${acts.length - 3}</span>` : nothing}`)
            : nothing}</span>
          <ca-theme-switch .value=${this.themeChoice()} .system=${resolveTheme('system', this.light)}></ca-theme-switch>
          <span class="langs" role="group" aria-label=${msg('Language')}>
            ${allLocales.map(
              (l) => html`<button type="button" lang=${l} aria-pressed=${l === getLocale()} @click=${() => this.pickLocale(l)}>
                ${LOCALE_NAMES[l]}
              </button>`,
            )}
          </span>
          <span title=${snap.connected ? msg('Connected to the monitor server') : msg('Not connected to the monitor server')}
            ><span class="live-dot ${snap.connected ? '' : 'off'}"></span><span class="sr">${snap.connected
              ? msg('Connected to the monitor server')
              : msg('Not connected to the monitor server')}</span></span
          >
          <ca-clock class="clock"></ca-clock>
        </div>
        <ca-run-picker style="left:110px" .runs=${snap.runs} current=${route.run} ?open=${this.pickerOpen}
          @ca-close=${() => (this.pickerOpen = false)}></ca-run-picker>
      </header>
      ${this.renderTabs(acts.length)} ${this.renderBar()}
      <main class=${route.tab === 'stream' ? 'stream' : ''}>${this.renderView()}</main>
      <ca-toasts></ca-toasts>
    `;
  }

  private renderTabs(busy: number) {
    const { state } = this.snap;
    const d = deriveRun(state.journal, state.plan);
    const { tries } = d.tries;
    const tasks = d.counts;
    // A tab's count is a total: neutral, never coloured by its worst part. Only a count of what is running is.
    const badge = (id: Tab): [string | number, string] | null =>
      id === 'tasks'
        ? [tasks.total || '', '']
        : id === 'journal'
          ? [tries || '', '']
          : id === 'procs'
            ? [state.procs?.alive ? busy || '' : '', 'running']
            : null;
    const tabs = this.tabs();
    return html`<nav>
      ${tabs.map((t, i) => {
        const b = badge(t.id);
        return html`${t.panel && !tabs[i - 1]?.panel ? html`<span class="tab-sep" title=${msg('Custom views')}></span>` : nothing}
          <button type="button" class="tab ${t.panel ? 'panel-tab' : ''} ${t.id === this.route.tab ? 'sel' : ''}" title=${t.tip ?? nothing}
            @click=${() => this.navigate({ tab: t.id })}>
            <span class="tab-ic" aria-hidden="true">${t.icon}</span>${t.label}${b && b[0] !== '' ? html`<span class="badge ${b[1]}">${b[0]}</span>` : nothing}
          </button>`;
      })}
      <span class="tab-ind init"></span>
      <span class="tabhint meta" role="note" aria-label=${msg('Keyboard shortcuts')}
        ><span aria-hidden="true"><span class="kbd">1</span>–<span class="kbd">${Math.min(9, tabs.length)}</span> ${msg('Tabs')} |
          <span class="kbd">r</span> ${msg('Runs')} | <span class="kbd">/</span> ${msg('Filter')}</span></span
      >
    </nav>`;
  }

  private renderBar() {
    const { route } = this;
    if (route.tab !== 'tasks' && route.tab !== 'journal') return nothing;
    const { state } = this.snap;
    const { counts, kinds } = deriveRun(state.journal, state.plan);
    const total = counts.total;
    return html`<div class="bar">
      <select title=${msg('Kind')} aria-label=${msg('Kind')} @change=${(e: Event) => this.navigate({ kind: (e.target as HTMLSelectElement).value })}>
        <option value="" ?selected=${!route.kind}>${msg('All kinds')}</option>
        ${kinds.map((k) => html`<option ?selected=${k === route.kind}>${k}</option>`)}
      </select>
      <input placeholder=${msg('Filter')} aria-label=${msg('Text filter')} size="22" title=${msg('Text filter (/)')} .value=${this.qDraft ?? route.q}
        @input=${(e: Event) => this.setQ((e.target as HTMLInputElement).value)} />
      <span class="meta">${route.tab === 'journal'
        ? this.triesLine()
        : total === 1 ? msg('1 task') : msg(str`${total} tasks`)}</span>
    </div>`;
  }

  private renderView() {
    const { snap, route } = this;
    const { state } = snap;
    if (!route.run) {
      return html`<div class="blank"><span class="ic" aria-hidden="true">✦</span><b>${msg('No runs yet', { id: 'no-runs-yet' })}</b></div>`;
    }
    const summary = runRow(snap.runs, snap.run);
    const live = isRunLive(state, summary);
    const q = this.qDraft ?? route.q;
    switch (route.tab) {
      case 'overview':
        return html`<ca-overview .state=${state} .summary=${summary} .info=${snap.info} .run=${route.run} .layer=${route.layer} .unit=${route.unit} .sel=${route.sel}></ca-overview>`;
      case 'tasks':
        return html`<ca-task-table .run=${route.run} .journal=${state.journal} .plan=${state.plan} .kind=${route.kind} .q=${q} ?live=${live}></ca-task-table>`;
      case 'journal':
        return html`<ca-journal-table .run=${route.run} .rows=${state.journal} .plan=${state.plan} .fresh=${snap.fresh} .kind=${route.kind} .stop=${route.stop} .q=${q}></ca-journal-table>`;
      case 'outputs':
        return html`<ca-contracts .run=${route.run} .outputs=${state.outputs} .journal=${state.journal} .plan=${state.plan}></ca-contracts>`;
      case 'definitions':
        return html`<ca-definitions .client=${this.store.client} .run=${route.run} .journal=${state.journal} .plan=${state.plan} .live=${live}
          .selected=${route.def}></ca-definitions>`;
      case 'procs':
        return html`<ca-procs-view .procs=${state.procs}></ca-procs-view>`;
      case 'stream':
        return html`<ca-task-view .client=${this.store.client} .journal=${state.journal} .plan=${state.plan} base-url=${this.baseUrl} .run=${route.run}
          .taskKey=${route.key ?? latestTask(deriveRun(state.journal, state.plan).rows)} .view=${route.view} .round=${route.round} .live=${live}></ca-task-view>`;
      default: {
        const name = route.tab.slice('panel:'.length);
        const info = snap.info.panels.find((p) => p.name === name);
        return html`<ca-panel-view .name=${name} .panel=${info} .data=${state.panels[name]}></ca-panel-view>`;
      }
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-monitor': CaMonitor;
    'ca-clock': CaClock;
  }
}
