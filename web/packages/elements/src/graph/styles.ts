// A layered graph's styles: the frame, the drawing, the nodes and clusters, the
// node table, the card and the row under the frame.
import { css } from 'lit';

export const graphStyles = css`
  :host { display: block; }
  /* A column: the crumbs, the frame, the row under it. A height set on the host is the frame's to fill or give up. */
  .col { display: flex; flex-direction: column; height: 100%; }
  .main { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }
  .foot { flex: none; }

  /* One frame for every view: the drawing, the node table and a mark matrix. */
  .frame { flex: 1 1 auto; min-height: 0; position: relative; overflow: hidden; border-radius: 8px; background: var(--well); box-sizing: border-box; }
  .gframe { cursor: grab; touch-action: none; }
  .gframe.drag { cursor: grabbing; }
  .stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
  .gframe.down { touch-action: pan-y pinch-zoom; }
  /* A view's content fades in when the view changes; the frame stays. */
  .view { animation: view-in 0.1s var(--ease) both; }
  @keyframes view-in { from { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .view { animation: none; } }
  .tools { display: flex; align-items: center; gap: 4px; justify-self: end; }
  .tools button { all: unset; cursor: pointer; min-width: 22px; height: 22px; padding: 0 7px; box-sizing: border-box; text-align: center;
    font-size: 11.5px; line-height: 22px; color: var(--text-2); border-radius: 6px; border: 1px solid var(--line); }
  .tools button:hover:not(:disabled) { color: var(--text); border-color: var(--line2); }
  .tools button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
  .tools button:disabled { cursor: default; opacity: 0.4; }
  /* Graph | Table: the chosen one is raised. */
  .views { margin-left: 6px; }

  .dag { position: relative; }
  .dag.unplaced { visibility: hidden; }
  .dag > *, .cluster > .in > * { position: absolute; }
  .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
  .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
  .edges path.dashed { stroke-dasharray: 5 4; }
  /* A cluster's return to its next round: dotted, lighter than the edges, under the cluster's nodes. */
  .edges path.ret, .legend svg path.ret { stroke: var(--text-2); stroke-width: 2; stroke-dasharray: 0.1 4; stroke-linecap: round; opacity: 0.8; }
  .edges path.ret-tip, .legend svg path.ret-head { fill: var(--text-2); stroke: none; opacity: 0.8; }
  .ic { display: block; flex: none; }
  .loop-ic { color: var(--text-2); }
  .in-ic { color: var(--text-muted); }

  .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); padding: 3px 9px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

  .cluster { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: color-mix(in srgb, var(--text-muted) 5%, transparent); }
  .cluster .cluster { background: color-mix(in srgb, var(--text-muted) 6%, transparent); }
  .cluster > .in { position: absolute; inset: 0; pointer-events: none; }
  .cluster > .in > * { pointer-events: auto; }
  /* Room on the right for the mark of an inner view: the cluster is as wide as its label. */
  .cluster > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
    white-space: nowrap; justify-content: flex-start; padding-right: 22px; }
  .cluster > .hd .line { display: flex; align-items: center; gap: 8px; }
  .cluster > .hd .name { display: inline-flex; align-items: center; gap: 5px; }
  .cluster > .hd { cursor: pointer; }
  .cluster.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
  .cluster > .hd .spread { font-size: 11px; color: var(--text-2); font-variant-numeric: tabular-nums; }

  .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
    display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
    border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s;
    cursor: pointer; box-shadow: var(--ex, 0 0 0 0 transparent); }
  /* An accent: a thin line along the node's left side, an identity, not a status. */
  .node.accent { --ex: inset 3px 0 0 -1px color-mix(in srgb, var(--agent) 60%, transparent); }
  .node .nm { display: flex; align-items: center; min-width: 0; gap: 0; }
  .node .right { display: flex; align-items: center; gap: 8px; }
  /* The mark of an inner view: at the top right of a node and of a cluster alike. */
  .cue { display: block; line-height: 0; }
  .cluster > .cue { position: absolute; top: 9px; right: 10px; }
  .node.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
  .node.drill { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
  .node[data-look='running'] { border-color: var(--status-running); }
  .node.drill[data-look='running'] { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--status-running), 0 0 14px var(--status-running-bg); }
  .node:not(.drill)[data-look='running'] { box-shadow: var(--ex, 0 0 0 0 transparent), 0 0 14px var(--status-running-bg); }
  .node[data-look='failed'] { border-color: color-mix(in srgb, var(--status-failed) 55%, transparent); }
  .node:focus-within { border-color: var(--text-2); }
  .hd { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .name { all: unset; cursor: pointer; font-family: var(--mono); font-weight: 600; font-size: 12.5px; color: var(--text);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
  .name:hover { text-decoration: underline; }
  .name:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
  .count { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .ex { display: flex; flex-wrap: wrap; gap: 0 10px; font-size: 11px; line-height: 1.5;
    max-width: max(98px, calc(var(--cols) * var(--m) + (var(--cols) - 1) * var(--g))); }
  .ex .err { color: var(--status-failed); }
  .ex .warn { color: var(--status-attention); }
  .ex .live { color: var(--status-running); }
  .ex .mut { color: var(--text-muted); }

  .marks { display: grid; grid-template-columns: repeat(var(--cols), var(--m)); gap: var(--g); }
  .slot { width: var(--m); height: var(--m); }
  .taskchip.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 1px; }
  .hl .mark:not(.on) { opacity: 0.16; }
  .hl .mark.on { transform: scale(1.2); }
  @media (prefers-reduced-motion: reduce) {
    .node { transition: none; }
  }

  .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
  .sbar i { display: block; min-width: 2px; height: 100%; background: var(--tone, var(--line2)); }
  .sbar i:not([data-tone]) { --tone: initial; }
  .sbar i[data-tone='done'] { opacity: 0.85; }
  .sbar i[data-tone='muted'] { opacity: 0.5; }
  .sbar i[data-shape='hatched'] { background: repeating-linear-gradient(135deg, var(--tone-bg) 0 2px, color-mix(in srgb, var(--tone) 60%, transparent) 2px 3px); }
  .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--text-muted); }
  .fails .taskchip { color: var(--status-failed); border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); }
  .fails .taskchip:focus-visible { outline: var(--focus-width) solid var(--text); outline-offset: 1px; }
  .hl .fails .taskchip:not(.on) { opacity: 0.4; }

  /* A mark matrix: centred in the frame. */
  .mxframe { display: grid; grid-template-columns: minmax(0, 1fr); place-items: center; padding: 14px 16px; }

  /* The legend on the left, the tools at the right end of the first line, in every view. */
  .foot { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 6px 14px; margin-top: 6px; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend .mark { --m: 12px; cursor: default; animation: none; }
  .legend .mark:hover { transform: none; outline: none; }
  /* A mark in the legend is a swatch: a rounded square, a problem's shape a sharper one. */
  .legend i.mark { border-radius: 3px; }
  .legend i.mark:is([data-shape='square'], [data-shape='hatched']) { border-radius: 2px; }
  .legend i.mark[data-shape='hatched'] { background: repeating-linear-gradient(135deg, transparent 0 2px, color-mix(in srgb, var(--tone) 55%, transparent) 2px 3px); }
  .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }

  .main { position: relative; min-width: 0; }
  .sep { color: var(--text-muted); }

  /* The selection's card: beside the item, joined to it by a pointer, in the accent of the item's outline. */
  .insp { position: absolute; left: 0; top: 0; z-index: 6; width: 272px; max-width: calc(100% - 16px); box-sizing: border-box;
    display: flex; flex-direction: column; gap: 9px; padding: 10px 12px 12px; border-radius: 10px;
    border: 1px solid var(--accent); background: var(--card); font-size: 12px; overflow: visible;
    box-shadow: 0 12px 32px color-mix(in srgb, var(--shadow) 55%, transparent); visibility: hidden;
    animation: insp-in 0.12s var(--ease) both; }
  .insp.placed { visibility: visible; }
  .insp .scroll { display: flex; flex-direction: column; gap: 9px; min-height: 0; overflow: auto; }
  .insp .ptr { position: absolute; width: 10px; height: 10px; background: var(--card); border: 1px solid var(--accent);
    transform: rotate(45deg); }
  .insp[data-side='right'] .ptr { left: -6px; top: calc(var(--arrow) - 5px); border-top: 0; border-right: 0; }
  .insp[data-side='left'] .ptr { right: -6px; top: calc(var(--arrow) - 5px); border-bottom: 0; border-left: 0; }
  .insp[data-side='below'] .ptr { top: -6px; left: calc(var(--arrow) - 5px); border-bottom: 0; border-right: 0; }
  .insp[data-side='above'] .ptr { bottom: -6px; left: calc(var(--arrow) - 5px); border-top: 0; border-left: 0; }
  /* A narrow screen: a sheet under the frame. */
  .insp.sheet { position: sticky; bottom: 8px; width: auto; max-width: none; margin-top: 8px; visibility: visible; }
  .insp.sheet .ptr { display: none; }
  @keyframes insp-in { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: none; } }
  /* The key hints keep their room: the focus moves nothing. */
  .keys { grid-column: 1 / -1; font-size: 11px; color: var(--text-muted); visibility: hidden; }
  .keys span { white-space: nowrap; }
  :host(:focus-within) .keys { visibility: visible; }
  /* Touch alone: no keys, no line. */
  @media not (any-pointer: fine) { .keys { display: none; } }

  /* The node table: across the frame's content box, the name and status as wide as their content, the relations sharing the rest. */
  /* A shadow at an edge the table scrolls past: a lid over it at the end, a shadow fixed to the frame. */
  .tframe { overflow: auto; padding: 0 12px 10px;
    background:
      linear-gradient(transparent, var(--well) 70%) center bottom / 100% 28px no-repeat local,
      radial-gradient(farthest-side at 50% 100%, color-mix(in srgb, var(--text-muted) 30%, transparent), transparent) center bottom / 100% 12px no-repeat scroll,
      var(--well); }
  /* On a narrow screen it keeps room for its relations and scrolls across. */
  table.list { width: 100%; min-width: 64rem; border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
  .list th, .list td { text-align: left; vertical-align: middle; padding: 6px 10px; border-bottom: 1px solid var(--line); }
  .list .fit { width: 1%; white-space: nowrap; }
  /* A header is as wide as its words, and stays at the top of the frame. */
  .list thead th { position: sticky; top: 0; z-index: 2; background: var(--well); color: var(--text-muted); font-weight: 500; font-size: 11px;
    white-space: nowrap; padding-top: 10px; }
  .list tbody th { font-weight: 600; }
  .list td { color: var(--text-2); }
  .list tbody tr { cursor: pointer; }
  .list tbody tr:hover > * { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
  .list tbody tr.sel > * { background-color: var(--accent-bg); }
  .list tbody tr.sel > th { box-shadow: inset 2px 0 0 var(--accent); }
  .list .nm { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; }
  .list .nm .in-ic { margin-right: -2px; }
  .list .name { max-width: 32ch; }
  .loopchip { display: inline-flex; align-items: center; gap: 4px; font-family: var(--sans); font-weight: 400; }
  .loopchip .ic { color: var(--text-muted); }
  .loopchip:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
  .list .st .n { color: var(--text); }
  .list .st .err { color: var(--status-failed); }
  .list .st .warn { color: var(--status-attention); }
  .list .st .live { color: var(--status-running); }
  .list .st .mut { color: var(--text-muted); }
`;

