import { describe, expect, it } from 'vitest';
import { problemTone, runTone, stopTone } from './tone.js';

describe('problemTone', () => {
  it('colours a problem count only above 0', () => {
    expect(problemTone(4, 'failed')).toBe('failed');
    expect(problemTone(1, 'attention')).toBe('attention');
    // a 0 is neutral: not green, not red
    expect(problemTone(0, 'failed')).toBe('');
  });
});

describe('runTone', () => {
  const t = (failed: number, not_started: number, total = 31) => ({ total, failed, not_started });
  it('is the run’s own status', () => {
    expect(runTone(true, t(1, 0))).toBe('running');
    expect(runTone(false, t(1, 1))).toBe('failed');
    expect(runTone(false, t(0, 1))).toBe('attention');
    expect(runTone(false, t(0, 0))).toBe('done');
    expect(runTone(false, t(0, 0, 0))).toBe('');
    expect(runTone(false, undefined)).toBe('');
  });
});

describe('stopTone', () => {
  it('names a failure for every stop but four', () => {
    expect(stopTone('completed')).toBe('done');
    expect(stopTone('invalid_input')).toBe('attention');
    expect(stopTone('skipped')).toBe('muted');
    expect(stopTone('running')).toBe('running');
    for (const s of ['error', 'timeout', 'rate_limited', 'invalid_output', 'something_new']) expect(stopTone(s)).toBe('failed');
  });
});
