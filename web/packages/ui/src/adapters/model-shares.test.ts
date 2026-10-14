import type { ModelUsage } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { OTHER_COLOUR, modelColours, modelRows, shareParts } from './model-shares.js';

const usage = (model: string, o: Partial<ModelUsage> = {}): ModelUsage => ({
  agent: 'claude',
  model,
  sessions: 1,
  calls: 1,
  input: 0,
  output: 0,
  cache_read: 0,
  cache_creation: 0,
  cost_usd: null,
  wall_s: 0,
  ...o,
});

describe('model shares', () => {
  const models = [
    usage('haiku', { cost_usd: 0.01, input: 900, wall_s: 10, sessions: 3 }),
    usage('opus', { cost_usd: 0.09, input: 100, wall_s: 30, sessions: 1 }),
  ];

  it('gives each model its colour by first use, whatever the measure and the rank', () => {
    for (const measure of ['cost', 'tokens', 'time', 'sessions'] as const) {
      expect(shareParts(models, measure).map((p) => [p.label, p.color])).toEqual([
        ['haiku', 'var(--series-1)'],
        ['opus', 'var(--series-2)'],
      ]);
    }
  });

  it('measures each model by the measure chosen, and the shares sum to 100%', () => {
    expect(shareParts(models, 'cost').map((p) => p.value)).toEqual([0.01, 0.09]);
    expect(shareParts(models, 'tokens').map((p) => p.value)).toEqual([900, 100]);
    expect(modelRows(models, 'cost').map((r) => r.share)).toEqual(['10%', '90%']);
    expect(modelRows(models, 'sessions').map((r) => r.share)).toEqual(['75%', '25%']);
    const thirds = [usage('a', { wall_s: 1 }), usage('b', { wall_s: 1 }), usage('c', { wall_s: 1 })];
    expect(modelRows(thirds, 'time').reduce((a, r) => a + Number.parseInt(r.share), 0)).toBe(100);
  });

  it('shows no share when nothing was measured', () => {
    expect(modelRows([usage('haiku')], 'cost').map((r) => r.share)).toEqual(['—']);
  });

  it('folds the models past six into one part, and keeps every model in the rows', () => {
    const many = Array.from({ length: 8 }, (_, i) => usage(`m${i}`, { sessions: i + 1 }));
    const colours = modelColours(many);
    expect([...colours.values()].slice(0, 5)).toEqual([1, 2, 3, 4, 5].map((i) => `var(--series-${i})`));
    expect([...colours.values()].slice(5)).toEqual([OTHER_COLOUR, OTHER_COLOUR, OTHER_COLOUR]);
    const parts = shareParts(many, 'sessions');
    expect(parts.map((p) => p.id)).toEqual(['claude/m0', 'claude/m1', 'claude/m2', 'claude/m3', 'claude/m4', 'other']);
    expect(parts.at(-1)!.value).toBe(6 + 7 + 8);
    expect(modelRows(many, 'sessions')).toHaveLength(8);
    const six = Array.from({ length: 6 }, (_, i) => usage(`m${i}`));
    expect([...modelColours(six).values()]).not.toContain(OTHER_COLOUR); // six fit their own colours
  });
});
