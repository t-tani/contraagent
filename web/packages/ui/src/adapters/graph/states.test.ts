import { describe, expect, it } from 'vitest';
import { node } from './plans.fixture.js';
import { worstState } from './states.js';

describe('worstState', () => {
  it('of nothing is done, else the most severe', () => {
    expect(worstState([])).toBe('done');
    expect(worstState([node('x', '', 'a', 'skipped'), node('y', '', 'a', 'blocked')])).toBe('blocked');
  });
});
