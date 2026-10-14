import { describe, expect, it } from 'vitest';
import { rowOffsets, windowRows, windowRowsAt } from './window.js';

describe('windowRows', () => {
  it('draws the rows in view and the overscan, with pads for the rest', () => {
    // 1000 rows of 32 px, 320 px of view at row 100.
    const w = windowRows(1000, 3200, 320, 32, 5);
    expect(w).toEqual({ from: 95, to: 116, padTop: 95 * 32, padBottom: (1000 - 116) * 32 });
  });

  it('keeps the total height', () => {
    for (const top of [0, 10, 5000, 31_990, 99_999]) {
      const w = windowRows(1000, top, 500, 32);
      expect(w.padTop + (w.to - w.from) * 32 + w.padBottom).toBe(1000 * 32);
      expect(w.from).toBeLessThanOrEqual(w.to);
    }
  });

  it('clamps at the start and the end', () => {
    expect(windowRows(1000, 0, 320, 32, 5)).toMatchObject({ from: 0, padTop: 0 });
    expect(windowRows(1000, 1e9, 320, 32, 5)).toMatchObject({ from: 1000, to: 1000, padBottom: 0 });
    expect(windowRows(1000, -50, 320, 32, 5).from).toBe(0);
  });

  it('draws every row of a short list, and none of an empty one', () => {
    expect(windowRows(10, 0, 800, 32)).toEqual({ from: 0, to: 10, padTop: 0, padBottom: 0 });
    expect(windowRows(0, 0, 800, 32)).toEqual({ from: 0, to: 0, padTop: 0, padBottom: 0 });
  });
});

describe('windowRowsAt', () => {
  // Rows of 20, 60, 20, 60 ... px: rows of different heights.
  const offsets = rowOffsets(1000, (i) => (i % 2 ? 60 : 20));

  it('draws the rows in view and the overscan, with pads of their own heights', () => {
    // 2000 px down: row 50 starts at 25 * 80 = 2000.
    const w = windowRowsAt(offsets, 2000, 160, 2);
    // rows 50-53 fill the 160 px; row 54 starts at its bottom edge
    expect(w).toEqual({ from: 48, to: 57, padTop: offsets[48], padBottom: offsets[1000]! - offsets[57]! });
  });

  it('keeps the total height', () => {
    for (const top of [0, 10, 5000, 39_990, 1e9]) {
      const w = windowRowsAt(offsets, top, 500);
      expect(w.padTop + (offsets[w.to]! - offsets[w.from]!) + w.padBottom).toBe(offsets[1000]);
      expect(w.from).toBeLessThanOrEqual(w.to);
    }
  });

  it('clamps at the start and the end, and draws nothing of an empty list', () => {
    expect(windowRowsAt(offsets, -50, 100, 0).from).toBe(0);
    expect(windowRowsAt(offsets, 1e9, 100, 0)).toMatchObject({ to: 1000, padBottom: 0 });
    expect(windowRowsAt(rowOffsets(0, () => 20), 0, 100)).toEqual({ from: 0, to: 0, padTop: 0, padBottom: 0 });
  });

  it('agrees with windowRows when every row is one height', () => {
    expect(windowRowsAt(rowOffsets(1000, () => 32), 3200, 320, 5)).toEqual(windowRows(1000, 3200, 320, 32, 5));
  });
});
