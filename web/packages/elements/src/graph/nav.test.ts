import { describe, expect, it } from 'vitest';
import { alongEdge } from './nav.js';

describe('keyboard', () => {
  it('moves along an edge to the nearest earlier or later node', () => {
    const g = { drawn: ['a', 'b', 'c'], edges: [{ from: 'a', to: 'b' }, { from: 'a', to: 'c' }], back: [false, false] };
    const across = (id: string) => ({ a: 50, b: 10, c: 60 })[id] ?? 0;
    expect(alongEdge(g, 'a', 'later', across)).toBe('c');
    expect(alongEdge(g, 'b', 'earlier', across)).toBe('a');
    expect(alongEdge(g, 'b', 'later', across)).toBeNull();
  });

  it('does not follow an edge that goes back', () => {
    const g = { drawn: ['a', 'b'], edges: [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }], back: [false, true] };
    expect(alongEdge(g, 'b', 'later', () => 0)).toBeNull();
    expect(alongEdge(g, 'a', 'later', () => 0)).toBe('b');
  });
});
