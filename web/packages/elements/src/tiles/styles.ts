// The look of `<cae-stat-tiles>`: figures in rows, a line between two of a
// row, neutral by default. A tile with a tone takes it on its value and on the
// mark before its label. The host is a container: fewer columns, and smaller
// values, as it narrows.
import { css } from 'lit';

export const statTilesStyles = css`
  /* the line before the first tile of a row lies outside the host, which clips it */
  :host { display: block; container-type: inline-size; overflow: clip; }
  .tiles { display: grid; grid-template-columns: repeat(var(--cae-stat-tiles-columns, 5), minmax(0, 1fr)); gap: var(--cae-stat-tiles-gap, 20px) 0; margin-inline-start: -17px; }
  @container (max-width: 1100px) { .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  @container (max-width: 660px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @container (max-width: 420px) { .value { font-size: var(--font-size-xl); } }
  @container (max-width: 240px) { .tiles { grid-template-columns: minmax(0, 1fr); } }
  .tile { position: relative; min-width: 0; padding: 0 16px; border-inline-start: 1px solid var(--line); }
  .label { font-size: var(--font-size-xs); font-weight: 500; color: var(--text-muted); }
  .value { overflow-wrap: anywhere; font-size: var(--font-size-2xl); font-weight: 650; line-height: 1.2; margin-top: 2px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; color: var(--text); }
  .sub { font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 2px; }
  /* a tile with an action is a link as a whole: the link covers the tile */
  .action { position: absolute; inset: 0 4px; border-radius: var(--radius-md); }
  .action:focus-visible { outline-offset: calc(-1 * var(--focus-width)); }
  .tile:has(.action):hover .label { color: var(--accent); }
  .tile[data-tone] .value, .tile[data-tone] .label::before { color: var(--tone); }
  .label[data-mark]::before { display: inline-block; }
`;
