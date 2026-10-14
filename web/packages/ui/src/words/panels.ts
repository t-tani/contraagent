// Words for a pipeline's own views (`monitor.Panel`): how a value of a panel body is
// written, by its format, and the words of the charts it draws.
import type { ValueFormat } from '@contraagent/api';
import type { ChartStrings } from '@contraagent/elements/charts';
import { msg, str } from '@lit/localize';
import { fmtDur, localTime, tokenCount, usd } from './format.js';

/** A fraction as a percent: `97%`, `4.5%` under 10, `<0.1%` above 0. */
export function fractionPct(v: number): string {
  const p = v * 100;
  if (p > 0 && p < 0.05) return '<0.1%';
  return Math.abs(p) < 10 ? `${Math.round(p * 10) / 10}%` : `${Math.round(p)}%`;
}

/** A number as it is, up to two decimals. */
const plain = (v: number): string => String(Math.round(v * 100) / 100);

/** A number of a body in words, by its format (`usd`, `pct` a fraction, `duration` seconds, `tokens`). */
export function numberText(format: ValueFormat | null | undefined): (v: number) => string {
  switch (format) {
    case 'usd':
      return usd;
    case 'pct':
      return fractionPct;
    case 'duration':
      return fmtDur;
    case 'tokens':
      return tokenCount;
    default:
      return plain;
  }
}

/** A cell of a table body in words: a number by its format, a `datetime` as an absolute time, '—' when empty. */
export function cellText(value: unknown, format: ValueFormat | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  if (format === 'datetime' && typeof value === 'string') return localTime(value, true) || value;
  if (typeof value === 'number') return numberText(format)(value);
  if (typeof value === 'boolean') return String(value);
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** The words of a chart, in the UI's language. */
export const chartStrings = (): Partial<ChartStrings> => ({
  empty: msg('No values'),
  showTable: msg('Show table'),
  showChart: msg('Show chart'),
  label: msg('Label', { desc: 'Column of a chart\'s table view: the label of each point or bar' }),
  other: msg('Other', { desc: 'The series of a chart past the sixth, summed into one' }),
  total: msg('Total'),
  none: '—',
  scale: (low: string, high: string) => msg(str`${low} to ${high}`, { desc: 'A heatmap\'s colour scale: its lowest and highest value' }),
});
