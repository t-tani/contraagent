import { describe, expect, it } from 'vitest';
import { roundLabel, roundMark, switchText } from '../../words/rounds.js';
import { classifyRounds } from './rounds.js';

const launch = (prompt = 'go') => ({ prompt });
const FIXUP = 'The output file(s) you wrote do not pass their checks.\nErrors:\n- out/a.json: [three_points] points: exactly 3';

describe('rounds', () => {
  it('names each agent session: attempt, correction, model switch', () => {
    const fix = classifyRounds([launch(), launch(FIXUP)], [{ attempt: 0, ok: true, stop: 'completed' }]);
    expect(fix.map((r) => roundLabel(r, 1))).toEqual(['Attempt 1', 'Correction round 1']);
    const retried = classifyRounds(
      [launch(), launch(), launch(FIXUP)],
      [
        { attempt: 0, ok: false, stop: 'error' },
        { attempt: 1, ok: true, stop: 'completed' },
      ],
    );
    expect(retried.map((r) => roundLabel(r, 2))).toEqual(['Attempt 1', 'Attempt 2', 'Attempt 2 | correction round 1']);
  });

  it('says which model stopped, why, and which model came next', () => {
    const rows = [
      {
        attempt: 0,
        ok: true,
        stop: 'completed',
        hops: [
          { model: 'primary-model', stop: 'rate_limited' },
          { model: 'fallback-model', stop: 'completed' },
        ],
      },
    ];
    const [first, second] = classifyRounds([launch(), launch()], rows);
    expect(roundLabel(second!, 1)).toBe('Model switch');
    expect(switchText(first!)).toBe('primary-model: rate limited → fallback-model');
    expect(roundMark(first!, 'run')).toEqual(['✕', 'rate limited', 'primary-model: rate limited → fallback-model']);
    expect(roundMark(second!, 'run')[0]).toBe('✓');
  });
});
