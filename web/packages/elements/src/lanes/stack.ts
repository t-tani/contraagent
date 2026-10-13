// Where the bars of `<cae-lanes>` go: their row in a lane, their box on the
// axis, and the axis when the host does not set one. Pure.
import type { Lane, TimeRange } from './types.js';

interface Span {
  start: number;
  end: number | null;
}

/**
 * The bars of a lane in order of start, each on the first row whose last bar
 * has ended, so overlapping bars do not hide each other. A running bar (`end`
 * null) keeps its row.
 */
export function stack<B extends Span>(bars: readonly B[]): { bar: B; row: number }[] {
  const ends: number[] = [];
  return [...bars]
    .sort((a, b) => a.start - b.start)
    .map((bar) => {
      const end = bar.end ?? Infinity;
      let row = ends.findIndex((e) => e <= bar.start);
      if (row < 0) row = ends.push(end) - 1;
      else ends[row] = end;
      return { bar, row };
    });
}

/** A running bar extends the axis to now plus this margin, rounded up to `STEP_MS`. */
const MARGIN_MS = 20e3;
const STEP_MS = 60e3;

/**
 * The axis that fits the bars: from the first start to the last end; with a
 * running bar, to `now` plus 20 seconds, rounded up to the minute. Null with no bars.
 */
export function fitRange(lanes: readonly Lane[], now: number): TimeRange | null {
  const bars = lanes.flatMap((l) => l.bars);
  if (!bars.length) return null;
  const start = Math.min(...bars.map((b) => b.start));
  const running = bars.some((b) => b.end === null);
  const end = running ? start + Math.ceil((now - start + MARGIN_MS) / STEP_MS) * STEP_MS : Math.max(...bars.map((b) => b.end ?? now));
  return { start, end };
}

/** A bar's left edge and width, in percent of the range; a running bar grows to `now`, within the range. */
export function barBox(b: Span, range: TimeRange, now: number): { left: number; width: number } {
  const span = Math.max(1, range.end - range.start);
  const left = ((b.start - range.start) / span) * 100;
  const w = (((b.end ?? now) - b.start) / span) * 100;
  return { left, width: Math.max(0.4, b.end === null ? Math.min(100 - left, w) : w) };
}
