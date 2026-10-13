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
    :host { display: block; }

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
