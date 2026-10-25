import { describe, expect, it } from 'vitest';
import { isFinished, latestTask, loopPass, outcomeCounts, outcomeOf, planOutcome, problems, retries, taskOutcomes, taskRows } from './outcomes.js';
import type { JournalRow, Plan, PlanNode, Stop } from './types.js';

const row = (key: string, stop: Stop, attempt = 0): JournalRow => ({
  ts: `2026-10-11T00:00:0${attempt}`, key, kind: key.split('-')[0]!, stop, ok: stop === 'completed' || stop === 'partial', attempt,
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

describe('outcomeOf', () => {
  it('a refusal is not a failed attempt: not started, then done, is done', () => {
    expect(outcomeOf({ state: 'done' }, [row('a', 'invalid_input', 0), row('a', 'completed', 1)])).toBe('done');
  });

  it('a try that ran and failed, then done, is done after retrying', () => {
    expect(outcomeOf({ state: 'done' }, [row('a', 'error', 0), row('a', 'completed', 1)])).toBe('recovered');
    expect(outcomeOf({ state: 'done' }, [row('a', 'invalid_input', 0), row('a', 'timeout', 1), row('a', 'completed', 2)])).toBe('recovered');
  });

  it('a partial last attempt is partly done: ok, and neither done nor failed', () => {
    expect(outcomeOf({ state: 'partial' }, [row('a', 'partial')])).toBe('partial');
    expect(outcomeOf({ state: 'partial' }, [row('a', 'error', 0), row('a', 'partial', 1)])).toBe('partial');
    expect(outcomeOf({ state: 'done' }, [row('a', 'partial', 0), row('a', 'completed', 1)])).toBe('done');
    const o = taskOutcomes([row('a', 'partial')], { nodes: [node('a', 'partial')], groups: [] });
    expect(outcomeCounts(o)).toMatchObject({ partial: 1, done: 0, failed: 0, total: 1 });
    expect(problems(o).partial.map((t) => t.key)).toEqual(['a']);
  });

  it('without rows, the plan state decides', () => {
    expect(outcomeOf(undefined, [])).toBe('waiting');
    expect(outcomeOf({ state: 'blocked' }, [])).toBe('not_started');
    expect(outcomeOf({ state: 'running' }, [row('a', 'error')])).toBe('running');
    expect(outcomeOf(undefined, [row('a', 'skipped')])).toBe('skipped');
  });
});

describe('retries', () => {
  it('a retry is a try that ran after a try of the same task ran and failed', () => {
    expect(retries(journal).map((r) => [r.key, r.attempt])).toEqual([
      ['review-g', 1],
      ['review-g', 2],
    ]);
  });

  it('a try after a refusal is no retry, as in outcomeOf', () => {
    expect(retries([row('a', 'invalid_input', 0), row('a', 'completed', 1)])).toEqual([]);
    expect(retries([row('a', 'invalid_input', 0), row('a', 'timeout', 1), row('a', 'completed', 2)]).map((r) => r.attempt)).toEqual([2]);
  });
});

describe('planOutcome', () => {
  it('names a plan state as an outcome', () => {
    expect(planOutcome('blocked')).toBe('not_started');
    expect(planOutcome('pending')).toBe('waiting');
    expect(planOutcome('done')).toBe('done');
    expect(planOutcome('skipped')).toBe('skipped');
  });

  it('finished: done, done after retrying, partly done, skipped', () => {
    expect((['done', 'recovered', 'partial', 'skipped', 'failed', 'not_started', 'running', 'waiting'] as const).filter(isFinished)).toEqual([
      'done', 'recovered', 'partial', 'skipped',
    ]);
    expect(planOutcome('partial')).toBe('partial');
  });
});

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
    expect(p.recovered.map((t) => t.key)).toEqual(['review-g']);
  });

  it('counts tasks, not attempts', () => {
    expect(outcomeCounts(o)).toMatchObject({ total: 6, done: 0, recovered: 1, failed: 1, not_started: 3, waiting: 1 });
  });
});

describe('taskRows', () => {
  it('one row per task of the plan, a task that never ran included: as many as outcomeCounts counts', () => {
    const rows = taskRows(taskOutcomes(journal, plan), plan);
    expect(rows.map((t) => t.key)).toEqual(plan.nodes.map((n) => n.key));
    expect(rows).toHaveLength(outcomeCounts(taskOutcomes(journal, plan)).total);
    const w = rows.find((t) => t.key === 'write-a');
    expect(w).toMatchObject({ outcome: 'waiting', tries: [], wall_s: 0, last_ts: '', last_stop: '' });
    const r = rows.find((t) => t.key === 'review-z');
    expect(r).toMatchObject({ outcome: 'not_started', cause: 'prepare-z', last_stop: 'invalid_input', tries: [] });
  });

  it("a task's claims from its plan node; none for a node without them", () => {
    const p: Plan = { nodes: [{ ...node('merge-a', 'pending'), claims: ['topic:a', 'topic:b'] }, node('write-a', 'pending')], groups: [] };
    const rows = taskRows(taskOutcomes([], p), p);
    expect(rows.map((t) => t.claims)).toEqual([['topic:a', 'topic:b'], []]);
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
    const rows = taskRows(taskOutcomes(j, p), p);
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

  it('latestTask: a running agent task first, else the agent task that ran last; a pass is its own task; never a Python task', () => {
    const at = (key: string, ts: string, executor: 'agent' | 'python' = 'agent'): JournalRow => ({ ...row(key, 'completed'), ts, executor });
    const p: Plan = {
      nodes: [node('review-g', 'done'), node('review-g~2', 'done'), node('prep-g', 'done'), node('write-a', 'pending')],
      groups: [],
    };
    const j = [at('review-g', '1'), at('review-g~2', '3'), at('prep-g', '9', 'python')];
    expect(latestTask(taskRows(taskOutcomes(j, p), p))).toBe('review-g~2');
    const live: Plan = { ...p, nodes: p.nodes.map((n) => (n.key === 'review-g' ? { ...n, state: 'running' as const } : n)) };
    expect(latestTask(taskRows(taskOutcomes(j, live), live))).toBe('review-g');
    expect(latestTask(taskRows(taskOutcomes([], p), p))).toBeNull();
  });
});

describe('taskOutcomes causes', () => {
  // A walk of each task's own: depth first from the task, each task visited once.
  const walk = (plan: Plan, out: Map<string, { outcome: string }>, key: string): string | null => {
    const nodes = new Map(plan.nodes.map((n) => [n.key, n]));
    const seen = new Set<string>();
    const rootOf = (k: string): string | null => {
      for (const dep of nodes.get(k)?.after ?? []) {
        if (seen.has(dep)) continue;
        seen.add(dep);
        const d = out.get(dep);
        if (d?.outcome === 'failed') return dep;
        if (d?.outcome === 'not_started') {
          const r = rootOf(dep);
          if (r) return r;
        }
      }
      return null;
    };
    return rootOf(key);
  };
  const random = (seed: number) => () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
  const states: PlanNode['state'][] = ['blocked', 'blocked', 'blocked', 'failed', 'done', 'pending'];

  it('names the cause a walk from each task names, on random plans with and without cycles', () => {
    for (let s = 1; s <= 300; s++) {
      const r = random(s);
      const n = 2 + Math.floor(r() * 30);
      const cyclic = s % 3 === 0;
      const keys = Array.from({ length: n }, (_, i) => `k${i}`);
      const plan: Plan = {
        nodes: keys.map((k, i) => {
          const after: string[] = [];
          const m = Math.floor(r() * 4);
          for (let j = 0; j < m; j++) {
            const to = Math.floor(r() * n);
            if (cyclic ? to !== i : to < i) after.push(`k${to}`);
          }
          if (r() < 0.1) after.push('missing');
          return node(k, states[Math.floor(r() * states.length)]!, after);
        }),
        groups: [],
      };
      const out = taskOutcomes([], plan);
      for (const t of out.values()) if (t.outcome === 'not_started') expect(t.cause, `seed ${s}, ${t.key}`).toBe(walk(plan, out, t.key));
    }
  });
});
