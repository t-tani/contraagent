// The styles of `ca-monitor`: its header and the view below. The tab list's
// (and the filter at its end) are in `tabs.ts`. The monitor is a container
// (`ca-monitor`): its parts follow the width it is given, not the window's, so
// it fits any box of a page that embeds it.
import { css } from 'lit';

export const monitorStyles = css`
  :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: var(--font-size-sm) / 1.5 var(--sans); color: var(--text);
    background: var(--backdrop); container: ca-monitor / inline-size; }
  /* One line: the name, the run, then what runs now, the connection and the settings at the end. */
  header { flex: none; display: flex; gap: 12px; align-items: center; padding: 8px 24px; min-height: 48px; position: relative; z-index: 20; }
  /* a page of no run (the trends, the hosts) has no tab list under the header: the line under it is the header's */
  header.solo { border-bottom: 1px solid var(--line); }
  .brand { display: flex; align-items: center; gap: 8px; font-weight: 650; font-size: var(--font-size-md); letter-spacing: -0.01em; }
  /* the name stays on one line and whole up to a third of the width; the run button gives up its width instead */
  .brand { flex: none; max-width: 30cqi; white-space: nowrap; }
  .brand span { overflow: hidden; text-overflow: ellipsis; }
  .brand svg { width: 20px; height: 20px; flex: none; }
  .logo-braces { stroke: var(--text); }
  .spark-a { stop-color: var(--accent); }
  .spark-b { stop-color: var(--agent); }
  .logo-spark { transform-origin: 60px 60px; }
  :host([live]) .logo-spark { animation: core-beat 1.8s var(--ease) infinite; }
  /* The run: its state, its name and its line of facts, in a field that opens the list of runs. */
  .runbtn { display: flex; align-items: center; gap: 8px; min-width: min(150px, 100%); max-width: 56cqi; height: 32px; cursor: pointer; padding: 0 10px;
    border-radius: var(--radius-md); background: var(--card); border: 1px solid var(--line); color: var(--text);
    transition: border-color 0.15s, background 0.15s; }
  .runbtn:hover, .runbtn[aria-expanded='true'] { border-color: var(--line2); background: var(--raise); }
  .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
  .rs { color: var(--text-muted); font-size: var(--font-size-xs); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { flex: none; width: 12px; height: 12px; color: var(--text-muted); margin-inline-start: 2px; }
  /* a hub: the run's host, after its name */
  .hostchip { flex: none; font-family: var(--mono); font-size: var(--font-size-xs); color: var(--text-2); padding: 0 6px; background: var(--raise);
    border-radius: var(--radius-sm); white-space: nowrap; max-width: 24ch; overflow: hidden; text-overflow: ellipsis; }
  .runbtn .pill { flex: none; }
  ca-run-picker { inset-inline-start: 24px; }
  /* the controls keep their width; the name and the run button give theirs */
  .hdr-right { margin-inline-start: auto; display: flex; align-items: center; gap: 12px; flex: none; white-space: nowrap; }
  .nowline { font-size: var(--font-size-xs); color: var(--text-2); white-space: nowrap; overflow: hidden; max-width: 40cqi;
    display: inline-flex; align-items: center; gap: 4px; }
  /* the connection to the monitor server: a dot, round while it holds; a hollow one when it is lost */
  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--status-running); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
  .live-dot.off { background: none; border: 1.5px solid var(--text-muted); animation: none; box-shadow: none; }
  @media (forced-colors: active) {
    .live-dot:not(.off) { forced-color-adjust: none; background: CanvasText; }
  }

  .api-error { flex: none; margin: 0; padding: 8px 24px; color: var(--status-failed); font: var(--font-size-xs) var(--mono); overflow-wrap: anywhere; }
  .api-error:empty { padding: 0; }
  /* --view-top: the room over the view, which a header that stays at the top of the view (a table's) covers */
  main { --view-top: 20px; flex: 1 1 auto; min-height: 0; overflow: auto; padding: var(--view-top) 24px 48px; }
  /* the tab's view (its panel): a box of no size of its own, its content laid out as the main part's */
  .view { display: contents; }
  /* the task view fills the view; a header taller than the room left for the transcript scrolls away above it (cqb: this box's height) */
  main.stream { display: flex; flex-direction: column; overflow: hidden auto; padding-bottom: 16px; container-type: size; }
  /* too narrow for one line: what runs now goes under the name and the run button */
  @container ca-monitor (max-width: 1000px) {
    header { flex-wrap: wrap; row-gap: 6px; }
    .nowline { order: 1; flex: 1 1 100%; max-width: none; }
    .nowline:empty { display: none; }
    .hdr-right { display: contents; }
    ca-settings { margin-inline-start: auto; }
    .hdr-right > [role='img'] { order: 0; }
  }
  @container ca-monitor (max-width: 760px) {
    header { gap: 8px; padding: 8px 12px; }
    /* the run button takes the rest of the first line; its run line gives up its width first */
    .runbtn { flex: 1 1 0; min-width: 0; max-width: none; }
    /* the run picker spans the header, 16px from each side */
    ca-run-picker { inset-inline: 16px; width: auto; }
    main { --view-top: 12px; padding: var(--view-top) 12px 40px; }
    .api-error { padding-inline: 12px; }
  }
  /* a phone: the mark without the name; the run button keeps room for its run's name */
  @container ca-monitor (max-width: 480px) {
    .brand span { display: none; }
    .runbtn { padding: 0 8px; min-width: min(140px, 100%); }
  }
  @media (pointer: coarse) {
    .runbtn { height: 40px; }
  }
`;
