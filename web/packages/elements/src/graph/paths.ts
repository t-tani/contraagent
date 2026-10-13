// Edges and loop returns as SVG paths.
import { RETURN_R, type LoopReturn, type Stretch } from './layout.js';

/**
 * A loop box's return as an SVG path: out from its last layer to the band, back along
 * it with rounded corners, and in to its first layer, stopping `gap` short of each item.
 */
export function returnPath(r: LoopReturn, down = false, gap = 3): string {
  const r2 = (n: number) => Math.round(n * 2) / 2;
  const pt = (u: number, v: number) => (down ? `${r2(v)},${r2(u)}` : `${r2(u)},${r2(v)}`);
  const k = Math.max(0, Math.min(RETURN_R, (r.from - r.to) / 2, r.band - r.v0 - gap, r.band - r.v1 - gap));
  return [
    `M${pt(r.from, r.v0 + gap)}`,
    `L${pt(r.from, r.band - k)}`,
    `Q${pt(r.from, r.band)} ${pt(r.from - k, r.band)}`,
    `L${pt(r.to + k, r.band)}`,
    `Q${pt(r.to, r.band)} ${pt(r.to, r.band - k)}`,
    `L${pt(r.to, r.v1 + gap)}`,
  ].join(' ');
}

/** An edge's line as an SVG path: its runs, joined by a curve in each gap where it bends. */
export function edgePath(runs: readonly Stretch[], down = false): string {
  const r2 = (n: number) => Math.round(n * 2) / 2;
  const pt = (u: number, v: number) => (down ? `${r2(v)},${r2(u)}` : `${r2(u)},${r2(v)}`);
  const first = runs[0];
  if (!first) return '';
  let d = `M${pt(first.a, first.at)}`;
  runs.forEach((r, i) => {
    if (r.b !== r.a) d += ` L${pt(r.b, r.at)}`;
    const next = runs[i + 1];
    if (!next) return;
    if (Math.abs(next.at - r.at) < 0.5) {
      if (next.a !== r.b) d += ` L${pt(next.a, next.at)}`;
      return;
    }
    const m = (r.b + next.a) / 2;
    d += ` C${pt(m, r.at)} ${pt(m, next.at)} ${pt(next.a, next.at)}`;
  });
  return d;
}
