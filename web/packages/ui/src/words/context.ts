// Words for the peak context: the whole input of the largest API call of an attempt
// (`usage.peak_context`), against its kind's context limit (`context_budget`).
import type { JournalRow } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, tokenCount } from './format.js';

/** The label before a peak context. */
export const peakContextLabel = (): string => msg('Peak context');

/** What a peak context is, for its tooltip. */
export const peakContextTip = (): string => msg('Largest input of one API call, cache read and cache write included (peak_context)');

/** A peak context, then its share of the context limit when one is set: `142k | 71% of the context limit 200k`. */
export function peakContextText(peak: number, budget?: number | null): string {
  const share = budget ? Math.round((100 * peak) / budget) : null;
  return facts(tokenCount(peak), share === null ? '' : msg(str`${share}% of the context limit ${tokenCount(budget)}`));
}

/** An attempt's peak context with its label (`Peak context: 142k | 71% of ...`); '' when it reported none. */
export function peakContextLine(r: Pick<JournalRow, 'usage' | 'context_budget'>): string {
  const peak = r.usage?.peak_context;
  return peak == null ? '' : msg(str`Peak context: ${peakContextText(peak, r.context_budget)}`);
}

/** The state of an attempt whose peak context passed the warning share of its context limit (`context_warned`). */
export const contextWarnedLabel = (): string => msg('near the context limit');

/** That state with the share of the limit when known: `near the context limit (91%)`. */
export function contextWarnedText(r: Pick<JournalRow, 'usage' | 'context_budget'>): string {
  const peak = r.usage?.peak_context;
  const budget = r.context_budget;
  if (peak == null || !budget) return contextWarnedLabel();
  return msg(str`near the context limit (${Math.round((100 * peak) / budget)}%)`);
}

/** What that state means, for its tooltip. */
export const contextWarnedTip = (): string => msg('Peak context past the warning threshold of the context limit (context_warned)');

/** Of `tries`, the one with the largest peak context; null when none reported one. */
export function peakTry<T extends Pick<JournalRow, 'usage'>>(tries: readonly T[]): T | null {
  let best: T | null = null;
  for (const r of tries) {
    const p = r.usage?.peak_context;
    if (p != null && (best === null || p > (best.usage?.peak_context ?? 0))) best = r;
  }
  return best;
}
