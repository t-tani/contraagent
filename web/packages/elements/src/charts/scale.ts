// The arithmetic the charts share: an axis of round numbers, the colours of the series.
import type { ChartSeries } from './types.js';

/** The series colours (`--series-1` ...), in their fixed order. */
export const SERIES_COLOURS = 6;
/** The colour of the series folded past the sixth, and of anything that is not a series. */
export const OTHER_COLOUR = 'var(--meter)';

/** Series `i`'s colour: the series colours in order, then the colour of "other". */
export const seriesColour = (i: number): string => (i < SERIES_COLOURS ? `var(--series-${i + 1})` : OTHER_COLOUR);

/** A series with its colour. */
export interface DrawnSeries extends ChartSeries {
  colour: string;
  /** It stands for several series, folded into one. */
  folded?: readonly string[];
}

/**
 * The series as drawn: the first six each in its own colour, by their order (a series
 * keeps its colour whatever its values); with more than six, the sixth and later are
 * summed into one series named `other`, so no colour is ever made up.
 */
export function foldSeries(series: readonly ChartSeries[], other: string): DrawnSeries[] {
  if (series.length <= SERIES_COLOURS) return series.map((s, i) => ({ ...s, colour: seriesColour(i) }));
  const own = series.slice(0, SERIES_COLOURS - 1).map((s, i) => ({ ...s, colour: seriesColour(i) }));
  const rest = series.slice(SERIES_COLOURS - 1);
  const n = Math.max(...rest.map((s) => s.values.length));
  const values = Array.from({ length: n }, (_, j) => {
    const vs = rest.map((s) => s.values[j]).filter((v): v is number => v !== null && v !== undefined);
    return vs.length ? vs.reduce((a, v) => a + v, 0) : null;
  });
  return [...own, { name: other, values, colour: OTHER_COLOUR, folded: rest.map((s) => s.name) }];
}

/** An axis from `low` (0 or below) to a round number at or above `high`, and its ticks (`count` or so). */
export function niceAxis(low: number, high: number, count = 4): { min: number; max: number; ticks: number[] } {
  const lo = Math.min(0, low);
  const hi = Math.max(0, high);
  if (!(hi > lo)) return { min: 0, max: 1, ticks: [0, 1] };
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const min = Math.floor(lo / step) * step;
  const max = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let v = min; v <= max + step / 2; v += step) ticks.push(Math.round(v / step) * step);
  return { min, max, ticks };
}

/** The space kept between two labels of an axis, in px. */
export const LABEL_GAP = 12;

/** Every `k`-th label of `n` fits in `width` px when a label is `labelWidth` px wide: the smallest such `k`. */
export function labelStride(n: number, width: number, labelWidth: number): number {
  if (n <= 0 || width <= 0) return 1;
  return Math.max(1, Math.ceil((n * labelWidth) / width));
}

/** A number as written when the host gives no format: up to two decimals. */
export const plainNumber = (v: number): string => String(Math.round(v * 100) / 100);
