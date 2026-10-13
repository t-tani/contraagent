import type { JournalRow, Outcome, Stop, TaskRow } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { attemptFacts, filterJournal, filterTasks, journalTally, sortTasks } from './filters.js';

const task = (key: string, kind: string, last_stop = 'completed', outcome: Outcome = 'done', last_ts = ''): TaskRow => ({
  key, kind, unit: key.split('-')[1] ?? '', executor: 'agent', outcome, attempts: [], tries: [], cause: null, deferred: '',
  pass: null, wall_s: 1, last_ts, last_stop, waits_for: [], extra_units: [],
});
const row = (key: string, kind: string, stop: Stop, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '', key, kind, stop, ok: stop === 'completed', ...extra,
});

describe('filterTasks', () => {
  const ts = [task('a-x', 'a'), task('b-y', 'b', 'timeout')];
  it('by kind and by text over kind, unit, key and last stop', () => {
    expect(filterTasks(ts, 'a', '').map((t) => t.key)).toEqual(['a-x']);
    expect(filterTasks(ts, '', 'TIME').map((t) => t.key)).toEqual(['b-y']);
    expect(filterTasks(ts, '', 'y').map((t) => t.key)).toEqual(['b-y']);
    expect(filterTasks(ts, '', '')).toHaveLength(2);
  });
});

describe('sortTasks', () => {
  it('failed, not started, running and waiting first; then the latest; a task that never ran stays in the list', () => {
    const ts = [
      task('a-1', 'a', 'completed', 'done', '2026-10-11T00:00:01'),
      task('a-2', 'a', '', 'waiting'),
      task('a-3', 'a', 'completed', 'recovered', '2026-10-11T00:00:03'),
      task('a-4', 'a', 'invalid_input', 'not_started', '2026-10-11T00:00:02'),
      task('a-5', 'a', 'error', 'failed', '2026-10-11T00:00:01'),
      task('a-6', 'a', '', 'not_started'),
    ];
    expect(sortTasks(ts).map((t) => t.key)).toEqual(['a-5', 'a-4', 'a-6', 'a-2', 'a-3', 'a-1']);
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
    row('r', 'review', 'invalid_input', { attempt: 0 }),
    row('r', 'review', 'completed', { attempt: 1 }),
  ];
  it("'fixup' keeps attempts whose output was sent back; 'retried' every row of a task retried after a failed try", () => {
    expect(filterJournal(rs, '', 'fixup', '').map((e) => e.key)).toEqual(['d']);
    expect(filterJournal(rs, '', 'retried', '').map((e) => e.key)).toEqual(['g', 'g']);
  });
});
