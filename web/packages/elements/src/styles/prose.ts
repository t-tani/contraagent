// Rendered markdown, highlighted code and JSON trees.
import { css } from 'lit';

/** Rendered markdown, highlighted code and JSON trees: transcripts, plugin files, panels. */
export const prose = css`
  .jtree { font-family: var(--mono); font-size: var(--font-size-md); overflow: auto; }
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
  .md-doc { padding: 10px 14px; background: var(--well); border: 1px solid var(--line); border-radius: var(--radius-md); max-height: 460px; overflow: auto; line-height: 1.55; }
  .md-doc code, .tx code { background: var(--raise); border-radius: var(--radius-sm); padding: 0 4px; font-size: 0.92em; }
  .md-doc pre { background: var(--well); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; white-space: pre-wrap; }
  .md-doc pre code, .tx pre code { background: none; padding: 0; border-radius: 0; font-size: inherit; }
  .md-front { margin-bottom: 10px; border-collapse: collapse; }
  .md-front td { padding: 2px 14px 2px 0; font-size: 12.5px; border: 0; vertical-align: top; }
  .md-front td:first-child { color: var(--text-muted); }
  .md-tele { color: var(--text-muted); font-size: 11.5px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .df-text { background: var(--well); border: 1px solid var(--line); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-md);
    white-space: pre-wrap; max-height: 420px; overflow: auto; margin: 0; }
  .df-tog { margin-left: auto; font-size: var(--font-size-sm); color: var(--accent); border: 1px solid var(--line2); border-radius: var(--radius-pill);
    padding: 0 9px; cursor: pointer; background: none; }
  .df-tog:hover { background: var(--accent-bg); }
  /* a template placeholder in a prompt */
  .pv { color: var(--code-constant); background: color-mix(in srgb, var(--code-constant) 12%, transparent); border-radius: var(--radius-sm); padding: 0 3px; }
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
  .hl-tag { color: var(--code-keyword); }
  .hl-attr { color: var(--code-name); }
  .hl-meta { color: var(--code-comment); font-weight: 600; }
  .hl-ins { color: var(--status-done); }
  .hl-del { color: var(--status-failed); }
`;
