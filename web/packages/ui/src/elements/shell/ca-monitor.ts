import {
  MonitorStore,
  isBad,
  isLaunched,
  outcomeCounts,
  spendOf,
  taskOutcomes,
  isRunLive,
  latestSlot,
  liveActivities,
  runRow,
  type JournalRow,
  type MonitorSnapshot,
  type RunSummary,
  runAccounts,
} from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import type { FilterDetail, OpenTaskDetail, SelectRunDetail } from '../../events.js';
import { LOCALE_NAMES, allLocales, chooseLocale, getLocale, isLocale, preferredLocale, setLocale, type Locale } from '../../i18n.js';
import { ClockController } from '../../lib/clock.js';
import { facts, fmtDur, kindUnit, usd } from '../../lib/format.js';
import { modelSwitch, runRelative, stopLabel } from '../../lib/labels.js';
import { ScrollMemory } from '../../lib/scroll.js';
import { elapsedS, tryCounts } from '../overview/logic.js';
import type { Route, RoutePatch, Tab } from '../../route.js';
import { Router, type RouteCause, type RouterMode } from '../../router.js';
import { accountsLine, accountsTip } from '../../lib/quota-format.js';
import { base } from '../../styles/base.js';
import { taskChip } from '../shared/task-chip.js';
import type { CaToasts } from './ca-toasts.js';
import './ca-run-picker.js';
import './ca-toasts.js';
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
  { id: 'tasks', label: msg('Tasks'), icon: '≡' },
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
    base,
    css`
      :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: 13px/1.5 var(--sans); color: var(--fg); }
      header { flex: none; display: flex; gap: 14px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--line);
        background: rgba(6, 10, 17, 0.75); backdrop-filter: blur(10px); position: relative; z-index: 20; }
      .brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
      .brand svg { width: 22px; height: 22px; }
      .logo-core { fill: var(--live); transform-origin: 12px 12px; }
      .logo-ring { stroke: var(--live); opacity: 0.5; transform-origin: 12px 12px; }
      :host([live]) .logo-core { animation: core-beat 1.8s var(--ease) infinite; }
      :host([live]) .logo-ring { animation: turn 7s linear infinite; }
      .runbtn { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 52vw; cursor: pointer; padding: 6px 13px;
        border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--fg); transition: border-color 0.2s, background 0.2s; }
      .runbtn:hover { border-color: var(--line2); background: var(--panel2); }
      .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
      .rs { color: var(--mut); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .chev { color: var(--mut); }
      .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
      .nowline { font-size: 12px; color: var(--fg2); white-space: nowrap; overflow: hidden; max-width: 40vw;
        display: inline-flex; align-items: center; gap: 4px; }
      .clock { font-family: var(--mono); font-size: 11.5px; color: var(--mut); }
      .langs { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
      .langs button { background: none; border: 0; padding: 2px 9px; font-size: 11px; color: var(--mut); cursor: pointer; }
      .langs button:hover { color: var(--fg2); }
      .langs button[aria-pressed='true'] { background: var(--raise); color: var(--fg); }
      .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ok); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
      .live-dot.off { background: #3b4760; animation: none; box-shadow: none; }

      nav { flex: none; display: flex; gap: 2px; padding: 6px 18px 0; position: relative; overflow-x: auto; scrollbar-width: none; align-items: center; }
      nav::-webkit-scrollbar { display: none; }
      .tab { position: relative; background: none; border: none; padding: 8px 14px 11px; color: var(--mut); cursor: pointer;
        font-weight: 500; white-space: nowrap; transition: color 0.2s; }
      .tab:hover { color: var(--fg2); }
      .tab.sel { color: var(--fg); }
      .tab-ic { opacity: 0.55; margin-right: 6px; font-size: 12px; }
      .tab.sel .tab-ic { opacity: 1; color: var(--live); }
      .tab.panel-tab { color: var(--llm); }
      .tab.panel-tab:hover { color: var(--fg); }
      .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--fg2); font-variant-numeric: tabular-nums; }
      .badge.err { background: var(--err-a); color: var(--err); }
      .badge.live { background: var(--live-a); color: var(--live); }
      .tab-sep { width: 1px; height: 18px; background: var(--line2); margin: 0 8px 3px; flex: none; align-self: center; }
      .tab-ind { position: absolute; bottom: 0; left: 0; width: 0; height: 2px; border-radius: 2px;
        background: linear-gradient(90deg, var(--live), var(--llm)); transition: left 0.3s var(--ease), width 0.3s var(--ease); }
      .tab-ind.init { transition: none; }
      .tabhint { margin-left: auto; padding-left: 12px; white-space: nowrap; }

      .bar { flex: none; display: flex; gap: 8px; padding: 8px 18px; border-top: 1px solid var(--line); align-items: center; flex-wrap: wrap; }
      .bar select, .bar input { background: var(--panel); color: var(--fg); border: 1px solid var(--line); border-radius: 8px;
        padding: 5px 9px; outline: none; font: inherit; font-size: 12px; }
      .bar input:focus, .bar select:focus { border-color: var(--live); }

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
  /** Reflects whether the run is live (the logo moves). */
  @property({ type: Boolean, reflect: true }) live = false;

  @state() private snap!: MonitorSnapshot;
  @state() private route!: Route;
  @state() private pickerOpen = false;
  /** The filter text as typed, ahead of the URL. */
  @state() private qDraft: string | null = null;

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
    this.store = new MonitorStore({ baseUrl: this.baseUrl });
    this.snap = this.store.snapshot;
    this.cleanups.push(
      this.store.subscribe((s) => {
        this.snap = s;
        this.pickDefaultRun();
      }),
      this.store.onNewRow((row) => this.announce(row)),
    );
    this.router = new Router(this.history, (route, cause) => this.onRoute(route, cause), this.run ? { run: this.run } : {});
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
    this.addEventListener('ca-navigate', (e: CustomEvent<RoutePatch>) => this.navigate(e.detail));
    this.addEventListener('ca-select-run', (e: CustomEvent<SelectRunDetail>) => this.navigate({ run: e.detail.run }));
    this.addEventListener('ca-filter', (e: CustomEvent<FilterDetail>) => this.navigate(e.detail));
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
    if (row.stop === 'invalid_input') this.toasts?.show('warn', msg(str`${name}: not started`), reason);
    else if (isBad(row)) this.toasts?.show('err', msg(str`${name}: ${stopLabel(row.stop)}`), reason);
    else if ((row.hops || []).length > 1) this.toasts?.show('llm', msg(str`${name}: model switch`), modelSwitch(row.hops, row.wall_s).slice(0, 110));
    else this.toasts?.show('ok', msg(str`${name}: done`), facts(fmtDur(row.wall_s), row.model));
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
    const c = outcomeCounts(taskOutcomes(this.snap.state.journal, this.snap.state.plan));
    return facts(msg(str`${c.done + c.recovered}/${c.total} tasks done`), tail);
  }

  /** Each account's latest subscription reading, busiest weekly first: from the live journal once replayed, else the run list's. */
  private accounts(summary: RunSummary) {
    return this.snap.state.ready ? runAccounts(this.snap.state.journal) : (summary.quota ?? []);
  }

  /** The history bar's count, as the overview counts: "23 attempts | 4 not started". */
  private triesLine(): string {
    const { tries, notStarted } = tryCounts(this.snap.state.journal);
    return facts(tries === 1 ? msg('1 attempt') : msg(str`${tries} attempts`), notStarted ? msg(str`${notStarted} not started`) : '');
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
    const dot = summary?.running ? 'live' : !t?.total ? '' : t.failed || t.not_started ? 'warn' : 'ok';
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
            ? html`${msg('Running')} ${acts
                .slice(0, 3)
                .map((a) => taskChip(this, kindUnit(a), { key: a.key }))}${acts.length > 3 ? html` <span>+${acts.length - 3}</span>` : nothing}`
            : nothing}</span>
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
          @close=${() => (this.pickerOpen = false)}></ca-run-picker>
      </header>
      ${this.renderTabs(acts.length)} ${this.renderBar()}
      <main class=${route.tab === 'stream' ? 'stream' : ''}>${this.renderView()}</main>
      <ca-toasts></ca-toasts>
    `;
  }

  private renderTabs(busy: number) {
    const { state } = this.snap;
    const { tries } = tryCounts(state.journal);
    const failed = state.journal.filter((r) => isLaunched(r) && isBad(r)).length;
    const badge = (id: Tab): [string | number, string] | null =>
      id === 'tasks'
        ? [state.tasks.length || '', state.tasks.some((t) => t.running) ? 'live' : '']
        : id === 'journal'
          ? [tries || '', failed ? 'err' : '']
          : id === 'procs'
            ? [state.procs?.alive ? busy || '' : '', 'live']
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
    const kinds = [...new Set(state.tasks.map((t) => t.kind))].sort();
    return html`<div class="bar">
      <select title=${msg('Kind')} aria-label=${msg('Kind')} @change=${(e: Event) => this.navigate({ kind: (e.target as HTMLSelectElement).value })}>
        <option value="" ?selected=${!route.kind}>${msg('All kinds')}</option>
        ${kinds.map((k) => html`<option ?selected=${k === route.kind}>${k}</option>`)}
      </select>
      <input placeholder=${msg('Filter')} aria-label=${msg('Text filter')} size="22" title=${msg('Text filter (/)')} .value=${this.qDraft ?? route.q}
        @input=${(e: Event) => this.setQ((e.target as HTMLInputElement).value)} />
      <span class="meta">${route.tab === 'journal'
        ? this.triesLine()
        : state.tasks.length === 1 ? msg('1 task') : msg(str`${state.tasks.length} tasks`)}</span>
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
        return html`<ca-overview .state=${state} .summary=${summary} .info=${snap.info} .run=${route.run} .layer=${route.layer} .unit=${route.unit}></ca-overview>`;
      case 'tasks':
        return html`<ca-task-table .run=${route.run} .tasks=${state.tasks} .journal=${state.journal} .plan=${state.plan} .kind=${route.kind} .q=${q}></ca-task-table>`;
      case 'journal':
        return html`<ca-journal-table .run=${route.run} .rows=${state.journal} .fresh=${snap.fresh} .kind=${route.kind} .stop=${route.stop} .q=${q}></ca-journal-table>`;
      case 'outputs':
        return html`<ca-contracts .run=${route.run} .outputs=${state.outputs} .journal=${state.journal} .plan=${state.plan}></ca-contracts>`;
      case 'definitions':
        return html`<ca-definitions .client=${this.store.client} .run=${route.run} .tasks=${state.tasks} .journal=${state.journal} .live=${live}
          .selected=${route.def}></ca-definitions>`;
      case 'procs':
        return html`<ca-procs-view .procs=${state.procs}></ca-procs-view>`;
      case 'stream':
        return html`<ca-task-view .client=${this.store.client} .journal=${state.journal} .plan=${state.plan} base-url=${this.baseUrl} .run=${route.run}
          .taskKey=${route.key ?? latestSlot(state.tasks)} .view=${route.view} .round=${route.round} .live=${live}></ca-task-view>`;
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
