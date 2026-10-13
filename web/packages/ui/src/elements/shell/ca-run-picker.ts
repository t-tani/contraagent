import { elapsedS, type RunSummary } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import { emit } from '../../core/events.js';
import { facts, fmtDur, localTime, relAgo, usd } from '../../words/format.js';
import { stateCount } from '../../words/index.js';
import { accountsLine, accountsTip } from '../../words/quota.js';
import { runTone } from '../../lib/tone.js';
import { toneAttr } from '@contraagent/elements';
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
 * @fires ca-select-run - `{run}`: a run was picked
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
      input { width: 100%; background: var(--well); border: 1px solid var(--line); color: var(--text); border-radius: 9px;
        padding: 8px 11px; font: inherit; outline: none; }
      input:focus { border-color: var(--accent); }
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
    `,
  ];

  @property({ attribute: false }) runs: RunSummary[] = [];
  /** The run shown now. */
  @property() current = '';
  @property({ type: Boolean, reflect: true }) open = false;
  @state() private q = '';
  /** The keyboard's place in the visible list; -1 for none. */
  @state() private kb = -1;
  @query('input') private input!: HTMLInputElement;

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

  private visible(): RunSummary[] {
    const q = this.q.toLowerCase().trim();
    const rows = this.runs.filter((r) => !q || r.run.toLowerCase().includes(q) || (r.run_group || '').toLowerCase().includes(q));
    return [
      ...rows.filter((r) => r.running),
      ...rows.filter((r) => !r.running && ago(r) < 86400),
      ...rows.filter((r) => !r.running && ago(r) >= 86400),
    ];
  }

  private pick(run: string): void {
    this.close();
    if (run !== this.current) emit(this, 'ca-select-run', { run });
  }

  private close(): void {
    emit(this, 'ca-close', {});
  }

  private onKey(e: KeyboardEvent, rows: RunSummary[]): void {
    if (e.key === 'Escape') return this.close();
    // The search field is the dialog's only stop: Tab stays in it.
    if (e.key === 'Tab') return e.preventDefault();
    if (e.key === 'ArrowDown') this.kb = Math.min(rows.length - 1, this.kb + 1);
    else if (e.key === 'ArrowUp') this.kb = Math.max(0, this.kb - 1);
    else if (e.key === 'Enter') {
      // The focus goes back to the button that opened the picker: this Enter must not press it.
      e.preventDefault();
      const r = rows[Math.max(0, this.kb)];
      if (r) this.pick(r.run);
      return;
    } else return;
    e.preventDefault();
    void this.updateComplete.then(() => this.renderRoot.querySelector('.item.kb')?.scrollIntoView({ block: 'nearest' }));
  }

  override render() {
    const rows = this.visible();
    const groups: [string, RunSummary[]][] = [
      [msg('Running'), rows.filter((r) => r.running)],
      [msg('Last 24 hours'), rows.filter((r) => !r.running && ago(r) < 86400)],
      [msg('Older'), rows.filter((r) => !r.running && ago(r) >= 86400)],
    ];
    let i = 0;
    const active = rows[this.kb] ? optionId(this.kb) : nothing;
    return html`<div class="search">
        <input placeholder=${msg('Search runs')} aria-label=${msg('Search runs')} autocomplete="off" .value=${this.q}
          role="combobox" aria-expanded=${rows.length ? 'true' : 'false'} aria-controls="runs" aria-autocomplete="list" aria-activedescendant=${active}
          @input=${(e: Event) => { this.q = (e.target as HTMLInputElement).value; this.kb = 0; }}
          @keydown=${(e: KeyboardEvent) => this.onKey(e, rows)} />
        <div class="keys meta" aria-hidden="true"><span class="kbd">↑</span><span class="kbd">↓</span> <span class="kbd">Enter</span> <span class="kbd">Esc</span></div>
      </div>
      <div class="list" @mousedown=${(e: MouseEvent) => e.preventDefault()}>
        ${rows.length
          ? html`<div id="runs" role="listbox" aria-label=${msg('Runs')}>
              ${groups.map(([name, rs]) =>
                rs.length
                  ? html`<div role="group" aria-label=${name}>
                      <div class="group" aria-hidden="true">${name} <span class="n">${rs.length}</span></div>
                      ${rs.map((r) => this.item(r, i++))}
                    </div>`
                  : nothing,
              )}
            </div>`
          : html`<div class="blank"><span>${msg('No runs match')}</span></div>`}
      </div>`;
  }

  /** Tasks by how they ended, as the run's own page counts them, and how long it took: one line. */
  private counts(r: RunSummary): string {
    const t = r.tasks;
    const parts = [msg(str`${t.done} of ${t.total} tasks done`)];
    if (t.failed) parts.push(stateCount('failed', t.failed));
    if (t.not_started) parts.push(stateCount('not_started', t.not_started));
    if (t.skipped) parts.push(stateCount('skipped', t.skipped));
    if (t.running) parts.push(stateCount('running', t.running));
    if (t.waiting) parts.push(stateCount('waiting', t.waiting));
    const s = took(r);
    if (s != null) parts.push(msg(str`took ${fmtDur(s)}`));
    if (r.cost_usd !== null && r.cost_usd !== undefined) parts.push(usd(r.cost_usd));
    const usage = accountsLine(r.quota ?? []);
    if (usage) parts.push(usage);
    return facts(...parts);
  }

  private item(r: RunSummary, i: number) {
    const dot = runTone(r.running, r.tasks);
    const cls = `item${r.run === this.current ? ' cur' : ''}${i === this.kb ? ' kb' : ''}`;
    // An option of the listbox: the search field keeps the focus and names the active option (`aria-activedescendant`).
    return html`<div class=${cls} id=${optionId(i)} role="option" aria-selected=${i === this.kb ? 'true' : 'false'}
      aria-current=${r.run === this.current ? 'true' : nothing} @click=${() => this.pick(r.run)}>
      <span class="dot" data-tone=${toneAttr(dot)} aria-hidden="true"></span><span class="nm">${r.run}</span>
      <span class="when" title=${localTime(r.last_ts, true)}>${r.running ? msg('running') : relAgo(r.last_ts)}</span>
      <span class="sub">
        ${r.run_group && r.run_group !== r.run ? html`<span>${msg(str`Run group ${r.run_group}`)}</span>` : nothing}
        <span title=${accountsTip(r.quota ?? [])}>${this.counts(r)}</span>
      </span>
    </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-run-picker': CaRunPicker;
  }
}
