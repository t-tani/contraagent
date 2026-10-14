// Words for a pipeline's own journal columns (`row_extras`): the columns it adds to each
// attempt's row, named by the pipeline itself.
import { msg } from '@lit/localize';

/** What such a column is, for a header's tooltip. */
export const customColumnTip = (): string => msg('Custom column (row_extras)');

/** A custom column's value as text: a string as it is, a number or a boolean as written, anything else as compact JSON; '—' when absent. */
export function customValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v) ?? '—';
  } catch {
    return '—'; // not JSON (a journal row is JSON, so only a hand-built value)
  }
}

/** The custom columns `names` of `row` that have a value, as `[name, text]`. */
export function customValues(row: object, names: readonly string[]): [string, string][] {
  const r = row as Record<string, unknown>;
  return names.filter((n) => r[n] !== null && r[n] !== undefined && r[n] !== '').map((n) => [n, customValue(r[n])]);
}
