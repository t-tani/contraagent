// A run's models (`Plan.models`) → the share bar's parts and the rows of the table
// beside it, for one measure (cost, tokens, time, agent sessions).
import { modelValue, type ModelMeasure, type ModelUsage } from '@contraagent/api';
import { wholePercents, sharePercent, type SharePart } from '@contraagent/elements/primitives';
import { measureText, otherModels } from '../words/models.js';

/** The series colours (`--series-1` ...), in their order. */
export const SERIES_COLOURS = 6;

/** The colour the models past the series colours share. */
export const OTHER_COLOUR = 'var(--meter)';

/** A model's identity: its coding agent and its name. */
export const modelId = (m: Pick<ModelUsage, 'agent' | 'model'>): string => `${m.agent}/${m.model}`;

/**
 * Each model's colour, by the order of first use (the order of `models`): the first
 * six take the series colours; with more than six, the sixth and later share the
 * colour of "other models". A model keeps its colour whatever the measure, and
 * whatever its rank.
 */
export function modelColours(models: readonly ModelUsage[]): Map<string, string> {
  const own = models.length > SERIES_COLOURS ? SERIES_COLOURS - 1 : SERIES_COLOURS;
  return new Map(models.map((m, i) => [modelId(m), i < own ? `var(--series-${i + 1})` : OTHER_COLOUR]));
}

/** The share bar's parts for `measure`: one per model with a colour of its own, the rest folded into one. */
export function shareParts(models: readonly ModelUsage[], measure: ModelMeasure): SharePart[] {
  const colours = modelColours(models);
  const parts: SharePart[] = [];
  let other = 0;
  for (const m of models) {
    const value = modelValue(m, measure) ?? 0;
    const colour = colours.get(modelId(m))!;
    if (colour === OTHER_COLOUR) other += value;
    else parts.push({ id: modelId(m), label: m.model, value, color: colour, text: measureText(m, measure) });
  }
  if (models.length > SERIES_COLOURS) parts.push({ id: 'other', label: otherModels(), value: other, color: OTHER_COLOUR });
  return parts;
}

export interface ModelRow {
  id: string;
  usage: ModelUsage;
  colour: string;
  /** The model's share of `measure` in words (`42%`, `<1%`); '—' when nothing was measured. */
  share: string;
}

/** One row per model, in the order of first use, with its share of `measure`. */
export function modelRows(models: readonly ModelUsage[], measure: ModelMeasure): ModelRow[] {
  const colours = modelColours(models);
  const values = models.map((m) => modelValue(m, measure) ?? 0);
  const pcts = wholePercents(values);
  const measured = values.some((v) => v > 0);
  return models.map((m, i) => ({
    id: modelId(m),
    usage: m,
    colour: colours.get(modelId(m))!,
    share: measured ? sharePercent(pcts[i]!, values[i]!) : '—',
  }));
}
