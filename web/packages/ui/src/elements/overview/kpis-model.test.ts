import type { JournalRow } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { kpis } from './kpis-model.js';

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
