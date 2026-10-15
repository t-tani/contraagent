import type { Stop } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { stopLabel } from '../words/stop.js';
import { ALL_STOPS, contractTone, isStop, outcomeTone, problemTone, runTone, stopTone, type Tone } from './tone.js';

describe('problemTone', () => {
  it('colours a problem count only above 0', () => {
    expect(problemTone(4, 'failed')).toBe('failed');
    expect(problemTone(1, 'attention')).toBe('attention');
    // a 0 is neutral: not green, not red
    expect(problemTone(0, 'failed')).toBe('neutral');
  });
});

describe('runTone', () => {
  const t = (failed: number, not_started: number, total = 31) => ({ total, failed, not_started });
  it('is the run’s own status', () => {
    expect(runTone('running', t(1, 0))).toBe('running');
    expect(runTone('stopped', t(1, 1))).toBe('failed');
    expect(runTone('stopped', t(0, 1))).toBe('attention');
    expect(runTone('stopped', t(0, 0))).toBe('done');
    expect(runTone('stopped', t(0, 0, 0))).toBe('neutral');
    expect(runTone('stopped', undefined)).toBe('neutral');
    // its host stopped reporting: not known to run, not known to have ended
    expect(runTone('unresponsive', t(0, 0))).toBe('attention');
    expect(runTone('unresponsive', t(1, 0))).toBe('attention');
  });
});

describe('stopTone', () => {
  // The Python `Stop` values plus `skipped`: the keys are checked against the generated schema type.
  const expected: Record<Stop, Tone> = {
    completed: 'done',
    partial: 'attention',
    invalid_input: 'attention',
    skipped: 'muted',
    timeout: 'failed',
    max_turns: 'failed',
    budget: 'failed',
    context_budget: 'failed',
    stalled: 'failed',
    auth_failed: 'failed',
    api_error: 'failed',
    rate_limited: 'failed',
    refused: 'failed',
    aborted: 'failed',
    denied: 'failed',
    error: 'failed',
    no_output: 'failed',
    launch_failed: 'failed',
    invalid_output: 'failed',
    credential_mismatch: 'failed',
  };

  it('lists every stop contraagent writes', () => {
    expect([...ALL_STOPS].sort()).toEqual(Object.keys(expected).sort());
    expect(ALL_STOPS).toHaveLength(20);
  });

  it('gives every stop its tone and its words', () => {
    for (const s of ALL_STOPS) {
      expect(stopTone(s), s).toBe(expected[s]);
      expect(stopLabel(s), s).not.toMatch(/^unknown|^—$/);
    }
  });

  it('shows a stop it does not know as a failure, by its own name', () => {
    expect(isStop('something_new')).toBe(false);
    expect(isStop('toString')).toBe(false);
    expect(stopTone('something_new')).toBe('failed');
    expect(stopLabel('something_new')).toBe('unknown (something_new)');
    expect(stopLabel('')).toBe('—');
  });
});

describe('outcomeTone and contractTone', () => {
  it('colour a task and a checked file by their status', () => {
    const outcomes = ['done', 'recovered', 'failed', 'not_started', 'running', 'waiting', 'skipped'] as const;
    expect(outcomes.map(outcomeTone)).toEqual(['done', 'done', 'failed', 'attention', 'running', 'muted', 'muted']);
    const statuses = ['valid', 'invalid', 'failed', 'refused', 'running', 'pending'] as const;
    expect(statuses.map(contractTone)).toEqual(['done', 'failed', 'failed', 'attention', 'running', 'muted']);
    expect(contractTone(undefined)).toBe('neutral');
  });
});
