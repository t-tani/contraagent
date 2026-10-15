import { css, html, nothing, svg, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import type { Tone } from '../core/tone.js';
import type { LegendItem } from '../primitives/legend.js';
import { ChartElement } from './base.js';
import { textWidth } from './column-chart.js';
import { LABEL_GAP, labelStride } from './scale.js';

/** One cell of a state grid: its state in words, the tone that colours it, and a fact of its own for the tooltip. */
export interface StateCell {
  label: string;
  tone: Tone;
  tip?: string | null;
}

const CELL_H = 22;
const GAP = 2;
const M = { top: 2, right: 2, bottom: 22 };
/** The narrowest cell that still holds its mark. */
const MARK_MIN = 14;

/**
 * A tone's fill: a failure and what needs attention stand out, a cell that ended well
 * stays quiet, so the exceptions are what the eye finds first.
 */
export function stateFill(tone: Tone): string {
  switch (tone) {
    case 'failed':
      return 'color-mix(in srgb, var(--status-failed) 72%, var(--card))';
    case 'attention':
      return 'color-mix(in srgb, var(--status-attention) 68%, var(--card))';
    case 'running':
      return 'color-mix(in srgb, var(--status-running) 60%, var(--card))';
    case 'done':
      return 'color-mix(in srgb, var(--status-done) 30%, var(--card))';
    case 'muted':
      return 'color-mix(in srgb, var(--text-muted) 26%, var(--card))';
    default:
      return 'color-mix(in srgb, var(--text) 12%, var(--card))';
  }
}

/** The mark a tone takes in a cell, beside its colour: ✓ done, ✕ failed, ◌ attention; none for the others. */
export function stateMark(tone: Tone): string {
  return tone === 'done' ? '✓' : tone === 'failed' ? '✕' : tone === 'attention' ? '◌' : '';
}

/** The order of the tones in a legend: the exceptions first, what ended well after. */
const TONE_ORDER: readonly Tone[] = ['failed', 'attention', 'running', 'done', 'muted', 'neutral'];

/** Each state of the cells once: by tone (failed, attention, running, done, muted, neutral), then in the order the cells first give it. */
export function statesOf(cells: readonly (readonly (StateCell | null | undefined)[])[]): StateCell[] {
  const seen = new Map<string, StateCell>();
  for (const row of cells) for (const c of row) if (c && !seen.has(`${c.tone}\u0000${c.label}`)) seen.set(`${c.tone}\u0000${c.label}`, c);
  return [...seen.values()].sort((a, b) => TONE_ORDER.indexOf(a.tone) - TONE_ORDER.indexOf(b.tone));
}

/**
 * A state per row (`y`) and column (`x`), each cell coloured by its tone
 * (`cells[row][column]`; a null cell is left empty): the states of hourly runs by day,
 * say. The colour is never alone: a cell wide enough holds its tone's mark (✓ ✕ ◌), the
 * legend names every state, and pointing at a cell, or moving to it with the arrow keys
 * (up and down by a row), shows its row, column, state and fact; the switch shows them
 * all as a table of words.
 *
 * @tagname cae-state-grid
 * @csspart plot - the grid
 * @csspart table - the table of its states
 * @csspart switch - the button between the two
 * @csspart empty - what it shows with no cells
 * @csspart legend - the legend
 */
export class CaeStateGrid extends ChartElement {
  static override styles = [
    ...ChartElement.styles,
    css`
      .mark { font-size: 11px; font-weight: 700; fill: var(--text); pointer-events: none; }
      /* a cell that ended well keeps its mark, quietly: the exceptions are what the eye finds */
      .mark.quiet { font-weight: 400; fill: var(--text-muted); }
      .legend .key { display: inline-grid; place-items: center; width: 14px; height: 14px; margin-right: 6px; border-radius: 3px;
        font-size: 9.5px; font-weight: 700; color: var(--text); vertical-align: -2px; }
    `,
  ];

  @property({ attribute: false }) x: readonly string[] = [];
  @property({ attribute: false }) y: readonly string[] = [];
  @property({ attribute: false }) cells: readonly (readonly (StateCell | null)[])[] = [];

  protected hasValues(): boolean {
    return this.x.length > 0 && this.y.length > 0 && this.cells.some((r) => r.some((c) => !!c));
  }

  protected legendItems(): LegendItem[] {
    return statesOf(this.cells).map((s) => ({
      label: s.label,
      icon: html`<span class="key" aria-hidden="true" style="background: ${stateFill(s.tone)}">${stateMark(s.tone)}</span>`,
    }));
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
    const left = Math.max(...this.y.map(textWidth)) + 2;
    const w = this.plotWidth;
    const pw = w - left - M.right;
    const cw = pw / nx;
    const h = M.top + ny * CELL_H + M.bottom;
    const stride = labelStride(nx, pw, Math.max(...this.x.map(textWidth)) + LABEL_GAP);
    const a = this.active;
    const marked = cw - GAP >= MARK_MIN;
    const cells: TemplateResult[] = [];
    for (let r = 0; r < ny; r++)
      for (let c = 0; c < nx; c++) {
        const cell = this.cells[r]?.[c];
        const x = left + c * cw;
        const y = M.top + r * CELL_H;
        const i = r * nx + c;
        const box = { x: x + GAP / 2, y: y + GAP / 2, w: Math.max(1, cw - GAP), h: CELL_H - GAP };
        if (!cell) {
          cells.push(svg`<rect x=${box.x} y=${box.y} width=${box.w} height=${box.h} rx="2" fill="none" stroke="var(--line)"
            @mouseenter=${() => (this.active = i)}></rect>`);
          continue;
        }
        const mark = marked ? stateMark(cell.tone) : '';
        cells.push(svg`<g @mouseenter=${() => (this.active = i)}>
          <rect x=${box.x} y=${box.y} width=${box.w} height=${box.h} rx="2" fill=${stateFill(cell.tone)}
            stroke=${a === i ? 'var(--text)' : 'none'} stroke-width="1.5"></rect>
          ${mark ? svg`<text class=${cell.tone === 'done' ? 'mark quiet' : 'mark'} x=${box.x + box.w / 2} y=${box.y + box.h / 2} dy="0.35em" text-anchor="middle" aria-hidden="true">${mark}</text>` : nothing}
        </g>`);
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
    const cell = this.cells[r]?.[c];
    return html`<b>${this.y[r]} | ${this.x[c]}</b>
      <div class="row">${cell
        ? html`<i style="background: ${stateFill(cell.tone)}"></i><span>${cell.label}</span>`
        : html`<span>${this.words.none}</span>`}</div>
      ${cell?.tip ? html`<div class="row"><span>${cell.tip}</span></div>` : nothing}`;
  }

  protected table(): TemplateResult {
    const none = this.words.none;
    return html`<table aria-label=${this.label || nothing}>
      <thead><tr><th scope="col">${this.words.label}</th>${this.x.map((l) => html`<th scope="col">${l}</th>`)}</tr></thead>
      <tbody>${this.y.map(
        (label, r) => html`<tr><th scope="row">${label}</th>${this.x.map((_, c) => {
          const cell = this.cells[r]?.[c];
          return html`<td title=${cell?.tip || nothing}>${cell ? cell.label : none}</td>`;
        })}</tr>`,
      )}</tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-state-grid': CaeStateGrid;
  }
}
