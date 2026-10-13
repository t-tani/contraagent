// @vitest-environment happy-dom
import { html } from 'lit';
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeDataTable } from './data-table.js';
import { sortRows, type DataColumn } from './types.js';

defineElement('cae-data-table', CaeDataTable);

interface Fruit {
  id: string;
  name: string;
  kg: number;
}
const FRUIT: Fruit[] = [
  { id: 'a', name: 'apple', kg: 3 },
  { id: 'b', name: 'banana', kg: 12 },
  { id: 'c', name: 'cherry', kg: 1 },
];
const COLUMNS: DataColumn<Fruit>[] = [
  { id: 'name', header: 'Name', rowHeader: true, cell: (f) => html`<b>${f.name}</b>`, text: (f) => f.name },
  { id: 'kg', header: 'Weight', align: 'end', width: '80px', cell: (f) => f.kg, compare: (x, y) => x.kg - y.kg },
];

async function mount(props: Partial<CaeDataTable<Fruit>> = {}) {
  const el = document.createElement('cae-data-table') as CaeDataTable<Fruit>;
  Object.assign(el, { columns: COLUMNS, rows: FRUIT, ...props });
  const events: string[] = [];
  for (const name of ['cae-activate', 'cae-select', 'cae-sort'] as const)
    el.addEventListener(name, (e) => events.push(`${name} ${JSON.stringify(e.detail)}`));
  document.body.append(el);
  await el.updateComplete;
  const root = el.shadowRoot!;
  const rows = () => [...root.querySelectorAll<HTMLElement>('tbody tr[data-key]')];
  return { el, root, rows, events };
}

const key = (target: HTMLElement, k: string) => target.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, composed: true, cancelable: true }));

describe('cae-data-table', () => {
  it('is a table: column headers, the row header, the columns as a grid', async () => {
    const { el, root, rows } = await mount({ caption: 'Fruit' });
    expect(root.querySelector('caption')?.textContent?.trim()).toBe('Fruit');
    expect([...root.querySelectorAll('thead th')].map((th) => [th.getAttribute('scope'), th.textContent?.trim()])).toEqual([
      ['col', 'Name'],
      ['col', 'Weight'],
    ]);
    expect(rows().map((r) => r.querySelector('th[scope=row]')?.textContent)).toEqual(['apple', 'banana', 'cherry']);
    expect(rows()[0]!.querySelector('td')?.getAttribute('data-align')).toBe('end');
    expect(root.querySelector('table')?.getAttribute('style')).toContain('minmax(0, 1fr) 80px');
    el.remove();
  });

  it('the rows are one tab stop; the arrow keys, Home and End move it', async () => {
    const { el, rows } = await mount();
    expect(rows().map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    key(rows()[0]!, 'ArrowDown');
    expect(rows().map((r) => r.tabIndex)).toEqual([-1, 0, -1]);
    key(rows()[1]!, 'End');
    expect(rows().map((r) => r.tabIndex)).toEqual([-1, -1, 0]);
    key(rows()[2]!, 'Home');
    expect(rows().map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    el.remove();
  });

  it('Enter and a click send cae-activate; not activatable, they select', async () => {
    const a = await mount();
    key(a.rows()[1]!, 'Enter');
    a.rows()[2]!.click();
    expect(a.events).toEqual(['cae-activate {"id":"b"}', 'cae-activate {"id":"c"}']);
    a.el.remove();

    const s = await mount({ activatable: false });
    s.rows()[0]!.click();
    await s.el.updateComplete;
    expect(s.events).toEqual(['cae-select {"id":"a"}']);
    expect(s.rows()[0]!.getAttribute('part')).toBe('row row-selected');
    expect(s.rows()[0]!.getAttribute('aria-current')).toBe('true');
    s.el.remove();
  });

  it('a click on a button inside a cell is the button\'s, not the row\'s', async () => {
    const cols: DataColumn<Fruit>[] = [{ id: 'x', header: 'X', cell: () => html`<button type="button">Show</button>` }];
    const { el, root, events } = await mount({ columns: cols });
    root.querySelector('button')!.click();
    expect(events).toEqual([]);
    el.remove();
  });

  it('a sortable header sends cae-sort; the sorted one has aria-sort', async () => {
    const { el, root, events } = await mount({ sort: { id: 'kg', direction: 'asc' } });
    expect(root.querySelector('th[data-col=name] button')).toBeNull();
    const kg = root.querySelector<HTMLElement>('th[data-col=kg]')!;
    expect(kg.getAttribute('aria-sort')).toBe('ascending');
    kg.querySelector('button')!.click();
    expect(events).toEqual(['cae-sort {"id":"kg","direction":"desc"}']);
    el.remove();
  });

  it('sortRows orders by compare, else by text, and keeps equal rows in order', () => {
    expect(sortRows(FRUIT, COLUMNS, { id: 'kg', direction: 'desc' }).map((f) => f.id)).toEqual(['b', 'a', 'c']);
    expect(sortRows(FRUIT, COLUMNS, { id: 'name', direction: 'desc' }).map((f) => f.id)).toEqual(['c', 'b', 'a']);
    expect(sortRows(FRUIT, COLUMNS, null).map((f) => f.id)).toEqual(['a', 'b', 'c']);
  });

  it('sortRows orders a sortable column without compare or text by its cell, a string or a number', () => {
    const cols: DataColumn<Fruit>[] = [
      { id: 'name', header: 'Name', cell: (f) => f.name, sortable: true },
      { id: 'kg', header: 'kg', cell: (f) => f.kg, sortable: true },
      { id: 'tpl', header: 'Template', cell: (f) => ({ f }), sortable: true },
    ];
    expect(sortRows(FRUIT, cols, { id: 'name', direction: 'desc' }).map((f) => f.id)).toEqual(['c', 'b', 'a']);
    expect(sortRows(FRUIT, cols, { id: 'kg', direction: 'asc' }).map((f) => f.id)).toEqual(['c', 'a', 'b']);
    expect(sortRows(FRUIT, cols, { id: 'tpl', direction: 'desc' }).map((f) => f.id)).toEqual(['a', 'b', 'c']);
  });

  it('with no rows: the empty words, or the empty slot', async () => {
    const { el, root } = await mount({ rows: [], strings: { empty: 'No fruit' } });
    expect(root.querySelector('[part=empty]')?.textContent?.trim()).toBe('No fruit');
    expect(root.querySelector('slot[name=empty]')).not.toBeNull();
    el.remove();
  });

  it('above windowAt rows, draws a window of them and spacers for the rest', async () => {
    const many: Fruit[] = Array.from({ length: 500 }, (_, i) => ({ id: `f${i}`, name: `fruit ${i}`, kg: i }));
    const { el, root, rows } = await mount({ rows: many, windowAt: 100, rowHeight: 20 });
    const drawn = rows();
    expect(drawn.length).toBeGreaterThan(0);
    expect(drawn.length).toBeLessThan(100);
    expect(drawn[0]!.dataset['key']).toBe('f0');
    expect(root.querySelector('table')?.getAttribute('aria-rowcount')).toBe('501');
    expect(drawn[0]!.getAttribute('aria-rowindex')).toBe('2');
    const spacers = [...root.querySelectorAll<HTMLElement>('tr.spacer')];
    expect(spacers).toHaveLength(1);
    expect(spacers[0]!.getAttribute('aria-hidden')).toBe('true');
    // End draws the last rows and moves there.
    key(drawn[0]!, 'End');
    await el.updateComplete;
    expect(rows().at(-1)!.dataset['key']).toBe('f499');
    expect(rows().filter((r) => r.tabIndex === 0).map((r) => r.dataset['key'])).toEqual(['f499']);
    el.remove();
  });

  it('sets the host\'s row attributes and tone', async () => {
    const { el, rows } = await mount({ rowAttrs: (f) => ({ 'data-heavy': String(f.kg > 5) }), rowTone: (f) => (f.kg > 5 ? 'failed' : undefined) });
    expect(rows().map((r) => [r.dataset['heavy'], r.dataset['tone']])).toEqual([
      ['false', undefined],
      ['true', 'failed'],
      ['false', undefined],
    ]);
    el.remove();
  });
});
