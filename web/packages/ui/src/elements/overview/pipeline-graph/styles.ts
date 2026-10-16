// The pipeline graph's own styles: the line above the graph (where the layer is, the
// pinned unit, a missing layer) and the card's content, which it renders into the
// generic graph's slots; and the executor icons the generic graph draws for it.
import { base, markStyles } from '@contraagent/elements/styles';
import { css } from 'lit';
import { executorIconStyles } from '../../../words/executor.js';

export const graphStyles = [
  base,
  executorIconStyles,
  markStyles,
  css`
    /* A column: a height set on the host is the graph's, less the outline's line above it. */
    :host { display: flex; flex-direction: column; }
    cae-layered-graph { flex: auto; min-height: 0; }

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
    .missing { margin-bottom: 8px; font-size: 12px; color: var(--status-attention); }
    .missing code { font-family: var(--mono); }

    /* The card's content: laid out by the card itself. */
    .card { display: contents; }
    .ic { display: block; flex: none; }
    .loop-ic { color: var(--text-2); }
    .in-ic { color: var(--text-muted); }
    .card h4 { margin: 0; display: flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 13px; font-weight: 600;
      color: var(--text); overflow-wrap: anywhere; }
    .card h4 .mark { --m: 11px; flex: none; cursor: default; animation: none; }
    .card h4 .mark:hover { transform: none; outline: none; }
    .card h4 .k-ic { width: 18px; height: 18px; margin: 0; border-radius: 5px; font-size: 10px; }
    .card .sub { color: var(--text-2); }
    .card dl { display: grid; grid-template-columns: fit-content(42%) minmax(0, 1fr); gap: 4px 12px; margin: 0; }
    .card dt { color: var(--text-muted); word-break: keep-all; overflow-wrap: break-word; }
    .card dd { margin: 0; color: var(--text); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
    .card dd .err { color: var(--status-failed); }
    .card dd .warn { color: var(--status-attention); }
    .card .acts { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding-top: 2px; }
    .card .go { all: unset; cursor: pointer; color: var(--accent); overflow-wrap: anywhere; }
    .card .go.primary { font-weight: 600; }
    .card .go:hover { text-decoration: underline; }
    .card .go:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; border-radius: 3px; }
    .card .acts .switch { margin-left: auto; }
    .switch { all: unset; cursor: pointer; font-size: 11.5px; color: var(--text-2); padding: 2px 8px; border-radius: 6px; border: 1px solid var(--line); }
    .switch:hover { color: var(--text); border-color: var(--line2); }
    .switch:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; }
    .switch[aria-pressed='true'] { color: var(--text); background: var(--accent-bg); border-color: var(--accent); }
    .opens { display: inline-flex; gap: 6px; margin-left: auto; }

    /* The outline: a column beside the graph, or a part above it on a narrow frame. */
    .whole { display: grid; grid-template-columns: minmax(200px, 282px) minmax(0, 1fr); gap: 14px; align-items: start; }
    .whole > .g { min-width: 0; }
    .outline { font-size: 12px; max-height: 70vh; overflow: auto; padding: 2px 6px 2px 0; border-right: 1px solid var(--line); }
    .otree, .otree ul { list-style: none; margin: 0; padding: 0; }
    .otree ul { padding-left: 10px; }
    .orow { display: grid; grid-template-columns: 16px minmax(0, 1fr); align-items: start; border-radius: 6px; }
    .orow.sel { background: var(--accent-bg); }
    .orow.cur .ol { font-weight: 600; color: var(--text); }
    .odisc { all: unset; cursor: pointer; width: 16px; text-align: center; color: var(--text-muted); font-size: 10px; line-height: 22px; }
    .odisc:focus-visible, .oname:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 1px; border-radius: 4px; }
    .oname { all: unset; cursor: pointer; display: flex; align-items: flex-start; gap: 6px; min-width: 0; padding: 3px 6px 3px 2px; border-radius: 6px; color: var(--text-2); }
    .oname:hover { background: var(--raise); color: var(--text); }
    .oname .loop-ic { flex: none; color: var(--text-muted); }
    .ol { flex: 1; min-width: 0; overflow-wrap: break-word; font-family: var(--mono); line-height: 1.35; }
    .obar { flex: none; width: 32px; height: 4px; margin-top: 6px; border-radius: 2px; background: var(--track); overflow: hidden; }
    .obar i { display: block; height: 100%; background: var(--meter); }
    .ocount { flex: none; font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
    .onote { grid-column: 2; display: flex; flex-wrap: wrap; gap: 0 8px; padding: 0 6px 2px 2px; font-size: 11px; }
    .onote .err { color: var(--status-failed); }
    .onote .warn { color: var(--status-attention); }
    .onote .live { color: var(--status-running); }
    .onote .mut { color: var(--text-muted); }
    .odet { margin-bottom: 8px; }
    .odet > summary { cursor: pointer; font-size: 12px; color: var(--text-2); padding: 2px 0; }
    .odet .outline { border-right: none; max-height: 50vh; }
  `,
];

/** The executor icons as the generic graph draws them: in a node's name, the legend, the table and a loop's passes. */
export const iconStyles = [
  executorIconStyles,
  css`
    .node .k-ic { width: 16px; height: 16px; margin-right: 6px; border-radius: 4px; font-size: 9.5px; }
    .legend .k-ic { width: 14px; height: 14px; margin: 0; border-radius: 4px; font-size: 8.5px; }
    .list .k-ic { width: 16px; height: 16px; border-radius: 4px; font-size: 9.5px; }
    .list .nm .k-ic { margin: 0 -2px 0 0; }
    .matrix thead th.nh .k-ic { width: 14px; height: 14px; margin-right: 5px; border-radius: 4px; font-size: 8.5px; vertical-align: -2px; }
  `,
];
