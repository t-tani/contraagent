// A task's extra units in words: by name up to two, then how many; the tooltip names them all.
import { describe, expect, it } from 'vitest';
import { alsoLocksNames, alsoLocksShort } from './units.js';

describe('alsoLocksShort', () => {
  it('names one or two units, and counts more', () => {
    expect(alsoLocksShort(['beta'])).toBe('Also locks beta');
    expect(alsoLocksShort(['beta', 'gamma'])).toBe('Also locks beta and gamma');
    expect(alsoLocksShort(['beta', 'gamma', 'delta'])).toBe('Also locks 3 units');
  });
  it('has a tooltip that names every unit', () => {
    expect(alsoLocksNames(['beta', 'gamma', 'delta'])).toBe(
      'Units this task locks while it runs, besides its own unit (extra_units) | beta, gamma, and delta',
    );
  });
});
