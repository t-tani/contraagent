import { describe, expect, it } from 'vitest';
import { layerGraph } from './layer.js';
import { alongEdge, gridStep } from './nav.js';
import { AT, LOOP, RUN, node, planOf, reviewRun } from './plans.fixture.js';

describe('keyboard', () => {
  it('moves along an edge to the nearest earlier or later node', () => {
    const plan = planOf([
      node('a-u', 'u', 'a', 'done'), node('b-u', 'u', 'b', 'done', { after: ['a-u'] }), node('c-u', 'u', 'c', 'done', { after: ['a-u'] }),
    ]);
    const g = layerGraph(plan);
    const across = (id: string) => ({ 'kind:a': 50, 'kind:b': 10, 'kind:c': 60 })[id] ?? 0;
    expect(alongEdge(g, 'kind:a', 'later', across)).toBe('kind:c');
    expect(alongEdge(g, 'kind:b', 'earlier', across)).toBe('kind:a');
    expect(alongEdge(g, 'kind:b', 'later', across)).toBeNull();
  });

  it('does not follow an edge back to the next pass', () => {
    const g = layerGraph(reviewRun({ a: 2 }), [RUN, LOOP]);
    expect(alongEdge(g, `kind:check@${AT}`, 'later', () => 0)).toBeNull();
  });

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
