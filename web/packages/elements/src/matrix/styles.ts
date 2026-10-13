// A mark matrix's styles: the line above it, the table, its sticky headers and its marks.
import { css, unsafeCSS } from 'lit';
import { FRAME_MIN, FRAME_SHARE } from '../core/frame.js';

/** A row's height, in px: what the windowing counts in. */
export const ROW_H = 24;

export const matrixStyles = css`
  /* The block is the box: it lays out where the host is placed. */
  :host { display: contents; }
  /* At least wide enough for the caption and the sort beside it: a narrower table is stretched to it. */
  .mxblock { display: flex; flex-direction: column; width: fit-content; max-width: 100%; min-width: min(100%, 27rem);
    animation: view-in 0.1s var(--ease) both; }
  @keyframes view-in { from { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .mxblock { animation: none; } }
  .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; margin-bottom: 8px; font-size: 12px; color: var(--text-2);
    width: 0; min-width: 100%; box-sizing: border-box; }
  .mxbar .cap { color: var(--text); font-weight: 600; }
  .mxbar .sum { flex: 1 0 100%; min-width: 0; }
  .mxbar .f { white-space: nowrap; }
  .sep { color: var(--text-muted); }
  .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--text-muted); font-size: 11.5px; white-space: nowrap; }
  .mxbar select { font: inherit; font-size: 11.5px; color: var(--text); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
  .mxbar select:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
  .mx { overflow: auto; max-width: 100%; max-height: max(${FRAME_MIN}px, ${unsafeCSS(FRAME_SHARE * 100)}vh); border-radius: 6px; border: 1px solid var(--line); }
  table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: 100%; min-width: max-content; }
  .matrix th, .matrix td { padding: 0 6px; height: ${ROW_H}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
  .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--text-muted); font-weight: 500; text-align: center; height: 22px; }
  .matrix thead th.nh { font-family: var(--mono); color: var(--text-2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
  .matrix thead th.group { color: var(--text-2); }
  .matrix thead th.group.code { font-family: var(--mono); color: var(--text-muted); }
  .matrix .uh, .matrix tbody th { position: sticky; left: 0; z-index: 1; background: var(--panel); text-align: left; }
  .matrix thead .uh { z-index: 3; }
  .matrix thead .uh, .matrix thead .pn { background: var(--panel2); }
  .matrix tbody th { font-family: var(--mono); font-weight: 600; color: var(--text); max-width: 220px; overflow: hidden; text-overflow: ellipsis; }
  .matrix tbody th.none { font-family: var(--sans); font-weight: 500; color: var(--text-muted); }
  .matrix .pn { text-align: right; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .matrix .pn.many { color: var(--text); font-weight: 600; }
  .matrix td.c { text-align: center; --m: 12px; }
  .matrix td.c .mark { vertical-align: middle; }
  .matrix .g0 { border-left: 1px solid var(--line2); }
  .matrix .g1 { border-left: 1px dashed var(--line); }
  .matrix tbody tr:hover td, .matrix tbody tr:hover th { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
  .matrix tbody tr.on td, .matrix tbody tr.on th { background-color: var(--accent-bg); }
  .matrix .gap td { padding: 0; border: 0; }
  .mx.hl .mark:not(.on) { opacity: 0.4; }
  .mx.hl .mark.on { transform: scale(1.2); }
`;
