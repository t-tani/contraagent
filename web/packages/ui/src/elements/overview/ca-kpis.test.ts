// @vitest-environment happy-dom
// The figures: neutral by default; only a problem count above 0 takes a status colour.
import type { JournalRow } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import './ca-kpis.js';

const row = (key: string, stop: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', wall_s: 1.5,
  executor: 'agent', cost_usd: 0.01, ...extra,
});

async function tiles(journal: JournalRow[]): Promise<Map<string, HTMLElement>> {
  const el = document.createElement('ca-kpis');
  el.journal = journal;
  document.body.append(el);
  await el.updateComplete;
  return new Map([...el.shadowRoot!.querySelectorAll<HTMLElement>('.kpi')].map((t) => [t.dataset['id']!, t]));
}

const tone = (t: HTMLElement | undefined) => [...(t?.classList ?? [])].filter((c) => c !== 'kpi');

describe('ca-kpis colours', () => {
  it('keeps the total neutral when a task failed, and colours the failed count', async () => {
    const t = await tiles([row('prepare-a', 'completed'), row('prepare-b', 'error'), row('review-a', 'completed', { hops: [{ model: 'a', stop: 'rate_limited' }, { model: 'b', stop: 'completed' }] as JournalRow['hops'] })]);
    expect(tone(t.get('tasks'))).toEqual([]);
    expect(t.get('tasks')!.querySelector('.t-failed')?.textContent).toBe('1 failed');
    expect(tone(t.get('bad'))).toEqual(['failed']);
    expect(t.get('bad')!.querySelector('.k')!.classList.contains('mk-failed')).toBe(true);
    // measures and counts that are not problems never take a colour
    for (const id of ['attempts', 'cost', 'tokens', 'wall', 'retry', 'ct', 'fo']) expect(tone(t.get(id)), id).toEqual([]);
  });

  it('shows a 0 of a problem neutral, with its words', async () => {
    const t = await tiles([row('prepare-a', 'completed')]);
    expect(tone(t.get('bad'))).toEqual([]);
    expect(t.get('bad')!.textContent).toContain('All attempts passed');
    expect(tone(t.get('notstarted'))).toEqual([]);
  });

  it('counts done and done after retrying as done; skipped apart; a refusal then done is done', async () => {
    const t = await tiles([
      row('prepare-a', 'completed'),
      row('prepare-b', 'error'),
      row('prepare-b', 'completed', { attempt: 1 }),
      row('prepare-c', 'invalid_input'),
      row('prepare-c', 'completed', { attempt: 1 }),
      row('prepare-d', 'skipped'),
    ]);
    expect(t.get('tasks')!.textContent).toContain('3 done');
    expect(t.get('tasks')!.textContent).toContain('1 skipped');
  });

  it('marks tasks not started as attention', async () => {
    const t = await tiles([row('prepare-a', 'completed'), row('summarize-a', 'invalid_input', { reason: 'input x.json is missing' })]);
    expect(tone(t.get('notstarted'))).toEqual(['attention']);
    expect(tone(t.get('tasks'))).toEqual([]);
  });
});
