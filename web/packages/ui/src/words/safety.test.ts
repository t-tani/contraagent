import { describe, expect, it } from 'vitest';
import { localTime } from './format.js';
import { safetyPartLabel, safetyStopCount, safetyStopLine } from './safety.js';

describe('safetyStopLine', () => {
  it('names what was stopped in words, then only the facts the coding agent reported', () => {
    const ts = '2026-10-14T00:00:01+00:00';
    expect(safetyStopLine({ part: 'tool', ts, model: 'haiku', category: 'cyber', tool: 'WebFetch' })).toBe(
      `tool request | haiku | cyber | WebFetch | ${localTime(ts, true)}`,
    );
    expect(safetyStopLine({ part: 'response', model: 'opus' })).toBe('model response | opus');
    expect(safetyStopLine({ part: 'unread' })).toBe('unrecognized');
  });

  it('counts safety stops, one in the singular', () => {
    expect([safetyStopCount(1), safetyStopCount(3)]).toEqual(['1 safety stop', '3 safety stops']);
    expect(safetyPartLabel('other')).toBe('other');
  });
});
