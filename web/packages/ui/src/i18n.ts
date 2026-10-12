// The language the elements speak. English is written in the sources; other
// locales are generated from xliff/<locale>.xlf by `pnpm i18n`
// (lit-localize, runtime mode) into src/locales/<locale>.ts.
//
// Every element is `@localized()`, so `setLocale` re-renders them in place.
import { configureLocalization } from '@lit/localize';
import { allLocales, sourceLocale, targetLocales } from './locales/codes.js';
import * as ja from './locales/ja.js';

export type Locale = (typeof allLocales)[number];
export { allLocales };

/** Each locale's name, written in itself (for a language switch). */
export const LOCALE_NAMES: Record<Locale, string> = { en: 'English', ja: '日本語' };

// Bundled, not fetched: the translations are small and the monitor is one module.
const TEMPLATES = new Map<string, typeof ja>([['ja', ja]]);

export const { getLocale, setLocale } = configureLocalization({
  sourceLocale,
  targetLocales,
  loadLocale: (locale) => Promise.resolve(TEMPLATES.get(locale)!),
});

const STORE_KEY = 'contraagent:locale';

export const isLocale = (x: unknown): x is Locale => (allLocales as readonly unknown[]).includes(x);

/** The reader's choice from an earlier visit, else the first of the browser's languages we have, else English. */
export function preferredLocale(): Locale {
  try {
    const saved = globalThis.localStorage?.getItem(STORE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    /* storage blocked: fall through */
  }
  for (const lang of globalThis.navigator?.languages ?? []) {
    const base = lang.toLowerCase().split('-')[0];
    if (isLocale(base)) return base;
  }
  return sourceLocale;
}

/** Switch every element to `locale`, and remember the choice for the next visit. */
export async function chooseLocale(locale: Locale): Promise<void> {
  try {
    globalThis.localStorage?.setItem(STORE_KEY, locale);
  } catch {
    /* storage blocked: the choice lasts for this page */
  }
  await setLocale(locale);
}
