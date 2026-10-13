import { spendByKind, spendByTask, spendOf, totalTokens, type JournalRow, type Spend } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../../events.js';
import { facts, kindUnit, tokenCount, usd } from '../../lib/format.js';
import { base } from '../../styles/base.js';

type Part = 'input' | 'cache_read' | 'cache_creation' | 'output';
const PARTS: readonly Part[] = ['input', 'cache_read', 'cache_creation', 'output'];

/**
 * Where a run's tokens and cost went: per kind, a bar of its tokens (input,
 * cache read, cache write, output) with its cost and share of the run's cost,
 * most expensive first; then the most expensive tasks.
 *
 * @fires ca-open-task - `{key}`: one of the most expensive tasks was clicked
 */
@customElement('ca-spend-breakdown')
@localized()
export class CaSpendBreakdown extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .kinds { display: grid; grid-template-columns: minmax(90px, max-content) minmax(0, 1fr) max-content max-content; gap: 8px 14px; align-items: center; }
      .kind { font-family: var(--mono); font-size: 12px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .bar { display: flex; height: 12px; border-radius: 4px; overflow: hidden; background: var(--track); }
      .bar i { display: block; height: 100%; }
      .num { font-variant-numeric: tabular-nums; text-align: right; font-size: 12px; white-space: nowrap; }
      .share { color: var(--text-muted); min-width: 3.5em; }
      .seg-input { background: var(--tok-input); }
      .seg-cache_read { background: var(--tok-cache-read); }
      .seg-cache_creation { background: var(--tok-cache-write); }
      .seg-output { background: var(--tok-output); }
      .legend { margin-top: 10px; }
      h4 { margin: 16px 0 6px; font-size: 12px; color: var(--text-2); font-weight: 600; }
      .top { display: grid; grid-template-columns: minmax(160px, max-content) 64px 64px 40px; column-gap: 24px; row-gap: 4px; align-items: baseline; }
      .top a { font-family: var(--mono); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    `,
  ];

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** How many of the most expensive tasks to list. */
  @property({ type: Number }) top = 5;

  private partLabel(p: Part): string {
    switch (p) {
      case 'input':
        return msg('input');
      case 'cache_read':
        return msg('cache read');
      case 'cache_creation':
        return msg('cache write');
      case 'output':
        return msg('output');
    }
  }

  private bar(s: Spend, max: number) {
    const total = totalTokens(s);
    const width = max ? (100 * total) / max : 0;
    const tip = facts(...PARTS.map((p) => `${this.partLabel(p)} ${tokenCount(s[p])}`));
    return html`<div class="bar" title=${tip} style="width:${Math.max(width, 0.5).toFixed(2)}%">
      ${PARTS.map((p) => (s[p] && total ? html`<i class="seg-${p}" style="width:${((100 * s[p]) / total).toFixed(2)}%"></i>` : nothing))}
    </div>`;
  }

  override render() {
    if (!spendOf(this.journal)) return html`<div class="meta">${msg('No tokens reported')}</div>`;
    const kinds = spendByKind(this.journal);
    const max = Math.max(1, ...kinds.map((k) => totalTokens(k.spend)));
    const tasks = spendByTask(this.journal).slice(0, this.top);
    return html`<div class="kinds">
        ${repeat(
          kinds,
          (k) => k.id,
          (k) => html`<span class="kind" title=${k.id}>${k.id}</span>${this.bar(k.spend, max)}
            <span class="num">${facts(tokenCount(totalTokens(k.spend)), usd(k.spend.cost))}</span>
            <span class="num share">${k.share !== null ? `${Math.round(k.share * 100)}%` : ''}</span>`,
        )}
      </div>
      <div class="legend">${PARTS.map((p) => html`<span><i class="seg-${p}"></i>${this.partLabel(p)}</span>`)}</div>
      <h4>${msg('Most expensive tasks')}</h4>
      <div class="top">
        ${tasks.map(
          (t) => html`<a class="lnk" href="#" title=${t.id} @click=${(e: Event) => {
              e.preventDefault();
              emit(this, 'ca-open-task', { key: t.id });
            }}>${kindUnit(t)}</a>
            <span class="num">${tokenCount(totalTokens(t.spend))}</span>
            <span class="num">${usd(t.spend.cost)}</span>
            <span class="num share">${t.share !== null ? msg(str`${Math.round(t.share * 100)}%`) : ''}</span>`,
        )}
      </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-spend-breakdown': CaSpendBreakdown;
  }
}
