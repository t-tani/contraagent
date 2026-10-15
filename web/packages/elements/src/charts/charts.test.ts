// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeBarChart } from './bar-chart.js';
import { CaeColumnChart } from './column-chart.js';
import { CaeHeatmap, heatStep } from './heatmap.js';
import { CaeLineChart, linePath } from './line-chart.js';
import { foldSeries, labelStride, niceAxis, OTHER_COLOUR } from './scale.js';
import { CaeStateGrid, stateFill, statesOf, texturesOf } from './state-grid.js';

defineElement('cae-column-chart', CaeColumnChart);
defineElement('cae-state-grid', CaeStateGrid);
defineElement('cae-line-chart', CaeLineChart);
defineElement('cae-heatmap', CaeHeatmap);
defineElement('cae-bar-chart', CaeBarChart);

async function mount<T extends HTMLElement & { updateComplete: Promise<boolean> }>(tag: string, props: Record<string, unknown>): Promise<T> {
  const el = document.createElement(tag) as T;
  Object.assign(el, { width: 600, ...props });
  document.body.append(el);
  await el.updateComplete;
  // The width a ResizeObserver would report (happy-dom lays nothing out).
  (el as unknown as { width: number }).width = 600;
  await el.updateComplete;
  return el;
}

const root = (el: HTMLElement) => el.shadowRoot!;
const legendWords = (el: HTMLElement) => [...root(el).querySelectorAll('[part="legend"] [role="listitem"]')].map((s) => s.textContent?.trim());
/** The tooltip's lines: its title, then a name and a value per line. */
const tipLines = (el: HTMLElement) => [
  root(el).querySelector('.tip b')?.textContent,
  ...[...root(el).querySelectorAll('.tip .row')].map((r) => [...r.querySelectorAll('span')].map((s) => s.textContent).join(' ')),
];
const key = (el: HTMLElement, k: string) =>
  root(el).querySelector('.plot')!.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, composed: true }));

describe('the arithmetic', () => {
  it('rounds an axis up to round ticks, from 0', () => {
    expect(niceAxis(0, 7.3)).toEqual({ min: 0, max: 8, ticks: [0, 2, 4, 6, 8] });
    expect(niceAxis(0, 0)).toEqual({ min: 0, max: 1, ticks: [0, 1] });
    expect(niceAxis(-3, 9).min).toBeLessThanOrEqual(-3);
  });

  it('folds the series past the sixth into one, summed, so no colour is made up', () => {
    const series = Array.from({ length: 8 }, (_, i) => ({ name: `s${i}`, values: [i, i === 7 ? null : 1] }));
    const drawn = foldSeries(series, 'Other');
    expect(drawn.map((s) => s.name)).toEqual(['s0', 's1', 's2', 's3', 's4', 'Other']);
    expect(drawn[5]).toMatchObject({ colour: OTHER_COLOUR, values: [5 + 6 + 7, 2], folded: ['s5', 's6', 's7'] });
    expect(drawn[0]!.colour).toBe('var(--series-1)');
  });

  it('spaces the labels so they fit, and breaks a line where a value is null', () => {
    expect(labelStride(30, 300, 40)).toBe(4);
    expect(labelStride(3, 300, 40)).toBe(1);
    expect(linePath([[0, 0], [1, 1], null, [3, 3]])).toBe('M0.0,0.0L1.0,1.0M3.0,3.0');
  });

  it('steps a heatmap value between the lowest and the highest', () => {
    expect([0, 2, 5, 9.9, 10].map((v) => heatStep(v, 0, 10))).toEqual([0, 1, 2, 4, 4]);
  });
});

describe('cae-column-chart', () => {
  const x = ['10-01', '10-02', '10-03'];
  const series = [
    { name: 'writer', values: [8, 7, null] },
    { name: 'research', values: [3, 4, 2] },
  ];

  it('stacks the series of a label on one bar, and names them in the legend', async () => {
    const el = await mount<CaeColumnChart>('cae-column-chart', { x, series, stacked: true, label: 'Cost by day' });
    expect(legendWords(el)).toEqual(['writer', 'research']);
    // Five parts: the null draws none.
    expect(root(el).querySelectorAll('svg path')).toHaveLength(5);
    expect(root(el).querySelector('svg')!.getAttribute('aria-label')).toBe('Cost by day');
  });

  it('shows a label\'s values and the total when the reader moves to it', async () => {
    const el = await mount<CaeColumnChart>('cae-column-chart', { x, series, stacked: true, format: (v: number) => `$${v}` });
    key(el, 'ArrowRight');
    await el.updateComplete;
    expect(tipLines(el)).toEqual(['10-01', 'research $3', 'writer $8', 'Total $11']);
    key(el, 'Escape');
    await el.updateComplete;
    expect(root(el).querySelector('.tip')).toBeNull();
  });

  it('shows its values as a table, and says when there is nothing to draw', async () => {
    const el = await mount<CaeColumnChart>('cae-column-chart', { x, series, stacked: true, strings: { showTable: 'Table' } });
    const sw = root(el).querySelector<HTMLButtonElement>('[part="switch"]')!;
    expect(sw.textContent).toBe('Table');
    sw.click();
    await el.updateComplete;
    const cells = [...root(el).querySelectorAll('tbody tr')].map((r) => [...r.children].map((c) => c.textContent));
    expect(cells[2]).toEqual(['10-03', '—', '2', '2']);
    const empty = await mount<CaeColumnChart>('cae-column-chart', { x, series: [{ name: 'a', values: [null, null, null] }] });
    expect(root(empty).querySelector('[part="empty"]')?.textContent).toBe('No values');
  });

  it('has no legend for a single series: the title names it', async () => {
    const el = await mount<CaeColumnChart>('cae-column-chart', { x, series: [series[1]] });
    expect(legendWords(el)).toEqual([]);
  });
});

describe('cae-line-chart', () => {
  it('draws a line per series and marks the label the reader points at', async () => {
    const el = await mount<CaeLineChart>('cae-line-chart', {
      x: ['a', 'b', 'c'],
      series: [
        { name: '5-hour', values: [10, 40, 35] },
        { name: 'weekly', values: [50, null, 52] },
      ],
    });
    expect(legendWords(el)).toEqual(['5-hour', 'weekly']);
    expect(root(el).querySelectorAll('svg path')).toHaveLength(2);
    key(el, 'End');
    await el.updateComplete;
    expect(tipLines(el)).toEqual(['c', '5-hour 35', 'weekly 52']);
  });
});

describe('cae-heatmap', () => {
  it('colours a cell per value, leaves a null cell empty, and gives the scale', async () => {
    const el = await mount<CaeHeatmap>('cae-heatmap', {
      x: ['0', '1'],
      y: ['Mon', 'Tue'],
      values: [
        [0, 4],
        [null, 8],
      ],
    });
    const rects = [...root(el).querySelectorAll('svg rect')];
    expect(rects).toHaveLength(4);
    expect(rects[2]!.getAttribute('fill')).toBe('none');
    expect(legendWords(el)).toEqual(['0 to 8']);
    key(el, 'ArrowDown');
    key(el, 'ArrowDown');
    await el.updateComplete;
    expect(tipLines(el)).toEqual(['Tue | 0', '—']);
  });
});

describe('cae-state-grid', () => {
  const ok = { label: 'done', tone: 'done' as const };
  const bad = { label: 'failed', tone: 'failed' as const, tip: 'run 0312' };
  const paused = { label: 'paused', tone: 'attention' as const };
  const cells = [
    [ok, bad, null],
    [paused, ok, ok],
  ];

  it('names each state once in the legend, the exceptions first, then in the order the cells give them', () => {
    expect(statesOf(cells).map((s) => s.label)).toEqual(['failed', 'paused', 'done']);
    const two = [[{ label: 'late', tone: 'done' as const }, ok]];
    expect(statesOf(two).map((s) => s.label)).toEqual(['late', 'done']);
  });

  it('colours a cell by its tone with its mark beside the colour, and leaves a null cell empty', async () => {
    const el = await mount<CaeStateGrid>('cae-state-grid', { x: ['00', '01', '02'], y: ['Mon', 'Tue'], cells });
    // Each entry: its key (the cell's colour and mark, hidden from screen readers), then its word.
    const keys = [...root(el).querySelectorAll('[part="legend"] .key')];
    expect(keys.map((k) => [k.getAttribute('aria-hidden'), k.textContent])).toEqual([
      ['true', '✕'],
      ['true', '◌'],
      ['true', '✓'],
    ]);
    expect(legendWords(el)).toEqual(['✕failed', '◌paused', '✓done']);
    const rects = [...root(el).querySelectorAll('svg rect')];
    expect(rects).toHaveLength(6);
    expect(rects[1]!.getAttribute('fill')).toBe(stateFill('failed'));
    expect(rects[2]!.getAttribute('fill')).toBe('none');
    expect([...root(el).querySelectorAll('svg text.mark')].map((t) => t.textContent)).toEqual(['✓', '✕', '◌', '✓', '✓']);
  });

  it('tells the states of one tone apart by a texture, in the cells and in the legend', async () => {
    const late = { label: 'late', tone: 'attention' as const };
    const capped = { label: 'capped', tone: 'attention' as const };
    const grid = [[paused, late, capped, ok]];
    expect([...texturesOf(statesOf(grid)).values()]).toEqual(['', 'stripes', 'dots', '']);
    const el = await mount<CaeStateGrid>('cae-state-grid', { x: ['00', '01', '02', '03'], y: ['Mon'], cells: grid });
    const keys = [...root(el).querySelectorAll('[part="legend"] .key')];
    expect(keys.map((k) => [k.textContent, k.getAttribute('data-texture')])).toEqual([
      ['◌', null],
      ['◌', 'stripes'],
      ['◌', 'dots'],
      ['✓', null],
    ]);
    const textured = [...root(el).querySelectorAll('svg rect.texture')];
    expect(textured.map((r) => r.getAttribute('data-texture'))).toEqual(['stripes', 'dots']);
    const id = textured[0]!.getAttribute('fill')!.slice(5, -1);
    expect(root(el).querySelector(`pattern[id="${id}"]`)).not.toBeNull();
  });

  it('says a cell\'s row, column, state and fact; the arrow keys move by a row with up and down', async () => {
    const el = await mount<CaeStateGrid>('cae-state-grid', { x: ['00', '01', '02'], y: ['Mon', 'Tue'], cells });
    key(el, 'ArrowRight');
    key(el, 'ArrowRight');
    await el.updateComplete;
    expect(tipLines(el)).toEqual(['Mon | 01', 'failed', 'run 0312']);
    key(el, 'ArrowDown');
    await el.updateComplete;
    expect(tipLines(el)).toEqual(['Tue | 01', 'done']);
  });

  it('shows every state in words in its table', async () => {
    const el = await mount<CaeStateGrid>('cae-state-grid', { x: ['00', '01', '02'], y: ['Mon', 'Tue'], cells });
    root(el).querySelector<HTMLButtonElement>('.switch')!.click();
    await el.updateComplete;
    const rows = [...root(el).querySelectorAll('tbody tr')].map((r) => [...r.children].map((c) => c.textContent));
    expect(rows).toEqual([
      ['Mon', 'done', 'failed', '—'],
      ['Tue', 'paused', 'done', 'done'],
    ]);
  });
});

describe('cae-bar-chart', () => {
  it('draws a bar per label as long as its value against the longest, each with its value', async () => {
    const el = await mount<CaeBarChart>('cae-bar-chart', {
      bars: [
        { label: 'collected', value: 200 },
        { label: 'kept', value: 50, tone: 'attention' },
      ],
    });
    const items = [...root(el).querySelectorAll('[role="listitem"]')].map((r) => r.getAttribute('aria-label'));
    expect(items).toEqual(['collected | 200', 'kept | 50']);
    const bars = [...root(el).querySelectorAll<HTMLElement>('.bar')];
    expect(bars.map((b) => b.style.width)).toEqual(['100%', '25%']);
    expect(bars[1]!.dataset['tone']).toBe('attention');
  });
});
