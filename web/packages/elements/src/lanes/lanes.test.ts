// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { defineElement } from '../core/define.js';
import { CaeLanes } from './lanes.js';
import type { Lane, LaneStyle } from './types.js';

defineElement('cae-lanes', CaeLanes);

const T = Date.parse('2026-10-11T10:00:00Z');
const STYLES: Record<string, LaneStyle> = {
  ok: { label: 'passed', color: 'green' },
  bad: { label: 'failed', color: 'red', pattern: 'hatched', group: 1 },
  run: { label: 'running', color: 'blue', pattern: 'striped', group: 1 },
};
const LANES: Lane[] = [
  { id: 'build', label: 'Build', bars: [{ id: 'b1', start: T, end: T + 60e3, style: 'ok', label: 'Build 1' }, { id: 'b2', start: T + 30e3, end: T + 90e3, style: 'bad', label: 'Build 2' }] },
  { id: 'test', label: 'Test', bars: [{ id: 't1', start: T + 90e3, end: T + 120e3, style: 'ok', label: 'Test 1' }] },
];

async function mount(props: Partial<CaeLanes> = {}) {
  const el = document.createElement('cae-lanes');
  Object.assign(el, { lanes: LANES, barStyles: STYLES, locale: 'en', ...props });
  document.body.append(el);
  await el.updateComplete;
  return el;
}

describe('cae-lanes', () => {
  it('draws a lane per group, overlapping bars on rows of their own', async () => {
    const el = await mount();
    const lanes = [...el.shadowRoot!.querySelectorAll('[part="lane"]')];
    expect(lanes.map((l) => l.querySelector('[part="lane-label"]')?.textContent)).toEqual(['Build', 'Test']);
    const bars = [...lanes[0]!.querySelectorAll<HTMLElement>('[part="bar"]')];
    expect(bars.map((b) => [b.title, b.dataset['pattern'], b.style.getPropertyValue('--row')])).toEqual([
      ['Build 1', 'solid', '0'],
      ['Build 2', 'hatched', '1'],
    ]);
    expect(lanes[0]!.querySelector<HTMLElement>('[part="track"]')!.style.getPropertyValue('--rows')).toBe('2');
  });

  it('fits the axis to the bars, with seconds on a short span', async () => {
    const el = await mount();
    const ticks = [...el.shadowRoot!.querySelectorAll('[part="axis"] span')].map((s) => s.textContent);
    expect(ticks).toHaveLength(5);
    expect(ticks[0]).toMatch(/^\d\d:\d\d:\d\d$/);
  });

  it('draws a legend row per group of the styles the bars use, the note of omitted bars last; no line at now when nothing runs', async () => {
    const el = await mount({ omitted: 2, strings: { omitted: (n) => `${n} hidden` } });
    const legends = [...el.shadowRoot!.querySelectorAll('[part="legend"]')].map((l) => [...l.querySelectorAll('[role="listitem"]')].map((i) => i.textContent?.trim()));
    expect(legends).toEqual([['passed'], ['failed', '2 hidden']]);
    expect(el.shadowRoot!.querySelector('[part="now"]')).toBeNull();
  });

  it('grows a running bar to now, with a line at now', async () => {
    const now = Date.now();
    const el = await mount({ lanes: [{ id: 'x', label: 'X', bars: [{ id: 'r', start: now - 30e3, end: null, style: 'ok', label: 'running' }] }] });
    expect(el.shadowRoot!.querySelector('[part="bar"]')?.classList.contains('running')).toBe(true);
    expect(el.shadowRoot!.querySelector('[part="now"]')).not.toBeNull();
  });

  it('shows its empty words with no bars', async () => {
    const el = await mount({ lanes: [] });
    expect(el.shadowRoot!.querySelector('[part="empty"]')?.textContent).toBe('No bars');
  });
});
