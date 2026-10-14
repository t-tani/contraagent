// What the charts take: plain series of numbers, and their words.
import type { Tone } from '../core/tone.js';

/** One series: a value per label of the chart's `x`, in that order; null where it has none. */
export interface ChartSeries {
  name: string;
  values: readonly (number | null)[];
}

/** One horizontal bar: its label and value; `tone` gives it a status colour. */
export interface ChartBar {
  label: string;
  value: number;
  tone?: Tone;
}

/** A number in words (`$1.20`, `42%`, `2m 05s`): the host's format for the chart's unit. */
export type ValueText = (value: number) => string;

/** The words of a chart. */
export interface ChartStrings {
  /** What a chart with nothing to draw says. */
  empty: string;
  /** The button that shows the values as a table, and the one that shows the chart again. */
  showTable: string;
  showChart: string;
  /** The column of a table view that holds the labels of `x` (or of the bars). */
  label: string;
  /** The name of the series past the sixth, folded into one. */
  other: string;
  /** The sum of a label's stacked series. */
  total: string;
  /** A value a series has not (null). */
  none: string;
  /** The heatmap's colour scale: its lowest and highest value. */
  scale: (low: string, high: string) => string;
}

export const DEFAULT_CHART_STRINGS: ChartStrings = {
  empty: 'No values',
  showTable: 'Show table',
  showChart: 'Show chart',
  label: 'Label',
  other: 'Other',
  total: 'Total',
  none: '—',
  scale: (low, high) => `${low} to ${high}`,
};
