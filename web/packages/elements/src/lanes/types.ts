// What `<cae-lanes>` shows: bars on a time axis, a lane per group.

/** Something that took time: from `start` to `end` (epoch ms); `end` null while it runs. */
export interface LaneBar {
  id: string;
  start: number;
  /** Null: running, the bar grows to now. */
  end: number | null;
  /** The key of its look in the element's `barStyles`. */
  style: string;
  /** The bar's tooltip: one item per line. */
  label: string;
}

/** A row of bars; overlapping bars of a lane are stacked (`stack`). */
export interface Lane {
  id: string;
  label: string;
  bars: readonly LaneBar[];
}

/** How a bar is filled: its colour, hatched, moving stripes, or only an outline. */
export type LanePattern = 'solid' | 'hatched' | 'striped' | 'outline';

/** A look of bars, and its entry in the legend. */
export interface LaneStyle {
  label: string;
  /** A CSS colour or `var(...)`. */
  color: string;
  pattern?: LanePattern;
  /** The legend row of its entry (0, the first, by default). */
  group?: number;
}

export interface LanesStrings {
  /** The note after the legend: bars the host left out. */
  omitted: (n: number) => string;
  /** No bars. */
  empty: string;
}

export const DEFAULT_LANES_STRINGS: LanesStrings = {
  omitted: (n) => (n === 1 ? '1 bar not shown' : `${n} bars not shown`),
  empty: 'No bars',
};

/** The time the axis spans, epoch ms. */
export interface TimeRange {
  start: number;
  end: number;
}
