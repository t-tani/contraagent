// Words for safety stops: a safety classifier stopped part of an agent session, which
// went on and ended on its own outcome (`JournalRow.safety_stops`, `Trends.safety_stops`).
import type { JournalRow } from '@contraagent/api';
import { msg, str } from '@lit/localize';
import { facts, localTime } from './format.js';

/** One safety stop of an attempt. */
export type SafetyStop = NonNullable<JournalRow['safety_stops']>[number];

/** The heading of the safety stops (the trends' table, a count's column). */
export const safetyStopsLabel = (): string => msg('Safety stops');

/** A count of safety stops: `1 safety stop`, `3 safety stops`. */
export const safetyStopCount = (n: number): string => (n === 1 ? msg('1 safety stop') : msg(str`${n} safety stops`));

/** What a safety stop is, for its tooltip. */
export const safetyStopTip = (): string => msg('A safety classifier stopped part of the agent session, and the session went on (safety_stops)');

/** What the safety classifier stopped (`SafetyStop.part`), in words. */
export function safetyPartLabel(part: string | null | undefined): string {
  switch (part) {
    case 'response':
      return msg('model response', { desc: 'A safety stop of a response of the model of the agent session' });
    case 'tool':
      return msg('tool request', { desc: 'A safety stop of a request of a model that a tool calls; the tool call ended in an error' });
    case 'unread':
      return msg('unrecognized', { desc: 'A safety stop the coding agent counted, in words this contraagent version does not recognize' });
    default:
      return part || '—';
  }
}

/** The column of the trends' table that names what was stopped. */
export const safetyPartColumn = (): string => msg('Stopped part', { desc: 'A column: what a safety classifier stopped (a model response, a tool request)' });

/** One safety stop as a row of its known facts: `model response | opus | cyber | 2026-10-11 09:00:01`. */
export const safetyStopLine = (s: SafetyStop): string => facts(safetyPartLabel(s.part), s.model, s.category, s.tool, localTime(s.ts, true));
