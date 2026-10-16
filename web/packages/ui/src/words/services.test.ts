// A service's state and facts, in words, from what `services.jsonl` recorded.
import type { ServiceSpan } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { localTime } from './format.js';
import { serviceFacts, serviceState, serviceStateLabel } from './services.js';

const START = '2026-10-14T04:30:00+00:00';
const STOP = '2026-10-14T04:35:00+00:00';
const span = (more: Partial<ServiceSpan> = {}): ServiceSpan => ({ name: 'index', started_at: START, start_s: 1.2, ...more });

describe('serviceState', () => {
  it('is running only while its run runs, until a stop is recorded', () => {
    expect(serviceState(span(), true)).toBe('running');
    expect(serviceState(span(), false)).toBe('unknown');
    expect(serviceState(span({ stopped_at: STOP, stop_cause: 'run_end' }), true)).toBe('stopped');
    expect(serviceState(span({ start_error: 'OSError: no' }), true)).toBe('failed');
    expect(serviceStateLabel('failed')).toBe('did not start');
  });
});

describe('serviceFacts', () => {
  it('names when it started and stopped, and why', () => {
    expect(serviceFacts(span({ stopped_at: STOP, stop_cause: 'idle' }))).toBe(
      `Started ${localTime(START)} in 1.2s | Stopped ${localTime(STOP)} | No task held it`,
    );
    expect(serviceFacts(span({ stopped_at: STOP, stop_cause: 'interrupted', stop_error: 'RuntimeError: busy' }))).toBe(
      `Started ${localTime(START)} in 1.2s | Stopped ${localTime(STOP)} | The run was stopped by a signal | Stop failed | RuntimeError: busy`,
    );
  });
  it('gives the error of a start that failed', () => {
    expect(serviceFacts(span({ start_error: 'OSError: port 9000 in use' }))).toBe(`${localTime(START)} | OSError: port 9000 in use`);
  });
});
