// The design tokens as an element's custom properties: each reads its `--ca-*`
// property, which `data-ca-theme` on an ancestor sets (themes/data.ts) and a
// `--ca-*` property of the page's own, set on the element or nearer to it,
// overrides.
import { css, unsafeCSS } from 'lit';
import { DEFAULT_THEME, THEMES, type ThemeToken } from '../themes/data.js';
import { TOKENS } from '../themes/tokens-list.js';

const fallback = THEMES[DEFAULT_THEME].tokens as Record<string, string>;

/** One token: its `--ca-*` property (a theme's value or the page's own), else the default theme's (or its derivation). */
const declaration = (t: (typeof TOKENS)[number]): string =>
  t.derive
    ? `--${t.name}: var(${t.prop}, ${t.derive});`
    : `--${t.name}: var(${t.prop}, ${fallback[t.name as ThemeToken]});`;

/**
 * The design tokens (`TOKENS` in themes/tokens-list.ts, with their meanings). A
 * colour means one thing: text and surfaces are neutral, a status colour marks a
 * status (only where it applies), the accent marks what can be clicked or is
 * selected, and identity colours are small cues (an icon, a thin edge, a legend).
 */
export const tokenStyles = css`
  :host {
    ${unsafeCSS(TOKENS.map(declaration).join('\n    '))}
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    color-scheme: var(--ca-color-scheme, ${unsafeCSS(THEMES[DEFAULT_THEME].scheme)});
    color: var(--text);
  }
  :host([hidden]) {
    display: none !important;
  }
`;
