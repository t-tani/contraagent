// Keyboard moves along a drawn edge.

/**
 * The node joined to `from` along a drawn edge: a later one (`later`, that waits for
 * it or was created after it) or an earlier one; of several, the one nearest across
 * the flow (`across`), then the first in drawing order. Null when there is none.
 */
export function alongEdge(
  g: { drawn: readonly string[]; edges: readonly { from: string; to: string }[]; back: readonly boolean[] },
  from: string,
  dir: 'later' | 'earlier',
  across: (id: string) => number,
): string | null {
  const rank = new Map(g.drawn.map((id, i) => [id, i]));
  const ids = [...new Set(g.edges.filter((e, i) => !g.back[i] && (dir === 'later' ? e.from === from : e.to === from)).map((e) => (dir === 'later' ? e.to : e.from)))];
  const at = across(from);
  ids.sort((a, b) => Math.abs(across(a) - at) - Math.abs(across(b) - at) || (rank.get(a) ?? 0) - (rank.get(b) ?? 0));
  return ids[0] ?? null;
}
