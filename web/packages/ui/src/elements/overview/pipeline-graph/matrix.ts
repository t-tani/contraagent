// A loop's passes: a row per unit, a column per node and pass, the nested loops'
// passes as nested groups of columns; only the rows in view above `WINDOW_AT` rows.
import { msg, str } from '@lit/localize';
import { html, nothing } from 'lit';
import { repeat } from 'lit/directives/repeat.js';
import { executorIcon } from '../../../words/executor.js';
import { facts, listText } from '../../../words/format.js';
import { loopLabel, passCount, passLabel, passSpread } from '../../../words/index.js';
import { sortRows, type MatrixHead, type MatrixRow, type MatrixSort, type PassMatrix } from '../graph/matrix.js';
import { gridStep } from '../graph/nav.js';
import { markSel } from '../graph/selection.js';
import type { GraphMark, GraphNode } from '../graph/types.js';
import { focusSelect, open, select } from './actions.js';
import { OVERSCAN, ROW_H, WINDOW_AT, causeOf, highlighted, type GraphHost } from './host.js';
import { executorWord, markText, where } from './words.js';

export function matrixView(h: GraphHost, mx: PassMatrix) {
  const rows = sortRows(mx.rows, h.sort);
  const cols = mx.columns;
  const hl = highlighted(h);
  // Where a group of columns starts: 0 at a pass of the loop shown, 1 at a pass of a loop in it, ...
  const starts = cols.map((c, i) => {
    const p = cols[i - 1]?.passes;
    if (!p) return -1;
    const k = c.passes.findIndex((x, j) => x !== p[j]);
    return k < 0 ? (c.passes.length !== p.length ? Math.min(c.passes.length, p.length) : -1) : k;
  });
  const groupCls = (ci: number) => (starts[ci] === 0 ? 'g0' : (starts[ci] ?? -1) > 0 ? 'g1' : '');
  const headRows = mx.head.length;
  // The rows in view (all of them up to `WINDOW_AT`).
  const many = rows.length > WINDOW_AT;
  const from = many ? Math.max(0, h.scrollRow - OVERSCAN) : 0;
  const to = many ? Math.min(rows.length, h.scrollRow + 2 * OVERSCAN + 20) : rows.length;
  const cur = h.cell && h.cell[0] < rows.length ? h.cell : firstCell(rows);
  const units = mx.rows.filter((r) => r.unit).length;
  // A header cell's class: where a group of columns starts.
  const headCls = (col: number) => (col === 0 || starts[col] === 0 ? 'g0' : (starts[col] ?? -1) > 0 ? 'g1' : '');
  const headCell = (hd: MatrixHead, col: number, level: number) => {
    const style = `top:${level * 22}px`;
    if (hd.type === 'pass')
      return html`<th scope="colgroup" colspan=${hd.span} class="pass ${headCls(col)}" style=${style}
        title=${hd.box.id === mx.box.id ? msg(str`Loop at ${where(hd.box.loop, hd.box.file)}`) : msg(str`Nested loop at ${where(hd.box.loop, hd.box.file)}`)}>${passLabel(hd.pass)}</th>`;
    if (hd.type === 'loop')
      return html`<th scope="colgroup" colspan=${hd.span} class="loop ${headCls(col)}" style=${style}
        title=${msg(str`Nested loop at ${where(hd.box.loop, hd.box.file)}`)}>${loopLabel()}</th>`;
    return html`<th scope="col" rowspan=${hd.rows} class="nh ${headCls(col)}" style=${style}
      title=${hd.node.type === 'flow' ? msg(str`Function ${hd.node.name}`) : facts(hd.node.label, executorWord(hd.node))}
      aria-label=${hd.node.type === 'flow' ? hd.node.label : facts(hd.node.label, executorWord(hd.node))}>${hd.node.executor && hd.node.executor !== 'mixed'
        ? executorIcon(hd.node.executor === 'python')
        : nothing}${hd.node.label}</th>`;
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
  const summary = [
    passCount(mx.box.passes),
    mx.box.spread.length > 1 ? passSpread(mx.box.spread) : '',
    units === 1 ? msg('1 unit') : msg(str`${units} units`),
  ].filter(Boolean);
  // In the graph's frame, at least as tall as the graph was (and as the card needs), the passes centred in it.
  const least = h.down ? 0 : Math.round(Math.max(h.pz.frameH, h.card.room));
  return html`<div class="frame mxframe" style=${least ? `min-height:${least}px` : ''}><div class="mxblock view">
    <div class="mxbar">
      <span class="cap" title=${mx.box.file ? `${mx.box.file}:${mx.box.loop}` : nothing}>${msg(str`Loop at ${where(mx.box.loop, mx.box.file)}`)}</span>
      <label>${msg('Sort units')}
        <select @change=${(e: Event) => (h.sort = (e.target as HTMLSelectElement).value as MatrixSort)}>
          <option value="order" ?selected=${h.sort === 'order'}>${msg('Scheduled order')}</option>
          <option value="passes" ?selected=${h.sort === 'passes'}>${msg('Number of passes')}</option>
          <option value="state" ?selected=${h.sort === 'state'}>${msg('Status', { id: 'status', desc: 'The status of a task: done, failed, not started' })}</option>
        </select>
      </label>
      <span class="sum">${summary.map((t, i) => html`${i ? html`<span class="sep"> | </span>` : nothing}<span class="f">${t}</span>`)}</span>
    </div>
    <div class="mx ${hl ? 'hl' : ''}" @scroll=${(e: Event) => onMatrixScroll(h, e)} @mouseleave=${() => (h.hover = null)}>
      <table class="matrix big" role="grid" aria-rowcount=${rows.length + headRows} aria-colcount=${cols.length + 2}
        aria-label=${facts(msg(str`Loop at ${where(mx.box.loop, mx.box.file)}`), passCount(mx.box.passes))}>
        <thead>
          ${mx.head.map((hr, level) => {
            const fc = firstCols(level);
            return html`<tr>
              ${level === 0
                ? html`<th scope="col" rowspan=${headRows} class="uh" style="top:0">${msg('Unit')}</th>
                    <th scope="col" rowspan=${headRows} class="pn" style="top:0" title=${msg('Passes of this loop')}>${msg('Passes')}</th>`
                : nothing}
              ${hr.map((hd, i) => headCell(hd, fc[i] ?? 0, level))}
            </tr>`;
          })}
        </thead>
        <tbody @keydown=${(e: KeyboardEvent) => onMatrixKey(h, e, rows)}>
          ${from > 0 ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + 2} style="height:${from * ROW_H}px"></td></tr>` : nothing}
          ${repeat(
            rows.slice(from, to),
            (r) => r.unit,
            (r, k) => {
              const ri = from + k;
              return html`<tr class=${r.unit && r.unit === hl ? 'on' : ''} aria-rowindex=${ri + headRows + 1}>
                ${r.unit
                  ? html`<th scope="row" title=${r.unit}>${r.unit}</th>`
                  : html`<th scope="row" class="none" title=${msg('Tasks that run once per run, not once per unit')}>${msg('No unit')}</th>`}
                <td class="pn ${r.passes > 1 ? 'many' : ''}">${r.passes}</td>
                ${r.cells.map((m, ci) => {
                  const col = cols[ci];
                  const focusable = !!m && cur !== null && cur[0] === ri && cur[1] === ci;
                  return html`<td class="c ${groupCls(ci)}" role="gridcell">${m && col ? cellMark(h, r, m, ri, ci, col.node, col.passes, focusable) : nothing}</td>`;
                })}
              </tr>`;
            },
          )}
          ${to < rows.length ? html`<tr class="gap" aria-hidden="true"><td colspan=${cols.length + 2} style="height:${(rows.length - to) * ROW_H}px"></td></tr>` : nothing}
        </tbody>
      </table>
    </div>
  </div></div>`;
}

function cellMark(h: GraphHost, r: MatrixRow, m: GraphMark, ri: number, ci: number, node: GraphNode, passes: number[], tabStop: boolean) {
  const { name, parts } = markText(node.label, m, { task: h.links.byKey.get(m.key), causeOf: (k) => causeOf(h, k), live: h.live }, listText(passes.map(passLabel)));
  const hlKey = m.unit || m.key;
  const id = markSel(node.id, m, passes);
  const sel = h.sel === id;
  return html`<button type="button" class="mark ${m.state} ${r.unit && r.unit === highlighted(h) ? 'on' : ''} ${sel ? 'sel' : ''}" data-r=${ri} data-c=${ci} tabindex=${tabStop ? 0 : -1}
    title=${[name, parts[0] ?? ''].filter(Boolean).join('\n')} aria-label=${facts(name, ...parts)} aria-pressed=${sel}
    @mouseenter=${() => (h.hover = hlKey)}
    @focus=${() => {
      h.hover = hlKey;
      h.cell = [ri, ci];
      focusSelect(h, id);
    }}
    @blur=${() => (h.hover = null)}
    @click=${() => select(h, id)}
    @dblclick=${() => open(h, m)}></button>`;
}

/** The first mark of the sorted rows, as (row, column). */
function firstCell(rows: readonly MatrixRow[]): [number, number] | null {
  for (let i = 0; i < rows.length; i++) {
    const j = rows[i]?.cells.findIndex((c) => c !== null) ?? -1;
    if (j >= 0) return [i, j];
  }
  return null;
}

function onMatrixScroll(h: GraphHost, e: Event): void {
  const top = Math.floor((e.currentTarget as HTMLElement).scrollTop / ROW_H);
  if (Math.abs(top - h.scrollRow) >= OVERSCAN / 2) h.scrollRow = top;
  h.card.place();
}

function onMatrixKey(h: GraphHost, e: KeyboardEvent, rows: readonly MatrixRow[]): void {
  const t = e.target as HTMLElement;
  if (!t.classList.contains('mark')) return;
  const r = Number(t.dataset['r']);
  const c = Number(t.dataset['c']);
  if (e.key === 'Enter') {
    const m = rows[r]?.cells[c];
    e.preventDefault();
    if (m) open(h, m);
    return;
  }
  const has = rows.map((row) => row.cells.map((x) => x !== null));
  const next = gridStep(has, r, c, e.key, e.ctrlKey || e.metaKey);
  if (!next) return;
  e.preventDefault();
  h.cell = next;
  const box = h.root.querySelector<HTMLElement>('.mx');
  if (box && rows.length > WINDOW_AT) {
    // Bring the row into view first: only the rows in view are drawn.
    const y = next[0] * ROW_H;
    if (y < box.scrollTop + ROW_H * 2 || y > box.scrollTop + box.clientHeight - ROW_H * 3) box.scrollTop = Math.max(0, y - box.clientHeight / 2);
    h.scrollRow = Math.floor(box.scrollTop / ROW_H);
  }
  h.el.requestUpdate();
  void h.el.updateComplete.then(() => h.root.querySelector<HTMLElement>(`.matrix .mark[data-r="${next[0]}"][data-c="${next[1]}"]`)?.focus());
}

/** A header row's column `c` is under a cell of an earlier row that spans down past it. */
function spannedAt(head: readonly MatrixHead[][], level: number, c: number): boolean {
  for (let l = 0; l < level; l++) {
    let x = 0;
    for (const hd of head[l] ?? []) {
      if (c >= x && c < x + hd.span && l + hd.rows > level) return true;
      x += hd.span;
    }
  }
  return false;
}
