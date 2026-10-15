import { describe, expect, it } from 'vitest';
import { preflightRows } from './preflight.js';

describe('preflightRows', () => {
  it('lists nothing without a preflight, or with policy off', () => {
    expect(preflightRows(null)).toEqual([]);
    expect(preflightRows({ policy: 'off' })).toEqual([]);
  });
  it('states that every model is available when none was dropped', () => {
    expect(preflightRows({ policy: 'substitute' }).map((r) => r.text)).toEqual(['all models available']);
  });
  it('lists the kinds with no model first, then the replaced models, then the unavailable ones', () => {
    const rows = preflightRows({
      policy: 'substitute',
      dropped: [{ agent: 'claude', model: 'opus', credential: 'ambient', reason: 'rate limited', kinds: ['review', 'summarize'] }],
      substituted: [{ kind: 'review', from_agent: 'claude', from_model: 'opus', to_agent: 'claude', to_model: 'sonnet' }],
      kept: [{ kind: 'summarize', agent: 'claude', model: 'opus', reason: 'no route answered' }],
    });
    expect(rows.map((r) => [r.label, r.text, r.tone])).toEqual([
      ['No available model', 'summarize | claude / opus | no route answered', 'attention'],
      ['Model replaced', 'review | claude / opus → claude / sonnet', 'attention'],
      ['Unavailable', 'claude / opus | identity default | rate limited | kinds review and summarize', 'muted'],
    ]);
  });
  it('names the kinds that ended the run', () => {
    expect(preflightRows({ policy: 'stop', stopped: ['review'] }).map((r) => [r.text, r.tone])).toEqual([['review', 'failed']]);
  });
});
