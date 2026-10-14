import { describe, expect, it } from 'vitest';
import { locksNames, locksShort } from './claims.js';

describe('locksShort', () => {
  it('names one or two claims, and counts more', () => {
    expect(locksShort(['topic:beta'])).toBe('Locks topic:beta');
    expect(locksShort(['topic:beta', 'topic:gamma'])).toBe('Locks topic:beta and topic:gamma');
    expect(locksShort(['topic:beta', 'topic:gamma', 'heavy'])).toBe('Locks 3 names');
  });
  it('names every claim in its tooltip', () => {
    expect(locksNames(['topic:beta', 'topic:gamma', 'heavy'])).toBe(
      'Names this task holds while it runs (claims) | topic:beta, topic:gamma, and heavy',
    );
  });
});
