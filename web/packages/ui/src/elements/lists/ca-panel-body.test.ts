// @vitest-environment happy-dom
import { typedBody, type PanelBody } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { bodyColumns, cellUrl, rowTone } from '../../adapters/panel-body.js';
import { cellText, fractionPct } from '../../words/panels.js';
import './ca-panel-body.js';
import './ca-panel-view.js';
import type { CaPanelBody } from './ca-panel-body.js';
import type { CaPanelView } from './ca-panel-view.js';

const BODY = {
  type: 'blocks',
  blocks: [
    { type: 'tiles', tiles: [{ id: 'cost', label: 'Cost over 14 days', value: '$212', sub: [['$15 a day']] }] },
    {
      type: 'columns',
      title: 'Cost by day',
      x: ['10-01', '10-02'],
      series: [
        { name: 'writer', values: [8.1, 7.2] },
        { name: 'research', values: [3, 4.4] },
      ],
      unit: 'usd',
      stacked: true,
    },
    {
      type: 'table',
      title: 'Kinds',
      collapsed: true,
      columns: [
        { id: 'kind', label: 'Kind' },
        { id: 'rate', label: 'Done', format: 'pct', bar: true },
        { id: 'last', label: 'Last', format: 'datetime' },
      ],
      rows: [
        { kind: 'writer', rate: 0.97, last: '2026-10-14T10:00:00Z' },
        { kind: 'research', rate: 0.5, _tone: 'failed' },
      ],
    },
    { anything: ['else'] },
  ],
} as unknown as PanelBody;

async function mount<T extends HTMLElement & { updateComplete: Promise<boolean> }>(tag: string, props: Record<string, unknown>): Promise<T> {
  const el = document.createElement(tag) as T;
  Object.assign(el, props);
  document.body.append(el);
  await el.updateComplete;
  return el;
}

describe('a panel body', () => {
  it('is typed by its type, and any other object is a JSON tree', () => {
    expect(typedBody(BODY)?.type).toBe('blocks');
    expect(typedBody({ type: 'nope' })).toBeNull();
    expect(typedBody({ x: 1 })).toBeNull();
    expect(typedBody([])).toBeNull();
  });

  it('writes a cell by its column\'s format', () => {
    expect(fractionPct(0.97)).toBe('97%');
    expect(fractionPct(0.045)).toBe('4.5%');
    expect(cellText(0.5, 'pct')).toBe('50%');
    expect(cellText(1.234, 'usd')).toBe('$1.23');
    expect(cellText(125, 'duration')).toBe('2m 05s');
    expect(cellText(12_000, 'tokens')).toBe('12k');
    expect(cellText(null, 'usd')).toBe('—');
    expect(cellText('2026-10-14T10:00:00Z', 'datetime')).toMatch(/\d\d:\d\d:\d\d/);
  });

  it('turns a table body into columns: numbers right-aligned, the first column names the row, a bar where asked', () => {
    const table = (BODY as { blocks: PanelBody[] }).blocks[2] as Parameters<typeof bodyColumns>[0];
    const cols = bodyColumns(table);
    expect(cols.map((c) => [c.id, c.align, !!c.rowHeader])).toEqual([
      ['kind', 'start', true],
      ['rate', 'end', false],
      ['last', 'start', false],
    ]);
    expect(cols[1]!.text!(table.rows[0]!)).toBe('97%');
    expect(rowTone(table.rows[1]!)).toBe('failed');
    expect(rowTone({ _tone: 'sideways' } as unknown as Parameters<typeof rowTone>[0])).toBeUndefined();
  });

  it('draws tiles, a chart, a folded table and a JSON tree, in order', async () => {
    const el = await mount<CaPanelBody>('ca-panel-body', { body: BODY });
    const r = el.shadowRoot!;
    expect([...r.querySelectorAll('cae-stat-tiles, cae-column-chart, cae-data-table, cae-json-tree')].map((e) => e.tagName.toLowerCase())).toEqual([
      'cae-stat-tiles',
      'cae-column-chart',
      'cae-data-table',
      'cae-json-tree',
    ]);
    expect(r.querySelector('h4')?.textContent).toBe('Cost by day');
    const fold = r.querySelector('details')!;
    expect(fold.open).toBe(false);
    expect(fold.querySelector('summary')?.textContent).toBe('Kinds');
    const chart = r.querySelector('cae-column-chart') as unknown as { stacked: boolean; format: (v: number) => string };
    expect(chart.stacked).toBe(true);
    expect(chart.format(1.5)).toBe('$1.50');
  });

  it('leads a link column\'s cell to its row\'s URL, http or https only', async () => {
    const table = {
      type: 'table',
      columns: [
        { id: 'topic', label: 'Topic', link: 'url' },
        { id: 'n', label: 'Items' },
      ],
      rows: [
        { topic: 'cve-2026-1', url: 'https://example.org/t/cve-2026-1', n: 3 },
        { topic: 'sneaky', url: 'javascript:alert(1)', n: 1 },
        { topic: 'no-url', n: 0 },
      ],
    } as unknown as PanelBody;
    expect(cellUrl('https://example.org/a')).toBe('https://example.org/a');
    expect(cellUrl('javascript:alert(1)')).toBeNull();
    expect(cellUrl('  http://x.test/ ')).toBe('http://x.test/');
    expect(cellUrl(42)).toBeNull();
    const el = await mount<CaPanelBody>('ca-panel-body', { body: table });
    const grid = el.shadowRoot!.querySelector('cae-data-table')!;
    await (grid as unknown as { updateComplete: Promise<boolean> }).updateComplete;
    const links = [...grid.shadowRoot!.querySelectorAll('a')];
    expect(links.map((a) => [a.textContent, a.getAttribute('href'), a.getAttribute('rel'), a.getAttribute('target')])).toEqual([
      ['cve-2026-1', 'https://example.org/t/cve-2026-1', 'noopener noreferrer', '_blank'],
    ]);
  });

  it('writes a note as escaped markdown, with its tone beside it', async () => {
    const body = { type: 'note', tone: 'attention', text: 'Counts **run starts**.\n\n<img src=x onerror=alert(1)> [docs](https://example.org)' } as unknown as PanelBody;
    const el = await mount<CaPanelBody>('ca-panel-body', { body });
    const note = el.shadowRoot!.querySelector<HTMLElement>('.note')!;
    expect(note.dataset['tone']).toBe('attention');
    expect(note.querySelector('b')?.textContent).toBe('run starts');
    expect(note.querySelector('img')).toBeNull();
    expect(note.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(note.querySelector('a')?.getAttribute('href')).toBe('https://example.org');
  });

  it('draws a status grid with its cells', async () => {
    const body = {
      type: 'status_grid',
      title: 'Cycles',
      x: ['00', '01'],
      y: ['Mon'],
      cells: [[{ label: 'done', tone: 'done' }, null]],
    } as unknown as PanelBody;
    const el = await mount<CaPanelBody>('ca-panel-body', { body });
    const grid = el.shadowRoot!.querySelector('cae-state-grid') as unknown as { label: string; cells: unknown[][] };
    expect(grid.label).toBe('Cycles');
    expect(grid.cells).toEqual([[{ label: 'done', tone: 'done' }, null]]);
  });

  it('is drawn by the panel view; any other body stays a JSON tree', async () => {
    const typed = await mount<CaPanelView>('ca-panel-view', { name: 'stats', data: BODY });
    expect(typed.shadowRoot!.querySelector('ca-panel-body')).not.toBeNull();
    const plain = await mount<CaPanelView>('ca-panel-view', { name: 'raw', data: { x: 1 } });
    expect(plain.shadowRoot!.querySelector('ca-panel-body')).toBeNull();
    expect(plain.shadowRoot!.querySelector('cae-json-tree')).not.toBeNull();
  });
});
