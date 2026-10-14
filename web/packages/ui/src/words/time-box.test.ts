// A flow call's own deadline (`time_box`), in words.
import { describe, expect, it } from 'vitest';
import { localTime } from './format.js';
import { deadlineAtText, timeBoxFacts } from './time-box.js';

const box = { started_at: '2026-10-14T01:00:00+00:00', deadline_s: 2700, grace_s: 900, slack_s: 675, finishing_kinds: ['lint_fixer', 'report'] };

describe('timeBoxFacts', () => {
  it('says the deadline, the finishing time and the finishing kinds', () => {
    expect(timeBoxFacts(box)).toBe('45m 00s | finishing time 15m 00s | finishing kinds: lint_fixer and report');
  });
  it('says only the deadline when no kind finishes past it', () => {
    expect(timeBoxFacts({ ...box, finishing_kinds: [] })).toBe('45m 00s');
  });
  it('says when one flow call\'s deadline falls, as an absolute time', () => {
    expect(deadlineAtText('2026-10-14T01:45:00.000Z')).toBe(localTime('2026-10-14T01:45:00.000Z', true));
  });
});
