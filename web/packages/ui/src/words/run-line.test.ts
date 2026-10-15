// The header's run line and the history bar's count, from `deriveRun`.
import { deriveRun, emptyRunState, type JournalRow, type Plan, type PlanNode, type RunState, type RunSummary, type Stop } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { mixedReplay, runLine, runMark, triesLine } from './run-line.js';

const node = (key: string, state: PlanNode['state'], after: string[] = []): PlanNode => ({
  key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', after, state, level: 0, group: key.split('-')[0]!,
});
const row = (key: string, stop: Stop, attempt = 0, cost_usd: number | null = null): JournalRow => ({
  ts: '2026-10-11T00:00:01', key, kind: key.split('-')[0]!, unit: key.split('-')[1] ?? '', stop, ok: stop === 'completed', wall_s: 1, attempt, cost_usd,
});

// a done after a retry (recovered), c failed, d not started.
const plan: Plan = {
  nodes: [node('a-1', 'done'), node('c-1', 'failed'), node('d-1', 'blocked', ['c-1'])],
  groups: [],
};
const journal = [row('a-1', 'error', 0, 0.25), row('a-1', 'completed', 1, 0.5), row('c-1', 'error', 0, 0.25), row('d-1', 'invalid_input')];
const summary = {
  run: 'r', started_at: '2026-10-11T00:00:00', last_ts: '2026-10-11T00:01:05', running: false, cost_usd: 9, quota: [],
  tasks: { total: 3, done: 1, failed: 1, not_started: 1, running: 0, waiting: 0, not_run: 0, skipped: 0 },
} as unknown as RunSummary;
const state = (ready: boolean): RunState => ({ ...emptyRunState(), journal, plan, ready });

describe('runLine', () => {
  it('counts done and recovered tasks out of all tasks, with the time and the cost of the live journal', () => {
    const c = deriveRun(journal, plan).counts;
    expect(c.doneTotal).toBe(1);
    expect(runLine(state(true), summary)).toBe(`${c.doneTotal} of ${c.total} tasks done | took 1m 05s | $1.00`);
  });

  it('before the replay is in: no count, and the run list cost', () => {
    expect(runLine(state(false), summary)).toBe('took 1m 05s | $9.00');
  });

  it('names the tasks that will not run, as the run list counts them', () => {
    const c = deriveRun(journal, plan).counts;
    expect(runLine(state(true), { ...summary, tasks: { ...summary.tasks, not_run: 2 } })).toBe(`${c.doneTotal} of ${c.total} tasks done | 2 not run | took 1m 05s | $1.00`);
  });

  it('a running run says so', () => {
    expect(runLine(state(true), { ...summary, running: true })).toMatch(/ \| running$/);
  });
});

describe('triesLine', () => {
  it('counts attempts and the tasks that did not start', () => {
    expect(triesLine(deriveRun(journal, plan).tries)).toBe('3 attempts | 1 not started');
    expect(triesLine({ tries: 1, notStarted: 0 })).toBe('1 attempt');
  });
});

describe('runMark', () => {
  it('marks a replay with its recordings, a stub run as the stub agent, and nothing else', () => {
    expect(runMark({ stub: true, replay: '/rec' })).toEqual({ text: 'replay', title: 'Agent sessions played from the recordings in /rec (replay)' });
    expect(runMark({ stub: true, replay: '' })?.text).toBe('stub agent');
    expect(runMark({ stub: false })).toBeNull();
  });

  it('marks a replay that also launched apart, and only then its played attempts', () => {
    expect(runMark({ stub: false, replay: '/rec' })).toEqual({
      text: 'replay and new sessions',
      title: 'Agent sessions played from the recordings in /rec, and new agent sessions recorded there (replay, record_missing)',
    });
    expect(mixedReplay({ stub: false, replay: '/rec' })).toBe(true);
    expect(mixedReplay({ stub: true, replay: '/rec' })).toBe(false);
    expect(mixedReplay({ stub: false, replay: '' })).toBe(false);
  });
});
