import { describe, expect, it } from 'vitest';
import { asBar, barParts, markGrid } from './marks.js';

describe('a node of many marks', () => {
  it("shows a bar above 200 marks, with each state's share", () => {
    const many = Array.from({ length: 201 }, (_, i) => ({ id: `k${i}`, state: 'done', label: `u${i}` }));
    expect(asBar({ marks: many, loose: [] })).toBe(true);
    expect(asBar({ marks: many.slice(1), loose: [] })).toBe(false);
    expect(asBar({ marks: many.slice(1), loose: [] }, 100)).toBe(true);
    expect(barParts({ done: 3, failed: 1, running: 0, pending: 0 }, ['done', 'failed', 'running'])).toEqual([
      { state: 'done', n: 3, pct: 75 },
      { state: 'failed', n: 1, pct: 25 },
    ]);
  });
});

describe('markGrid', () => {
  it('one row up to 12 units, then 10 and 20 columns of smaller marks', () => {
    expect([0, 6, 12, 13, 100, 101, 2000].map(markGrid)).toEqual([
      { cols: 1, size: 12 },
      { cols: 6, size: 12 },
      { cols: 12, size: 12 },
      { cols: 10, size: 10 },
      { cols: 10, size: 10 },
      { cols: 20, size: 6 },
      { cols: 20, size: 6 },
    ]);
  });
});
