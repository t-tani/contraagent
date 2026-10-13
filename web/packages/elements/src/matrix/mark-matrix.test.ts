// @vitest-environment happy-dom
// The mark matrix over hand-written data: rows, groups of columns, the keyboard and its events.
import { afterEach, describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeMarkMatrix } from './mark-matrix.js';
import type { MarkMatrixInput } from './types.js';

const matrix: MarkMatrixInput = {
  caption: 'Checks',
  label: 'Checks by service',
  head: [
    [{ id: 'n1', label: 'Mon', span: 2, rows: 1, type: 'group' }, { id: 'n2', label: 'Tue', span: 1, rows: 1, type: 'group' }],
    [
      { id: 'c1', label: 'lint', span: 1, rows: 1, type: 'column' },
      { id: 'c2', label: 'unit', span: 1, rows: 1, type: 'column' },
      { id: 'c3', label: 'lint', span: 1, rows: 1, type: 'column' },
    ],
  ],
  columns: [{ id: 'c1', groups: ['n1'] }, { id: 'c2', groups: ['n1'] }, { id: 'c3', groups: ['n2'] }],
  rows: [
    { id: 'api', label: 'api', cells: [{ id: 'a1', state: 'ok', label: 'a1' }, null, { id: 'a3', state: 'ok', label: 'a3', drill: true }] },
    { id: 'web', label: 'web', cells: [{ id: 'w1', state: 'ok', label: 'w1' }, { id: 'w2', state: 'ok', label: 'w2' }, null] },
  ],
  sorts: [{ id: 'name', label: 'Name' }, { id: 'state', label: 'State' }],
  sort: 'name',
};

defineElement('cae-mark-matrix', CaeMarkMatrix);

afterEach(() => document.body.replaceChildren());

describe('cae-mark-matrix', () => {
  it('draws a row per series, the groups over the columns, and a border where a group starts', async () => {
    const el = document.createElement('cae-mark-matrix');
    el.matrix = matrix;
    document.body.append(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    expect([...root.querySelectorAll('tbody th')].map((t) => t.textContent)).toEqual(['api', 'web']);
    expect([...root.querySelectorAll('thead th.group')].map((t) => t.textContent)).toEqual(['Mon', 'Tue']);
    expect([...root.querySelectorAll('tbody tr:first-child td.c')].map((t) => t.className.trim())).toEqual(['c', 'c', 'c g0']);
  });

  it('moves with the arrow keys, acts on Enter, and asks the host to sort', async () => {
    const el = document.createElement('cae-mark-matrix');
    el.matrix = matrix;
    const sent: [string, unknown][] = [];
    for (const n of ['cae-select', 'cae-activate', 'cae-drill', 'cae-sort']) el.addEventListener(n, (e) => sent.push([n, (e as CustomEvent).detail]));
    document.body.append(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    const first = root.querySelector<HTMLElement>('.mark[tabindex="0"]')!;
    first.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    await el.updateComplete;
    root.querySelector<HTMLElement>('.mark[data-r="0"][data-c="2"]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    const select = root.querySelector('select')!;
    select.value = 'state';
    select.dispatchEvent(new Event('change'));
    expect(sent.filter(([n]) => n !== 'cae-select')).toEqual([
      ['cae-drill', { id: 'a3' }],
      ['cae-activate', { id: 'a1' }],
      ['cae-sort', { id: 'state', direction: 'asc' }],
    ]);
  });
});
