// The look of `<cae-stat-tiles>`: a grid of tiles, neutral by default. A tile
// with a tone takes it on its value, the mark before its label and a thin edge.
import { css } from 'lit';

export const statTilesStyles = css`
  :host { display: block; }
  .tiles { display: grid; grid-template-columns: repeat(var(--cae-stat-tiles-columns, 5), minmax(0, 1fr)); gap: var(--cae-stat-tiles-gap, 12px); }
  @media (max-width: 1150px) { .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  @media (max-width: 700px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .tile { position: relative; background: color-mix(in srgb, var(--text) 2.5%, transparent); border: 1px solid var(--line);
    border-radius: 11px; padding: 12px 14px; overflow: hidden; }
  .tile::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--edge, transparent); }
  .label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
  .value { font-size: 28px; font-weight: 700; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; color: var(--text); }
  .sub { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
  .action { font-size: 11.5px; margin-top: 4px; }
  .tile[data-tone] { --edge: var(--tone); }
  .tile[data-tone] .value, .tile[data-tone] .label::before { color: var(--tone); }
  .label[data-mark]::before { display: inline-block; }
`;
