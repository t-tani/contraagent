import { deriveRun, type JournalRow, type Stop } from '@contraagent/api';
import type { StatTile } from '@contraagent/elements/tiles';
import { describe, expect, it } from 'vitest';
import { kpiAction, kpiTiles, kpis } from './kpi-tiles.js';

const row = (key: string, extra: Partial<JournalRow> = {}): JournalRow => ({
  ts: '2026-10-11T10:00:00Z', key, kind: 'k', stop: 'completed', ok: true, ...extra,
});

describe('kpis', () => {
  it('counts tries that ran: a refusal is no try, no session and no failure', () => {
    const k = kpis([
      row('a', { wall_s: 2 }),
      row('b', { executor: 'python', wall_s: 1 }),
      row('c', { stop: 'timeout', ok: false, wall_s: 1 }),
      row('c', { attempt: 1, rounds: 3, hops: [{}, {}] }),
      row('d', { stop: 'invalid_input', ok: false }),
    ]);
    expect(k).toEqual({
      attempts: 4, python: 1, launches: 3, bad: 1, launchWall: 3, pythonWall: 1,
      retries: 1, retriedTasks: 1, fixups: 2, fixupTasks: 1, switches: 1, switchTasks: 1,
      retriedKeys: ['c'], fixupKeys: ['c'],
    });
  });

  it('counts a retry only after a try that ran and failed: refused, then done, is no retry', () => {
    const k = kpis([row('a', { stop: 'invalid_input', ok: false }), row('a', { attempt: 1 })]);
    expect(k).toMatchObject({ attempts: 1, bad: 0, retries: 0, retriedTasks: 0, retriedKeys: [] });
  });
});

// The tiles: neutral by default; only a problem count above 0 takes a status colour.
describe('kpiTiles', () => {
  const r = (key: string, stop: Stop, extra: Partial<JournalRow> = {}): JournalRow => ({
    ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', wall_s: 1.5,
    executor: 'agent', cost_usd: 0.01, ...extra,
  });
  const tiles = (journal: JournalRow[]) => new Map(kpiTiles(journal, deriveRun(journal)).map((t) => [t.id, t]));
  const line = (t: StatTile | undefined) =>
    (t?.sub ?? [])
      .flat()
      .map((f) => (typeof f === 'string' ? f : f.text))
      .filter(Boolean)
      .join(' | ');

  it('keeps the total neutral when a task failed, and colours the failed count', () => {
    const t = tiles([r('prepare-a', 'completed'), r('prepare-b', 'error'), r('review-a', 'completed', { hops: [{ model: 'a', stop: 'rate_limited' }, { model: 'b', stop: 'completed' }] as JournalRow['hops'] })]);
    expect(t.get('tasks')?.tone).toBeUndefined();
    expect(t.get('tasks')?.sub?.[0]).toContainEqual({ text: '1 failed', tone: 'failed' });
    expect(t.get('bad')?.tone).toBe('failed');
    expect(t.get('bad')?.action?.id).toBe('history:bad');
    // measures and counts that are not problems never take a colour
    for (const id of ['attempts', 'cost', 'tokens', 'wall', 'retry', 'ct', 'fo']) expect(t.get(id)?.tone ?? 'neutral', id).toBe('neutral');
  });

  it('shows a 0 of a problem neutral, with its words', () => {
    const t = tiles([r('prepare-a', 'completed')]);
    expect(t.get('bad')?.tone).toBe('neutral');
    expect(line(t.get('bad'))).toContain('All attempts done');
    expect(t.get('notstarted')?.tone).toBe('neutral');
    expect(t.get('bad')?.action).toBeUndefined();
  });

  it('counts done and done after retrying as done; skipped apart; a refusal then done is done', () => {
    const t = tiles([
      r('prepare-a', 'completed'),
      r('prepare-b', 'error'),
      r('prepare-b', 'completed', { attempt: 1 }),
      r('prepare-c', 'invalid_input'),
      r('prepare-c', 'completed', { attempt: 1 }),
      r('prepare-d', 'skipped'),
    ]);
    expect(line(t.get('tasks'))).toContain('3 done');
    expect(line(t.get('tasks'))).toContain('1 skipped');
    // one retried task: its link opens it
    expect(t.get('retry')?.action).toEqual({ id: 'task:prepare-b', label: 'prepare · b' });
  });

  it('marks tasks not started as attention, with the cause', () => {
    const t = tiles([r('prepare-a', 'completed'), r('summarize-a', 'invalid_input', { reason: 'invalid input: x.json: required input is missing' })]);
    expect(t.get('notstarted')?.tone).toBe('attention');
    expect(line(t.get('notstarted'))).toBe('Input missing');
    expect(t.get('tasks')?.tone).toBeUndefined();
  });
});

describe('kpiAction', () => {
  it('opens one task, or the history filtered by a stop', () => {
    expect(kpiAction('task:a-b:c')).toEqual({ key: 'a-b:c' });
    expect(kpiAction('history:invalid_input')).toEqual({ stop: 'invalid_input' });
  });
});
