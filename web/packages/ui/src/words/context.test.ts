import { describe, expect, it } from 'vitest';
import { contextWarnedText, peakContextLine, peakContextText, peakTry } from './context.js';

describe('peakContextText', () => {
  it('gives the peak, then its share of the context limit when one is set', () => {
    expect(peakContextText(142_000)).toBe('142k');
    expect(peakContextText(142_000, 200_000)).toBe('142k | 71% of the context limit 200k');
  });
});

describe('peakContextLine', () => {
  it("labels an attempt's peak context, and says nothing for an attempt that reported none", () => {
    expect(peakContextLine({ usage: { peak_context: 9_500 }, context_budget: null })).toBe('Peak context: 9.5k');
    expect(peakContextLine({ usage: null })).toBe('');
  });
});

describe('peakTry', () => {
  it('picks the attempt with the largest peak context', () => {
    const a = { usage: { peak_context: 10 } };
    const b = { usage: { peak_context: 30 } };
    expect(peakTry([a, b, { usage: null }])).toBe(b);
    expect(peakTry([{ usage: null }])).toBeNull();
  });
});

describe('contextWarnedText', () => {
  it('gives the share of the context limit when the attempt has one', () => {
    expect(contextWarnedText({ usage: { peak_context: 182_000 }, context_budget: 200_000 })).toBe('near the context limit (91%)');
    expect(contextWarnedText({ usage: null })).toBe('near the context limit');
  });
});
