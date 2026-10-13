// Styles every element shares. Theming: `data-ca-theme` on an ancestor picks a
// built-in theme (themes.ts); a `--ca-*` custom property on an ancestor (or the
// element itself) overrides one token, whatever the theme.
import { css, unsafeCSS } from 'lit';
import { DEFAULT_THEME, THEMES, TOKENS, themeProp, type ThemeToken } from './themes.js';

const fallback = THEMES[DEFAULT_THEME].tokens as Record<string, string>;

/** One token: its `--ca-*` property, else the theme's value, else the default theme's (or its derivation). */
const declaration = (t: (typeof TOKENS)[number]): string =>
  t.derive
    ? `--${t.name}: var(${t.prop}, ${t.derive});`
    : `--${t.name}: var(${t.prop}, var(${themeProp(t.name)}, ${fallback[t.name as ThemeToken]}));`;

/**
 * The design tokens (`TOKENS` in themes.ts, with their meanings). A colour means
 * one thing: text and surfaces are neutral, a status colour marks a status
 * (only where it applies), the accent marks what can be clicked or is
 * selected, and identity colours are small cues (an icon, a thin edge, a legend).
 */
export const tokenStyles = css`
  :host {
    ${unsafeCSS(TOKENS.map(declaration).join('\n    '))}
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color-scheme: var(--ca-color-scheme, var(${unsafeCSS(themeProp('color-scheme'))}, ${unsafeCSS(THEMES[DEFAULT_THEME].scheme)}));
    color: var(--text);
  }
  :host([hidden]) {
    display: none !important;
  }
`;

export const base = css`
  ${tokenStyles}
  *, *::before, *::after { box-sizing: border-box; }
  * { scrollbar-width: thin; scrollbar-color: var(--line2) transparent; }
  *:hover { scrollbar-color: var(--text-muted) transparent; }
  ::selection { background: var(--selection); }
  :focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: 2px; }
  button { font: inherit; color: inherit; }
  [hidden] { display: none !important; }

  .jmono, code, .mono { font-family: var(--mono); }
  /* read by screen readers, not shown: the word beside a status mark or an icon */
  .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .jmono { font-size: 11.5px; }
  .meta { color: var(--text-muted); font-size: 11px; }
  /* a label in a tight box: it wraps at spaces and between phrases, never inside a word (Japanese included) */
  .words { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }
  /* one fact of a row in .words (factLine): the line breaks between facts first, inside one only when it is wider than the box */
  .words .f { display: inline-block; max-width: 100%; }
  @supports (word-break: auto-phrase) {
    .words:lang(ja) { word-break: auto-phrase; }
  }
  .mut, .jdim { color: var(--text-muted); }
  /* text in a status colour: only on a status that applies (a count above 0 of a problem, a status word) */
  .t-failed { color: var(--status-failed); }
  .t-attention { color: var(--status-attention); }
  .t-done { color: var(--status-done); }
  .t-running { color: var(--status-running); }
  .t-muted { color: var(--status-muted); }
  a.lnk { color: var(--accent); cursor: pointer; text-decoration: none; }
  a.lnk:hover { text-decoration: underline; }

  /*
   * A status mark before a status word: ✓ done, ✕ failed, ◌ not started or waiting.
   * The shape keeps the meaning without colour; screen readers read the word only.
   */
  .mk-done::before, .mk-failed::before, .mk-pending::before { display: inline-block; margin-right: 0.35em; font-weight: 700; }
  .mk-done::before { content: '✓'; content: '✓' / ''; color: var(--status-done); }
  .mk-failed::before { content: '✕'; content: '✕' / ''; }
  .mk-pending::before { content: '◌'; content: '◌' / ''; }

  /*
   * A status as a pill, always with its word. A problem is tinted and marked (✕ failed, ◌ not started);
   * done is quiet (a ✓ and the word): it is the usual case, and the problems are what stand out.
   */
  .pill { border-radius: 999px; padding: 1px 10px; font-size: 11px; font-weight: 500; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .o-done, .o-recovered, .p-completed { background: none; padding-left: 2px; color: var(--text-2); }
  .o-done::before, .o-recovered::before, .p-completed::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .o-failed, .p-invalid_output, .p-timeout, .p-max_turns, .p-stalled, .p-error, .p-launch_failed, .p-no_output, .p-aborted {
    background: var(--status-failed-bg); color: var(--status-failed); }
  .o-failed::before, .p-invalid_output::before, .p-timeout::before, .p-max_turns::before, .p-stalled::before, .p-error::before,
  .p-launch_failed::before, .p-no_output::before, .p-aborted::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; font-weight: 700; }
  .o-not_started, .p-invalid_input { background: var(--status-attention-bg); color: var(--status-attention); }
  .o-not_started::before, .p-invalid_input::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; font-weight: 700; }
  .o-running, .p-running { background: var(--status-running-bg); color: var(--status-running); }
  .o-waiting, .o-skipped, .p-skipped { background: var(--status-muted-bg); color: var(--status-muted); }
  .o-waiting::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; }
  /* a limit near (a subscription's usage): attention, not a failure */
  .p-near { background: var(--status-attention-bg); color: var(--status-attention); }

  /* a status as a word in a row (History, Problems, Outputs) */
  .jstop { font-weight: 600; }
  .jstop.j-completed { color: var(--text-2); font-weight: 500; }
  .jstop.j-completed::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .jstop.j-timeout, .jstop.j-max_turns, .jstop.j-stalled, .jstop.j-error, .jstop.j-launch_failed, .jstop.j-no_output,
  .jstop.j-invalid_output, .jstop.j-aborted { color: var(--status-failed); }
  .jstop.j-timeout::before, .jstop.j-max_turns::before, .jstop.j-stalled::before, .jstop.j-error::before, .jstop.j-launch_failed::before,
  .jstop.j-no_output::before, .jstop.j-invalid_output::before, .jstop.j-aborted::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; }
  .jstop.j-invalid_input { color: var(--status-attention); }
  .jstop.j-invalid_input::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; }

  /*
   * A status as a dot (a run in the header and the run list). The shape carries it too:
   * round done, square failed, diamond attention, a breathing ring running.
   */
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line2); flex: none; display: inline-block; }
  .dot.running { background: var(--status-running); animation: breathe 1.8s ease-in-out infinite; }
  .dot.done { background: var(--status-done); }
  .dot.attention { background: var(--status-attention); border-radius: 1px; transform: rotate(45deg) scale(0.86); }
  .dot.failed { background: var(--status-failed); border-radius: 1.5px; }
  .spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--status-running-bg);
    border-top-color: var(--status-running); animation: turn 0.9s linear infinite; flex: none; display: inline-block; }
  .kbd { font-family: var(--mono); font-size: 10px; border: 1px solid var(--line2); border-bottom-width: 2px;
    border-radius: 4px; padding: 0 4px; color: var(--text-muted); }

  .tag { font-size: 10px; padding: 0 7px; border-radius: 999px; border: 1px solid var(--line2); color: var(--text-muted); white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--text-muted); white-space: nowrap; }
  .chip.done { color: var(--text-2); }
  .chip.done > [aria-hidden] { color: var(--status-done); font-weight: 700; }
  .chip.cur { background: var(--status-running); color: var(--bg); border-color: var(--status-running); font-weight: 600; animation: ping 1.6s var(--ease) infinite; }
  .chip.todo { opacity: 0.65; }
  .taskchip { display: inline-block; font: inherit; font-family: var(--mono); font-size: 11px; line-height: 1.5; padding: 0 8px;
    border-radius: 999px; border: 1px solid var(--line); background: var(--raise); color: var(--text-2); white-space: nowrap; }
  button.taskchip { cursor: pointer; }
  button.taskchip:hover { border-color: var(--accent); color: var(--text); }

  .g12 { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
  .c12 { grid-column: span 12; }
  .c7 { grid-column: span 7; }
  .c5 { grid-column: span 5; }
  @media (max-width: 1150px) {
    .c7, .c5 { grid-column: span 12; }
  }
  .panel { background: linear-gradient(180deg, var(--panel2), var(--panel)); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px 16px; min-width: 0; box-shadow: 0 10px 28px color-mix(in srgb, var(--shadow) 40%, transparent); }
  .panel > h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: var(--text-2); }
  .panel > h3 .r { margin-left: auto; font-weight: 400; font-size: 11.5px; color: var(--text-muted); }
  .enter { animation: enter 0.5s var(--ease) both; }
  .sect-h { margin: 14px 0 8px; font-size: 12px; color: var(--text-2); font-weight: 600; }
  .sect-h .meta { margin-left: 8px; font-weight: 400; }

  .blank { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 16px; color: var(--text-muted); text-align: center; }
  .blank .ic { font-size: 30px; opacity: 0.55; }
  .blank b { color: var(--text-2); font-weight: 600; }
  .blank a.lnk { text-decoration: underline; }
  .blank.small { padding: 24px; }

  /* a short clickable row (failures, launches) */
  .fl { padding: 7px 10px; border-radius: 8px; cursor: pointer; display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; align-items: baseline; }
  .fl > .meta:last-child { grid-column: 1 / 4; overflow: hidden; text-overflow: ellipsis; }
  .fl:hover { background: var(--raise); }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11px; color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }

  /* who ran it (identity, a small cue): an agent launch or Python */
  .k-ic { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; margin-right: 7px;
    font-size: 11px; background: var(--raise); color: var(--text-muted); flex: none; }
  .k-ic.llm { background: var(--agent-bg); color: var(--agent); }
  /* a duration: it measures, it does not judge (red only for a failed attempt) */
  .jdur { position: relative; display: block; height: 6px; border-radius: 3px; background: var(--track); overflow: hidden; margin-top: 2px; }
  .jdur i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--meter); }
  .jdur i.bad { background: var(--status-failed); }

  /* contracts */
  .ct-chip { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: 11.5px; background: var(--raise); color: var(--text-2); white-space: nowrap; }
  .ct-chip b { margin-left: 4px; }
  .ct-chip.valid { background: none; box-shadow: inset 0 0 0 1px var(--line2); color: var(--text-2); }
  .ct-chip.valid::before { content: '✓'; content: '✓' / ''; color: var(--status-done); margin-right: 0.35em; font-weight: 700; }
  .ct-chip.invalid, .ct-chip.failed { background: var(--status-failed-bg); color: var(--status-failed); }
  .ct-chip.invalid::before, .ct-chip.failed::before { content: '✕'; content: '✕' / ''; margin-right: 0.35em; font-weight: 700; }
  .ct-chip.running { background: var(--status-running-bg); color: var(--status-running); }
  .ct-chip.pending { background: var(--status-muted-bg); color: var(--status-muted); }
  .ct-chip.refused { background: var(--status-attention-bg); color: var(--status-attention); }
  .ct-chip.refused::before { content: '◌'; content: '◌' / ''; margin-right: 0.35em; font-weight: 700; }
  .ct-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drv-facts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 12px; }
  .drv-facts i { font-style: normal; color: var(--text-muted); margin-right: 5px; font-size: 11px; }

  @keyframes turn { to { transform: rotate(360deg); } }
  @keyframes breathe {
    0%, 100% { opacity: 0.45; box-shadow: 0 0 0 0 transparent; transform: scale(0.85); }
    50% { opacity: 1; box-shadow: 0 0 0 4px var(--status-running-bg); transform: scale(1); }
  }
  @keyframes ping { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--status-running) 55%, transparent); } 80%, 100% { box-shadow: 0 0 0 9px transparent; } }
  @keyframes enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes bump { 0% { transform: scale(1); } 35% { transform: scale(1.04); box-shadow: 0 0 0 1px var(--line2); } 100% { transform: scale(1); } }
  @keyframes scan { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
  @keyframes growx { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  @keyframes stripes { to { background-position: 17px 0; } }
  @keyframes toast-in { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
  @keyframes toast-out { to { opacity: 0; transform: translateX(24px); } }
  @keyframes rowin { from { background: color-mix(in srgb, var(--text) 10%, transparent); } to { background: transparent; } }
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
  .jk { color: var(--code-name); }
  .js { color: var(--code-string); }
  .jn { color: var(--code-number); }

  .md-p { margin: 0.15em 0; }
  .md-gap { height: 0.5em; }
  .md-h { font-weight: 600; margin: 0.7em 0 0.25em; }
  .md-h1 { font-size: 1.25em; }
  .md-h2 { font-size: 1.12em; }
  .md-h3 { font-size: 1.03em; color: var(--text-2); }
  .md-h4 { color: var(--text-2); }
  .md-li { padding-left: 16px; text-indent: -12px; margin: 0.1em 0; }
  .md-li::before { content: '• '; color: var(--text-muted); }
  .md-ol::before { content: ''; }
  .md-n { color: var(--text-muted); margin-right: 6px; }
  .md-q { border-left: 3px solid var(--line2); padding-left: 10px; color: var(--text-2); margin: 0.2em 0; }
  .md-hr { border: 0; border-top: 1px solid var(--line); margin: 0.7em 0; }
  .md-t { border-collapse: collapse; margin: 0.4em 0; }
  .md-t th, .md-t td { border: 1px solid var(--line); padding: 3px 9px; text-align: left; font-size: 12.5px; }
  .md-t th { background: var(--raise); }
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: 8px; max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: 4px; padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: var(--well); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--text-muted); }
  .md-tele { color: var(--text-muted); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 12px;
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: 11px; color: var(--accent); border: 1px solid var(--line2); border-radius: 999px;
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--accent-bg); }
  /* a template placeholder in a prompt */
  .pv { color: var(--code-constant); background: color-mix(in srgb, var(--code-constant) 12%, transparent); border-radius: 4px; padding: 0 3px; }
  .pv.pc { color: var(--code-keyword); background: color-mix(in srgb, var(--code-keyword) 12%, transparent); }

  .hl { font-family: var(--mono); }
  .hl-k { color: var(--code-keyword); }
  .hl-const { color: var(--code-constant); font-style: italic; }
  .hl-s { color: var(--code-string); }
  .hl-doc { color: var(--code-string); font-style: italic; opacity: 0.85; }
  .hl-c { color: var(--code-comment); font-style: italic; }
  .hl-n { color: var(--code-number); }
  .hl-d { color: var(--code-function); }
  .hl-f { color: var(--code-function); font-weight: 600; }
  .hl-cls { color: var(--code-type); font-weight: 700; }
  .hl-t { color: var(--code-type); }
  .hl-b { color: var(--code-name); }
  .hl-key { color: var(--code-name); }
`;
