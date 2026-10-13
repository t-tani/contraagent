import { deriveRun, type JournalRow, type Plan, type PlanNode } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { inputCause, notStartedCause } from './causes.js';

const row = (over: Partial<JournalRow>): JournalRow =>
  ({ ts: '2026-10-12T08:25:33+00:00', key: 'k', kind: 'k', unit: '', attempt: 0, stop: 'completed', ok: true, wall_s: 1, ...over });

const node = (over: Partial<PlanNode>): PlanNode => ({ key: 'k', kind: 'k', unit: '', state: 'pending', after: [], ...over }) as PlanNode;

describe('input causes', () => {
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
    const o = deriveRun(journal, plan).outcomes;
    expect(notStartedCause(o.get('python:report')!, o, 'docs')).toBe('input out/review/zeta.json is missing because review · zeta failed');
    expect(notStartedCause(o.get('summary')!, o, 'docs')).toBe('earlier task review · zeta failed');
  });
});
