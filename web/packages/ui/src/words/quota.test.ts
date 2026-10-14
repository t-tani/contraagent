import { describe, expect, it } from 'vitest';
import { accountLabel, accountReading, quotaStatusLabel, readingShort, readingTip, resetsIn, windowName } from './quota.js';

describe('quota words', () => {
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

  it('names the window a status is about, and a model\'s own window', () => {
    expect(quotaStatusLabel('allowed_warning', 'seven_day')).toBe('near the limit | weekly');
    expect(quotaStatusLabel('allowed', 'five_hour')).toBe('');
    expect([windowName('five_hour'), windowName('seven_day'), windowName('seven_day_opus'), windowName('odd')]).toEqual([
      '5-hour',
      'weekly',
      'weekly (opus)',
      'odd',
    ]);
  });

  it('writes the rest of a reading in its tooltip: other windows, threshold, extra usage, account', () => {
    const tip = readingTip({
      seven_day_pct: 98,
      five_hour_pct: 6,
      status: 'allowed_warning',
      status_window: 'seven_day',
      threshold_pct: 75,
      overage_status: 'rejected',
      account: '3f9c2a1b7d10',
      windows: { seven_day: { pct: 98 }, five_hour: { pct: 6 }, seven_day_opus: { pct: 30 } },
    });
    expect(tip).toContain('Weekly (opus) usage 30%');
    expect(tip).toContain('Status: near the limit | weekly');
    expect(tip).toContain('Warning threshold: 75%');
    expect(tip).toContain('Extra usage: not allowed');
    expect(tip).toContain('Account: 3f9c2a1b7d10');
    expect(accountLabel('3f9c2a1b7d10')).toBe('account 3f9c2a');
  });

  it('counts down to a reset in the one duration format', () => {
    const now = Date.parse('2026-10-12T10:00:00Z');
    expect(resetsIn('2026-10-12T12:58:00Z', now)).toBe('resets in 2h 58m');
    expect(resetsIn('2026-10-12T09:00:00Z', now)).toBe('reset');
  });
});
