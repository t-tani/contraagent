import { runAccounts, type JournalRow, type QuotaReading } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { ClockController } from '../../lib/clock.js';
import { localTime } from '../../lib/format.js';
import { credentialLabel } from '../../lib/labels.js';
import { pct, quotaStatusLabel, resetsIn } from '../../lib/quota-format.js';
import { base } from '../../styles/base.js';

type Window = 'five_hour' | 'seven_day';

/**
 * Subscription usage over the run, per account (credential): for the weekly and
 * the 5-hour window, the account's first reading and its last, and when each
 * window resets. Readings come at session starts and are account-wide.
 */
@customElement('ca-quota')
@localized()
export class CaQuota extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .rows { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content max-content; gap: 10px 14px; align-items: center; }
      .name { font-size: 12px; color: var(--fg2); white-space: nowrap; }
      .bar { position: relative; height: 12px; border-radius: 4px; background: var(--track); overflow: hidden; }
      .bar i { position: absolute; top: 0; bottom: 0; }
      .bar .before { left: 0; background: var(--muted); opacity: 0.55; }
      .bar .during { background: var(--live); }
      .bar.hot .during { background: var(--warn); }
      .bar.full .during { background: var(--err); }
      .val { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .val b { color: var(--fg); }
      .reset { font-size: 11.5px; color: var(--mut); white-space: nowrap; }
      .status { margin-top: 8px; }
      .acct { padding: 10px 0; border-top: 1px solid var(--line); }
      .acct:first-child { border-top: 0; padding-top: 0; }
      .acct-h { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; font-size: 12px; }
      .acct-h i { font-style: normal; color: var(--mut); font-size: 11px; }
      .acct-h b { font-family: var(--mono); color: var(--fg); font-weight: 600; }
    `,
  ];

  @property({ attribute: false }) journal: JournalRow[] = [];

  constructor() {
    super();
    new ClockController(this); // "resets in" counts down
  }

  private row(w: Window, name: string, first: QuotaReading, last: QuotaReading) {
    const a = first[`${w}_pct`];
    const b = last[`${w}_pct`];
    if (a == null && b == null) return nothing;
    const from = Math.max(0, Math.min(100, a ?? b ?? 0));
    const to = Math.max(from, Math.min(100, b ?? from));
    const resets = last[`${w}_resets_at`];
    const cls = to >= 100 ? 'full' : to >= 80 ? 'hot' : '';
    return html`<span class="name">${name}</span>
      <span class="bar ${cls}" title=${`${pct(a)} → ${pct(b)}`}>
        <i class="before" style="width:${from}%"></i>
        <i class="during" style="left:${from}%;width:${to - from}%"></i>
      </span>
      <span class="val">${pct(a)} → <b>${pct(b)}</b></span>
      <span class="reset" title=${resets ? localTime(resets, true) : ''}>${resetsIn(resets)}</span>`;
  }

  override render() {
    const accounts = runAccounts(this.journal);
    if (!accounts.length) return nothing;
    return html`${accounts.map((a) => {
      const status = quotaStatusLabel(a.last.status);
      return html`<div class="acct">
        <div class="acct-h"><i>${msg('Identity')}</i><b>${credentialLabel(a.credential) || '—'}</b>${status
            ? html`<span class="pill p-timeout" title=${a.last.status ?? ''}>${status}</span>`
            : nothing}</div>
        <div class="rows">
          ${this.row('seven_day', msg('Weekly usage'), a.first, a.last)} ${this.row('five_hour', msg('5-hour usage'), a.first, a.last)}
        </div>
      </div>`;
    })}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-quota': CaQuota;
  }
}
