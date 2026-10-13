import { describe, expect, it } from 'vitest';
import { barBox, fitRange, stack } from './stack.js';
import type { Lane } from './types.js';

const bar = (id: string, start: number, end: number | null) => ({ id, start, end, style: 's', label: id });

describe('stack', () => {
  it('puts each bar on the first row whose last bar has ended, in order of start', () => {
    const placed = stack([bar('c', 15, 20), bar('a', 0, 10), bar('b', 5, 12)]);
    expect(placed.map((p) => [p.bar.id, p.row])).toEqual([
      ['a', 0],
      ['b', 1],
      ['c', 0],
    ]);
  });

  it('keeps a running bar on its row', () => {
    expect(stack([bar('run', 0, null), bar('later', 50, 60)]).map((p) => p.row)).toEqual([0, 1]);
  });
});

describe('fitRange', () => {
  const lanes = (...bs: ReturnType<typeof bar>[]): Lane[] => [{ id: 'l', label: 'l', bars: bs }];

  it('spans the first start to the last end', () => {
    expect(fitRange(lanes(bar('a', 1000, 5000), bar('b', 2000, 9000)), 99999)).toEqual({ start: 1000, end: 9000 });
  });

  it('with a running bar, ends at now plus 20 seconds, rounded up to the minute', () => {
    expect(fitRange(lanes(bar('a', 0, null)), 30e3)).toEqual({ start: 0, end: 60e3 });
    expect(fitRange(lanes(bar('a', 0, null)), 50e3)).toEqual({ start: 0, end: 120e3 });
  });

  it('is null with no bars', () => {
    expect(fitRange([], 0)).toBeNull();
  });
});

describe('barBox', () => {
  it('places a bar in percent of the range', () => {
    expect(barBox({ start: 25, end: 75 }, { start: 0, end: 100 }, 0)).toEqual({ left: 25, width: 50 });
  });

  it('grows a running bar to now, within the range', () => {
    expect(barBox({ start: 0, end: null }, { start: 0, end: 60e3 }, 30e3)).toEqual({ left: 0, width: 50 });
    expect(barBox({ start: 50, end: null }, { start: 0, end: 100 }, 500)).toEqual({ left: 50, width: 50 });
  });

  it('draws a bar too short to see at a minimum width', () => {
    expect(barBox({ start: 10, end: 10 }, { start: 0, end: 100 }, 0).width).toBe(0.4);
  });
});
