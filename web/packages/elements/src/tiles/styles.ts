// The look of `<cae-stat-tiles>`: a grid of tiles, neutral by default. A tile
// with a tone takes it on its value, the mark before its label and a thin edge.
// The host is a container: fewer columns, and smaller values, as it narrows.
import { css } from 'lit';

export const statTilesStyles = css`
  :host { display: block; container-type: inline-size; }
  .tiles { display: grid; grid-template-columns: repeat(var(--cae-stat-tiles-columns, 5), minmax(0, 1fr)); gap: var(--cae-stat-tiles-gap, 12px); }
  @container (max-width: 1100px) { .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  @container (max-width: 660px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @container (max-width: 420px) { .tile { padding: 10px 12px; } .value { font-size: 22px; } }
  @container (max-width: 240px) { .tiles { grid-template-columns: minmax(0, 1fr); } }
  .tile { position: relative; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line);
    border-radius: 11px; padding: 12px 14px; overflow: hidden; }
  .tile::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--edge, transparent); }
  .label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
  .value { overflow-wrap: anywhere; font-size: 28px; font-weight: 700; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; color: var(--text); }
  .sub { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
  /* a tile with an action is a link as a whole: the link covers the tile */
  .action { position: absolute; inset: 0; border-radius: inherit; }
  .action:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .tile:has(.action):hover { border-color: var(--accent); }
  .tile[data-tone] { --edge: var(--tone); }
  .tile[data-tone] .value, .tile[data-tone] .label::before { color: var(--tone); }
  .label[data-mark]::before { display: inline-block; }
`;
