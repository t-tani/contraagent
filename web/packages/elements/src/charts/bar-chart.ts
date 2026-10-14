import { css, html, nothing, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { toneAttr } from '../core/tone.js';
import type { LegendItem } from '../primitives/legend.js';
import { ChartElement } from './base.js';
import type { ChartBar } from './types.js';

/**
 * Horizontal bars, one per label, in the order given (a funnel's stages, a ranking):
 * each its label, a bar as long as its value against the longest, and the value in
 * words. A bar with a `tone` takes that status colour, the others one colour. Every
 * value is written beside its bar, so no tooltip is needed; the switch shows them as
 * a table.
 *
 * @tagname cae-bar-chart
 * @csspart plot - the bars
 * @csspart table - the table of its values
 * @csspart switch - the button between the two
 * @csspart empty - what it shows with no values
 */
export class CaeBarChart extends ChartElement {
  static override styles = [
    ...ChartElement.styles,
    css`
      .bars { display: grid; grid-template-columns: minmax(80px, max-content) minmax(0, 1fr) max-content; gap: 6px 12px; align-items: center;
        font-size: var(--font-size-sm); }
      .bars .r { display: contents; }
      .bars .l { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 34ch; }
      .bars .track { display: block; height: 12px; }
      .bars .bar { display: block; height: 100%; min-width: 2px; border-radius: 1px 4px 4px 1px; background: var(--series-1); }
      .bars .bar[data-tone] { background: var(--tone); }
      .bars .v { color: var(--text-2); font-variant-numeric: tabular-nums; text-align: right; }
    `,
  ];

  @property({ attribute: false }) bars: readonly ChartBar[] = [];

  protected hasValues(): boolean {
    return this.bars.length > 0;
  }

  protected legendItems(): LegendItem[] {
    return [];
  }

  protected itemCount(): number {
    return 0;
  }

  protected plot(): TemplateResult {
    const top = Math.max(0, ...this.bars.map((b) => b.value));
    return html`<div class="bars" role="list" aria-label=${this.label || nothing}>
      ${this.bars.map(
        (b) => html`<div class="r" role="listitem" aria-label="${b.label} | ${this.format(b.value)}">
          <span class="l" aria-hidden="true" title=${b.label}>${b.label}</span>
          <span class="track" aria-hidden="true"><span class="bar" data-tone=${toneAttr(b.tone)}
            style="width: ${top > 0 ? (100 * Math.max(0, b.value)) / top : 0}%"></span></span>
          <span class="v" aria-hidden="true">${this.format(b.value)}</span></div>`,
      )}
    </div>`;
  }

  protected table(): TemplateResult {
    return html`<table aria-label=${this.label || nothing}>
      <tbody>${this.bars.map((b) => html`<tr><th scope="row">${b.label}</th><td>${this.format(b.value)}</td></tr>`)}</tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-bar-chart': CaeBarChart;
  }
}
