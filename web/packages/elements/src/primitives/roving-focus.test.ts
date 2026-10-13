import { describe, expect, it } from 'vitest';
import { rovingStep } from './roving-focus.js';

describe('rovingStep', () => {
  it('moves along a row or a column, stops at the ends unless it wraps', () => {
    const h = { layout: 'horizontal' as const };
    expect(rovingStep(3, 0, 'ArrowRight', h)).toBe(1);
    expect(rovingStep(3, 2, 'ArrowRight', h)).toBeNull();
    expect(rovingStep(3, 2, 'ArrowRight', { ...h, wrap: true })).toBe(0);
    expect(rovingStep(3, 0, 'ArrowLeft', { ...h, wrap: true })).toBe(2);
    expect(rovingStep(3, 1, 'ArrowDown', h)).toBeNull();
    expect(rovingStep(3, 1, 'ArrowDown', { layout: 'vertical' })).toBe(2);
    expect(rovingStep(3, 1, 'Home', h)).toBe(0);
    expect(rovingStep(3, 1, 'End', h)).toBe(2);
    expect(rovingStep(3, 0, 'Home', h)).toBeNull();
    expect(rovingStep(0, 0, 'ArrowRight', h)).toBeNull();
  });

  // A grid of 7 items in rows of 3:
  //   0 1 2
  //   3 4 5
  //   6
  const grid = { layout: 'grid' as const, cols: 3 };

  it('moves in a grid: in the row, in the column, to the row ends', () => {
    expect(rovingStep(7, 4, 'ArrowRight', grid)).toBe(5);
    expect(rovingStep(7, 5, 'ArrowRight', grid)).toBeNull();
    expect(rovingStep(7, 3, 'ArrowLeft', grid)).toBeNull();
    expect(rovingStep(7, 1, 'ArrowDown', grid)).toBe(4);
    expect(rovingStep(7, 4, 'ArrowDown', grid)).toBeNull();
    expect(rovingStep(7, 3, 'ArrowDown', grid)).toBe(6);
    expect(rovingStep(7, 4, 'ArrowUp', grid)).toBe(1);
    expect(rovingStep(7, 1, 'ArrowUp', grid)).toBeNull();
    expect(rovingStep(7, 5, 'Home', grid)).toBe(3);
    expect(rovingStep(7, 3, 'End', grid)).toBe(5);
    expect(rovingStep(7, 6, 'End', grid)).toBeNull();
    expect(rovingStep(7, 6, 'ArrowRight', grid)).toBeNull();
  });

  it('goes to the first and last item with Ctrl+Home and Ctrl+End', () => {
    expect(rovingStep(7, 4, 'Home', { ...grid, ctrl: true })).toBe(0);
    expect(rovingStep(7, 4, 'End', { ...grid, ctrl: true })).toBe(6);
  });

  it('ignores other keys', () => {
    expect(rovingStep(7, 4, 'Enter', grid)).toBeNull();
    expect(rovingStep(7, 4, 'a', { layout: 'horizontal' })).toBeNull();
  });
});
