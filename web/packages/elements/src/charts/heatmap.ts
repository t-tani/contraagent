import { html, nothing, svg, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import type { LegendItem } from '../primitives/legend.js';
import { ChartElement } from './base.js';
import { textWidth } from './column-chart.js';
import { LABEL_GAP, labelStride } from './scale.js';

/** One hue, light to dark: a value's share of the colour, by its step of five. */
export const HEAT_STEPS = [16, 34, 52, 72, 92] as const;
/** The hue of the scale. */
const HUE = 'var(--series-1)';
const CELL_H = 22;
const GAP = 2;
const M = { top: 2, right: 2, bottom: 22 };

/** A colour of the scale: `pct` percent of its hue over the card. */
export const heatColour = (pct: number): string => `color-mix(in srgb, ${HUE} ${pct}%, var(--card))`;

/** The step (0..4) of `v` between `low` and `high`. */
export function heatStep(v: number, low: number, high: number): number {
  if (!(high > low)) return HEAT_STEPS.length - 1;
  const t = (v - low) / (high - low);
  return Math.min(HEAT_STEPS.length - 1, Math.max(0, Math.floor(t * HEAT_STEPS.length)));
}

/**
 * A value per row (`y`) and column (`x`), each a cell coloured on one scale, light to
 * dark (`values[row][column]`; a null cell is left empty, a 0 is the lightest step).
 * The legend gives the scale's lowest and highest value. Pointing at a cell, or moving
 * to it with the arrow keys (up and down by a row), shows its row, column and value;
 * the switch shows them all as a table.
 *
 * @tagname cae-heatmap
 * @csspart plot - the chart
 * @csspart table - the table of its values
 * @csspart switch - the button between the two
 * @csspart empty - what it shows with no values
 * @csspart legend - the legend
 */
export class CaeHeatmap extends ChartElement {
  @property({ attribute: false }) x: readonly string[] = [];
  @property({ attribute: false }) y: readonly string[] = [];
  @property({ attribute: false }) values: readonly (readonly (number | null)[])[] = [];

  private get range(): [number, number] {
    const all = this.values.flat().filter((v): v is number => v !== null && v !== undefined);
    return all.length ? [Math.min(0, ...all), Math.max(...all)] : [0, 0];
  }

  protected hasValues(): boolean {
    return this.x.length > 0 && this.y.length > 0 && this.values.some((r) => r.some((v) => v !== null && v !== undefined));
  }

  protected legendItems(): LegendItem[] {
    const [low, high] = this.range;
    const strip = html`<span class="scale" aria-hidden="true">${HEAT_STEPS.map((p) => html`<i style="background: ${heatColour(p)}"></i>`)}</span>`;
    return [{ label: this.words.scale(this.format(low), this.format(high)), icon: strip }];
  }

  protected itemCount(): number {
    return this.x.length * this.y.length;
  }

  protected override rowLength(): number {
    return this.x.length;
  }

  protected plot(): TemplateResult {
    const nx = this.x.length;
    const ny = this.y.length;
    const [low, high] = this.range;
    const left = Math.max(...this.y.map(textWidth)) + 2;
    const w = this.plotWidth;
    const pw = w - left - M.right;
    const cw = pw / nx;
    const h = M.top + ny * CELL_H + M.bottom;
    const stride = labelStride(nx, pw, Math.max(...this.x.map(textWidth)) + LABEL_GAP);
    const a = this.active;
    const cells: TemplateResult[] = [];
    for (let r = 0; r < ny; r++)
      for (let c = 0; c < nx; c++) {
        const v = this.values[r]?.[c];
        const x = left + c * cw;
        const y = M.top + r * CELL_H;
        const i = r * nx + c;
        cells.push(
          v === null || v === undefined
            ? svg`<rect x=${x + GAP / 2} y=${y + GAP / 2} width=${Math.max(1, cw - GAP)} height=${CELL_H - GAP} rx="2" fill="none" stroke="var(--line)"
                @mouseenter=${() => (this.active = i)}></rect>`
            : svg`<rect x=${x + GAP / 2} y=${y + GAP / 2} width=${Math.max(1, cw - GAP)} height=${CELL_H - GAP} rx="2"
                fill=${heatColour(HEAT_STEPS[heatStep(v, low, high)] ?? 92)} stroke=${a === i ? 'var(--text)' : 'none'} stroke-width="1.5"
                @mouseenter=${() => (this.active = i)}></rect>`,
        );
      }
    const at = a !== null && a < nx * ny ? { r: Math.floor(a / nx), c: a % nx } : null;
    return html`<svg width=${w} height=${h} role="img" aria-label=${this.label || nothing}>
        ${this.y.map((label, r) => svg`<text class="axis" x=${left - 6} y=${M.top + r * CELL_H + CELL_H / 2} dy="0.32em" text-anchor="end">${label}</text>`)}
        ${cells}
        ${this.x.map((label, c) =>
          c % stride === 0 ? svg`<text class="axis" x=${left + c * cw + cw / 2} y=${h - 6} text-anchor="middle">${label}</text>` : nothing,
        )}
      </svg>
      ${at ? this.tip(left + at.c * cw + cw / 2, M.top + (at.r + 1) * CELL_H, this.tipBody(at.r, at.c)) : nothing}`;
  }

  private tipBody(r: number, c: number): TemplateResult {
    const v = this.values[r]?.[c];
    return html`<b>${this.y[r]} | ${this.x[c]}</b>
      <div class="row"><span>${v === null || v === undefined ? this.words.none : this.format(v)}</span></div>`;
  }

  protected table(): TemplateResult {
    const none = this.words.none;
    return html`<table aria-label=${this.label || nothing}>
      <thead><tr><th scope="col">${this.words.label}</th>${this.x.map((l) => html`<th scope="col">${l}</th>`)}</tr></thead>
      <tbody>${this.y.map(
        (label, r) => html`<tr><th scope="row">${label}</th>${this.x.map((_, c) => {
          const v = this.values[r]?.[c];
          return html`<td>${v === null || v === undefined ? none : this.format(v)}</td>`;
        })}</tr>`,
      )}</tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-heatmap': CaeHeatmap;
  }
}
