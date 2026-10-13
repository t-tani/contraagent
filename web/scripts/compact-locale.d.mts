import type { Plugin } from 'vite';

/** Each id's shortest prefix that is not a prefix of any other id. Throws when an id is a prefix of another. */
export function shortKeys(ids: Iterable<string>): Map<string, string>;
/** The lookup of a compacted locale: `templates[id]` is the template stored under the first prefix of `id` that is a key. */
export function lookup<T>(table: Record<string, T>): Record<string, T | undefined>;
/** The source of a lit-localize locale module with its keys shortened and `templates` the lookup. */
export function compactLocale(code: string): string;
/** `code` with each `import('…/locales/<locale>.js')` a static import, resolved at once. */
export function staticLocaleImports(code: string): string;
/** The Vite plugin: compacts the locale modules of `@contraagent/ui`. */
export function compactLocales(): Plugin;
/** The Vite plugin: the locales loaded with the page, for a one-file bundle. */
export function staticLocales(): Plugin;
