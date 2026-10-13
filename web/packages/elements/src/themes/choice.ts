// The reader's choice of a theme: which theme it shows, and remembering it in
// this browser.
import { DEFAULT_THEME, SYSTEM_THEMES, THEME_CHOICES, THEME_NAMES, type ThemeChoice, type ThemeName } from './data.js';

export const isThemeName = (x: unknown): x is ThemeName => (THEME_NAMES as readonly unknown[]).includes(x);
export const isThemeChoice = (x: unknown): x is ThemeChoice => (THEME_CHOICES as readonly unknown[]).includes(x);

/** The theme a choice shows: `system` by the system's colour scheme; anything else not a theme, the default. */
export function resolveTheme(choice: unknown, prefersLight: boolean): ThemeName {
  if (choice === 'system') return prefersLight ? SYSTEM_THEMES.light : SYSTEM_THEMES.dark;
  return isThemeName(choice) ? choice : DEFAULT_THEME;
}

/** Where the reader's choice is kept (this browser only). */
export const THEME_STORE_KEY = 'contraagent:theme';

type Store = Pick<Storage, 'getItem' | 'setItem'>;
const storage = (): Store | undefined => {
  try {
    return globalThis.localStorage;
  } catch {
    return undefined;
  }
};

/** The reader's choice from an earlier visit, else the default theme. */
export function preferredTheme(store: Store | undefined = storage()): ThemeChoice {
  try {
    const saved = store?.getItem(THEME_STORE_KEY);
    if (isThemeChoice(saved)) return saved;
  } catch {
    /* storage blocked: the default */
  }
  return DEFAULT_THEME;
}

/** Remember the reader's choice for the next visit. */
export function rememberTheme(choice: ThemeChoice, store: Store | undefined = storage()): void {
  try {
    store?.setItem(THEME_STORE_KEY, choice);
  } catch {
    /* storage blocked: the choice lasts for this page */
  }
}

/** Whether the system asks for a light colour scheme. */
export const prefersLight = (): boolean => globalThis.matchMedia?.('(prefers-color-scheme: light)').matches ?? false;
