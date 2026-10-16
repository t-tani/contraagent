// What every chart shares: its width, its words, a legend, the switch to a table of
// its values, and the tooltip of the item the reader points at or moves to.
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { withDefaults } from '../core/strings.js';
import { legend, legendStyles, type LegendItem } from '../primitives/legend.js';
import { base } from '../styles/index.js';
import { plainNumber } from './scale.js';
import { DEFAULT_CHART_STRINGS, type ChartStrings, type ValueText } from './types.js';

/** The size of the axis labels, in px. */
const AXIS_PX = 10.5;
/** The room beside a label, in px, so that labels side by side do not touch. */
const LABEL_ROOM = 6;

let measurer: CanvasRenderingContext2D | null | undefined;
const measured = new Map<string, number>();

/** `text`'s width in px in the CSS font `font`; where there is no canvas to measure it, an estimate. */
function measureText(text: string, font: string): number {
  measurer ??= typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
  if (!measurer) return text.length * AXIS_PX * 0.62;
  const key = `${font}\n${text}`;
  let w = measured.get(key);
  if (w === undefined) {
    measurer.font = font;
    w = measurer.measureText(text).width;
    measured.set(key, w);
  }
  return w;
}

export abstract class ChartElement extends LitElement {
  static override styles = [
    base,
    legendStyles,
    css`
      :host { display: block; min-width: 0; }
      .head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; min-height: 22px; }
      .head .legend { flex: 1; min-width: 0; }
      .head .legend span { color: var(--text-2); }
      .switch { margin-left: auto; flex: none; background: none; border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px;
        font: inherit; font-size: var(--font-size-sm); color: var(--text-muted); cursor: pointer; }
      .switch:hover, .switch:focus-visible { color: var(--text); border-color: var(--line2); }
      .plot { position: relative; outline-offset: 2px; }
      .plot:focus-visible { outline: 2px solid var(--accent); border-radius: var(--radius-sm); }
      svg { display: block; overflow: visible; }
      .axis { font-size: ${AXIS_PX}px; fill: var(--text-muted); font-variant-numeric: tabular-nums; }
      .grid { stroke: var(--line); stroke-width: 1; shape-rendering: crispEdges; }
      .base { stroke: var(--line2); stroke-width: 1; shape-rendering: crispEdges; }
      .hit { fill: transparent; }
      .band { fill: var(--text); opacity: 0.05; }
      .tip { position: absolute; z-index: 2; pointer-events: none; padding: 6px 9px; border-radius: var(--radius-sm); background: var(--raise);
        border: 1px solid var(--line2); box-shadow: 0 4px 14px var(--shadow); color: var(--text); font-size: var(--font-size-sm);
        white-space: nowrap; line-height: 1.45; }
      .tip b { font-weight: 600; }
      .tip .row { display: flex; align-items: center; gap: 6px; }
      .tip .row i { width: 9px; height: 9px; border-radius: 2px; flex: none; }
      .tip .row .v { margin-left: auto; padding-left: 12px; font-variant-numeric: tabular-nums; }
      .scale { display: inline-flex; gap: 1px; margin-right: 6px; vertical-align: -1px; }
      .legend .scale i { width: 12px; height: 10px; margin: 0; border-radius: 2px; }
      .empty { padding: 18px 0; color: var(--text-muted); font-size: var(--font-size-sm); }
      table { border-collapse: collapse; font-size: var(--font-size-sm); font-variant-numeric: tabular-nums; }
      .tbl { overflow-x: auto; max-width: 100%; }
      th, td { padding: 4px 12px 4px 0; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--line); }
      th { color: var(--text-muted); font-weight: 500; }
      th:first-child, td:first-child { text-align: left; }
      td { color: var(--text-2); }
    `,
  ];

  /** The chart's accessible name (its title, or what it shows). */
  @property() label = '';
  /** A value in words: the host's format for the chart's unit. */
  @property({ attribute: false }) format: ValueText = plainNumber;
  @property({ attribute: false }) strings: Partial<ChartStrings> = {};
  /** The plot's height in px (the axis included). */
  @property({ type: Number }) height = 200;

  /** The width the chart has, in px. */
  @state() protected width = 0;
  /** The values shown as a table instead of the chart. */
  @state() protected asTable = false;
  /** The item the reader points at or moved to with the keys; null: none. */
  @state() protected active: number | null = null;

  private resized: ResizeObserver | null = null;

  protected get words(): ChartStrings {
    return withDefaults(DEFAULT_CHART_STRINGS, this.strings);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (typeof ResizeObserver === 'undefined') return;
    this.resized ??= new ResizeObserver((entries) => {
      const w = Math.floor(entries[0]?.contentRect.width ?? 0);
      if (w && Math.abs(w - this.width) >= 1) this.width = w;
    });
    this.resized.observe(this);
    document.fonts?.addEventListener('loadingdone', this.fontsLoaded);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.resized?.disconnect();
    document.fonts?.removeEventListener('loadingdone', this.fontsLoaded);
  }

  /** A font that loads late changes the labels' widths: they are measured again. */
  private readonly fontsLoaded = (): void => {
    measured.clear();
    this.requestUpdate();
  };

  /** An axis label's width in px, as the chart draws it, with room beside it: measured in the chart's font. */
  protected labelWidth(text: string): number {
    const cs = getComputedStyle(this);
    return Math.ceil(measureText(text, `${cs.fontStyle} ${cs.fontWeight} ${AXIS_PX}px ${cs.fontFamily}`)) + LABEL_ROOM;
  }

  protected override firstUpdated(): void {
    if (!this.width) this.width = Math.floor(this.getBoundingClientRect().width) || 600;
  }

  /** The plot area's width: the element's, never less than a narrow screen's. */
  protected get plotWidth(): number {
    return Math.max(240, this.width || 600);
  }

  /** Whether there is anything to draw. */
  protected abstract hasValues(): boolean;
  /** The legend's entries: none for a single series, whose title names it. */
  protected abstract legendItems(): LegendItem[];
  /** How many items the keys move between. */
  protected abstract itemCount(): number;
  /** How many items the up and down keys move by: a row of a grid; 1 for a row of items. */
  protected rowLength(): number {
    return 1;
  }
  protected abstract plot(): TemplateResult;
  protected abstract table(): TemplateResult;

  override render() {
    const s = this.words;
    if (!this.hasValues()) return html`<div class="empty" part="empty">${s.empty}</div>`;
    const items = this.legendItems();
    return html`<div class="head">
        ${items.length ? legend(items, { label: this.label }) : html`<span class="legend"></span>`}
        <button type="button" class="switch" part="switch" aria-pressed=${this.asTable}
          @click=${() => ((this.asTable = !this.asTable), (this.active = null))}>${this.asTable ? s.showChart : s.showTable}</button>
      </div>
      ${this.asTable
        ? html`<div class="tbl" part="table">${this.table()}</div>`
        : html`<div class="plot" part="plot" tabindex=${this.itemCount() ? 0 : nothing} role="group" aria-label=${this.label || nothing}
            @keydown=${this.onKey} @blur=${() => (this.active = null)} @mouseleave=${() => (this.active = null)}>${this.plot()}</div>`}`;
  }

  /** The arrow keys move between the items (up and down by a row of a grid), Home and End to the first and the last; Escape hides the tooltip. */
  private readonly onKey = (e: KeyboardEvent): void => {
    const n = this.itemCount();
    if (!n) return;
    const at = this.active;
    let next: number | null = at;
    const row = this.rowLength();
    const by = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowDown' ? row : e.key === 'ArrowUp' ? -row : 0;
    if (by) next = at === null ? (by > 0 ? 0 : n - 1) : Math.min(n - 1, Math.max(0, at + by));
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = n - 1;
    else if (e.key === 'Escape') next = null;
    else return;
    e.preventDefault();
    this.active = next;
  };

  /** A tooltip at `left` px (its middle) and `top` px of the plot, kept inside it. */
  protected tip(left: number, top: number, body: TemplateResult): TemplateResult {
    const w = this.plotWidth;
    const side = left > w * 0.6 ? 'right' : 'left';
    const x = side === 'left' ? Math.max(0, left + 12) : Math.max(0, w - left + 12);
    return html`<div class="tip" role="status" style="${side}: ${x}px; top: ${Math.max(0, top)}px">${body}</div>`;
  }

  /** One line of a tooltip: a swatch, a name and its value. */
  protected tipRow(colour: string | null, name: string, value: string): TemplateResult {
    return html`<div class="row">${colour ? html`<i style="background: ${colour}"></i>` : nothing}<span>${name}</span><span class="v">${value}</span></div>`;
  }
}
