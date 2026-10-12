import { describe, expect, it } from 'vitest';
import { loopPass, outcomeCounts, problems, taskOutcomes, taskRows } from './outcomes.js';
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

describe('taskRows', () => {
  it('one row per task of the plan, a task that never ran included: as many as outcomeCounts counts', () => {
    const rows = taskRows(journal, plan);
    expect(rows.map((t) => t.key)).toEqual(plan.nodes.map((n) => n.key));
    expect(rows).toHaveLength(outcomeCounts(taskOutcomes(journal, plan)).total);
    const w = rows.find((t) => t.key === 'write-a');
    expect(w).toMatchObject({ outcome: 'waiting', tries: [], wall_s: 0, last_ts: '', last_stop: '' });
    const r = rows.find((t) => t.key === 'review-z');
    expect(r).toMatchObject({ outcome: 'not_started', cause: 'prepare-z', last_stop: 'invalid_input', tries: [] });
  });

  it('a loop pass per task: two tasks of one kind and unit are two rows', () => {
    const at = (pass: number | null) => [{ function: 'f', file: 'f.py', line: 1, loops: [{ line: 3, pass }] }];
    const p: Plan = {
      nodes: [
        { ...node('review-g', 'done'), flow: at(1) },
        { ...node('fix-g', 'done', ['review-g']), flow: at(1) },
        { ...node('review-g~2', 'pending', ['fix-g']), unit: 'g', flow: at(2) },
        { ...node('late-g', 'pending', ['review-g~2', 'gone-g']), flow: [] },
      ],
      groups: [],
    };
    const j = [{ ...row('review-g', 'completed'), unit: 'g', wall_s: 2 }, { ...row('fix-g', 'completed'), wall_s: 1.5 }];
    const rows = taskRows(j, p);
    expect(rows.map((t) => [t.key, t.unit, t.pass, t.outcome])).toEqual([
      ['review-g', 'g', 1, 'done'],
      ['fix-g', 'g', 1, 'done'],
      ['review-g~2', 'g', 2, 'waiting'],
      ['late-g', 'g', null, 'waiting'],
    ]);
    expect(rows[0]?.wall_s).toBe(2);
    expect(rows[2]?.waits_for).toEqual([]);
    expect(rows[3]?.waits_for).toEqual(['review-g~2', 'gone-g']);
    expect(outcomeCounts(taskOutcomes(j, p)).total).toBe(4);
  });

  it('loopPass: the innermost loop of the last frame in a loop; a pass not counted is the first', () => {
    expect(loopPass(undefined)).toBeNull();
    expect(loopPass({ flow: [] })).toBeNull();
    expect(loopPass({ flow: [{ function: 'f', file: '', line: 1, loops: [{ line: 2, pass: 3 }] }, { function: 'g', file: '', line: 1, loops: [] }] })).toBe(3);
    expect(loopPass({ flow: [{ function: 'f', file: '', line: 1, loops: [{ line: 2, pass: 2 }, { line: 5, pass: null }] }] })).toBe(1);
  });
});
