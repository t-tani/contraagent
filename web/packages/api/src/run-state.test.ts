import { describe, expect, it } from 'vitest';
import { JOURNAL_CAP, emptyRunState, isBad, liveActivities, reduceRun, runStarts, type RunAction } from './run-state.js';
import type { JournalRow, Plan, Procs } from './types.js';

const row = (key: string, stop = 'completed'): JournalRow => ({ ts: `2026-10-11T00:00:${key}`, key, kind: 'k', stop, ok: stop === 'completed' });

describe('reduceRun', () => {
  it('appends journal rows and keeps only the newest JOURNAL_CAP', () => {
    const msgs: RunAction[] = Array.from({ length: JOURNAL_CAP + 5 }, (_, i) => ({ event: 'journal', data: row(String(i)) }));
    const s = reduceRun(emptyRunState(), msgs);
    expect(s.journal).toHaveLength(JOURNAL_CAP);
    expect(s.journal[0]?.key).toBe('5');
  });

  it('starts the journal over on reconnect, and is ready after `ready`', () => {
    let s = reduceRun(emptyRunState(), [{ event: 'journal', data: row('1') }, { event: 'ready', data: { journal: 1 } }]);
    expect(s.ready).toBe(true);
    s = reduceRun(s, [{ event: 'connected' }]);
    expect(s).toMatchObject({ journal: [], ready: false });
  });

  it('keeps each panel under its name and replaces the other views', () => {
    const outputs = { contracts: [], tally: { valid: 1, invalid: 0, refused: 0, pending: 0, failed: 0, running: 0 } };
    const s = reduceRun(emptyRunState(), [
      { event: 'panel:facts', data: { n: 1 } },
      { event: 'outputs', data: outputs },
      { event: 'cursor', data: null },
    ]);
    expect(s.panels).toEqual({ facts: { n: 1 } });
    expect(s.outputs).toBe(outputs);
  });

  it('takes the plan with its flow calls as the feed sends it', () => {
    const plan: Plan = {
      nodes: [{ key: 'review-a~2', kind: 'review', state: 'done', level: 2, group: 'review', created_from: ['revise-a'], flow_call: '0.1' }],
      groups: [],
      flow_calls: [
        { id: '0', parent: null, function: 'flow.docs', flow: [], state: 'running' },
        { id: '0.1', parent: '0', function: 'flow.review_loop', flow: [{ function: 'flow.docs', file: 'flow.py', line: 9, loops: [] }], state: 'returned', error: null },
      ],
    };
    expect(emptyRunState().plan.flow_calls).toEqual([]);
    const s = reduceRun(emptyRunState(), [{ event: 'plan', data: plan }]);
    expect(s.plan.flow_calls?.map((c) => [c.id, c.state])).toEqual([['0', 'running'], ['0.1', 'returned']]);
  });

  it('does not mutate the state it is given', () => {
    const s0 = emptyRunState();
    reduceRun(s0, [{ event: 'journal', data: row('1') }]);
    expect(s0.journal).toEqual([]);
  });
});

describe('selectors', () => {
  it('isBad: only stops other than completed and skipped', () => {
    expect([isBad(row('1')), isBad(row('2', 'skipped')), isBad(row('3', 'timeout'))]).toEqual([false, false, true]);
  });

  it('liveActivities: agent launches, then Python tasks', () => {
    const procs = {
      run: 'r', alive: true, pid: 1, argv: [], started_at: '', max_workers: 2, run_group: 'r', tree: [],
      launches: [{ key: 'k-u', kind: 'k', unit: 'u', role: '', model: 'm', plugin: '', pid: 2, age_s: 3, cmd: '', full_cmd: '' }],
      python_tasks: [{ key: 'p', kind: 'prep', unit: '', pid: 1, age_s: 1 }],
    } satisfies Procs;
    expect(liveActivities(procs).map((a) => [a.cls, a.kind, a.unit, a.detail, a.key])).toEqual([
      ['llm', 'k', 'u', 'u | m', 'k-u'],
      ['py', 'prep', '', 'Python', ''],
    ]);
  });
});

describe('runStarts', () => {
  it('begins the next start of the run where a task numbers its attempts from 0 again', () => {
    expect(runStarts([])).toEqual([]);
    expect(runStarts([{ attempt: 0 }, { attempt: 1 }, { attempt: 2 }])).toEqual([0, 0, 0]);
    // Resumed twice: attempt 1 after one retry, then attempt 1 again, then again.
    expect(runStarts([{ attempt: 0 }, { attempt: 1 }, { attempt: 0 }, {}])).toEqual([0, 0, 1, 2]);
  });
});
