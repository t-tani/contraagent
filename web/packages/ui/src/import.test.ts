// The entries of @contraagent/ui without elements (the adapters, the words, the
// core and the languages) import outside a browser (Node, no DOM) without an
// error and without touching `document`; the languages are not configured at
// import.
import { describe, expect, it } from 'vitest';

const ENTRIES = ['@contraagent/ui/adapters', '@contraagent/ui/words', '@contraagent/ui/core', '@contraagent/ui/localize'];

describe('importing @contraagent/ui without a DOM', () => {
  it.each(ENTRIES)('%s', async (spec) => {
    const mod = (await import(spec)) as Record<string, unknown>;
    expect(Object.keys(mod).length).toBeGreaterThan(0);
    expect(globalThis.document).toBeUndefined();
  }, 30_000); // the first import transforms the whole package

  it('configures Lit Localize only when asked, once', async () => {
    const { configureLocales, getLocale } = await import('@contraagent/ui/localize');
    const { configureLocalization } = await import('@lit/localize');
    expect(getLocale()).toBe('en');
    // Nothing configured it at import: a page can still configure Lit Localize itself.
    expect(configureLocales()).toBe(true);
    expect(configureLocales()).toBe(true);
    expect(() => configureLocalization({ sourceLocale: 'en', targetLocales: [], loadLocale: () => Promise.reject(new Error()) })).toThrow();
  });
});
