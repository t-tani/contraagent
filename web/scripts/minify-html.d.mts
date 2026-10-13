import type { Plugin } from 'vite';

/** One template's literal parts, minified in order; `keep` is the depth of <pre>-like elements open around it. */
export function minifyHtmlParts(parts: string[], keep?: number): { parts: string[]; keep: number[] };
/** `code` with the text of every `html` and `svg` tagged template minified. */
export function minifyHtmlTemplates(code: string, fileName?: string): string;
/** The Vite plugin: minifies the html and svg templates of the packages' sources. */
export function minifyHtml(): Plugin;
