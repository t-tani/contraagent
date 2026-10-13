import { describe, expect, it } from 'vitest';
import { attemptLabel, attemptNames, correctionsText } from './attempts.js';

describe('attempts', () => {
  it('counts attempts and corrections as the reader does', () => {
    expect([attemptLabel(0), attemptLabel(2), attemptLabel(undefined)]).toEqual(['Attempt 1', 'Attempt 3', 'Attempt 1']);
    expect([correctionsText(0), correctionsText(1), correctionsText(3)]).toEqual(['', '1 correction', '3 corrections']);
  });

  it('names the attempts of a resumed run apart from those of the start before it', () => {
    const at = (attempt: number, ts: string) => ({ attempt, ts });
    expect(attemptNames([at(0, '2026-10-12T17:00:00Z'), at(1, '2026-10-12T17:01:00Z')])).toEqual(['Attempt 1', 'Attempt 2']);
    expect(attemptNames([at(0, '2026-10-12T17:15:01Z'), at(0, '2026-10-12T17:15:08Z')])).toEqual(['Attempt 1', 'Attempt 1 | resumed run']);
    // Resumed twice: the two resumed runs' attempts also name the time they ended.
    const names = attemptNames([at(0, '2026-10-12T17:00:00Z'), at(0, '2026-10-12T17:10:00Z'), at(0, '2026-10-12T17:20:00Z')]);
    expect(names[0]).toBe('Attempt 1');
    expect(names[1]).toMatch(/^Attempt 1 \| resumed run \| .+/);
    expect(names[2]).not.toBe(names[1]);
  });
});
