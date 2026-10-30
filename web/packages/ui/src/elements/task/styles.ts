// The styles of `ca-task-view`: its header, its view tabs and its panes.
import { css } from 'lit';

export const taskViewStyles = css`
  /* The views come first: a short header, the view tabs, then the view, which takes the rest of the height. The rest
     about the task (.tm-more) opens under the header on a narrow view and stands beside the views on a wide one. The view
     is at least half as tall as the box around (cqb: the monitor's view), so what is open above it makes the box scroll. */
  :host { display: flex; flex-direction: column; flex: 1 0 auto; min-height: 0; position: relative; container-type: inline-size; }
  .tv { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: auto auto auto minmax(0, 1fr); }
  .taskmeta { display: contents; }
  .tm-top { grid-row: 1; }
  .tm-more { grid-row: 2; }
  .tviews { grid-row: 3; }
  .body { grid-row: 4; }
  .body { display: flex; flex-direction: column; min-height: 50cqb; }
  .body > ca-transcript[mode='full'], .body > .pane, .body > .notrans { flex: 1 1 0; min-height: 0; }
  /* a phone on its side (the height is the monitor's view's): the view takes the whole box once the header is scrolled past */
  @container (max-height: 420px) {
    .body { min-height: calc(100cqb - 44px); }
  }

  .tm-top { padding: 0 2px 6px; color: var(--text-2); min-width: 0; }
  .tm-line { font-size: 15px; font-weight: 600; color: var(--text); display: flex; gap: 8px; align-items: center; min-width: 0; }
  .tm-name { min-width: 0; overflow-wrap: anywhere; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; }
  .tm-av { width: 22px; height: 22px; border-radius: 7px; display: grid; place-items: center; font-size: 11px; flex: none;
    background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
  .tm-av.py { background: var(--raise); color: var(--text-muted); box-shadow: none; }
  .verdict { font-size: 12.5px; color: var(--text); margin-top: 3px; overflow-wrap: anywhere;
    display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; line-clamp: 3; overflow: hidden; }
  .tm-facts { display: flex; align-items: center; gap: 6px; margin-top: 3px; font-size: 12px; color: var(--text-2); font-variant-numeric: tabular-nums; }
  .tm-toggle { background: none; border: 0; padding: 2px 0; cursor: pointer; font: inherit; font-size: 12px; text-align: start; }
  .tm-toggle:hover { color: var(--text); }
  .tm-toggle .chev { color: var(--text-muted); font-size: 10px; transition: transform 0.2s var(--ease); }
  .tm-toggle[aria-expanded='true'] .chev { transform: rotate(180deg); }
  .tm-static { display: none; }
  /* the rest, open on a narrow view: a box under the header no taller than half the monitor's view, which scrolls */
  .tm-more { display: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 12px; padding: 4px 12px 10px; margin: 0 0 8px; color: var(--text-2); max-height: 50cqb; overflow: auto; }
  .tm-more.open { display: block; }
  .tm-more > :first-child { margin-top: 6px; }
  .tm-more .pill { max-width: 100%; white-space: normal; overflow-wrap: anywhere; }
  /* open, the verdict shows whole */
  .tm-top.open .verdict, .tm-top.open .tm-name { display: block; }
  /* a wide view: the rest stands beside the views, as tall as they are, and scrolls on its own */
  @container (min-width: 1100px) {
    .tv { grid-template-columns: minmax(0, 1fr) 300px; grid-template-rows: auto auto minmax(0, 1fr); column-gap: 16px; }
    .tm-top { grid-area: 1 / 1; }
    .tm-top.open .verdict { display: -webkit-box; }
    .tviews { grid-area: 2 / 1; }
    .body { grid-area: 3 / 1; }
    .tm-more { display: block; grid-area: 1 / 2 / -1 / 3; contain: size; max-height: none; margin: 0; }
    .tm-toggle { display: none; }
    .tm-static { display: flex; }
  }
  .verdict[data-tone='failed'], .verdict[data-tone='attention'] { color: var(--tone); }
  .verdict[data-tone='muted'] { color: var(--text-muted); }
  .whos { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
  .runchips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .spend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 6px; font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .spend.quota { flex-direction: column; gap: 0; }
  .usage-wrap { overflow-x: auto; margin: 4px 0 12px; }
  /* sized to its content (a full-width table spreads a few numbers far apart); the wrap scrolls when it is wider */
  .usage { width: auto; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
  .usage th { text-align: right; font-weight: 600; color: var(--text-muted); font-size: 10.5px; white-space: nowrap;
    padding: 6px 14px; border-bottom: 1px solid var(--line2); vertical-align: bottom; }
  .usage td { text-align: right; padding: 8px 14px; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: baseline; }
  .usage th:first-child, .usage td:first-child { padding-left: 4px; }
  .usage td.l.jmono { font-size: 12px; }
  /* the subscription readings wrap at a narrow width rather than push the table past the edge */
  .usage td.l:not(:first-child):not(.jmono) { white-space: normal; min-width: 12ch; }
  .usage th.l, .usage td.l { text-align: left; }
  .usage tr.hop td { padding-top: 4px; padding-bottom: 4px; color: var(--text-muted); }
  .usage tr.hop td:first-child { padding-left: 28px; }
  .runchip { font-size: 11px; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--line2); color: var(--text-2); }
  .runchip.ok > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .runchip.part { border-color: color-mix(in srgb, var(--status-attention) 45%, transparent); background: var(--status-attention-bg); }
  .runchip.part > [aria-hidden] { color: var(--status-attention); font-weight: 700; }
  .runchip.bad { border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); color: var(--status-failed); background: var(--status-failed-bg); }
  .io-fold { margin-top: 6px; }
  .io-fold > summary, .launch > summary { cursor: pointer; color: var(--text-muted); }
  .searches { margin: 4px 0 0; padding-left: 22px; }
  .unread { color: var(--status-attention); margin-top: 4px; }
  .qlink { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; text-align: left; font: inherit; }
  .qlink:hover { text-decoration: underline; }

  .tviews { flex: none; display: flex; flex-wrap: wrap; gap: 4px; margin: 2px 0 8px; border-bottom: 1px solid var(--line); }
  /* a phone: the view tabs stay on one line, and scroll sideways when they do not fit */
  @container (max-width: 480px) {
    .tm-line { font-size: 14px; }
    .tviews { gap: 0; flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
    .tview { padding: 6px 10px; flex: none; white-space: nowrap; }
  }
  .tview { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 6px 14px; cursor: pointer; }
  .tview:hover { color: var(--text-2); }
  .tview.sel { color: var(--text); border-bottom-color: var(--accent); }
  .tview .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); }

  /* A positioned box: what is placed in it (a screen reader's text) scrolls with it, not past the view's end. */
  .pane { overflow: auto; position: relative; }
  .upstream { margin-bottom: 12px; }
  .up-hd { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin: 2px 0 6px; }
  .down { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
  /* How a task is joined to an earlier one, drawn as the graph draws its edge: given output solid, runs after dotted, created after result dashed. */
  .lineage { font-size: 11px; color: var(--text-2); border: 1.5px solid var(--line2); border-radius: 999px; padding: 0 7px; white-space: nowrap; }
  .lineage[data-lineage='after'] { border-style: dotted; }
  .lineage[data-lineage='created_from'] { border-style: dashed; }
  .notrans { border: 1px solid var(--line); border-radius: 14px; }
  details.upstream > summary { cursor: pointer; list-style: none; }
  details.upstream > summary::-webkit-details-marker { display: none; }
  .params td { vertical-align: top; }
  .from { color: var(--text-muted); white-space: nowrap; }
`;
