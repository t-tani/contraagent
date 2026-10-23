// @vitest-environment happy-dom
import type { TrendsView } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import { TRENDS } from '../../adapters/trends.test.js';
import './ca-trends.js';
import type { CaTrends } from './ca-trends.js';

const VIEW: TrendsView = { query: {}, data: TRENDS, panels: { quality: { type: 'tiles', tiles: [{ id: 'q', label: 'Q1', value: 'ok' }] } }, loading: false, error: null };

async function mount(props: Partial<CaTrends>): Promise<CaTrends> {
  const el = document.createElement('ca-trends');
  Object.assign(el, { view: VIEW, tz: 'Asia/Tokyo', ...props });
  document.body.append(el);
  await el.updateComplete;
  return el;
}

afterEach(() => document.body.replaceChildren());

describe('ca-trends', () => {
  it('draws a section per fact, wide ones and pairs, then the trend panels', async () => {
    const el = await mount({ panels: [{ name: 'quality', title: 'Quality', description: '', icon: '✓', scope: 'trends' }] });
    const root = el.shadowRoot!;
    expect([...root.querySelectorAll('[data-section]')].map((s) => s.getAttribute('data-section'))).toEqual([
      'totals',
      'cost-by-day',
      'kinds',
      'models',
      'usage',
      'outcomes',
      'deferred',
      'starts',
      'runs',
    ]);
    expect(root.querySelectorAll('.pairs [data-section]')).toHaveLength(2);
    expect(root.querySelector('[data-panel="quality"] h3')?.textContent).toContain('Quality');
    // The time zone control beside it names the zone.
    expect(root.querySelector('.period')?.textContent).toBe('Oct 13 to Oct 14, 2026');
  });

  it('has no tabs while no trend panel names one', async () => {
    const root = (await mount({ panels: [{ name: 'quality', title: 'Quality', description: '', icon: '✓', scope: 'trends', tab: '' }] })).shadowRoot!;
    expect(root.querySelector('[role="tablist"]')).toBeNull();
  });

  it('puts the trend panels of each tab on a tab of their own, the trends and the panels of no tab first', async () => {
    const panel = (name: string, tab: string) => ({ name, title: name, description: '', icon: '▤', scope: 'trends' as const, tab });
    const panels = [panel('latency', 'Reliability'), panel('quality', ''), panel('spend', 'Cost'), panel('errors', 'Reliability')];
    const el = await mount({ panels });
    const root = el.shadowRoot!;
    const tabs = () => [...root.querySelectorAll('[role="tab"]')].map((t) => [t.textContent?.trim(), t.getAttribute('aria-selected')]);
    const shown = () => [...root.querySelectorAll('[data-panel]')].map((s) => s.getAttribute('data-panel'));
    expect(tabs()).toEqual([['Summary', 'true'], ['Reliability', 'false'], ['Cost', 'false']]);
    expect(shown()).toEqual(['quality']);
    expect(root.querySelector('[data-section="totals"]')).not.toBeNull();
    const seen: unknown[] = [];
    el.addEventListener('ca-navigate', (e) => seen.push((e as CustomEvent).detail));
    root.querySelectorAll<HTMLButtonElement>('[role="tab"]')[1]!.click();
    expect(seen).toEqual([{ trendsTab: 'Reliability' }]);
    el.tab = 'Reliability';
    await el.updateComplete;
    expect(tabs()[1]).toEqual(['Reliability', 'true']);
    expect(shown()).toEqual(['latency', 'errors']);
    expect(root.querySelector('[data-section]')).toBeNull();
    expect(root.querySelector('.period')).not.toBeNull(); // the period is every tab's
    el.tab = 'Gone';
    await el.updateComplete;
    expect(shown()).toEqual(['quality']); // a tab no panel names: the first
  });

  it('asks for another period, as the page address', async () => {
    const el = await mount({ days: 14 });
    const seen: unknown[] = [];
    el.addEventListener('ca-navigate', (e) => seen.push((e as CustomEvent).detail));
    el.shadowRoot!.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: '30' } }));
    el.shadowRoot!.querySelector('cae-segmented')!.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'dates' } }));
    expect(seen).toEqual([
      { days: 30, from: '', to: '' },
      { days: 0, from: '2026-10-01', to: '2026-10-14' },
    ]);
  });

  it('names the period of an export, which offers no other', async () => {
    const root = (await mount({ exported: true })).shadowRoot!;
    expect(root.querySelector('cae-segmented')).toBeNull();
    expect(root.querySelector('.controls')?.textContent).toContain('Period of this export');
  });

  it('says when no run worked in the period', async () => {
    const root = (await mount({ view: { ...VIEW, data: { ...TRENDS, totals: { ...TRENDS.totals, runs: 0 } } } })).shadowRoot!;
    expect(root.textContent).toContain('No runs in this period');
  });
});
