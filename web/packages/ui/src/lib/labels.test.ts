import { taskOutcomes, type JournalRow, type Plan, type PlanNode } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import {
  attemptLabel,
  correctionsText,
  credentialLabel,
  credentialTip,
  inputCause,
  inputProblems,
  modelSwitch,
  notStartedCause,
  planStateLabel,
  runRelative,
  stopLabel,
  taskState,
} from './labels.js';

const row = (over: Partial<JournalRow>): JournalRow =>
  ({ ts: '2026-10-12T08:25:33+00:00', key: 'k', kind: 'k', unit: '', attempt: 0, stop: 'completed', ok: true, wall_s: 1, ...over });

const node = (over: Partial<PlanNode>): PlanNode => ({ key: 'k', kind: 'k', unit: '', state: 'pending', after: [], ...over }) as PlanNode;

describe('labels', () => {
  it('cuts paths inside the run directory to the part after it', () => {
    expect(runRelative('invalid input: /home/x/demo-runs/docs/out/summarize/zeta.json: required input is missing', 'docs')).toBe(
      'invalid input: out/summarize/zeta.json: required input is missing',
    );
    expect(runRelative('no path here', 'docs')).toBe('no path here');
  });

  it('names stops in words, and an unknown one as unknown with its value', () => {
    expect([stopLabel('completed'), stopLabel('invalid_input'), stopLabel('invalid_output'), stopLabel('custom_stop'), stopLabel('')]).toEqual([
      'done',
      'not started (input missing or failed checks)',
      'failed checks',
      'unknown (custom_stop)',
      '—',
    ]);
    expect(stopLabel('invalid_input', 'invalid input: /r/out/a.json: required input is missing')).toBe('not started (input missing)');
    expect(stopLabel('invalid_input', 'invalid input: /r/out/a.json: field x: wrong type')).toBe('not started (input failed checks)');
  });

  it('counts attempts and corrections as the reader does', () => {
    expect([attemptLabel(0), attemptLabel(2), attemptLabel(undefined)]).toEqual(['Attempt 1', 'Attempt 3', 'Attempt 1']);
    expect([correctionsText(0), correctionsText(1), correctionsText(3)]).toEqual(['', '1 correction', '3 corrections']);
  });

  it('shows the built-in credential as default, with local credentials in its tooltip', () => {
    expect([credentialLabel('ambient'), credentialLabel('team-key'), credentialLabel('')]).toEqual(['default', 'team-key', '']);
    expect([credentialTip('ambient'), credentialTip('team-key')]).toEqual(['local credentials (ambient)', '']);
  });

  it('tells a waiting task from one that did not start', () => {
    expect(planStateLabel('pending')).toBe('waiting');
    expect(planStateLabel('blocked')).toBe('not started');
    // From the run: no attempt, waiting in the plan or behind a failed task.
    const plan: Plan = {
      nodes: [node({ key: 'a', state: 'failed' }), node({ key: 'b', state: 'blocked', after: ['a'] }), node({ key: 'c', state: 'pending' })],
      groups: [],
    };
    const outcomes = taskOutcomes([row({ key: 'a', ok: false, stop: 'error' })], plan);
    expect(taskState([], outcomes.get('b'))).toBe('not_started');
    expect(taskState([], outcomes.get('c'))).toBe('waiting');
    // From its own rows when the plan does not list it.
    expect(taskState([])).toBe('waiting');
    expect(taskState([row({ stop: 'invalid_input', ok: false })])).toBe('not_started');
    expect(taskState([row({ stop: 'error', ok: false }), row({ attempt: 1 })])).toBe('recovered');
  });
});

describe('modelSwitch', () => {
  it('writes the models in order, each one that stopped with why', () => {
    const hops = [
      { route: 'r1', model: 'primary-model', stop: 'rate_limited', wall_s: 0.1 },
      { route: 'r2', model: 'fallback-model', stop: 'completed', wall_s: 0.1 },
    ];
    expect(modelSwitch(hops)).toBe('primary-model (rate limited) → fallback-model');
    expect(modelSwitch(hops, 0.2)).toBe('primary-model (rate limited) → fallback-model | 0.2s');
  });

  it('is empty for a single hop, and falls back to the route for a hop with no model', () => {
    expect(modelSwitch([{ route: 'r1', model: 'm', stop: 'completed' }])).toBe('');
    expect(modelSwitch(null)).toBe('');
    expect(modelSwitch([{ route: 'hop 1', model: '', stop: 'timeout' }, { route: 'hop 2', model: '', stop: 'completed' }])).toBe(
      'hop 1 (timed out) → hop 2',
    );
  });
});

describe('input causes', () => {
  it('reads each form of a refusal reason', () => {
    expect(inputProblems('invalid input: input from review-zeta is missing: /r/docs/out/review/zeta.json')).toEqual([
      { path: '/r/docs/out/review/zeta.json', producer: 'review-zeta', problem: 'missing' },
    ]);
    expect(inputProblems('invalid input: /r/docs/in.json: required input is missing; /r/docs/b.json: 1 validation error')).toEqual([
      { path: '/r/docs/in.json', producer: '', problem: 'missing' },
      { path: '/r/docs/b.json', producer: '', problem: 'checks' },
    ]);
    expect(inputProblems('ValueError: boom')).toEqual([]);
  });

  it('names the real cause: missing or failed checks, and what happened to the earlier task', () => {
    expect(inputCause('out/a.json', 'missing')).toBe('input out/a.json is missing');
    expect(inputCause('out/a.json', 'checks')).toBe('input out/a.json failed checks');
    expect(inputCause('out/a.json', 'missing', { name: 'review · zeta', outcome: 'failed' })).toBe(
      'input out/a.json is missing because review · zeta failed',
    );
    expect(inputCause('out/a.json', 'missing', { name: 'review · zeta', outcome: 'not_started' })).toBe(
      'input out/a.json is missing because review · zeta did not start',
    );
    expect(inputCause('out/a.json', 'missing', { name: 'review · zeta', outcome: 'running' })).toBe(
      'input out/a.json is missing because review · zeta did not finish',
    );
    expect(inputCause('out/a.json', 'checks', { name: 'prepare · zeta' })).toBe('input out/a.json from prepare · zeta failed checks');
  });

  it('follows a refused task to the earlier task, and a blocked one to the failed task upstream', () => {
    const journal = [
      row({ key: 'review-zeta', kind: 'review', unit: 'zeta', ok: false, stop: 'error' }),
      row({
        key: 'python:report',
        kind: 'report',
        ok: false,
        stop: 'invalid_input',
        reason: 'invalid input: input from review-zeta is missing: /x/docs/out/review/zeta.json',
      }),
    ];
    const plan: Plan = {
      nodes: [
        node({ key: 'review-zeta', kind: 'review', unit: 'zeta', state: 'failed' }),
        node({ key: 'python:report', kind: 'report', state: 'blocked', after: ['review-zeta'] }),
        node({ key: 'summary', kind: 'summary', state: 'blocked', after: ['review-zeta'] }),
      ],
      groups: [],
    };
    const o = taskOutcomes(journal, plan);
    expect(notStartedCause(o.get('python:report')!, o, 'docs')).toBe('input out/review/zeta.json is missing because review · zeta failed');
    expect(notStartedCause(o.get('summary')!, o, 'docs')).toBe('earlier task review · zeta failed');
  });
});
