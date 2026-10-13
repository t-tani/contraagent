// A mark matrix: a row per series, a column per item, nested groups of columns
// above them; only the rows in view above `windowAt` rows.
import { LitElement, adoptStyles, html, nothing, type CSSResult, type PropertyValues } from 'lit';
import { property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../core/events.js';
import { withDefaults } from '../core/strings.js';
import { toneAttr } from '../core/tone.js';
import { icon } from '../primitives/icon.js';
import type { StateStyles } from '../primitives/states.js';
import { base, markStyles } from '../styles/index.js';
import { gridStep } from './grid-step.js';
import { ROW_H, matrixStyles } from './styles.js';
import { DEFAULT_MARK_MATRIX_STRINGS, type MarkMatrixInput, type MarkMatrixStrings, type MatrixHeadCell, type MatrixMark, type MatrixRowInput } from './types.js';

/** The rows drawn around those in view, when windowed. */
const OVERSCAN = 30;

const EMPTY: MarkMatrixInput = { caption: '', label: '', head: [], columns: [], rows: [] };

/**
 * A table of marks: a row per series (its label, then a value), a column per item,
 * the columns under nested groups (a border where a group starts). A mark is
 * drawn in its state's look (`states`). A click selects a mark (`cae-select`);
 * a double click or Enter is its action (`cae-activate`, or `cae-drill` for a mark
 * with an inner view). The arrow keys, Home, End, Page Up and Page Down move
 * between the marks (Ctrl with Home and End: the first and the last row). The
 * hovered, focused or selected mark's row is highlighted, else `highlight`'s. The
 * host sorts the rows: the sort control sends `cae-sort`. Above `windowAt` rows,
 * only the rows in view are drawn.
 *
 * @tagname cae-mark-matrix
 * @fires cae-select - `{id}`: a mark was clicked or focused
 * @fires cae-activate - `{id}`: a mark's action (a double click or Enter)
 * @fires cae-drill - `{id}`: a mark's inner view (a double click or Enter on a mark with `drill`)
 * @fires cae-sort - `{id, direction: 'asc'}`: an order was chosen
 * @csspart matrix - the `<table>`
 * @csspart head-cell - each header cell
 * @csspart row-header - each row's label
 * @csspart mark - each mark
 * @csspart sort - the sort control
 */
export class CaeMarkMatrix extends LitElement {
  static override styles = [base, markStyles, matrixStyles];

  @property({ attribute: false }) matrix: MarkMatrixInput = EMPTY;
  @property({ attribute: false }) states: StateStyles = {};
  /** The selected mark's id, or null. */
  @property({ attribute: false }) selected: string | null = null;
  /** The row highlighted while no mark is hovered, focused or selected. */
  @property({ attribute: false }) highlight: string | null = null;
  /** The matrix's identity: a new key is a new matrix (the scroll and the focused mark start over). */
  @property() key = '';
  /** Above this many rows, only the rows in view are drawn. */
  @property({ type: Number }) windowAt = 150;
  @property({ attribute: false }) strings: Partial<MarkMatrixStrings> = {};
  /** Draws an icon of a header cell; default: `icon(name)`. */
  @property({ attribute: false }) renderIcon: (name: string) => unknown = (name) => icon(name);
  /** Styles for what `renderIcon` draws, added to the element's own. */
  @property({ attribute: false }) iconStyles: readonly CSSResult[] = [];

  /** The row (or a mark without one) under the pointer or focus. */
  @state() private hover: string | null = null;
  /** The first row in view, and the focused cell (row, column). */
  @state() private scrollRow = 0;
  private cell: [number, number] | null = null;

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has('key') && changed.get('key') !== undefined) {
      this.scrollRow = 0;
      this.cell = null;
    }
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has('iconStyles') && this.renderRoot instanceof ShadowRoot)
      adoptStyles(this.renderRoot, [...(this.constructor as typeof LitElement).elementStyles, ...this.iconStyles]);
  }

  /** The highlighted row: the one hovered or focused, else the selected mark's, else `highlight`. */
  private lit(): string | null {
    if (this.hover !== null) return this.hover;
    const row = this.selected ? this.matrix.rows.find((r) => r.cells.some((m) => m?.id === this.selected)) : undefined;
    return row ? row.id || this.selected : this.highlight;
  }

  private select(id: string): void {
    if (id !== this.selected) emit(this, 'cae-select', { id });
  }

  private act(m: MatrixMark): void {
    if (m.drill) emit(this, 'cae-drill', { id: m.id });
    else emit(this, 'cae-activate', { id: m.id });
  }

  override render() {
    const mx = this.matrix;
    const w = withDefaults(DEFAULT_MARK_MATRIX_STRINGS, this.strings);
    const rows = mx.rows;
    const cols = mx.columns;
    const hl = this.lit();
    // Where a group of columns starts: 0 at an outermost group, 1 at a group in it, ...
    const starts = cols.map((c, i) => {
      const p = cols[i - 1]?.groups;
      if (!p) return -1;
      const k = c.groups.findIndex((x, j) => x !== p[j]);
      return k < 0 ? (c.groups.length !== p.length ? Math.min(c.groups.length, p.length) : -1) : k;
    });
    const groupCls = (ci: number) => (starts[ci] === 0 ? 'g0' : (starts[ci] ?? -1) > 0 ? 'g1' : '');
    const headRows = mx.head.length;
    const value = !!mx.value;
    const lead = value ? 2 : 1;
    // The rows in view (all of them up to `windowAt`).
    const many = rows.length > this.windowAt;
    const from = many ? Math.max(0, this.scrollRow - OVERSCAN) : 0;
    const to = many ? Math.min(rows.length, this.scrollRow + 2 * OVERSCAN + 20) : rows.length;
    const cur = this.cell && this.cell[0] < rows.length ? this.cell : firstCell(rows);
    // A header cell's class: where a group of columns starts.
    const headCls = (col: number) => (col === 0 || starts[col] === 0 ? 'g0' : (starts[col] ?? -1) > 0 ? 'g1' : '');
    const headCell = (hd: MatrixHeadCell, col: number, level: number) => {
      const style = `top:${level * 22}px`;
      if (hd.type === 'group')
        return html`<th scope="colgroup" part="head-cell" colspan=${hd.span} class="group ${hd.code ? 'code' : ''} ${headCls(col)}" style=${style}
          title=${hd.tip ?? nothing} aria-label=${hd.summary ?? nothing}>${hd.label}</th>`;
      return html`<th scope="col" part="head-cell" rowspan=${hd.rows} class="nh ${headCls(col)}" style=${style}
        title=${hd.tip ?? nothing} aria-label=${hd.summary ?? nothing}>${(hd.icons ?? []).map((n) => this.renderIcon(n))}${hd.label}</th>`;
    };
    // The column each cell of a header row starts at: a cell under one that spans down starts after it.
    const firstCols = (level: number) => {
      const out: number[] = [];
      let c = 0;
      for (const hd of mx.head[level] ?? []) {
        while (spannedAt(mx.head, level, c)) c++;
        out.push(c);
        c += hd.span;
      }
      return out;
    };
    const facts = (mx.facts ?? []).filter((f) => (typeof f === 'string' ? f : f.text));
    return html`<div class="mxblock view">
      <div class="mxbar">
        <span class="cap" title=${mx.captionTip ?? nothing}>${mx.caption}</span>
        ${mx.sorts?.length
          ? html`<label>${w.sortBy}
              <select part="sort" @change=${(e: Event) => emit(this, 'cae-sort', { id: (e.target as HTMLSelectElement).value, direction: 'asc' })}>
                ${mx.sorts.map((s) => html`<option value=${s.id} ?selected=${mx.sort === s.id}>${s.label}</option>`)}
              </select>
            </label>`
          : nothing}
        <span class="sum">${facts.map(
          (f, i) =>
            html`${i ? html`<span class="sep"> | </span>` : nothing}${typeof f === 'string'
              ? html`<span class="f">${f}</span>`
              : html`<span class="f tone-text" data-tone=${toneAttr(f.tone)}>${f.text}</span>`}`,
        )}</span>
      </div>
      <div class="mx ${hl ? 'hl' : ''}" @scroll=${this.onScroll} @mouseleave=${() => (this.hover = null)}>
        <table class="matrix big" part="matrix" role="grid" aria-rowcount=${rows.length + headRows} aria-colcount=${cols.length + lead} aria-label=${mx.label}>
          <thead>
            ${mx.head.map((hr, level) => {
              const fc = firstCols(level);
              return html`<tr>
                ${level === 0
                  ? html`<th scope="col" rowspan=${headRows} class="uh" style="top:0">${w.rowsHeader}</th>
                      ${value ? html`<th scope="col" rowspan=${headRows} class="pn" style="top:0" title=${mx.value?.tip ?? nothing}>${mx.value?.label}</th>` : nothing}`
                  : nothing}
                ${hr.map((hd, i) => headCell(hd, fc[i] ?? 0, level))}
              </tr>`;
            })}
          </thead>
          <tbody @keydown=${(e: KeyboardEvent) => this.onKey(e, rows)}>
            ${from > 0 ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + lead} style="height:${from * ROW_H}px"></td></tr>` : nothing}
            ${repeat(
              rows.slice(from, to),
              (r) => r.id,
              (r, k) => {
                const ri = from + k;
                return html`<tr class=${r.id && r.id === hl ? 'on' : ''} aria-rowindex=${ri + headRows + 1}>
                  <th scope="row" part="row-header" class=${r.muted ? 'none' : nothing} title=${r.tip ?? r.label}>${r.label}</th>
                  ${value ? html`<td class="pn ${r.strong ? 'many' : ''}">${r.value}</td>` : nothing}
                  ${r.cells.map((m, ci) => {
                    const focusable = !!m && cur !== null && cur[0] === ri && cur[1] === ci;
                    return html`<td class="c ${groupCls(ci)}" role="gridcell">${m ? this.mark(r, m, ri, ci, focusable, hl) : nothing}</td>`;
                  })}
                </tr>`;
              },
            )}
            ${to < rows.length
              ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + lead} style="height:${(rows.length - to) * ROW_H}px"></td></tr>`
              : nothing}
          </tbody>
        </table>
      </div>
    </div>`;
  }

  private mark(r: MatrixRowInput, m: MatrixMark, ri: number, ci: number, tabStop: boolean, hl: string | null) {
    const look = this.states[m.state];
    const hlKey = r.id || m.id;
    const sel = this.selected === m.id;
    return html`<button type="button" part="mark" class="mark ${r.id && r.id === hl ? 'on' : ''} ${sel ? 'sel' : ''}"
      data-tone=${toneAttr(look?.tone)} data-shape=${look?.shape ?? nothing} data-r=${ri} data-c=${ci} tabindex=${tabStop ? 0 : -1}
      title=${m.tip ?? nothing} aria-label=${m.label} aria-pressed=${sel}
      @mouseenter=${() => (this.hover = hlKey)}
      @focus=${() => {
        this.hover = hlKey;
        this.cell = [ri, ci];
        this.select(m.id);
      }}
      @blur=${() => (this.hover = null)}
      @click=${() => this.select(m.id)}
      @dblclick=${() => this.act(m)}></button>`;
  }

  private readonly onScroll = (e: Event): void => {
    const top = Math.floor((e.currentTarget as HTMLElement).scrollTop / ROW_H);
    if (Math.abs(top - this.scrollRow) >= OVERSCAN / 2) this.scrollRow = top;
  };

  private onKey(e: KeyboardEvent, rows: readonly MatrixRowInput[]): void {
    const t = e.target as HTMLElement;
    if (!t.classList.contains('mark')) return;
    const r = Number(t.dataset['r']);
    const c = Number(t.dataset['c']);
    if (e.key === 'Enter') {
      const m = rows[r]?.cells[c];
      e.preventDefault();
      if (m) this.act(m);
      return;
    }
    const has = rows.map((row) => row.cells.map((x) => x !== null));
    const next = gridStep(has, r, c, e.key, e.ctrlKey || e.metaKey);
    if (!next) return;
    e.preventDefault();
    this.cell = next;
    const box = this.renderRoot.querySelector<HTMLElement>('.mx');
    if (box && rows.length > this.windowAt) {
      // Bring the row into view first: only the rows in view are drawn.
      const y = next[0] * ROW_H;
      if (y < box.scrollTop + ROW_H * 2 || y > box.scrollTop + box.clientHeight - ROW_H * 3) box.scrollTop = Math.max(0, y - box.clientHeight / 2);
      this.scrollRow = Math.floor(box.scrollTop / ROW_H);
    }
    this.requestUpdate();
    void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(`.matrix .mark[data-r="${next[0]}"][data-c="${next[1]}"]`)?.focus());
  }
}

/** The first mark of the rows, as (row, column). */
function firstCell(rows: readonly MatrixRowInput[]): [number, number] | null {
  for (let i = 0; i < rows.length; i++) {
    const j = rows[i]?.cells.findIndex((c) => c !== null) ?? -1;
    if (j >= 0) return [i, j];
  }
  return null;
}

/** A header row's column `c` is under a cell of an earlier row that spans down past it. */
function spannedAt(head: readonly (readonly MatrixHeadCell[])[], level: number, c: number): boolean {
  for (let l = 0; l < level; l++) {
    let x = 0;
    for (const hd of head[l] ?? []) {
      if (c >= x && c < x + hd.span && l + hd.rows > level) return true;
      x += hd.span;
    }
  }
  return false;
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-mark-matrix': CaeMarkMatrix;
  }
}
