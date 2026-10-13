import { describe, expect, it } from 'vitest';
import { inputProblems, runRelative } from './reasons.js';

describe('reasons', () => {
  it('cuts paths inside the run directory to the part after it', () => {
    expect(runRelative('invalid input: /home/x/demo-runs/docs/out/summarize/zeta.json: required input is missing', 'docs')).toBe(
      'invalid input: out/summarize/zeta.json: required input is missing',
    );
    expect(runRelative('no path here', 'docs')).toBe('no path here');
    expect(runRelative(null, 'docs')).toBe('');
  });

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
});
