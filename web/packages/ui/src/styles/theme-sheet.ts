// The built-in themes as stylesheets: for a document (or any shadow root that
// holds the elements), and for an element that applies a theme to itself.
import { unsafeCSS, type CSSResult } from 'lit';
import { themeRules } from './themes.js';

/** Applies the theme named by `data-ca-theme` on any element (`<html data-ca-theme="nord">`). */
export const themeStyles: CSSResult = unsafeCSS(themeRules((n) => `[data-ca-theme="${n}"]`));

/** The same rules for a host element: `:host([data-ca-theme="nord"])`. */
export const hostThemeStyles: CSSResult = unsafeCSS(themeRules((n) => `:host([data-ca-theme="${n}"])`));

const adopted = new WeakSet<Document | ShadowRoot>();

/**
 * Adds `themeStyles` to a document or a shadow root, once. Importing the package
 * does it for the page's document; call it for a shadow root of your own that
 * holds the elements and sets `data-ca-theme` inside it.
 */
export function adoptThemes(root: Document | ShadowRoot = document): void {
  if (adopted.has(root)) return;
  const sheet = themeStyles.styleSheet;
  if (!sheet || !('adoptedStyleSheets' in root)) return;
  root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
  adopted.add(root);
}
