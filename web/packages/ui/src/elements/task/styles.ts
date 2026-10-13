// The styles of `ca-task-view`: its header, its view tabs and its panes.
import { css } from 'lit';

export const taskViewStyles = css`
  :host { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; position: relative; }
  .taskmeta { flex: none; background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; color: var(--text-2); }
  .tm-head { display: flex; gap: 12px; align-items: center; }
  .tm-av { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; font-size: 16px; flex: none;
    background: var(--agent-bg); color: var(--agent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--agent) 35%, transparent); }
  .tm-av.py { background: var(--raise); color: var(--text-muted); box-shadow: none; }
  .tm-name { font-size: 15px; font-weight: 600; color: var(--text); display: flex; gap: 8px; align-items: center; }
  .verdict { font-size: 12.5px; color: var(--text); margin-top: 2px; }
  .verdict[data-tone='failed'], .verdict[data-tone='attention'] { color: var(--tone); }
  .verdict[data-tone='muted'] { color: var(--text-muted); }
  .whos { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; }
  .runchips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .spend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 6px; font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .spend b { color: var(--text); font-weight: 600; }
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
  .runchip.bad { border-color: color-mix(in srgb, var(--status-failed) 45%, transparent); color: var(--status-failed); background: var(--status-failed-bg); }
  .io-fold { margin-top: 6px; }
  .io-fold > summary, .launch > summary { cursor: pointer; color: var(--text-muted); }
  .searches { margin: 4px 0 0; padding-left: 22px; }
  .unread { color: var(--status-attention); margin-top: 4px; }
  .qlink { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; text-align: left; font: inherit; }
  .qlink:hover { text-decoration: underline; }

  .tviews { flex: none; display: flex; gap: 4px; margin: 2px 0 8px; border-bottom: 1px solid var(--line); }
  .tview { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 6px 14px; cursor: pointer; }
  .tview:hover { color: var(--text-2); }
  .tview.sel { color: var(--text); border-bottom-color: var(--accent); }
  .tview .badge { margin-left: 6px; font-size: 10px; padding: 0 6px; border-radius: 999px; background: var(--raise); color: var(--text-2); }

  .pane { flex: 1 1 auto; min-height: 0; overflow: auto; }
  .upstream { margin-bottom: 12px; }
  .up-hd { display: flex; align-items: center; gap: 10px; margin: 2px 0 6px; }
  .down { display: flex; flex-wrap: wrap; gap: 8px; }
  .notrans { flex: 1 1 auto; border: 1px solid var(--line); border-radius: 14px; }
  details.upstream > summary { cursor: pointer; list-style: none; }
  details.upstream > summary::-webkit-details-marker { display: none; }
  .params td { vertical-align: top; }
  .from { color: var(--text-muted); white-space: nowrap; }
`;
