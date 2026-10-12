import { describe, expect, it } from 'vitest';
import { outcomeCounts, problems, taskOutcomes } from './outcomes.js';
import type { JournalRow, Plan, PlanNode } from './types.js';

const row = (key: string, stop: string, attempt = 0): JournalRow => ({
  ts: `2026-10-11T00:00:0${attempt}`, key, kind: key.split('-')[0]!, stop, ok: stop === 'completed', attempt,
});
const node = (key: string, state: PlanNode['state'], after: string[] = []): PlanNode => ({
  key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', after, state, level: 0, group: key.split('-')[0]!,
});

// The demo's shape: prepare-z raised, so summarize-z and review-z were refused;
// review-g failed twice and then succeeded.
const plan: Plan = {
  nodes: [
    node('prepare-z', 'failed'),
    node('summarize-z', 'blocked', ['prepare-z']),
    node('review-z', 'blocked', ['summarize-z']),
    node('review-g', 'done'),
    node('write-a', 'pending'),
    node('note-x', 'blocked', ['missing-upstream']),
  ],
  groups: [],
};
const journal = [
  row('prepare-z', 'error'),
  row('summarize-z', 'invalid_input'),
  row('review-z', 'invalid_input'),
  row('review-g', 'error', 0),
  row('review-g', 'error', 1),
  row('review-g', 'completed', 2),
  row('note-x', 'invalid_input'),
];

describe('taskOutcomes', () => {
  const o = taskOutcomes(journal, plan);

  it('names what happened to each task', () => {
    expect(Object.fromEntries([...o].map(([k, t]) => [k, t.outcome]))).toEqual({
      'prepare-z': 'failed',
      'summarize-z': 'not_started',
      'review-z': 'not_started',
      'review-g': 'recovered',
      'write-a': 'waiting',
      'note-x': 'not_started',
    });
    expect(o.get('review-g')?.attempts).toHaveLength(3);
  });

  it('traces a task that did not start to the failed task upstream', () => {
    expect(o.get('review-z')?.cause).toBe('prepare-z');
    expect(o.get('note-x')?.cause).toBeNull();
  });

  it('lists problems causes first, without the tasks that recovered', () => {
    const p = problems(o);
    expect(p.failed.map((x) => [x.task.key, x.stopped.map((s) => s.key)])).toEqual([['prepare-z', ['summarize-z', 'review-z']]]);
    expect(p.notStarted.map((t) => t.key)).toEqual(['note-x']);
  });

  it('counts tasks, not attempts', () => {
    expect(outcomeCounts(o)).toMatchObject({ total: 6, done: 0, recovered: 1, failed: 1, not_started: 3, waiting: 1 });
  });
});
