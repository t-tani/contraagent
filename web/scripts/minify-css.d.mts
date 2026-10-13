import type { Plugin } from 'vite';

/** CSS text without comments, with each run of whitespace one space, and none around `{`, `}` and `;`. */
export function minifyCssText(text: string): string;
/** `code` with the literal text of every css`...` template minified; the `${...}` parts are kept as they are. */
export function minifyCssTemplates(code: string): string;
/** The Vite plugin: minifies the css templates of the packages' sources. */
export function minifyCss(): Plugin;
