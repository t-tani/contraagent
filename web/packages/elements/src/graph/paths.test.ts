import { describe, expect, it } from 'vitest';
import { edgePath } from './paths.js';

describe('edgePath', () => {
  it('draws an edge as its runs, joined by a curve where it bends', () => {
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 5 }])).toBe('M10,5 L20,5 L40,5');
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 25 }])).toBe('M10,5 L20,5 C30,5 30,25 40,25');
    expect(edgePath([{ a: 10, b: 20, at: 5 }, { a: 40, b: 40, at: 25 }], true)).toBe('M5,10 L5,20 C5,30 25,30 25,40');
    expect(edgePath([])).toBe('');
  });
});
