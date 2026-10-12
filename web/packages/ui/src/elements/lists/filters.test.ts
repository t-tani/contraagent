import type { JournalRow, TaskRollup } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { attemptFacts, filterJournal, filterTasks, journalTally, rollupOutcome } from './filters.js';

const task = (slot: string, kind: string, last_stop = 'completed'): TaskRollup => ({
  slot, kind, unit: '', executor: 'agent', attempts: 1, ok: 1, last_stop, last_ts: '', wall_s: 1,
});
const row = (key: string, kind: string, stop: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '', key, kind, stop, ok: stop === 'completed', ...extra,
});

describe('filterTasks', () => {
  const ts = [task('a-x', 'a'), task('b-y', 'b', 'timeout')];
  it('by kind and by text over slot and last stop', () => {
    expect(filterTasks(ts, 'a', '').map((t) => t.slot)).toEqual(['a-x']);
    expect(filterTasks(ts, '', 'TIME').map((t) => t.slot)).toEqual(['b-y']);
    expect(filterTasks(ts, '', '')).toHaveLength(2);
  });
});

describe('filterJournal', () => {
  const rs = [row('1', 'a', 'completed'), row('2', 'a', 'timeout', { reason: 'slow' }), row('3', 'b', 'skipped'), row('4', 'b', 'error')];
  it('bad keeps every attempt that did not complete', () => {
    expect(filterJournal(rs, '', 'bad', '').map((e) => e.key)).toEqual(['2', '4']);
  });
  it('an exact stop, a kind and a text', () => {
    expect(filterJournal(rs, '', 'skipped', '').map((e) => e.key)).toEqual(['3']);
    expect(filterJournal(rs, 'b', '', '').map((e) => e.key)).toEqual(['3', '4']);
    expect(filterJournal(rs, '', '', 'SLOW').map((e) => e.key)).toEqual(['2']);
  });
});

describe('journalTally', () => {
  it('counts per stop, most frequent first', () => {
    expect(journalTally([row('1', 'a', 'error'), row('2', 'a', 'completed'), row('3', 'a', 'completed')])).toEqual([
      ['completed', 2],
      ['error', 1],
    ]);
  });
});

describe('rollupOutcome', () => {
  it('names a task by how it ended', () => {
    expect(rollupOutcome(task('a', 'a'))).toBe('done');
    expect(rollupOutcome({ ...task('a', 'a'), attempts: 3, ok: 1 })).toBe('recovered');
    expect(rollupOutcome(task('a', 'a', 'invalid_input'))).toBe('not_started');
    expect(rollupOutcome({ ...task('a', 'a', 'error'), ok: 0 })).toBe('failed');
    expect(rollupOutcome({ ...task('a', 'a'), running: true })).toBe('running');
  });
});

describe('attemptFacts', () => {
  it('counts attempts per task and finds the last success', () => {
    const f = attemptFacts([row('k', 'k', 'error'), row('k', 'k', 'completed'), row('j', 'j', 'error')]);
    expect(f.get('k')).toEqual({ count: 2, lastOk: 1, lastOkTry: 1 });
    expect(f.get('j')).toEqual({ count: 1, lastOk: -1, lastOkTry: 0 });
    // A refusal is not a try.
    expect(attemptFacts([row('r', 'r', 'invalid_input')]).get('r')?.count).toBe(0);
  });
});

describe('fix-up and retry filters', () => {
  const rs = [
    row('d', 'summarize', 'completed', { rounds: 2 }),
    row('g', 'review', 'error', { attempt: 0 }),
    row('g', 'review', 'completed', { attempt: 1 }),
    row('z', 'review', 'invalid_input'),
    row('z', 'review', 'invalid_input'),
  ];
  it("'fixup' keeps attempts whose output was sent back; 'retried' every row of a task that ran twice", () => {
    expect(filterJournal(rs, '', 'fixup', '').map((e) => e.key)).toEqual(['d']);
    expect(filterJournal(rs, '', 'retried', '').map((e) => e.key)).toEqual(['g', 'g']);
  });
});
