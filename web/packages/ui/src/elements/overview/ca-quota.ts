import { runAccounts, type AccountUsage, type CredentialRest, type JournalRow, type QuotaCap, type QuotaReading } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { ClockController } from '@contraagent/elements';
import { localTime } from '../../words/format.js';
import { capLabel, capsLine, credentialLabel, restFacts, restSpan } from '../../words/index.js';
import { pct, quotaStatusLabel, resetsIn } from '../../words/quota.js';
import { pill } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';

type Window = 'five_hour' | 'seven_day';

/**
 * Subscription usage over the run, per account (credential): for the weekly and
 * the 5-hour window, the account's first reading and its last, and when each
 * window resets. Readings come at session starts and are account-wide. The
 * accounts are the run's (`journal`), or given (`accounts`: a hub's, over every
 * run of every host, `Hosts.quota`). With the run's quota caps and rests
 * (`caps`, `rests`, `rule`: `Plan.quota_caps`, `.rests`, `.quota_rule`), each
 * window shows its cap, and each account whether it is paused and its rests.
 */
@customElement('ca-quota')
@localized()
export class CaQuota extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; container-type: inline-size; }
      /* the bar keeps a width of its own, and ends near its figures on a wide card */
      .rows { display: grid; grid-template-columns: max-content minmax(70px, 420px) max-content max-content; justify-content: start; gap: 10px 14px; align-items: center; }
      .name { font-size: 12px; color: var(--text-2); white-space: nowrap; }
      .bar { position: relative; height: 12px; border-radius: 4px; background: var(--track); overflow: hidden; }
      .bar i { position: absolute; top: 0; bottom: 0; }
      /* usage measures, it does not judge: neutral, attention from 80% (the number says it too) */
      .bar .before { left: 0; background: var(--meter); opacity: 0.45; }
      .bar .during { background: var(--meter); }
      .bar.hot .during, .bar.full .during, .bar.hot .before, .bar.full .before { background: var(--status-attention); }
      /* the cap: a line across the bar where the account is paused */
      .bar .cap { width: 2px; margin-left: -1px; background: var(--text); opacity: 0.7; }
      .val.hot b, .val.full b { color: var(--status-attention); }
      .val { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
      .val b { color: var(--text); }
      .val .lim { color: var(--text-muted); }
      .reset { font-size: 11.5px; color: var(--text-muted); white-space: nowrap; }
      /* a narrow card: the reset time goes under its bar */
      @container (max-width: 460px) {
        .rows { grid-template-columns: max-content minmax(70px, 1fr) max-content; row-gap: 2px; }
        .reset { grid-column: 2 / -1; margin-bottom: 6px; }
      }
      .status { margin-top: 8px; }
      .acct { padding: 10px 0; border-top: 1px solid var(--line); }
      .acct:first-child { border-top: 0; padding-top: 0; }
      .acct-h { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; font-size: 12px; }
      .acct-h i { font-style: normal; color: var(--text-muted); font-size: 11px; }
      .acct-h b { font-family: var(--mono); color: var(--text); font-weight: 600; }
      .rests { margin: 8px 0 0; padding: 0; list-style: none; font-size: 11.5px; color: var(--text-2); }
      .rests li { padding: 2px 0; }
      .rule { margin-bottom: 10px; font-size: 12px; color: var(--text-2); }
      .rule code { font-family: var(--mono); color: var(--text); }
    `,
  ];

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** Each account's first and last reading, highest weekly use first; null: from `journal`. */
  @property({ attribute: false }) accounts: readonly AccountUsage[] | null = null;
  /** The run's quota caps, by credential (`Plan.quota_caps`). */
  @property({ attribute: false }) caps: readonly QuotaCap[] = [];
  /** Each rest of a credential in the run, in start order (`Plan.rests`). */
  @property({ attribute: false }) rests: readonly CredentialRest[] = [];
  /** The run's quota rule, `module.qualname` (`Plan.quota_rule`); '' for none. */
  @property() rule = '';
  /** The run is live: a rest with no reset time (a rule's) stands only while it is. */
  @property({ type: Boolean }) live = false;

  constructor() {
    super();
    new ClockController(this); // "resets in" counts down
  }

  private row(w: Window, name: string, first: QuotaReading, last: QuotaReading, cap: number | null | undefined) {
    const a = first[`${w}_pct`];
    const b = last[`${w}_pct`];
    if (a == null && b == null) return nothing;
    const from = Math.max(0, Math.min(100, a ?? b ?? 0));
    const to = Math.max(from, Math.min(100, b ?? from));
    const resets = last[`${w}_resets_at`];
    const cls = to >= 100 || (cap != null && to >= cap) ? 'full' : to >= 80 ? 'hot' : '';
    const limit = cap != null ? capLabel(cap) : '';
    return html`<span class="name">${name}</span>
      <span class="bar ${cls}" title=${limit ? `${pct(a)} → ${pct(b)} | ${limit}` : `${pct(a)} → ${pct(b)}`}>
        <i class="before" style="width:${from}%"></i>
        <i class="during" style="left:${from}%;width:${to - from}%"></i>
        ${cap != null ? html`<i class="cap" style="left:${Math.min(100, cap)}%" aria-hidden="true"></i>` : nothing}
      </span>
      <span class="val ${cls}">${pct(a)} → <b>${pct(b)}</b>${limit ? html` <span class="lim">| ${limit}</span>` : nothing}</span>
      <span class="reset" title=${resets ? localTime(resets, true) : ''}>${resetsIn(resets)}</span>`;
  }

  /**
   * An account's pill while it is paused: `paused until 10/14 14:30`; nothing otherwise. A rest
   * stands until it ended, until its window reset, and (a rule's, with no reset) while the run is live.
   */
  private paused(rests: readonly CredentialRest[]) {
    const at = Date.now();
    const now = rests.find((r) => !r.ended && (r.until ? Date.parse(r.until) > at : this.live));
    if (!now) return nothing;
    const text = now.until ? msg(str`paused until ${localTime(now.until, true)}`) : msg('paused');
    return pill({ text, tone: 'attention', title: restFacts(now) });
  }

  override render() {
    const accounts = this.accounts ?? runAccounts(this.journal);
    if (!accounts.length && !this.rests.length) return nothing;
    const caps = new Map(this.caps.map((c) => [c.credential, c]));
    return html`${this.rule
        ? html`<div class="rule" title="quota_rule">${msg('Usage rule')} <code>${this.rule}</code></div>`
        : nothing}${accounts.map((a) => {
      const status = quotaStatusLabel(a.last.status);
      const cap = caps.get(a.credential);
      const rests = this.rests.filter((r) => r.credential === a.credential);
      return html`<div class="acct">
        <div class="acct-h"><i>${msg('Identity')}</i><b>${credentialLabel(a.credential) || '—'}</b>${status
            ? pill({ text: status, tone: 'attention', title: a.last.status, mark: null })
            : nothing}${this.paused(rests)}${cap ? html`<i title="max_five_hour_pct, max_seven_day_pct">${capsLine(cap)}</i>` : nothing}</div>
        <div class="rows">
          ${this.row('seven_day', msg('Weekly usage'), a.first, a.last, cap?.seven_day_pct)}
          ${this.row('five_hour', msg('5-hour usage'), a.first, a.last, cap?.five_hour_pct)}
        </div>
        ${this.restList(rests)}
      </div>`;
    })}${this.unread(accounts, caps)}`;
  }

  private restList(rests: readonly CredentialRest[]) {
    return rests.length ? html`<ul class="rests" title="rests.jsonl">${rests.map((r) => html`<li>${restSpan(r)}</li>`)}</ul>` : nothing;
  }

  /** The accounts paused in the run with no reading in its journal (their reading came from an earlier run). */
  private unread(accounts: readonly AccountUsage[], caps: ReadonlyMap<string, QuotaCap>) {
    const shown = new Set(accounts.map((a) => a.credential));
    const others = [...new Set(this.rests.map((r) => r.credential))].filter((c) => !shown.has(c));
    return others.map((credential) => {
      const rests = this.rests.filter((r) => r.credential === credential);
      const cap = caps.get(credential);
      return html`<div class="acct">
        <div class="acct-h"><i>${msg('Identity')}</i><b>${credentialLabel(credential)}</b>${this.paused(rests)}${cap
            ? html`<i title="max_five_hour_pct, max_seven_day_pct">${capsLine(cap)}</i>`
            : nothing}</div>
        ${this.restList(rests)}
      </div>`;
    });
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-quota': CaQuota;
  }
}
