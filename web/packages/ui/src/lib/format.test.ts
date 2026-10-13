import { describe, expect, it } from 'vitest';
import { facts, fmtDur, localTime, sentence, tokenCount, unreadEvents, usd } from './format.js';

describe('format', () => {
  it('writes token counts compactly', () => {
    expect([950, 1200, 1000, 34_200, 1_340_000, 2_000_000].map(tokenCount)).toEqual(['950', '1.2k', '1k', '34k', '1.3M', '2M']);
  });

  it('writes costs in USD, and — when none was reported', () => {
    expect([0.0409, 0.5, 1.234, 0.0004, null].map(usd)).toEqual(['$0.041', '$0.500', '$1.23', '<$0.001', '—']);
  });

  it('writes every duration one way', () => {
    expect([0, 0.04, 0.2, 4.24, 9.96, 37.4, 59.6, 125, 3600 + 125, null].map(fmtDur)).toEqual([
      '<0.1s',
      '<0.1s',
      '0.2s',
      '4.2s',
      '10s',
      '37s',
      '1m 00s',
      '2m 05s',
      '1h 02m',
      '—',
    ]);
  });

  it('writes dates with the month as a word, in the UI locale', () => {
    const at = new Date(2026, 9, 12, 10, 38, 40).toISOString();
    expect(localTime(at, false, 'en')).toBe('10:38:40');
    expect(localTime(at, true, 'en')).toBe('Oct 12, 10:38:40');
    expect(localTime(at, true, 'ja')).toBe('10月12日 10:38:40');
    expect(localTime('', true, 'en')).toBe('');
    expect(localTime('not a time', true, 'en')).toBe('not a time');
  });

  it('joins the facts of a row with a bar, leaving out empty ones', () => {
    expect(facts('Attempt 1', 'done', '', null, '0.2s')).toBe('Attempt 1 | done | 0.2s');
  });
});

describe('unreadEvents', () => {
  it('sums each type over the rows', () => {
    expect(unreadEvents([{ unread_events: { session_settled: 1 } }, { unread_events: { session_settled: 2, x: 1 } }, {}])).toBe(
      'session_settled ×3, x ×1',
    );
    expect(unreadEvents([{ unread_events: {} }])).toBe('');
  });
});

describe('sentence', () => {
  it('starts a phrase that stands alone with a capital; Japanese is left as it is', () => {
    expect(sentence('input out/a.json is missing')).toBe('Input out/a.json is missing');
    expect(sentence('入力 out/a.json がありません')).toBe('入力 out/a.json がありません');
    expect(sentence('')).toBe('');
  });
});
