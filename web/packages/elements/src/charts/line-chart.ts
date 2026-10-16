import { html, nothing, svg, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import type { LegendItem } from '../primitives/legend.js';
import { ChartElement } from './base.js';
import { LABEL_GAP, labelStride, niceAxis, seriesColour } from './scale.js';
import type { ChartSeries } from './types.js';

const M = { top: 8, right: 10, bottom: 22 };

/** The path of a series: a line through its values, broken where a value is null. */
export function linePath(points: readonly ([number, number] | null)[]): string {
  let d = '';
  let open = false;
  for (const p of points) {
    if (!p) {
      open = false;
      continue;
    }
    d += `${open ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`;
    open = true;
  }
  return d;
}

/**
 * Lines over the labels of `x`, one per series (a value per label; null breaks the
 * line). Six series take the series colours in their order; any past six are drawn in
 * the colour of "other" and named in the legend and the tooltip. Pointing at a label,
 * or moving to it with the arrow keys, marks it with a rule and shows every series'
 * value there; the switch shows them all as a table.
 *
 * @tagname cae-line-chart
 * @csspart plot - the chart
 * @csspart table - the table of its values
 * @csspart switch - the button between the two
 * @csspart empty - what it shows with no values
 * @csspart legend - the legend
 */
export class CaeLineChart extends ChartElement {
  @property({ attribute: false }) x: readonly string[] = [];
  @property({ attribute: false }) series: readonly ChartSeries[] = [];

  protected hasValues(): boolean {
    return this.x.length > 0 && this.series.some((s) => s.values.some((v) => v !== null && v !== undefined));
  }

  protected legendItems(): LegendItem[] {
    return this.series.length > 1 ? this.series.map((s, i) => ({ label: s.name, swatch: seriesColour(i) })) : [];
  }

  protected itemCount(): number {
    return this.x.length;
  }

  protected plot(): TemplateResult {
    const n = this.x.length;
    const values = this.series.flatMap((s) => s.values.filter((v): v is number => v !== null && v !== undefined));
    const axis = niceAxis(Math.min(0, ...values), Math.max(0, ...values));
    const left = Math.max(...axis.ticks.map((t) => this.labelWidth(this.format(t)))) + 4;
    const w = this.plotWidth;
    const h = this.height;
    const pw = w - left - M.right;
    const ph = h - M.top - M.bottom;
    const step = n > 1 ? pw / (n - 1) : 0;
    const px = (j: number) => (n > 1 ? left + j * step : left + pw / 2);
    const py = (v: number) => M.top + ph - ((v - axis.min) / (axis.max - axis.min)) * ph;
    const stride = labelStride(n, pw, Math.max(...this.x.map((s) => this.labelWidth(s))) + LABEL_GAP);
    const a = this.active;
    const hitW = n > 1 ? step : pw;
    return html`<svg width=${w} height=${h} role="img" aria-label=${this.label || nothing}>
        ${axis.ticks.map(
          (t) => svg`<line class=${t === 0 ? 'base' : 'grid'} x1=${left} x2=${w - M.right} y1=${py(t)} y2=${py(t)}></line>
            <text class="axis" x=${left - 6} y=${py(t)} dy="0.32em" text-anchor="end">${this.format(t)}</text>`,
        )}
        ${a !== null ? svg`<line class="base" x1=${px(a)} x2=${px(a)} y1=${M.top} y2=${M.top + ph}></line>` : nothing}
        ${this.series.map((s, i) => {
          const pts = this.x.map((_, j) => {
            const v = s.values[j];
            return v === null || v === undefined ? null : ([px(j), py(v)] as [number, number]);
          });
          const lone = pts.filter((p, j) => p && !pts[j - 1] && !pts[j + 1]) as [number, number][];
          return svg`<path d=${linePath(pts)} fill="none" stroke=${seriesColour(i)} stroke-width="2" stroke-linejoin="round" stroke-linecap="round"></path>
            ${lone.map((p) => svg`<circle cx=${p[0]} cy=${p[1]} r="2.5" fill=${seriesColour(i)}></circle>`)}`;
        })}
        ${a !== null
          ? this.series.map((s, i) => {
              const v = s.values[a];
              return v === null || v === undefined
                ? nothing
                : svg`<circle cx=${px(a)} cy=${py(v)} r="4.5" fill=${seriesColour(i)} stroke="var(--card)" stroke-width="2"></circle>`;
            })
          : nothing}
        ${this.x.map((label, j) =>
          j % stride === 0
            ? svg`<text class="axis" x=${px(j)} y=${h - 6} text-anchor=${n > 1 && j === 0 ? 'start' : n > 1 && j === n - 1 ? 'end' : 'middle'}>${label}</text>`
            : nothing,
        )}
        ${this.x.map(
          (_, j) => svg`<rect class="hit" x=${px(j) - hitW / 2} y=${M.top} width=${hitW} height=${ph + M.bottom}
            @mouseenter=${() => (this.active = j)}></rect>`,
        )}
      </svg>
      ${a !== null && a < n ? this.tip(px(a), M.top, this.tipBody(a)) : nothing}`;
  }

  private tipBody(j: number): TemplateResult {
    const none = this.words.none;
    return html`<b>${this.x[j]}</b>
      ${this.series.map((s, i) => this.tipRow(seriesColour(i), s.name, s.values[j] === null || s.values[j] === undefined ? none : this.format(s.values[j])))}`;
  }

  protected table(): TemplateResult {
    const none = this.words.none;
    return html`<table aria-label=${this.label || nothing}>
      <thead><tr><th scope="col">${this.words.label}</th>${this.series.map((s) => html`<th scope="col">${s.name}</th>`)}</tr></thead>
      <tbody>${this.x.map(
        (label, j) =>
          html`<tr><th scope="row">${label}</th>${this.series.map((s) => html`<td>${s.values[j] === null || s.values[j] === undefined ? none : this.format(s.values[j])}</td>`)}</tr>`,
      )}</tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-line-chart': CaeLineChart;
  }
}
