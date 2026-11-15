// The design tokens as an element's custom properties: each reads its `--ca-*`
// property, which `data-ca-theme` on an ancestor sets (themes/data.ts) and a
// `--ca-*` property of the page's own, set on the element or nearer to it,
// overrides.
import { css, unsafeCSS } from 'lit';
import { SYSTEM_THEMES, THEMES, type ThemeToken } from '../themes/data.js';
import { TOKENS } from '../themes/tokens-list.js';

const light = THEMES[SYSTEM_THEMES.light].tokens as Record<string, string>;
const dark = THEMES[SYSTEM_THEMES.dark].tokens as Record<string, string>;

/**
 * A token's value where no theme and no page sets it: contraagent Light's or
 * contraagent Dark's, as the `color-scheme` of the page says (`light-dark()`), so
 * an element on a page that names no theme reads on that page. A value that is
 * not a colour is the same in both.
 */
function fallback(name: ThemeToken): string {
  const [l, d] = [light[name]!, dark[name]!];
  if (l === d) return d;
  return name === 'tint' ? '12%' : `light-dark(${l}, ${d})`;
}

/** One token: its `--ca-*` property (a theme's value or the page's own), else its derivation or its fallback. */
const declaration = (t: (typeof TOKENS)[number]): string =>
  t.derive ? `--${t.name}: var(${t.prop}, ${t.derive});` : `--${t.name}: var(${t.prop}, ${fallback(t.name as ThemeToken)});`;

/**
 * The design tokens (`TOKENS` in themes/tokens-list.ts, with their meanings). A
 * colour means one thing: text and surfaces are neutral, a status colour marks a
 * status (only where it applies), the accent marks what can be clicked or is
 * selected, and identity colours are small cues (an icon, a thin edge, a legend).
 *
 * A reader who asks the system for more contrast gets stronger lines and no
 * muted text, in every theme.
 */
export const tokenStyles = css`
  :host {
    ${unsafeCSS(TOKENS.map(declaration).join('\n    '))}
    --sans: var(--ca-sans, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif);
    --mono: var(--ca-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    /* a theme names its colour scheme; with no theme the page's own stays (an unset value inherits) */
    color-scheme: var(--ca-color-scheme);
    color: var(--text);
  }
  @media (prefers-contrast: more) {
    :host {
      --line: var(--ca-line2, ${unsafeCSS(fallback('line2'))});
      --line2: var(--line-field);
      --text-muted: var(--ca-text-secondary, ${unsafeCSS(fallback('text-2'))});
    }
  }
  :host([hidden]) {
    display: none !important;
  }
`;
