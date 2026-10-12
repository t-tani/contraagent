// Styles every element shares. Theming: set any `--ca-*` custom property on an
// ancestor (or the element itself); each falls back to the dark default here.
import { css } from 'lit';

/** The design tokens, read from `--ca-*` with the defaults. Internal names are short. */
export const tokens = css`
  :host {
    --bg: var(--ca-bg, #060a11);
    --card: var(--ca-card, #0f1724);
    --panel: var(--ca-panel, #0f1724);
    --panel2: var(--ca-panel2, #142034);
    --raise: var(--ca-raise, #1a2740);
    --line: var(--ca-line, #1d2940);
    --line2: var(--ca-line2, #2b3c58);
    --fg: var(--ca-fg, #e7edf5);
    --fg2: var(--ca-fg2, #bcc7d6);
    --mut: var(--ca-mut, #8492a8);
    --muted: var(--ca-muted, #94a3b8);
    --ok: var(--ca-ok, #34d399);
    --warn: var(--ca-warn, #fbbf24);
    --err: var(--ca-err, #f87171);
    --info: var(--ca-info, #60a5fa);
    --live: var(--ca-live, #22d3ee);
    --llm: var(--ca-llm, #a78bfa);
    --ok-a: var(--ca-ok-a, rgba(52, 211, 153, 0.13));
    --live-a: var(--ca-live-a, rgba(34, 211, 238, 0.13));
    --llm-a: var(--ca-llm-a, rgba(167, 139, 250, 0.15));
    --warn-a: var(--ca-warn-a, rgba(251, 191, 36, 0.13));
    --err-a: var(--ca-err-a, rgba(248, 113, 113, 0.13));
    --muted-a: var(--ca-muted-a, rgba(148, 163, 184, 0.12));
    --well: var(--ca-well, #0a111c);
    --track: var(--ca-track, #1b273b);
    --tok-input: var(--ca-tok-input, #60a5fa);
    --tok-cache-read: var(--ca-tok-cache-read, #475569);
    --tok-cache-write: var(--ca-tok-cache-write, #fbbf24);
    --tok-output: var(--ca-tok-output, #a78bfa);
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color: var(--fg);
  }
  :host([hidden]) {
    display: none !important;
  }
`;

export const base = css`
  ${tokens}
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: #2b3c58 transparent; }
  *:hover { scrollbar-color: #3d5478 transparent; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }

  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--mut); font-size: 11px; }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--mut); }
  .v-ok { color: var(--ok); }
  .v-bad { color: var(--err); }
  .v-mut { color: var(--mut); }
  a.lnk { color: var(--live); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }

  .pill { border-radius: 999px; padding: 1px 10px; font-size: 11px; font-weight: 500; background: var(--raise); color: var(--fg2); white-space: nowrap; }
  /* a task's status (Outcome): one colour per status, always with its word */
  .o-done, .o-recovered { background: var(--ok-a); color: var(--ok); }
  .o-failed { background: var(--err-a); color: var(--err); }
  .o-not_started { background: var(--warn-a); color: var(--warn); }
  .o-running { background: var(--live-a); color: var(--live); }
  .o-waiting, .o-skipped { background: var(--muted-a); color: var(--muted); }
  .p-completed { background: var(--ok-a); color: var(--ok); }
  .p-invalid_input { background: var(--warn-a); color: var(--warn); }
  .p-invalid_output { background: var(--err-a); color: var(--err); }
  .p-skipped { background: var(--muted-a); color: var(--muted); }
  .p-running { background: var(--live-a); color: var(--live); }
  .p-timeout, .p-max_turns, .p-stalled { background: var(--warn-a); color: var(--warn); }
  .p-error, .p-launch_failed, .p-no_output, .p-aborted { background: var(--err-a); color: var(--err); }

  .jstop { font-weight: 600; }
  .jstop.j-completed { color: #57ab5a; }
  .jstop.j-timeout { color: #d29922; }
  .jstop.j-error, .jstop.j-launch_failed, .jstop.j-no_output { color: #e5534b; }
  .jstop.j-invalid_input { color: var(--warn); }

  .dot { width: 8px; height: 8px; border-radius: 50%; background: #3b4760; flex: none; display: inline-block; }
  .dot.live { background: var(--live); animation: breathe 1.8s ease-in-out infinite; }
  .dot.ok { background: var(--ok); }
  .dot.warn { background: var(--warn); }
  .dot.err { background: var(--err); }
  .dot.llm { background: var(--llm); }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(34, 211, 238, 0.25);
    border-top-color: var(--live); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
  .kbd { font-family: var(--mono); font-size: 10px; border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: 4px; padding: 0 4px; color: var(--mut); }

  .tag { font-size: 10px; padding: 0 7px; border-radius: 999px; border: 1px solid var(--line2); color: var(--mut); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--mut); white-space: nowrap; }
  .chip.done { color: var(--ok); border-color: rgba(52, 211, 153, 0.5); }
  .chip.cur { background: var(--live); color: #03222a; border-color: var(--live); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: 11px; line-height: 1.5; padding: 0 8px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--raise); color: var(--fg2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--line2); color: var(--fg); }

  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--fg2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--mut); }
  .enter { animation: enter 0.5s var(--ease) both; }
  .sect-h { margin: 14px 0 8px; font-size: 12px; color: var(--fg2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--mut); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--fg2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: 8px; cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: var(--mut); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  /* who ran it: an agent launch or Python */
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: 11px; background: var(--muted-a); color: var(--muted); flex: none; }
  .k-ic.llm { background: var(--llm-a); color: var(--llm); }
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--muted); }
  .jdur i.llm { background: var(--llm); }
  .jdur i.bad { background: var(--err); }

  /* contracts */
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: 11.5px; background: var(--raise); color: var(--fg2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  .ct-chip.valid { background: var(--ok-a); color: var(--ok); }
  .ct-chip.invalid, .ct-chip.failed { background: var(--err-a); color: var(--err); }
  .ct-chip.running { background: var(--live-a); color: var(--live); }
  .ct-chip.pending { background: var(--muted-a); color: var(--muted); }
  .ct-chip.refused { background: var(--warn-a); color: var(--warn); }
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 12px; }
  .drv-facts i { font-style: normal; color: var(--mut); margin-right: 5px; font-size: 11px; }

  @keyframes turn { to { transform: rotate(360deg); } }
  @keyframes breathe {
    0%, 100% { opacity: 0.45; box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); transform: scale(0.85); }
    50% { opacity: 1; box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.18); transform: scale(1); }
  }
  @keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.55); } 80%, 100% { box-shadow: 0 0 0 9px rgba(34, 211, 238, 0); } }
  @keyframes enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes bump { 0% { transform: scale(1); } 35% { transform: scale(1.04); box-shadow: 0 0 0 1px var(--live); } 100% { transform: scale(1); } }
  @keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
  @keyframes growx { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @keyframes stripes { to { background-position: 17px 0; } }
  @keyframes toast-in { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
  @keyframes toast-out { to { opacity: 0; transform: translateX(24px); } }
  @keyframes rowin { from { background: rgba(34, 211, 238, 0.18); } to { background: transparent; } }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: 0.45; } 40% { transform: translateY(-5px); opacity: 1; } }
  @keyframes core-beat { 0%, 100% { transform: scale(1); } 50% { transform: scale(0.72); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
`;

/** Rendered markdown, highlighted code and JSON trees: transcripts, plugin files, panels. */
export const prose = css`
  .jtree { font-family: var(--mono); font-size: 12px; overflow: auto; }
  .jt { margin-left: 16px; }
  details.jt > summary { cursor: pointer; list-style: revert; }
  .jk { color: var(--info); }
  .js { color: var(--ok); }
  .jn { color: var(--warn); }

  .md-p { margin: 0.15em 0; }
  .md-gap { height: 0.5em; }
  .md-h { font-weight: 600; margin: 0.7em 0 0.25em; }
  .md-h1 { font-size: 1.25em; }
  .md-h2 { font-size: 1.12em; }
  .md-h3 { font-size: 1.03em; color: var(--fg2); }
  .md-h4 { color: var(--fg2); }
  .md-li { padding-left: 16px; text-indent: -12px; margin: 0.1em 0; }
  .md-li::before { content: '• '; color: var(--mut); }
  .md-ol::before { content: ''; }
  .md-n { color: var(--mut); margin-right: 6px; }
  .md-q { border-left: 3px solid var(--line2); padding-left: 10px; color: var(--fg2); margin: 0.2em 0; }
  .md-hr { border: 0; border-top: 1px solid var(--line); margin: 0.7em 0; }
  .md-t { border-collapse: collapse; margin: 0.4em 0; }
  .md-t th, .md-t td { border: 1px solid var(--line); padding: 3px 9px; text-align: left; font-size: 12.5px; }
  .md-t th { background: var(--raise); }
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: 8px; max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: 4px; padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: #070d16; border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--mut); }
  .md-tele { color: var(--mut); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 12px;
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: 11px; color: var(--live); border: 1px solid var(--line2); border-radius: 999px;
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--live-a); }
  .pv { color: var(--live); background: var(--live-a); border-radius: 4px; padding: 0 3px; }
  .pv.pc { color: var(--llm); background: var(--llm-a); }

  .hl { font-family: var(--mono); }
  .hl-k { color: #c4a5ff; }
  .hl-const { color: #ff9e64; font-style: italic; }
  .hl-s { color: #7ee2a8; }
  .hl-doc { color: #6fcf97; font-style: italic; }
  .hl-c { color: #6b7a90; font-style: italic; }
  .hl-n { color: #f5c26b; }
  .hl-d { color: #7dd3fc; }
  .hl-f { color: #7dd3fc; font-weight: 600; }
  .hl-cls { color: #ffd479; font-weight: 700; }
  .hl-t { color: #ffd479; }
  .hl-b { color: #79b8ff; }
  .hl-key { color: #79b8ff; }
`;
