import { html, nothing, svg, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import type { LegendItem } from '../primitives/legend.js';
import { ChartElement } from './base.js';
import { foldSeries, LABEL_GAP, labelStride, niceAxis, type DrawnSeries } from './scale.js';
import type { ChartSeries } from './types.js';

/** The plot's margins: the value axis on the left, the labels under it. */
const M = { top: 8, right: 4, bottom: 22 };
/** A bar's top: rounded, the end anchored to the axis square. */
const RADIUS = 4;
/** The gap between the stacked parts of a bar, and between the bars of a group. */
const GAP = 2;

/** A bar from the axis up, its top corners rounded when `round`. */
export function barPath(x: number, y: number, w: number, h: number, round: boolean): string {
  if (h <= 0 || w <= 0) return '';
  const r = round ? Math.min(RADIUS, w / 2, h) : 0;
  return `M${x},${y + h}V${y + r}${r ? `Q${x},${y} ${x + r},${y}` : ''}H${x + w - r}${r ? `Q${x + w},${y} ${x + w},${y + r}` : ''}V${y + h}Z`;
}

/**
 * Vertical bars, one group per label of `x`: a bar per series side by side, or with
 * `stacked`, the series of a label on one bar. Six series take the series colours in
 * their order; past six, the sixth and later are one bar part, "other". A legend
 * names the series when there are two or more. Pointing at a label, or moving to it
 * with the arrow keys, shows its values; the switch shows them all as a table.
 *
 * @tagname cae-column-chart
 * @csspart plot - the chart
 * @csspart table - the table of its values
 * @csspart switch - the button between the two
 * @csspart empty - what it shows with no values
 * @csspart legend - the legend
 */
export class CaeColumnChart extends ChartElement {
  /** A label per group of bars, in order. */
  @property({ attribute: false }) x: readonly string[] = [];
  @property({ attribute: false }) series: readonly ChartSeries[] = [];
  /** The series of a label on one bar, instead of side by side. */
  @property({ type: Boolean }) stacked = false;

  private get drawn(): DrawnSeries[] {
    return foldSeries(this.series, this.words.other);
  }

  protected hasValues(): boolean {
    return this.x.length > 0 && this.series.some((s) => s.values.some((v) => v !== null && v !== undefined));
  }

  protected legendItems(): LegendItem[] {
    const d = this.drawn;
    return d.length > 1 ? d.map((s) => ({ label: s.name, swatch: s.colour })) : [];
  }

  protected itemCount(): number {
    return this.x.length;
  }

  /** The total of label `j` (the stacked bar's height). */
  private total(j: number): number {
    return this.drawn.reduce((a, s) => a + Math.max(0, s.values[j] ?? 0), 0);
  }

  protected plot(): TemplateResult {
    const d = this.drawn;
    const n = this.x.length;
    const values = d.flatMap((s) => s.values.filter((v): v is number => v !== null && v !== undefined));
    const high = this.stacked ? Math.max(0, ...this.x.map((_, j) => this.total(j))) : Math.max(0, ...values);
    const axis = niceAxis(Math.min(0, ...values), high);
    const left = Math.max(...axis.ticks.map((t) => this.labelWidth(this.format(t)))) + 4;
    const w = this.plotWidth;
    const h = this.height;
    const pw = w - left - M.right;
    const ph = h - M.top - M.bottom;
    const y = (v: number) => M.top + ph - ((v - axis.min) / (axis.max - axis.min)) * ph;
    const band = pw / n;
    const barW = Math.max(2, Math.min(40, band * (this.stacked || d.length === 1 ? 0.62 : 0.8)));
    const stride = labelStride(n, pw, Math.max(...this.x.map((s) => this.labelWidth(s))) + LABEL_GAP);
    const bars: TemplateResult[] = [];
    for (let j = 0; j < n; j++) {
      const x0 = left + j * band + (band - barW) / 2;
      if (this.stacked) {
        let at = 0;
        const parts = d.map((s) => ({ s, v: Math.max(0, s.values[j] ?? 0) })).filter((p) => p.v > 0);
        parts.forEach((p, k) => {
          const top = y(at + p.v);
          const bottom = y(at);
          // Each part is 2px shorter than its share, so the surface shows between the parts.
          const hgt = bottom - top - (k > 0 ? GAP : 0);
          bars.push(svg`<path d=${barPath(x0, top, barW, Math.max(0, hgt), k === parts.length - 1)} fill=${p.s.colour}></path>`);
          at += p.v;
        });
      } else {
        const each = (barW - GAP * (d.length - 1)) / d.length;
        d.forEach((s, k) => {
          const v = s.values[j];
          if (v === null || v === undefined || v === 0) return;
          const top = y(Math.max(0, v));
          const bottom = y(Math.min(0, v));
          bars.push(svg`<path d=${barPath(x0 + k * (each + GAP), top, Math.max(1, each), bottom - top, v > 0)} fill=${s.colour}></path>`);
        });
      }
    }
    const a = this.active;
    return html`<svg width=${w} height=${h} role="img" aria-label=${this.label || nothing}>
        ${axis.ticks.map(
          (t) => svg`<line class=${t === 0 ? 'base' : 'grid'} x1=${left} x2=${w - M.right} y1=${y(t)} y2=${y(t)}></line>
            <text class="axis" x=${left - 6} y=${y(t)} dy="0.32em" text-anchor="end">${this.format(t)}</text>`,
        )}
        ${a !== null ? svg`<rect class="band" x=${left + a * band} y=${M.top} width=${band} height=${ph}></rect>` : nothing}
        ${bars}
        ${this.x.map((label, j) =>
          j % stride === 0
            ? svg`<text class="axis" x=${left + j * band + band / 2} y=${h - 6} text-anchor="middle">${label}</text>`
            : nothing,
        )}
        ${this.x.map(
          (_, j) => svg`<rect class="hit" x=${left + j * band} y=${M.top} width=${band} height=${ph + M.bottom}
            @mouseenter=${() => (this.active = j)}></rect>`,
        )}
      </svg>
      ${a !== null && a < n ? this.tip(left + a * band + band / 2, M.top, this.tipBody(a)) : nothing}`;
  }

  private tipBody(j: number): TemplateResult {
    const d = this.drawn;
    const none = this.words.none;
    return html`<b>${this.x[j]}</b>
      ${[...d].reverse().map((s) => this.tipRow(s.colour, s.name, s.values[j] === null || s.values[j] === undefined ? none : this.format(s.values[j])))}
      ${this.stacked && d.length > 1 ? this.tipRow(null, this.words.total, this.format(this.total(j))) : nothing}`;
  }

  protected table(): TemplateResult {
    const d = this.drawn;
    const none = this.words.none;
    const sum = this.stacked && d.length > 1;
    return html`<table aria-label=${this.label || nothing}>
      <thead><tr><th scope="col">${this.words.label}</th>${d.map((s) => html`<th scope="col">${s.name}</th>`)}${sum ? html`<th scope="col">${this.words.total}</th>` : nothing}</tr></thead>
      <tbody>${this.x.map(
        (label, j) => html`<tr><th scope="row">${label}</th>${d.map((s) => html`<td>${s.values[j] === null || s.values[j] === undefined ? none : this.format(s.values[j])}</td>`)}${
          sum ? html`<td>${this.format(this.total(j))}</td>` : nothing
        }</tr>`,
      )}</tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-column-chart': CaeColumnChart;
  }
}
