import { describe, expect, it } from 'vitest';
import { accountReading, quotaStatusLabel, readingShort, resetsIn } from './quota-format.js';

describe('quota-format', () => {
  it('writes a reading with whole windows, and its account in words', () => {
    const r = { seven_day_pct: 41.4, five_hour_pct: 14, credential: 'ambient' };
    expect(readingShort(r)).toBe('weekly 41% | 5-hour 14%');
    expect(accountReading(r)).toBe('weekly 41% | 5-hour 14% | default');
  });

  it('maps a raw status to words', () => {
    expect([quotaStatusLabel('allowed'), quotaStatusLabel('allowed_warning'), quotaStatusLabel('rejected'), quotaStatusLabel('odd')]).toEqual([
      '',
      'near the limit',
      'limit reached',
      'unknown (odd)',
    ]);
  });

  it('counts down to a reset in the one duration format', () => {
    const now = Date.parse('2026-10-12T10:00:00Z');
    expect(resetsIn('2026-10-12T12:58:00Z', now)).toBe('resets in 2h 58m');
    expect(resetsIn('2026-10-12T09:00:00Z', now)).toBe('reset');
  });
});
