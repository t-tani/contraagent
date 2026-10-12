import { describe, expect, it } from 'vitest';
import { runAccounts, runReadings, tryQuota } from './quota.js';
import type { JournalRow, QuotaReading } from './types.js';

const q = (time: string, five: number, week = 40, credential = 'sub'): QuotaReading => ({
  observed_at: `2026-10-11T00:00:${time}+00:00`, credential, five_hour_pct: five, seven_day_pct: week, status: 'allowed',
});
const row = (key: string, ended: string, quota: QuotaReading[], attempt = 0): JournalRow => ({
  ts: `2026-10-11T00:00:${ended}+00:00`, key, kind: key, stop: 'completed', ok: true, attempt, quota,
});

describe('quota', () => {
  // Two tasks in parallel, then a third; b had a fix-up (a second session start).
  const journal = [row('a', '05', [q('01', 10)]), row('b', '06', [q('02', 11), q('04', 13)]), row('c', '09', [q('07', 15)]), row('p', '03', [])];

  it('orders every reading of the run by when it arrived', () => {
    expect(runReadings(journal).map((r) => [r.key, r.reading.five_hour_pct])).toEqual([['a', 10], ['b', 11], ['b', 13], ['c', 15]]);
    expect(runAccounts(journal)).toMatchObject([{ credential: 'sub', first: { five_hour_pct: 10 }, last: { five_hour_pct: 15 } }]);
    expect(runAccounts([row('p', '03', [])])).toEqual([]);
  });

  it('gives a try its start reading and the next one observed after it ended', () => {
    const all = runReadings(journal);
    expect(tryQuota(journal[0]!, all)).toMatchObject({ start: { five_hour_pct: 10 }, next: { five_hour_pct: 15 } });
    expect(tryQuota(journal[1]!, all)).toMatchObject({ start: { five_hour_pct: 11 }, next: { five_hour_pct: 15 } });
    expect(tryQuota(journal[2]!, all)).toEqual({ start: { ...q('07', 15) }, next: null });
    expect(tryQuota(journal[3]!, all)).toMatchObject({ start: null });
  });

  it('keeps accounts apart: first/last per account, the busiest weekly first; next reading of the same account only', () => {
    const two = [
      row('x', '03', [q('01', 10, 30, 'sub-a')]),
      row('y', '04', [q('02', 50, 70, 'sub-b')]),
      row('z', '08', [q('05', 12, 31, 'sub-a'), q('06', 55, 72, 'sub-b')]),
    ];
    expect(runAccounts(two).map((a) => [a.credential, a.first.seven_day_pct, a.last.seven_day_pct])).toEqual([
      ['sub-b', 70, 72],
      ['sub-a', 30, 31],
    ]);
    const all = runReadings(two);
    expect(tryQuota(two[0]!, all).next).toMatchObject({ credential: 'sub-a', five_hour_pct: 12 });
    expect(tryQuota(two[1]!, all).next).toMatchObject({ credential: 'sub-b', five_hour_pct: 55 });
  });
});
