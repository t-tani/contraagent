// The run's preflight (`Plan.preflight`) → the rows the run's card lists: the kinds
// with no available model first (the run's cause when it ended before its first
// agent session), then the replaced models, then each unavailable model.
import type { Preflight } from '@contraagent/api';
import type { Tone } from '../lib/tone.js';
import { facts } from '../words/format.js';
import { allAvailable, keptTip, noModelLabel, replacedLabel, replacedText, replacedTip, routeName, unavailableLabel, unavailableText } from '../words/preflight.js';

export interface PreflightRow {
  label: string;
  text: string;
  tone: Tone;
  /** What the label means; '' for none. */
  tip: string;
}

/** The rows of a preflight; none for no preflight or one with policy `off` (no model was sent a request). */
export function preflightRows(p: Preflight | null | undefined): PreflightRow[] {
  if (!p || p.policy === 'off') return [];
  const rows: PreflightRow[] = [
    ...(p.stopped ?? []).map((kind): PreflightRow => ({ label: noModelLabel(), text: kind, tone: 'failed', tip: '' })),
    ...(p.kept ?? []).map((k): PreflightRow => ({ label: noModelLabel(), text: facts(k.kind, routeName(k.agent, k.model), k.reason), tone: 'attention', tip: keptTip() })),
    ...(p.substituted ?? []).map((s): PreflightRow => ({ label: replacedLabel(), text: replacedText(s), tone: 'attention', tip: replacedTip() })),
    ...(p.dropped ?? []).map((d): PreflightRow => ({ label: unavailableLabel(), text: unavailableText(d), tone: 'muted', tip: '' })),
  ];
  return rows.length ? rows : [{ label: '', text: allAvailable(), tone: 'neutral', tip: '' }];
}
