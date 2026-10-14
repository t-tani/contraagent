// A paused identity and why a task was deferred, in words: from the data, the run's
// own sentence only for a cause these words do not know.
import type { DeferralCause, SkippedHop } from '@contraagent/api';
import { describe, expect, it } from 'vitest';
import { localTime } from './format.js';
import { modelSwitch } from './hops.js';
import { capsLine, deferredText, deferredTip, restLine, restSpan } from './rests.js';

const UNTIL = '2026-10-14T04:30:00+00:00';
const capped = (credential = 'personal'): SkippedHop => ({
  route: 'hop 1/2 claude/claude-haiku-5-5@personal',
  model: 'claude-haiku-5-5',
  credential,
  window: 'five_hour',
  pct: 93,
  cap: 90,
  rule: '',
  until: UNTIL,
});

describe('restLine', () => {
  it('names the identity, the window, its cap and when it resets', () => {
    expect(restLine(capped())).toBe(`Identity personal paused | 5-hour usage 93% | limit 90% | until ${localTime(UNTIL, true)}`);
    expect(restLine({ ...capped('ambient'), window: 'seven_day', pct: 96, cap: 95, until: '' })).toBe(
      'Identity default paused | Weekly usage 96% | limit 95%',
    );
  });
  it('says what the usage rule said', () => {
    expect(restLine({ credential: 'personal', rule: 'over the pace' })).toBe('Identity personal paused | Usage rule: over the pace');
  });
});

describe('deferredText', () => {
  it('words each cause the queue records', () => {
    const c = (cause: DeferralCause) => deferredText(cause, 'recorded');
    expect(c({ cause: 'deadline' })).toBe('Past the deadline');
    expect(c({ cause: 'grace_window' })).toBe('Past the deadline and its finishing time');
    expect(c({ cause: 'cannot_finish', need_s: 720, left_s: 190 })).toBe('Cannot finish before the deadline | needs 12m 00s | 3m 10s left');
    expect(c({ cause: 'dependency_not_queued' })).toBe('An earlier task was never scheduled');
  });
  it('names a paused identity once, and counts the others', () => {
    const one: DeferralCause = { cause: 'rest', rests: [capped(), { ...capped(), route: 'hop 2/2 x' }] };
    expect(deferredText(one)).toBe(restLine(capped()));
    expect(deferredTip(one)).toBe('');
    const two: DeferralCause = { cause: 'rest', rests: [capped(), capped('sub-b')] };
    expect(deferredText(two)).toBe(`${restLine(capped())} | +1 paused identities`);
    expect(deferredTip(two)).toBe(`${restLine(capped())}\n${restLine(capped('sub-b'))}`);
  });
  it('falls back to the recorded sentence for a cause it does not know, or none', () => {
    expect(deferredText({ cause: 'a_runner_of_its_own' }, 'recorded')).toBe('recorded');
    expect(deferredText(null, 'recorded')).toBe('recorded');
  });
});

describe('a model switch with a paused identity', () => {
  it('puts the hop passed over first, once', () => {
    const hops = [{ route: 'hop 2/2 omp/m2', model: 'anthropic/claude-haiku-5-5', stop: 'completed' }];
    expect(modelSwitch(hops, null, [capped(), capped()])).toBe('claude-haiku-5-5 (identity paused) → anthropic/claude-haiku-5-5');
    expect(modelSwitch(hops, null, [])).toBe('');
  });
});

describe('rests over a run', () => {
  it('says when a rest began and ended, and the caps', () => {
    const since = '2026-10-14T01:00:00+00:00';
    const ended = '2026-10-14T01:20:00+00:00';
    expect(restSpan({ ...capped(), since, ended })).toBe(`Paused ${localTime(since)} → ${localTime(ended)} | 5-hour usage 93% | limit 90%`);
    expect(restSpan({ credential: 'personal', rule: 'over the pace', since, ended: '' })).toBe(
      `Paused since ${localTime(since)} | Usage rule: over the pace`,
    );
    expect(capsLine({ credential: 'personal', five_hour_pct: 90, seven_day_pct: 95 })).toBe('Limits: weekly 95% | 5-hour 90%');
    expect(capsLine({ credential: 'personal' })).toBe('');
  });
});
