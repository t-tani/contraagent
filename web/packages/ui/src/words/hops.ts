// A model switch (the hops of one attempt), in words.
import type { Hop, SkippedHop } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { fmtDur } from './format.js';
import { skippedHopStep } from './rests.js';
import { stopLabel } from './stop.js';

/** One hop's model, or its route when the journal names no model. */
const hopModel = (h: Pick<Hop, 'model' | 'route'>): string => h.model || h.route || '—';

/**
 * A model switch in words, the one form every view uses:
 * `primary-model (rate limited) → fallback-model`; '' for a single hop.
 * The hops passed over without an agent session (`skipped`: their identity was
 * paused) come first: `primary-model (identity paused) → fallback-model`.
 * With `time`, the attempt's time follows: `... → fallback-model | 0.2s`.
 */
export function modelSwitch(hops: readonly Hop[] | null | undefined, time?: number | null, skipped?: readonly SkippedHop[] | null): string {
  const passed = [...new Map((skipped ?? []).map((h) => [h.route || h.model, h])).values()];
  if (!hops || hops.length + passed.length < 2 || !hops.length) return '';
  const steps = [
    ...passed.map(skippedHopStep),
    ...hops.map((h, i) => (i < hops.length - 1 ? msg(str`${hopModel(h)} (${stopLabel(h.stop)})`) : hopModel(h))),
  ];
  const chain = steps.join(' → ');
  return time === undefined || time === null ? chain : `${chain} | ${fmtDur(time)}`;
}
