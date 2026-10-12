import { describe, expect, it } from 'vitest';
import { rowSpend, spendByKind, spendByTask, spendOf, totalTokens } from './spend.js';
import type { JournalRow } from './types.js';

const row = (key: string, kind: string, cost: number | null, input = 0, output = 0): JournalRow => ({
  ts: '2026-10-11T00:00:00', key, kind, stop: 'completed', ok: true,
  ...(cost === null ? {} : { cost_usd: cost }),
  ...(input || output ? { usage: { input, output, cache_read: 10, cache_creation: 5, calls: 1 } } : {}),
});

describe('spend', () => {
  const journal = [
    row('s-a', 's', 0.03, 100, 20),
    row('s-a', 's', 0.01, 50, 10), // a retry of the same task
    row('r-a', 'r', 0.02, 80, 30),
    row('python:p', 'p', null), // a Python task: reports nothing
  ];

  it('adds tokens and cost, and is null when nothing was reported', () => {
    expect(spendOf(journal)).toMatchObject({ input: 230, output: 60, cache_read: 30, cache_creation: 15, calls: 3, reported: 3 });
    expect(spendOf(journal)?.cost).toBeCloseTo(0.06);
    expect(rowSpend(row('python:p', 'p', null))).toBeNull();
    expect(totalTokens(spendOf(journal)!)).toBe(335);
  });

  it('groups per task and per kind, most expensive first, with the share of the run', () => {
    expect(spendByTask(journal).map((g) => [g.id, Number(g.spend.cost?.toFixed(2))])).toEqual([['s-a', 0.04], ['r-a', 0.02]]);
    const kinds = spendByKind(journal);
    expect(kinds.map((g) => g.id)).toEqual(['s', 'r']);
    expect(kinds[0]?.share).toBeCloseTo(2 / 3);
  });
});
