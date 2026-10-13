import { describe, expect, it } from 'vitest';
import { planStateLabel } from './outcome.js';

describe('outcome', () => {
  it('tells a waiting task from one that did not start', () => {
    expect(planStateLabel('pending')).toBe('waiting');
    expect(planStateLabel('blocked')).toBe('not started');
    expect(planStateLabel('done')).toBe('done');
  });
});
