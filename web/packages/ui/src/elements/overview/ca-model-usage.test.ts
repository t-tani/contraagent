// @vitest-environment happy-dom
// Each model's share of a run, by the measure the reader picks, with every model named in a table.
import type { ModelUsage } from '@contraagent/api';
import { afterEach, describe, expect, it } from 'vitest';
import type { CaModelUsage } from './ca-model-usage.js';
import './ca-model-usage.js';

const usage = (agent: string, model: string, o: Partial<ModelUsage> = {}): ModelUsage => ({
  agent,
  model,
  sessions: 1,
  calls: 2,
  input: 100,
  output: 10,
  cache_read: 0,
  cache_creation: 0,
  cost_usd: null,
  wall_s: 5,
  ...o,
});

async function draw(models: ModelUsage[]): Promise<CaModelUsage> {
  const el = document.createElement('ca-model-usage');
  el.models = models;
  document.body.append(el);
  await el.updateComplete;
  return el;
}

afterEach(() => document.body.replaceChildren());

describe('ca-model-usage', () => {
  const models = [usage('claude', 'claude-haiku-5-5', { cost_usd: 0.03, sessions: 3 }), usage('omp', 'glm-5.3', { cost_usd: 0.01, sessions: 1 })];

  it('draws one bar of the models, cost first, with each model named in the table beside its colour', async () => {
    const el = await draw(models);
    const root = el.shadowRoot!;
    const segs = [...root.querySelectorAll<HTMLElement>('.share-seg')];
    expect(segs.map((s) => s.getAttribute('aria-label'))).toEqual(['claude-haiku-5-5 | 75% | $0.030', 'glm-5.3 | 25% | $0.010']);
    const rows = [...root.querySelectorAll('tbody tr')].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent.trim().replace(/\s+/g, ' ')));
    expect(rows.map((r) => r.slice(1, 3))).toEqual([
      ['75%', '$0.030'],
      ['25%', '$0.010'],
    ]);
    const names = [...root.querySelectorAll('.model')].map((m) => [m.querySelector('b')!.textContent, m.querySelector('small')!.textContent]);
    expect(names).toEqual([
      ['claude-haiku-5-5', 'claude'],
      ['glm-5.3', 'omp'],
    ]);
    const swatches = [...root.querySelectorAll<HTMLElement>('.model i')].map((i) => i.style.background);
    expect(swatches).toEqual(['var(--series-1)', 'var(--series-2)']);
  });

  it('switches the measure and keeps each colour on its model', async () => {
    const el = await draw(models);
    const seg = el.shadowRoot!.querySelector('cae-segmented')!;
    seg.dispatchEvent(new CustomEvent('cae-change', { detail: { value: 'sessions' } }));
    await el.updateComplete;
    const segs = [...el.shadowRoot!.querySelectorAll<HTMLElement>('.share-seg')];
    expect(segs.map((s) => [s.getAttribute('aria-label'), s.style.background])).toEqual([
      ['claude-haiku-5-5 | 75% | 3', 'var(--series-1)'],
      ['glm-5.3 | 25% | 1', 'var(--series-2)'],
    ]);
    expect(el.shadowRoot!.querySelector('th.on + th, th.on')!.textContent).toBe('Share');
  });

  it('offers only the measures some model has, and starts on tokens when no cost was reported', async () => {
    const el = await draw([usage('claude', 'a'), usage('omp', 'b')]);
    const seg = el.shadowRoot!.querySelector('cae-segmented')!;
    expect(seg.options.map((o) => o.value)).toEqual(['tokens', 'time', 'sessions']);
    expect(seg.value).toBe('tokens');
  });

  it('says so when no agent session ran', async () => {
    const el = await draw([]);
    expect(el.shadowRoot!.textContent.trim()).toBe('No agent sessions');
  });
});
