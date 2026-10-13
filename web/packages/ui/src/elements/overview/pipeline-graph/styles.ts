// The pipeline graph's styles: the frame, the graph, the marks, a loop's passes, the
// table, the card and the row under the frame.
import { base } from '@contraagent/elements/styles';
import { legendStyles } from '@contraagent/elements/primitives';
import { css } from 'lit';
import { executorIconStyles } from '../../../words/executor.js';
import { FRAME_MIN, FRAME_SHARE } from '../graph/pan-zoom.js';
import { ROW_H } from './host.js';

export const graphStyles = [
  base,
  executorIconStyles,
  legendStyles,
  css`
    :host { display: block; }

    /* One frame for every view of a layer: the graph, the table and a loop's passes. */
    .frame { position: relative; overflow: hidden; border-radius: 8px; background: var(--well); box-sizing: border-box; }
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
    /* Graph | Table: the chosen one is raised, as the header's language switch. */
    .views { margin-left: 6px; }

    .dag { position: relative; }
    .dag.unplaced { visibility: hidden; }
    .dag > *, .box > .in > * { position: absolute; }
    .edges { left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 0; }
    .edges path { fill: none; stroke: var(--line2); stroke-width: 1.5; }
    .edges path.created { stroke-dasharray: 5 4; }
    /* A loop's return to its next pass: dotted, lighter than the edges, under the box's nodes. */
    .edges path.ret, .legend svg path.ret { stroke: var(--text-2); stroke-width: 2; stroke-dasharray: 0.1 4; stroke-linecap: round; opacity: 0.8; }
    .edges path.ret-tip, .legend svg path.ret-head { fill: var(--text-2); stroke: none; opacity: 0.8; }
    .ic { display: block; flex: none; }
    .loop-ic { color: var(--text-2); }
    .in-ic { color: var(--text-muted); }
    .unset { visibility: hidden; }

    .stub { z-index: 1; font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); padding: 3px 9px;
      border-radius: 999px; border: 1px solid var(--line); background: var(--card); white-space: nowrap; }

    .box { z-index: 1; box-sizing: border-box; border-radius: 14px; border: 1px solid var(--line2); background: color-mix(in srgb, var(--text-muted) 5%, transparent); }
    .box .box { background: color-mix(in srgb, var(--text-muted) 6%, transparent); }
    .box > .in { position: absolute; inset: 0; pointer-events: none; }
    .box > .in > * { pointer-events: auto; }
    /* Room on the right for the mark of an inner view: the box is as wide as its label. */
    .box > .hd { position: absolute; left: 11px; top: 6px; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
      white-space: nowrap; justify-content: flex-start; padding-right: 22px; }
    .box > .hd .line { display: flex; align-items: center; gap: 8px; }
    .box > .hd .name { display: inline-flex; align-items: center; gap: 5px; }
    .box > .hd { cursor: pointer; }
    .box.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
    .box > .hd .spread { font-size: 11px; color: var(--text-2); font-variant-numeric: tabular-nums; }

    .node { z-index: 1; width: max-content; min-width: 120px; box-sizing: border-box;
      display: flex; flex-direction: column; gap: 7px; padding: 8px 10px 9px;
      border-radius: 10px; border: 1px solid var(--line); background: var(--card); transition: border-color 0.3s, box-shadow 0.3s;
      cursor: pointer; box-shadow: var(--ex, 0 0 0 0 transparent); }
    /* An agent task's node: a thin accent along its left side, the colour the timeline gives agent tasks; a Python task's stays neutral. */
    .node.agent { --ex: inset 3px 0 0 -1px color-mix(in srgb, var(--agent) 60%, transparent); }
    .node .k-ic { width: 16px; height: 16px; margin-right: 6px; border-radius: 4px; font-size: 9.5px; }
    .node .nm { display: flex; align-items: center; min-width: 0; gap: 0; }
    .node .right { display: flex; align-items: center; gap: 8px; }
    /* The mark of an inner view: at the top right of a function node and of a loop box alike. */
    .cue { display: block; line-height: 0; }
    .box > .cue { position: absolute; top: 9px; right: 10px; }
    .node.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; }
    .node.flow { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--line2); }
    .node.cur { border-color: var(--status-running); }
    .node.flow.cur { box-shadow: 4px 4px 0 -1px var(--card), 4px 4px 0 0 var(--status-running), 0 0 14px var(--status-running-bg); }
    .node:not(.flow).cur { box-shadow: var(--ex, 0 0 0 0 transparent), 0 0 14px var(--status-running-bg); }
    .node.fail { border-color: color-mix(in srgb, var(--status-failed) 55%, transparent); }
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
    .mark { width: var(--m); height: var(--m); padding: 0; margin: 0; border: 0; border-radius: 50%; background: var(--status-done); opacity: 0.9;
      cursor: pointer; position: relative; transition: opacity 0.2s, transform 0.15s, background 0.3s; }
    .mark.skipped { background: var(--status-muted); opacity: 0.55; }
    .mark.running { background: var(--status-running); opacity: 1; animation: breathe 1.4s ease-in-out infinite; }
    .mark.pending { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line2); }
    .mark.blocked { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, color-mix(in srgb, var(--status-attention) 55%, transparent) 2px 3px);
      box-shadow: inset 0 0 0 1.5px var(--status-attention); opacity: 1; }
    .mark.failed { border-radius: 2px; background: var(--status-failed); opacity: 1; }
    .big .mark.failed::after { content: '✕'; position: absolute; inset: 0; display: grid; place-items: center; color: var(--bg);
      font-size: calc(var(--m) - 3px); line-height: 1; font-weight: 700; }
    /* A unit that ran more than 1 pass: its number in the mark; a small mark has a hole instead. */
    .mark[data-n]::after { content: ''; position: absolute; inset: 32%; border-radius: 50%; background: var(--card); }
    .big .mark[data-n]::after { content: attr(data-n); inset: 0; display: grid; place-items: center; border-radius: 0; background: none;
      font: 700 max(7px, calc(var(--m) - 4px)) / 1 var(--sans); color: var(--bg); letter-spacing: -0.5px; }
    .big .mark.failed[data-n]::after, .big .mark.running[data-n]::after { color: var(--bg); }
    .big .mark.pending[data-n]::after, .big .mark.blocked[data-n]::after, .big .mark.skipped[data-n]::after { color: var(--text); }
    .mark:hover, .mark:focus-visible { transform: scale(1.4); outline: var(--focus-width) solid var(--text); outline-offset: 1px; z-index: 2; }
    .mark.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 2px; z-index: 2; }
    .taskchip.sel { outline: var(--focus-width) solid var(--accent); outline-offset: 1px; }
    .hl .mark:not(.on) { opacity: 0.16; }
    .hl .mark.on { transform: scale(1.2); }
    .mx.hl .mark:not(.on) { opacity: 0.4; }
    @media (prefers-reduced-motion: reduce) {
      .mark, .node { transition: none; }
      .mark.running { animation: none; background: linear-gradient(90deg, var(--status-running) 50%, transparent 50%); box-shadow: inset 0 0 0 1.5px var(--status-running); }
    }

    .sbar { display: flex; width: 220px; height: 10px; border-radius: 3px; overflow: hidden; background: var(--track); gap: 1px; }
    .sbar i { display: block; min-width: 2px; height: 100%; }
    .sbar .done { background: var(--status-done); opacity: 0.85; }
    .sbar .running { background: var(--status-running); }
    .sbar .pending { background: var(--line2); }
    .sbar .failed { background: var(--status-failed); }
    .sbar .blocked { background: repeating-linear-gradient(135deg, var(--status-attention-bg) 0 2px, color-mix(in srgb, var(--status-attention) 60%, transparent) 2px 3px); }
    .sbar .skipped { background: var(--status-muted); opacity: 0.5; }
    .fails { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; max-width: 220px; font-size: 11px; color: var(--text-muted); }
    .fails .taskchip { color: var(--status-failed); border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); }
    .fails .taskchip:focus-visible { outline: var(--focus-width) solid var(--text); outline-offset: 1px; }
    .hl .fails .taskchip:not(.on) { opacity: 0.4; }

    /* A loop's passes: centred in the frame, the line above as wide as the table (it adds no width of its own). */
    .mxframe { display: grid; grid-template-columns: minmax(0, 1fr); place-items: center; padding: 14px 16px; }
    /* At least wide enough for the loop's name and the sort beside it: a narrower table is stretched to it. */
    .mxblock { display: flex; flex-direction: column; width: fit-content; max-width: 100%; min-width: min(100%, 27rem); }
    .mxbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; margin-bottom: 8px; font-size: 12px; color: var(--text-2);
      width: 0; min-width: 100%; box-sizing: border-box; }
    .mxbar .cap { color: var(--text); font-weight: 600; }
    .mxbar .sum { flex: 1 0 100%; min-width: 0; }
    .mxbar .f { white-space: nowrap; }
    .sep { color: var(--text-muted); }
    .mxbar label { display: inline-flex; align-items: center; gap: 6px; margin-left: auto; color: var(--text-muted); font-size: 11.5px; white-space: nowrap; }
    .mxbar select { font: inherit; font-size: 11.5px; color: var(--text); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }
    .mxbar select:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
    .mx { overflow: auto; max-width: 100%; max-height: max(${FRAME_MIN}px, ${FRAME_SHARE * 100}vh); border-radius: 6px; border: 1px solid var(--line); }
    table.matrix { border-collapse: separate; border-spacing: 0; font-size: 11px; width: 100%; min-width: max-content; }
    .matrix th, .matrix td { padding: 0 6px; height: ${ROW_H}px; border-bottom: 1px solid var(--line); white-space: nowrap; }
    .matrix thead th { position: sticky; z-index: 2; background: var(--panel2); color: var(--text-muted); font-weight: 500; text-align: center; height: 22px; }
    .matrix thead th.nh { font-family: var(--mono); color: var(--text-2); font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; }
    .matrix thead th.pass { color: var(--text-2); }
    .matrix thead th.loop { font-family: var(--mono); }
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

    .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-bottom: 8px; font-size: 12px; }
    .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; list-style: none; margin: 0; padding: 0; }
    .crumbs li { display: inline-flex; align-items: center; gap: 4px; }
    .crumbs .sep { color: var(--text-muted); }
    .crumbs button { all: unset; cursor: pointer; color: var(--accent); font-family: var(--mono); }
    .crumbs button:hover { text-decoration: underline; }
    .crumbs button:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
    .crumbs [aria-current] { font-family: var(--mono); color: var(--text); font-weight: 600; }
    .pin { display: inline-flex; align-items: center; gap: 8px; color: var(--text-2); }
    .pin b { font-family: var(--mono); }

    /* The legend on the left, the tools at the right end of the first line, in every view. */
    .foot { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 6px 14px; margin-top: 6px; }
    .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11px; color: var(--text-muted); }
    .legend > span { white-space: nowrap; }
    .legend span { display: inline-flex; align-items: center; gap: 6px; }
    .legend .mark { --m: 12px; cursor: default; animation: none; }
    .legend .mark:hover { transform: none; outline: none; }
    .legend svg path { stroke: var(--line2); stroke-width: 1.5; fill: none; }
    .legend .k-ic { width: 14px; height: 14px; margin: 0; border-radius: 4px; font-size: 8.5px; }
    .list .k-ic { width: 16px; height: 16px; border-radius: 4px; font-size: 9.5px; }
    .matrix thead th.nh .k-ic { width: 14px; height: 14px; margin-right: 5px; border-radius: 4px; font-size: 8.5px; vertical-align: -2px; }

    .main { position: relative; min-width: 0; }
    .missing { margin-bottom: 8px; font-size: 12px; color: var(--status-attention); }
    .missing code { font-family: var(--mono); }

    /* the selection's card: beside the item, joined to it by a pointer, in the accent of the item's outline */
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
    /* a narrow screen: a sheet under the frame, naming the item */
    .insp.sheet { position: sticky; bottom: 8px; width: auto; max-width: none; margin-top: 8px; visibility: visible; }
    .insp.sheet .ptr { display: none; }
    @keyframes insp-in { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: none; } }
    .insp h4 { margin: 0; display: flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 13px; font-weight: 600;
      color: var(--text); overflow-wrap: anywhere; }
    .insp h4 .mark { --m: 11px; flex: none; cursor: default; animation: none; }
    .insp h4 .mark:hover { transform: none; outline: none; }
    .insp h4 .k-ic { width: 18px; height: 18px; margin: 0; border-radius: 5px; font-size: 10px; }
    .insp .sub { color: var(--text-2); }
    .insp dl { display: grid; grid-template-columns: fit-content(42%) minmax(0, 1fr); gap: 4px 12px; margin: 0; }
    .insp dt { color: var(--text-muted); word-break: keep-all; overflow-wrap: break-word; }
    .insp dd { margin: 0; color: var(--text); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
    .insp dd .err { color: var(--status-failed); }
    .insp dd .warn { color: var(--status-attention); }
    .insp .acts { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding-top: 2px; }
    .insp .go { all: unset; cursor: pointer; color: var(--accent); overflow-wrap: anywhere; }
    .insp .go.primary { font-weight: 600; }
    .insp .go:hover { text-decoration: underline; }
    .insp .go:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
    .insp .acts .switch { margin-left: auto; }
    .keys { grid-column: 1 / -1; font-size: 11px; color: var(--text-muted); display: none; }
    .keys span { white-space: nowrap; }
    :host(:focus-within) .keys { display: block; }
    .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--text-2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
    .switch:hover { color: var(--text); border-color: var(--line2); }
    .switch:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }

    /* The table: across the frame's content box, the name and status as wide as their content, the relations sharing the rest. */
    /* A shadow at an edge the table scrolls past: a lid over it at the end, a shadow fixed to the frame. */
    .tframe { overflow: auto; padding: 0 12px 10px;
      background:
        linear-gradient(transparent, var(--well) 70%) center bottom / 100% 28px no-repeat local,
        radial-gradient(farthest-side at 50% 100%, color-mix(in srgb, var(--text-muted) 30%, transparent), transparent) center bottom / 100% 12px no-repeat scroll,
        var(--well); }
    /* on a narrow screen it keeps room for its relations and scrolls across */
    table.list { width: 100%; min-width: 64rem; border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
    .list th, .list td { text-align: left; vertical-align: middle; padding: 6px 10px; border-bottom: 1px solid var(--line); }
    .list .fit { width: 1%; white-space: nowrap; }
    /* a header is as wide as its words, and stays at the top of the frame */
    .list thead th { position: sticky; top: 0; z-index: 2; background: var(--well); color: var(--text-muted); font-weight: 500; font-size: 11px;
      white-space: nowrap; padding-top: 10px; }
    .list tbody th { font-weight: 600; }
    .list td { color: var(--text-2); }
    .list tbody tr { cursor: pointer; }
    .list tbody tr:hover > * { background-color: color-mix(in srgb, var(--text-muted) 8%, transparent); }
    .list tbody tr.sel > * { background-color: var(--accent-bg); }
    .list tbody tr.sel > th { box-shadow: inset 2px 0 0 var(--accent); }
    .list .nm { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; }
    .list .nm .k-ic { margin: 0 -2px 0 0; }
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
  `,
];
