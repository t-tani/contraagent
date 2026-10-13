import { describe, expect, it } from 'vitest';
import { windowRows } from './window.js';

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
