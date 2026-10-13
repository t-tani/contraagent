// The styles of `ca-monitor`: its header, the filter bar and the view below.
// The tab list's are in `tabs.ts`.
import { css } from 'lit';

export const monitorStyles = css`
  :host { display: flex; flex-direction: column; height: 100%; min-height: 0; font: 13px/1.5 var(--sans); color: var(--text);
    background: var(--backdrop); }
  header { flex: none; display: flex; gap: 14px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg) 75%, transparent); backdrop-filter: blur(10px); position: relative; z-index: 20; }
  .brand { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; letter-spacing: 0.02em; }
  .brand svg { width: 22px; height: 22px; }
  .logo-core { fill: var(--accent); transform-origin: 12px 12px; }
  .logo-ring { stroke: var(--accent); opacity: 0.5; transform-origin: 12px 12px; }
  :host([live]) .logo-core { animation: core-beat 1.8s var(--ease) infinite; }
  :host([live]) .logo-ring { animation: turn 7s linear infinite; }
  .runbtn { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 52vw; cursor: pointer; padding: 6px 13px;
    border-radius: 999px; background: var(--panel); border: 1px solid var(--line); color: var(--text); transition: border-color 0.2s, background 0.2s; }
  .runbtn:hover { border-color: var(--line2); background: var(--panel2); }
  .rn { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: none; max-width: 40%; }
  .rs { color: var(--text-muted); font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chev { color: var(--text-muted); }
  ca-run-picker { inset-inline-start: 110px; }
  .hdr-right { margin-left: auto; display: flex; align-items: center; gap: 12px; min-width: 0; }
  .nowline { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; max-width: 40vw;
    display: inline-flex; align-items: center; gap: 4px; }
  .clock { font-family: var(--mono); font-size: 11.5px; color: var(--text-muted); }
  .langs { --cae-segmented-radius: 999px; --cae-segmented-height: auto; --cae-segmented-padding: 2px 9px; --cae-segmented-font-size: 11px;
    --cae-segmented-divider: 0; --cae-segmented-hover: var(--text-2); }
  .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--status-running); display: inline-block; animation: breathe 1.8s ease-in-out infinite; }
  .live-dot.off { background: var(--line2); animation: none; box-shadow: none; }

  .bar { flex: none; display: flex; gap: 8px; padding: 8px 18px; border-top: 1px solid var(--line); align-items: center; flex-wrap: wrap; }
  .bar select, .bar input { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 8px;
    padding: 5px 9px; outline: none; font: inherit; font-size: 12px; }
  .bar input:focus, .bar select:focus { border-color: var(--focus); box-shadow: 0 0 0 calc(var(--focus-width) - 2px) var(--focus); }

  .api-error { flex: none; margin: 0; padding: 8px 18px; border-top: 1px solid var(--line); color: var(--status-failed);
    font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
  .api-error:empty { padding: 0; border: 0; }
  main { border-top: 1px solid var(--line); flex: 1 1 auto; min-height: 0; overflow: auto; padding: 16px 18px 48px; }
  main.stream { display: flex; flex-direction: column; overflow: hidden; padding-bottom: 16px; }
  @media (max-width: 760px) {
    header { flex-wrap: wrap; gap: 8px; padding: 8px 12px; }
    .runbtn { max-width: calc(100vw - 130px); }
    .hdr-right { width: 100%; margin-left: 0; }
    .nowline { max-width: none; flex: 1; }
    nav { padding: 4px 8px 0; }
    main { padding: 12px 12px 40px; }
  }
`;
