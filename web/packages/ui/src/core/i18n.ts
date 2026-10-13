// The language the elements speak. English is written in the sources; other
// locales are generated from xliff/<locale>.xlf by `pnpm i18n`
// (lit-localize, runtime mode) into src/locales/<locale>.ts.
//
// Importing this module configures nothing: `configureLocales()` sets up Lit
// Localize, once, when the page or `<ca-monitor>` calls it. Until then, and in
// a page whose own code configured Lit Localize first, the elements speak
// English. Every element is `@localized()`, so `setLocale` re-renders them in place.
import { configureLocalization } from '@lit/localize';
import { allLocales, sourceLocale, targetLocales } from '../locales/codes.js';

export type Locale = (typeof allLocales)[number];
export { allLocales };

/** Each locale's name, written in itself (for a language switch). */
export const LOCALE_NAMES: Record<Locale, string> = { en: 'English', ja: '日本語' };

/** Each target locale's module, loaded when the locale is first chosen. */
const LOADERS: Record<(typeof targetLocales)[number], () => Promise<typeof import('../locales/ja.js')>> = {
  ja: () => import('../locales/ja.js'),
};

let localization: ReturnType<typeof configureLocalization> | null | undefined;

/**
 * Sets up Lit Localize for these elements, once; true when the elements can
 * switch language. False when the page had already configured Lit Localize
 * (it can be configured once per page): the elements then stay in English.
 */
export function configureLocales(): boolean {
  if (localization === undefined) {
    try {
      localization = configureLocalization({ sourceLocale, targetLocales, loadLocale: (l) => LOADERS[l as keyof typeof LOADERS]() });
    } catch {
      localization = null;
    }
  }
  return localization !== null;
}

/** The language shown now: English before `configureLocales()`. */
export const getLocale = (): Locale => (localization?.getLocale() as Locale | undefined) ?? sourceLocale;

/** Show every element in `locale`; it configures the locales first if nothing has. */
export async function setLocale(locale: Locale): Promise<void> {
  if (configureLocales()) await localization!.setLocale(locale);
}

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
