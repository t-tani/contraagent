import { describe, expect, it } from 'vitest';
import { gridStep } from './grid-step.js';

describe('gridStep', () => {
  it('moves between the marks of a grid, past the empty cells', () => {
    const has = [
      [true, false, true],
      [false, false, false],
      [false, true, false],
      [true, false, false],
    ];
    expect(gridStep(has, 0, 0, 'ArrowRight')).toEqual([0, 2]);
    expect(gridStep(has, 0, 2, 'ArrowRight')).toBeNull();
    expect(gridStep(has, 0, 0, 'ArrowDown')).toEqual([3, 0]);
    expect(gridStep(has, 0, 2, 'ArrowDown')).toEqual([2, 1]);
    expect(gridStep(has, 3, 0, 'ArrowUp')).toEqual([0, 0]);
    expect(gridStep(has, 2, 1, 'Home')).toEqual([2, 1]);
    expect(gridStep(has, 3, 0, 'Home', true)).toEqual([0, 0]);
    expect(gridStep(has, 0, 0, 'End', true)).toEqual([3, 0]);
    expect(gridStep(has, 0, 0, 'PageDown', false, 2)).toEqual([2, 1]);
    expect(gridStep(has, 0, 0, 'x')).toBeNull();
  });
});
