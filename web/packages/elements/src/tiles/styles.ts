// The look of `<cae-stat-tiles>`: figures in rows, a line between two of a
// row, neutral by default. A tile with a tone takes it on its value and on the
// mark before its label. The host is a container: fewer columns, and smaller
// values, as it narrows.
import { css } from 'lit';

export const statTilesStyles = css`
  /* The line before a tile stands in the middle of the space before it, whatever a page gives the tile itself
     (its part); the one before the first tile of a row lies outside the host, which clips it. */
  :host { display: block; container-type: inline-size; overflow-x: clip; }
  .tiles { --_gap: var(--cae-stat-tiles-gap, 32px); display: grid; grid-template-columns: repeat(var(--cae-stat-tiles-columns, 5), minmax(0, 1fr));
    gap: min(var(--_gap), 20px) var(--_gap); }
  @container (max-width: 1100px) { .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  @container (max-width: 660px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @container (max-width: 420px) { .value { font-size: var(--font-size-xl); } }
  @container (max-width: 240px) { .tiles { grid-template-columns: minmax(0, 1fr); } }
  .tile { position: relative; min-width: 0; }
  .tile::before { content: ''; position: absolute; inset-block: 0; inset-inline-start: calc(var(--_gap) / -2); border-inline-start: 1px solid var(--line); }
  .label { font-size: var(--font-size-xs); font-weight: 500; color: var(--text-muted); }
  .value { overflow-wrap: anywhere; font-size: var(--font-size-2xl); font-weight: 650; line-height: 1.2; margin-top: 2px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; color: var(--text); }
  .sub { font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 2px; }
  /* a tile with an action is a link as a whole: the link covers the tile */
  .action { position: absolute; inset: 0; border-radius: var(--radius-md); }
  .action:focus-visible { outline-offset: 2px; }
  .tile:has(.action):hover .label { color: var(--accent); }
  .tile[data-tone] .value, .tile[data-tone] .label::before { color: var(--tone); }
  .label[data-mark]::before { display: inline-block; }
`;
