import { describe, expect, it } from 'vitest';
import { outcomeLabel, planStateLabel, stateCount } from './outcome.js';
import { stopLabel } from './stop.js';

describe('outcome', () => {
  it('tells a waiting task from one that did not start', () => {
    expect(planStateLabel('pending')).toBe('waiting');
    expect(planStateLabel('blocked')).toBe('not started');
    expect(planStateLabel('done')).toBe('done');
  });

  it('names a partial task and attempt as partly done, counted apart', () => {
    expect(planStateLabel('partial')).toBe('partly done');
    expect(outcomeLabel('partial')).toBe('partly done');
    expect(stopLabel('partial')).toBe('partly done');
    expect(stateCount('partial', 2)).toBe('2 partly done');
  });
});
