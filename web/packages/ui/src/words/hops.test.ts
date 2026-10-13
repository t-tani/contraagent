import { describe, expect, it } from 'vitest';
import { modelSwitch } from './hops.js';

describe('modelSwitch', () => {
  it('writes the models in order, each one that stopped with why', () => {
    const hops = [
      { route: 'r1', model: 'primary-model', stop: 'rate_limited', wall_s: 0.1 },
      { route: 'r2', model: 'fallback-model', stop: 'completed', wall_s: 0.1 },
    ];
    expect(modelSwitch(hops)).toBe('primary-model (rate limited) → fallback-model');
    expect(modelSwitch(hops, 0.2)).toBe('primary-model (rate limited) → fallback-model | 0.2s');
  });

  it('is empty for a single hop, and falls back to the route for a hop with no model', () => {
    expect(modelSwitch([{ route: 'r1', model: 'm', stop: 'completed' }])).toBe('');
    expect(modelSwitch(null)).toBe('');
    expect(modelSwitch([{ route: 'hop 1', model: '', stop: 'timeout' }, { route: 'hop 2', model: '', stop: 'completed' }])).toBe(
      'hop 1 (timed out) → hop 2',
    );
  });
});
