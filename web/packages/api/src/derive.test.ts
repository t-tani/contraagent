import { describe, expect, it } from 'vitest';
import { deriveRun, elapsedS, progress, result, tryCounts } from './derive.js';
import { emptyRunState, reduceRun } from './run-state.js';
import type { JournalRow, Plan, PlanGroup, PlanNode, Stop } from './types.js';

const row = (key: string, stop: Stop, attempt = 0): JournalRow => ({
  ts: `2026-10-11T00:00:0${attempt}`, key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', attempt,
});
const node = (key: string, state: PlanNode['state'], after: string[] = []): PlanNode => ({
  key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', after, state, level: 0, group: key.split('-')[0]!,
});
const group = (id: string, counts: Partial<PlanGroup> = {}): PlanGroup => ({
  id, label: id, total: 0, done: 0, failed: 0, running: 0, pending: 0, skipped: 0, blocked: 0, ...counts,
});

// A run with every way a task ends: done, done after retrying (a failed try),
// done after a refusal (not a try: done), skipped, failed, not started, waiting.
const plan: Plan = {
  nodes: [
    node('prep-a', 'done'),
    node('prep-b', 'done'),
    node('prep-c', 'done'),
    node('prep-d', 'skipped'),
    node('review-a', 'failed', ['prep-a']),
    node('review-b', 'blocked', ['review-a']),
    node('review-c', 'pending', ['prep-c']),
  ],
  groups: [],
};
const journal: JournalRow[] = [
  row('prep-a', 'completed'),
  row('prep-b', 'error', 0),
  row('prep-b', 'completed', 1),
  row('prep-c', 'invalid_input', 0),
  row('prep-c', 'completed', 1),
  row('prep-d', 'skipped'),
  row('review-a', 'error'),
  row('review-b', 'invalid_input'),
];

/**
 * The server's count for the run list (`RunSummary.tasks`), as
 * `contraagent/monitor/core.py: MonitorCore._task_counts` computes it: one
 * per plan node, by plan state; `done` there is plan state `done`, which
 * includes the tasks done after retrying.
 */
function serverTaskCounts(p: Plan) {
  const counts = { total: 0, done: 0, failed: 0, not_started: 0, running: 0, waiting: 0, skipped: 0 };
  const name: Partial<Record<PlanNode['state'], keyof typeof counts>> = { done: 'done', failed: 'failed', blocked: 'not_started', skipped: 'skipped' };
  for (const n of p.nodes) {
    counts.total++;
    counts[name[n.state] ?? 'waiting']++;
  }
  return counts;
}

describe('deriveRun', () => {
  it('counts tasks: done is done and done after retrying; skipped is apart', () => {
    const d = deriveRun(journal, plan);
    expect(d.counts).toMatchObject({ total: 7, done: 2, recovered: 1, skipped: 1, failed: 1, not_started: 1, waiting: 1, doneTotal: 3, finished: 4 });
    expect(d.outcomes.get('prep-c')?.outcome).toBe('done');
    expect(d.outcomes.get('prep-b')?.outcome).toBe('recovered');
  });

  it('"N of M tasks done" is the server\'s figure', () => {
    const d = deriveRun(journal, plan);
    const s = serverTaskCounts(plan);
    expect(d.counts.doneTotal).toBe(s.done);
    expect(d.counts.total).toBe(s.total);
    expect(d.counts.skipped).toBe(s.skipped);
  });

  it('lists rows, problems, kinds and tries', () => {
    const d = deriveRun(journal, plan);
    expect(d.rows.map((t) => t.key)).toEqual(plan.nodes.map((n) => n.key));
    expect(d.rows.find((t) => t.key === 'review-c')?.waits_for).toEqual([]);
    expect(d.problems.failed.map((p) => [p.task.key, p.stopped.map((t) => t.key)])).toEqual([['review-a', ['review-b']]]);
    expect(d.problems.recovered.map((t) => t.key)).toEqual(['prep-b']);
    expect(d.kinds).toEqual(['prep', 'review']);
    expect(d.tries).toEqual({ tries: 5, notStarted: 3 });
  });

  it('is computed once per journal and plan', () => {
    const d = deriveRun(journal, plan);
    expect(deriveRun(journal, plan)).toBe(d);
    expect(deriveRun(journal, { ...plan })).not.toBe(d);
    expect(deriveRun([...journal], plan)).not.toBe(d);
    expect(deriveRun(journal)).toBe(deriveRun(journal, null));
    expect(deriveRun(journal).counts.total).toBe(6);
  });

  it('a new journal row is a new journal: the run state copies it per batch', () => {
    const s0 = reduceRun(emptyRunState(), [{ event: 'plan', data: plan }, { event: 'journal', data: journal[0]! }]);
    const d0 = deriveRun(s0.journal, s0.plan);
    const s1 = reduceRun(s0, [{ event: 'journal', data: journal[1]! }]);
    expect(s1.journal).not.toBe(s0.journal);
    expect(s1.plan).toBe(s0.plan);
    const d1 = deriveRun(s1.journal, s1.plan);
    expect(d1).not.toBe(d0);
    expect(d1.outcomes.get('prep-b')?.outcome).toBe('failed');
  });
});

describe('progress', () => {
  it('counts done and skipped apart; both are finished', () => {
    expect(progress({ nodes: [], groups: [group('a', { total: 4, done: 1, skipped: 1 }), group('b', { total: 4 })] })).toEqual({
      total: 8, done: 1, skipped: 1, pct: 25,
    });
    expect(progress({ nodes: [], groups: [] }).pct).toBe(0);
  });
});

describe('run result', () => {
  it('counts how the scheduled tasks ended', () => {
    expect(result(plan)).toEqual({ done: 3, skipped: 1, failed: 1, notStarted: 1, left: 1 });
  });

  it('counts tries and tasks that never started the one way the UI shows them', () => {
    expect(tryCounts([row('a', 'completed'), row('b', 'invalid_input'), row('c', 'error')])).toEqual({ tries: 2, notStarted: 1 });
  });

  it('measures a run from its start to its last activity', () => {
    expect(elapsedS({ started_at: '2026-10-11T10:00:00Z', last_ts: '2026-10-11T10:00:07Z' })).toBe(7);
    expect(elapsedS({ started_at: '', last_ts: '2026-10-11T10:00:07Z' })).toBeNull();
  });
});
