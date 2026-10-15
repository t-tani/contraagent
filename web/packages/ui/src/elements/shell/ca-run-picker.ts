import { elapsedS, hostGroups, hostOf, runActivity, runIdOf, type HostSummary, type RunSummary } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import type { Page } from '../../core/route.js';
import { trendsTitle, trendsTip } from '../../words/trends.js';
import { facts, fmtDur, localTime, relAgo, usd } from '../../words/format.js';
import { runMark, stateCount } from '../../words/index.js';
import { accountsLine, accountsTip } from '../../words/quota.js';
import { hostFact, noReportLabel, hostStateSince, hostsLine, lastReport, runCount } from '../../words/hosts.js';
import { runTone } from '../../lib/tone.js';
import { toneAttr } from '@contraagent/elements';
import { pill, statusWord } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';

const took = (r: RunSummary) => elapsedS(r);

/** The id of the option at `i` in the visible list. */
const optionId = (i: number) => `run-${i}`;

const ago = (r: RunSummary) => {
  const t = Date.parse(r.last_ts || '');
  return Number.isNaN(t) ? Infinity : (Date.now() - t) / 1000;
};

/**
 * The run switcher: runs grouped by recency, searchable, keyboard driven. A
 * dialog: its search field (a combobox) holds the focus while it is open (Tab
 * stays in it), and the arrow keys move through the list
 * (`aria-activedescendant`). Sends `ca-select-run` for a pick and `ca-close`
 * when it should be closed (Escape, or a pick); the host returns the focus.
 *
 * While nothing is searched, the first options are the pages of no run: the
 * trends, and on a hub the hosts. On a hub (`hub`), the runs are grouped by host,
 * each group headed by its host's state; a host filter (a select, the dialog's
 * second Tab stop) shows one host's runs.
 *
 * @fires ca-select-run - `{run}`: a run was picked
 * @fires ca-navigate - `{page, run: ''}`: a page of no run was picked (`trends`, or on a hub `hosts`)
 * @fires ca-close - the picker should close
 */
@customElement('ca-run-picker')
@localized()
export class CaRunPicker extends LitElement {
  static override styles = [
    base,
    css`
      :host { position: absolute; top: 50px; width: min(580px, calc(100vw - 24px)); max-height: min(72vh, 660px);
        display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line2); border-radius: 14px;
        box-shadow: 0 24px 70px color-mix(in srgb, var(--shadow) 70%, transparent); opacity: 0; transform: translateY(-6px) scale(0.985);
        pointer-events: none; z-index: 40; visibility: hidden;
        transition: opacity 0.16s var(--ease), transform 0.16s var(--ease), visibility 0s linear 0.16s; }
      /* Visible (and focusable) at once when it opens; hidden only after it has faded out. */
      :host([open]) { opacity: 1; transform: none; pointer-events: auto; visibility: visible; transition-delay: 0s; }
      .search { padding: 10px; border-bottom: 1px solid var(--line); }
      input, select { background: var(--well); border: 1px solid var(--line); color: var(--text); border-radius: 9px; font: inherit; outline: none; }
      input { width: 100%; padding: 8px 11px; }
      input:focus, select:focus { border-color: var(--accent); }
      .list { overflow: auto; padding: 6px; }
      .group { font-size: 11.5px; font-weight: 600; color: var(--text-muted); padding: 10px 9px 4px; }
      .group .n { font-weight: 400; margin-left: 4px; }
      .keys { margin-top: 6px; display: flex; gap: 4px; align-items: center; }
      .item { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 3px 10px; align-items: center;
        padding: 7px 9px; border-radius: 9px; cursor: pointer; }
      .item:hover, .item.kb { background: var(--raise); }
      .item.cur { box-shadow: inset 2px 0 0 var(--accent); background: var(--accent-bg); }
      .nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .when { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
      .sub { grid-column: 2 / 4; display: flex; gap: 7px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); }
      /* a hub: the host filter beside the search field, a header per host, the hosts page as the first option */
      .row { display: flex; gap: 8px; }
      select { max-width: 40%; padding: 0 8px; }
      .host { display: flex; gap: 8px; flex-wrap: wrap; color: var(--text-2); border-top: 1px solid var(--line); margin-top: 6px; }
      .host b { font-family: var(--mono); color: var(--text); }
      .host .n { margin-left: auto; }
      .when[data-tone] { color: var(--tone); font-weight: 600; }
    `,
  ];

  @property({ attribute: false }) runs: RunSummary[] = [];
  /** The run shown now. */
  @property() current = '';
  @property({ type: Boolean, reflect: true }) open = false;
  /** The runs come from many hosts (`Info.hosts`): group them by host, with a host filter and the hosts page. */
  @property({ type: Boolean }) hub = false;
  /** The host list (a hub). */
  @property({ attribute: false }) hosts: HostSummary[] = [];
  /** The page of no run shown now (`trends`, `hosts`; it is the current option); '' while a run is shown. */
  @property() page: Page = '';
  @state() private q = '';
  /** A hub: only this host's runs; '' for every host. */
  @state() private host = '';
  /** The keyboard's place in the visible list; -1 for none. */
  @state() private kb = -1;
  @query('input') private input!: HTMLInputElement;
  @query('select') private select!: HTMLSelectElement | null;

  override connectedCallback(): void {
    super.connectedCallback();
    this.setAttribute('role', 'dialog');
    this.setAttribute('aria-modal', 'true');
  }

  protected override willUpdate(): void {
    this.setAttribute('aria-label', msg('Runs'));
  }

  protected override updated(changed: Map<string, unknown>): void {
    if (changed.has('open') && this.open) {
      this.q = '';
      this.kb = -1;
      setTimeout(() => this.input?.focus(), 30);
    }
  }

  /**
   * The runs the search and the host filter leave, in groups, in list order:
   * by host on a hub, each headed by its host's id, its state (attention once
   * its reports stopped) and how many of its runs are listed; else by recency.
   * Each group: its accessible name, its header, its runs.
   */
  private groups(): [string, unknown, RunSummary[]][] {
    const q = this.q.toLowerCase().trim();
    const rows = this.runs.filter(
      (r) => (!q || r.run.toLowerCase().includes(q) || (r.run_group || '').toLowerCase().includes(q)) && (!this.host || r.host_id === this.host),
    );
    if (this.hub) {
      return hostGroups(rows, this.hosts).map(({ hostId, host: h, runs }) => {
        const id = hostId || hostFact('');
        const state = h ? hostStateSince(h) : '';
        const n = runCount(runs.length);
        return [facts(id, state, n), html`<b>${id}</b>${h ? statusWord({ text: state, tone: h.up ? 'done' : 'attention', title: lastReport(h) }) : nothing}<span class="n">${n}</span>`, runs];
      });
    }
    const old = (r: RunSummary) => !r.running && ago(r) >= 86400;
    return (
      [
        [msg('Running'), rows.filter((r) => r.running)],
        [msg('Last 24 hours'), rows.filter((r) => !r.running && !old(r))],
        [msg('Older'), rows.filter(old)],
      ] as const
    ).map(([name, rs]) => [name, html`${name} <span class="n">${rs.length}</span>`, rs]);
  }

  /** A run, or a page of no run. */
  private pick(r: Option): void {
    this.close();
    if (typeof r === 'string') {
      if (r !== this.page) emit(this, 'ca-navigate', { page: r, run: '' });
    } else if (r.run !== this.current || this.page) emit(this, 'ca-select-run', { run: r.run });
  }

  private close(): void {
    emit(this, 'ca-close', {});
  }

  /** The dialog's keys: Escape closes; Tab stays in the dialog, between the search field and (on a hub) the host filter. */
  private onDialogKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') this.close();
    else if (e.key === 'Tab') {
      e.preventDefault();
      (e.target === this.input && this.hub ? this.select : this.input)?.focus();
    }
  }

  /** The search field's keys: the arrow keys move through the options, Enter picks one. */
  private onKey(e: KeyboardEvent, opts: Option[]): void {
    if (e.key === 'ArrowDown') this.kb = Math.min(opts.length - 1, this.kb + 1);
    else if (e.key === 'ArrowUp') this.kb = Math.max(0, this.kb - 1);
    else if (e.key === 'Enter') {
      // The focus goes back to the button that opened the picker: this Enter must not press it.
      e.preventDefault();
      const r = opts[Math.max(0, this.kb)];
      if (r !== undefined) this.pick(r);
      return;
    } else return;
    e.preventDefault();
    void this.updateComplete.then(() => this.renderRoot.querySelector('.item.kb')?.scrollIntoView({ block: 'nearest' }));
  }

  override render() {
    const groups = this.groups().filter((g) => g[2].length);
    const rows = groups.flatMap((g) => g[2]);
    // While nothing is searched, the pages of no run come first: the trends, and on a hub the hosts.
    const pages: Exclude<Page, ''>[] = this.q.trim() ? [] : this.hub ? ['trends', 'hosts'] : ['trends'];
    const opts: Option[] = [...pages, ...rows];
    const active = opts[this.kb] !== undefined ? optionId(this.kb) : nothing;
    const search = html`<input placeholder=${msg('Search runs')} aria-label=${msg('Search runs')} autocomplete="off" .value=${this.q}
      role="combobox" aria-expanded=${opts.length ? 'true' : 'false'} aria-controls="runs" aria-autocomplete="list" aria-activedescendant=${active}
      @input=${(e: Event) => { this.q = (e.target as HTMLInputElement).value; this.kb = 0; }}
      @keydown=${(e: KeyboardEvent) => this.onKey(e, opts)} />`;
    let i = 0;
    return html`<div class="search" @keydown=${(e: KeyboardEvent) => this.onDialogKey(e)}>
        ${this.hub ? html`<div class="row">${search}${this.hostFilter()}</div>` : search}
        <div class="keys meta" aria-hidden="true"><span class="kbd">↑</span><span class="kbd">↓</span> <span class="kbd">Enter</span> <span class="kbd">Esc</span></div>
      </div>
      <div class="list" @mousedown=${(e: MouseEvent) => e.preventDefault()}>
        ${opts.length
          ? html`<div id="runs" role="listbox" aria-label=${msg('Runs')}>
              ${pages.map((p) => this.item(p, i++))}
              ${groups.map(
                ([name, head, rs]) => html`<div role="group" aria-label=${name}>
                  <div class="group${this.hub ? ' host' : ''}" aria-hidden="true">${head}</div>
                  ${rs.map((r) => this.item(r, i++))}
                </div>`,
              )}
            </div>`
          : html`<div class="blank"><span>${msg('No runs match')}</span></div>`}
      </div>`;
  }

  /** The host filter: every host with runs. */
  private hostFilter() {
    return html`<select aria-label=${msg('Host')} title=${msg('Host')}
      @change=${(e: Event) => { this.host = (e.target as HTMLSelectElement).value; this.kb = -1; }}>
      <option value="" ?selected=${!this.host}>${msg('All hosts')}</option>
      ${hostGroups(this.runs, this.hosts).map((g) => html`<option value=${g.hostId} ?selected=${g.hostId === this.host}>${g.hostId || hostFact('')}</option>`)}
    </select>`;
  }

  /** Tasks by how they ended, as the run's own page counts them, and how long it took: one line. */
  private counts(r: RunSummary): string {
    const t = r.tasks;
    const parts = [msg(str`${t.done} of ${t.total} tasks done`)];
    if (t.failed) parts.push(stateCount('failed', t.failed));
    if (t.not_started) parts.push(stateCount('not_started', t.not_started));
    if (t.partial) parts.push(stateCount('partial', t.partial));
    if (t.skipped) parts.push(stateCount('skipped', t.skipped));
    if (t.running) parts.push(stateCount('running', t.running));
    if (t.waiting) parts.push(stateCount('waiting', t.waiting));
    if (t.not_run) parts.push(stateCount('not_run', t.not_run));
    const s = took(r);
    if (s != null) parts.push(msg(str`took ${fmtDur(s)}`));
    if (r.cost_usd !== null && r.cost_usd !== undefined) parts.push(usd(r.cost_usd));
    const usage = accountsLine(r.quota ?? []);
    if (usage) parts.push(usage);
    return facts(...parts);
  }

  /** The run's state where its age goes: running, no report from its host (a hub), or how long ago it was last active. */
  private when(r: RunSummary) {
    const a = runActivity(r);
    const at = localTime(r.last_ts, true);
    const quiet = a === 'unresponsive';
    return html`<span class="when" data-tone=${quiet ? 'attention' : nothing} data-mark=${quiet ? 'pending' : nothing}
      title=${quiet ? facts(lastReport(hostOf(this.hosts, r)), msg(str`Last activity ${at}`)) : at}
      >${a === 'running' ? msg('running') : quiet ? noReportLabel() : relAgo(r.last_ts)}</span>`;
  }

  /** An option: a run, or a page of no run. */
  private item(r: Option, i: number) {
    const page = typeof r === 'string' ? r : null;
    const cur = page ? page === this.page : !this.page && (r as RunSummary).run === this.current;
    const cls = `item${cur ? ' cur' : ''}${i === this.kb ? ' kb' : ''}`;
    // An option of the listbox: the search field keeps the focus and names the active option (`aria-activedescendant`).
    return html`<div class=${cls} id=${optionId(i)} role="option" aria-selected=${i === this.kb ? 'true' : 'false'}
      aria-current=${cur ? (page ? 'page' : 'true') : nothing} @click=${() => this.pick(r)}>
      ${typeof r !== 'string'
        ? html`<span class="dot" data-tone=${toneAttr(runTone(runActivity(r), r.tasks))} aria-hidden="true"></span><span class="nm"
              title=${this.hub ? r.run : nothing}>${this.hub ? runIdOf(r) : r.run}${runMark(r) ? html` ${pill({ ...runMark(r)!, tone: 'muted' })}` : nothing}</span>
            ${this.when(r)}
            <span class="sub">
              ${r.run_group && r.run_group !== runIdOf(r) ? html`<span>${msg(str`Run group ${r.run_group}`)}</span>` : nothing}              <span title=${accountsTip(r.quota ?? [])}>${this.counts(r)}</span>
            </span>`
        : page === 'hosts'
          ? html`<span aria-hidden="true">⊞</span><span class="nm">${msg('Hosts')}</span><span class="when">${hostsLine(this.hosts)}</span>`
          : html`<span aria-hidden="true">▥</span><span class="nm">${trendsTitle()}</span><span class="when">${trendsTip()}</span>`}
    </div>`;
  }
}

/** An option of the list: a run, or a page of no run. */
type Option = RunSummary | Exclude<Page, ''>;

declare global {
  interface HTMLElementTagNameMap {
    'ca-run-picker': CaRunPicker;
  }
}
