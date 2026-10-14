// Words for what each model was used for in a run (`Plan.models`).
import type { ModelMeasure, ModelUsage } from '@contraagent/api';
import { modelTokens } from '@contraagent/api';
import { msg } from '@lit/localize';
import { fmtDur, tokenCount, usd } from './format.js';

/** A measure's name: the name of the column it is in, too. */
export function measureLabel(m: ModelMeasure): string {
  switch (m) {
    case 'cost':
      return msg('Cost');
    case 'tokens':
      return msg('Tokens');
    case 'time':
      return msg('Time');
    case 'sessions':
      return msg('Agent sessions');
  }
}

/** What a measure counts, for its tooltip. */
export function measureTip(m: ModelMeasure): string {
  switch (m) {
    case 'cost':
      return msg('Reported by the coding agent');
    case 'tokens':
      return msg('Input, output, cache read and cache write');
    case 'time':
      return msg('Time of the agent sessions, summed');
    case 'sessions':
      return msg('Agent sessions started on the model');
  }
}

/** A model's amount of `measure` in words: `$0.12`, `12.3k`, `2m 05s`, `4`; '—' for no cost reported. */
export function measureText(u: ModelUsage, m: ModelMeasure): string {
  switch (m) {
    case 'cost':
      return u.cost_usd === null || u.cost_usd === undefined ? '—' : usd(u.cost_usd);
    case 'tokens':
      return tokenCount(modelTokens(u));
    case 'time':
      return fmtDur(u.wall_s ?? 0);
    case 'sessions':
      return String(u.sessions);
  }
}

/** The name the parts of a share past the colours fold into. */
export const otherModels = (): string => msg('Other models');
