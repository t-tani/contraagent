import { LitElement, adoptStyles, html, nothing, type CSSResult, type PropertyValues, type TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { Directive, directive, PartType, type ElementPart, type PartInfo } from 'lit/directive.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../core/events.js';
import { withDefaults } from '../core/strings.js';
import { toneAttr, type Tone } from '../core/tone.js';
import { RovingFocusController } from '../primitives/roving-focus.js';
import { rowOffsets, windowRowsAt, type RowWindow } from '../primitives/window.js';
import { base } from '../styles/index.js';
import { dataTableStyles } from './styles.js';
import { DEFAULT_DATA_TABLE_STRINGS, isSortable, type DataColumn, type DataTableStrings, type SortState } from './types.js';

/** Sets the attributes of a map on an element, and removes those it set before that the map no longer has. */
class AttrsDirective extends Directive {
  private names: string[] = [];

  constructor(part: PartInfo) {
    super(part);
    if (part.type !== PartType.ELEMENT) throw new Error('attrs() goes on an element');
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- the argument update() reads
  render(_map: Readonly<Record<string, string>> | undefined) {
    return nothing;
  }

  override update(part: ElementPart, [map]: [Readonly<Record<string, string>> | undefined]) {
    const el = part.element;
    const next = Object.keys(map ?? {});
    for (const n of this.names) if (!next.includes(n)) el.removeAttribute(n);
    for (const n of next) if (el.getAttribute(n) !== map![n]) el.setAttribute(n, map![n]!);
    this.names = next;
    return nothing;
  }
}
const attrs = directive(AttrsDirective);

/** Interactive content inside a cell: a click on it is its own, not the row's. */
const INTERACTIVE = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY', 'LABEL']);

/** The rows drawn before the first measure of the viewport. */
const FIRST_ROWS = 60;

/**
 * A table of rows, one per item, in a real `<table>`: a header cell per column
 * (`scope="col"`), the first `rowHeader` column as the row's header. The rows
 * are one tab stop: the arrow keys, Home and End move between them, and Enter or
 * a click is the row's primary action (`cae-activate`), or chooses it as the
 * selection when the table is not `activatable` (`cae-select`). A sortable
 * header sends `cae-sort`; the host orders the rows (`sortRows`) and sets them.
 * Above `windowAt` rows, only the rows on screen are drawn, and a spacer stands
 * for the others: as high as those rows were when drawn, or, for a row not drawn
 * yet, as the rows drawn are on average. Rows may differ in height.
 *
 * Its look: `--cae-data-table-gap` (between the columns), `--cae-data-table-row-padding`,
 * the parts, and `cellStyles` (styles for what the cells draw, added to the
 * table's own).
 *
 * @tagname cae-data-table
 * @fires cae-activate - `{id}`: a row's primary action (a click or Enter, when `activatable`)
 * @fires cae-select - `{id}`: a row chosen as the selection (a click or Enter, when not `activatable`)
 * @fires cae-sort - `{id, direction}`: a sortable header was clicked
 * @csspart table - the `<table>`
 * @csspart caption - the caption
 * @csspart head - the header row's group
 * @csspart header-cell - each header cell
 * @csspart row - each row
 * @csspart row-selected - the selected row
 * @csspart cell - each cell
 * @csspart empty - the cell that stands for no rows
 * @slot caption - the caption, instead of `caption`
 * @slot empty - what the table shows with no rows, instead of `strings.empty`
 */
export class CaeDataTable<R = unknown> extends LitElement {
  static override styles = [base, dataTableStyles];

  @property({ attribute: false }) columns: readonly DataColumn<R>[] = [];
  @property({ attribute: false }) rows: readonly R[] = [];
  /** A row's id: unique among the rows (`data-key`, the `id` of the events). By default its `id`. */
  @property({ attribute: false }) rowKey: (row: R) => string = (row) => {
    const id = (row as { id?: unknown }).id;
    return typeof id === 'string' || typeof id === 'number' ? String(id) : '';
  };
  /** A row's tone (`data-tone` on the row). */
  @property({ attribute: false }) rowTone?: (row: R) => Tone | undefined;
  /** More attributes on a row (`data-*`), for the host's styles and tests. */
  @property({ attribute: false }) rowAttrs?: (row: R) => Readonly<Record<string, string>>;
  /** A click or Enter on a row is its primary action (`cae-activate`); otherwise it selects the row (`cae-select`). */
  @property({ type: Boolean }) activatable = true;
  /** The id of the selected row. */
  @property() selected: string | null = null;
  /** The column the rows are ordered by: shown in its header (`aria-sort`). The host orders the rows. */
  @property({ attribute: false }) sort: SortState | null = null;
  /** Above this many rows, only the rows on screen are drawn. */
  @property({ type: Number }) windowAt = 200;
  /** A row's height in px, until rows are measured. */
  @property({ type: Number }) rowHeight = 32;
  /** The table's caption (its accessible name). */
  @property() caption = '';
  @property({ attribute: false }) strings: Partial<DataTableStrings> = {};
  /** Styles for what the cells draw, added after the table's own (the rows are `tr`, the cells `th` and `td`). */
  @property({ attribute: false }) cellStyles: readonly CSSResult[] = [];

  /** The rows drawn, when windowed. */
  @state() private range: { from: number; to: number } = { from: 0, to: FIRST_ROWS };
  /** Each drawn row's height, by its key: what stands for it while it is not drawn. */
  private heights = new Map<string, number>();
  /** Where each row starts (`rowOffsets`), for the rows as they are; null: to work out again. */
  private offsets: number[] | null = null;
  /** The row that holds the tab stop. */
  private focusKey: string | null = null;
  private scroller: HTMLElement | Window | null = null;
  private resized: ResizeObserver | null = null;
  private frame = 0;
  /** The next update keeps `range` as set (Home and End set it before the scroller reports). */
  private held = false;

  private readonly roving = new RovingFocusController(this, {
    items: () => [...this.renderRoot.querySelectorAll<HTMLElement>('tbody tr[data-key]')],
    layout: 'vertical',
    onMove: (el) => (this.focusKey = el.dataset['key'] ?? null),
  });

  private get windowed(): boolean {
    return this.rows.length > this.windowAt;
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unwatch();
  }

  /** Where each row starts: its measured height, else the drawn rows' average. */
  private rowStarts(): number[] {
    if (this.offsets) return this.offsets;
    let sum = 0;
    for (const h of this.heights.values()) sum += h;
    const typical = this.heights.size ? sum / this.heights.size : this.rowHeight;
    return (this.offsets = rowOffsets(this.rows.length, (i) => this.heights.get(this.rowKey(this.rows[i]!)) ?? typical));
  }

  /** The rows on screen, from where the table's body is in its scroller. */
  private visible(): RowWindow {
    const starts = this.rowStarts();
    const body = this.renderRoot.querySelector('tbody');
    // Before the first measure of the view: the first rows, about FIRST_ROWS of them.
    if (!body || !this.scroller) return windowRowsAt(starts, 0, (starts.at(-1)! / Math.max(1, this.rows.length)) * FIRST_ROWS, 0);
    const view =
      this.scroller instanceof HTMLElement
        ? { top: this.scroller.getBoundingClientRect().top, height: this.scroller.clientHeight }
        : { top: 0, height: this.scroller.innerHeight };
    return windowRowsAt(starts, view.top - body.getBoundingClientRect().top, view.height);
  }

  /** Scrolls the body's first row (or its last, `last`) into the scroller's view. */
  private scrollToEnd(last: boolean): void {
    const body = this.renderRoot.querySelector('tbody');
    const s = this.scroller;
    if (!body || !s) return;
    const r = body.getBoundingClientRect();
    const view = s instanceof HTMLElement ? s.getBoundingClientRect() : { top: 0, bottom: s.innerHeight };
    const by = last ? r.bottom - view.bottom : r.top - view.top;
    if (s instanceof HTMLElement) s.scrollTop += by;
    else s.scrollBy(0, by);
  }

  private reframe(): void {
    const w = this.visible();
    if (w.from !== this.range.from || w.to !== this.range.to) this.range = { from: w.from, to: w.to };
  }

  private readonly onScroll = (): void => {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.reframe();
    });
  };

  /** The nearest ancestor that scrolls the table vertically, across shadow roots; the window when none does. */
  private findScroller(): HTMLElement | Window {
    let n: Node | null = this.parentNode;
    while (n) {
      if (n instanceof HTMLElement) {
        const o = getComputedStyle(n).overflowY;
        if ((o === 'auto' || o === 'scroll' || o === 'overlay') && n.scrollHeight > n.clientHeight + 1) return n;
      }
      n = n instanceof ShadowRoot ? n.host : n.parentNode;
    }
    return window;
  }

  private watch(): void {
    if (this.scroller) return;
    this.scroller = this.findScroller();
    this.scroller.addEventListener('scroll', this.onScroll, { passive: true });
    // Its height decides how many rows show: the window's when the page scrolls, else the scroller's own.
    if (!(this.scroller instanceof HTMLElement)) window.addEventListener('resize', this.onScroll, { passive: true });
    else if (typeof ResizeObserver !== 'undefined') (this.resized ??= new ResizeObserver(this.onScroll)).observe(this.scroller);
  }

  private unwatch(): void {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.scroller?.removeEventListener('scroll', this.onScroll);
    window.removeEventListener('resize', this.onScroll);
    this.resized?.disconnect();
    this.scroller = null;
  }

  override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('rows') || changed.has('rowHeight')) this.offsets = null;
    if (changed.has('rows') || changed.has('windowAt')) {
      if (this.windowed && this.hasUpdated) {
        const w = this.visible();
        this.range = { from: w.from, to: w.to };
      } else if (!this.windowed) this.unwatch();
    }
    // The tab stop stays on its row while the rows drawn change.
    const keys = this.shown().map(this.rowKey);
    const i = this.focusKey === null ? -1 : keys.indexOf(this.focusKey);
    this.roving.current = Math.max(0, i);
  }

  override updated(changed: PropertyValues<this>): void {
    if (changed.has('cellStyles') && this.renderRoot instanceof ShadowRoot)
      adoptStyles(this.renderRoot, [...(this.constructor as typeof LitElement).elementStyles, ...this.cellStyles]);
    if (!this.windowed) return;
    this.watch();
    // Measure the drawn rows: each stands for itself while it is not drawn. A row keeps its
    // height, so the spacers settle as the rows are drawn once each.
    let moved = false;
    for (const tr of this.renderRoot.querySelectorAll<HTMLElement>('tbody tr[data-key]')) {
      const h = tr.getBoundingClientRect().height;
      const key = tr.dataset['key']!;
      if (h > 0 && Math.abs(h - (this.heights.get(key) ?? -1)) > 0.5) {
        this.heights.set(key, h);
        moved = true;
      }
    }
    if (moved) this.offsets = null;
    if (this.held) this.held = false;
    // On the next frame, never in this update: a window that changes the measures and so
    // the window again then gives the page a frame, and the reader's input, each time.
    else this.onScroll();
  }

  /** The rows drawn now. */
  private shown(): readonly R[] {
    if (!this.windowed) return this.rows;
    return this.rows.slice(this.range.from, Math.min(this.rows.length, this.range.to));
  }

  /** The row of an event, and its id. */
  private rowOf(e: Event): { tr: HTMLElement; id: string } | null {
    for (const t of e.composedPath()) {
      if (!(t instanceof HTMLElement)) continue;
      if (INTERACTIVE.has(t.tagName)) return null;
      if (t.tagName === 'TR' && t.dataset['key'] !== undefined) return { tr: t, id: t.dataset['key'] };
      if (t === this) break;
    }
    return null;
  }

  private act(id: string): void {
    if (this.activatable) {
      emit(this, 'cae-activate', { id });
      return;
    }
    this.selected = id;
    emit(this, 'cae-select', { id });
  }

  private readonly onClick = (e: MouseEvent): void => {
    const r = this.rowOf(e);
    if (r) this.act(r.id);
  };

  private readonly onFocusIn = (e: FocusEvent): void => {
    const r = this.rowOf(e);
    if (r) this.focusKey = r.id;
  };

  private readonly onKey = (e: KeyboardEvent): void => {
    const t = e.composedPath()[0];
    if (!(t instanceof HTMLElement) || t.tagName !== 'TR' || t.dataset['key'] === undefined) return;
    if (e.key === 'Enter') {
      e.preventDefault();
      this.act(t.dataset['key']);
      return;
    }
    // Windowed, the first and last rows may not be drawn: draw them, then move there.
    if (this.windowed && (e.key === 'Home' || e.key === 'End')) {
      e.preventDefault();
      e.stopPropagation();
      const last = e.key === 'End';
      const row = this.rows[last ? this.rows.length - 1 : 0];
      if (row === undefined) return;
      this.focusKey = this.rowKey(row);
      const n = this.rows.length;
      const span = Math.max(1, this.range.to - this.range.from);
      this.scrollToEnd(last);
      // Drawn at once, before the scroll reports where the view is.
      this.range = last ? { from: Math.max(0, n - span), to: n } : { from: 0, to: span };
      this.held = true;
      void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(`tbody tr[data-key="${CSS.escape(this.focusKey ?? '')}"]`)?.focus());
    }
  };

  private header(c: DataColumn<R>, s: DataTableStrings): TemplateResult {
    const on = this.sort?.id === c.id ? this.sort.direction : null;
    const sort = on === 'asc' ? 'ascending' : on === 'desc' ? 'descending' : nothing;
    const label = isSortable(c)
      ? html`<button type="button" class="sort" title=${on === 'asc' ? s.sortDescending : s.sortAscending}
          @click=${() => emit(this, 'cae-sort', { id: c.id, direction: on === 'asc' ? 'desc' : 'asc' })}>${c.header}${on
            ? html`<span class="arrow" aria-hidden="true">${on === 'asc' ? '▲' : '▼'}</span>`
            : nothing}</button>`
      : c.header;
    return html`<th scope="col" role="columnheader" part="header-cell" data-col=${c.id} data-align=${c.align ?? nothing} aria-sort=${sort}
      title=${c.tip || nothing}>${label}</th>`;
  }

  private row(r: R, index: number, head: string | undefined): TemplateResult {
    const id = this.rowKey(r);
    const sel = this.selected !== null && this.selected === id;
    return html`<tr role="row" part=${sel ? 'row row-selected' : 'row'} data-key=${id} data-tone=${toneAttr(this.rowTone?.(r))}
      aria-current=${sel ? 'true' : nothing} aria-rowindex=${this.windowed ? index + 2 : nothing} ${attrs(this.rowAttrs?.(r))}>
      ${this.columns.map((c) =>
        c.id === head
          ? html`<th scope="row" role="rowheader" part="cell" data-col=${c.id} data-align=${c.align ?? nothing}>${c.cell(r, index)}</th>`
          : html`<td role="cell" part="cell" data-col=${c.id} data-align=${c.align ?? nothing}>${c.cell(r, index)}</td>`,
      )}
    </tr>`;
  }

  override render() {
    const s = withDefaults(DEFAULT_DATA_TABLE_STRINGS, this.strings);
    const n = this.rows.length;
    const tracks = this.columns.map((c) => c.width ?? 'minmax(0, 1fr)').join(' ');
    const head = this.columns.find((c) => c.rowHeader)?.id;
    const from = this.windowed ? this.range.from : 0;
    const shown = this.shown();
    const starts = this.windowed ? this.rowStarts() : null;
    const padTop = starts ? starts[from]! : 0;
    const padBottom = starts ? starts[n]! - starts[from + shown.length]! : 0;
    return html`<table part="table" data-scroll="x" role="table" class=${this.activatable ? '' : 'passive'} style="--cae-data-table-columns: ${tracks}"
      aria-rowcount=${this.windowed ? n + 1 : nothing}>
      <caption part="caption"><slot name="caption">${this.caption}</slot></caption>
      <thead part="head" role="rowgroup"><tr role="row">${this.columns.map((c) => this.header(c, s))}</tr></thead>
      <tbody role="rowgroup" @click=${this.onClick} @keydown=${this.onKey} @focusin=${this.onFocusIn}>
        ${padTop > 0 ? html`<tr class="spacer" aria-hidden="true" style="height: ${padTop}px"></tr>` : nothing}
        ${repeat(shown, this.rowKey, (r, i) => this.row(r, from + i, head))}
        ${padBottom > 0 ? html`<tr class="spacer" aria-hidden="true" style="height: ${padBottom}px"></tr>` : nothing}
        ${n
          ? nothing
          : html`<tr class="empty" role="row"><td part="empty" role="cell" colspan=${this.columns.length || 1}><slot name="empty">${s.empty}</slot></td></tr>`}
      </tbody>
    </table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-data-table': CaeDataTable;
  }
}
