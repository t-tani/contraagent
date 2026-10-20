// The entries of @contraagent/ui without elements (the adapters, the words, the
// core and the languages) import outside a browser (Node, no DOM) without an
// error and without touching `document`; the languages are not configured at
// import.
import { describe, expect, it } from 'vitest';

const ENTRIES = ['@contraagent/ui/adapters', '@contraagent/ui/words', '@contraagent/ui/core', '@contraagent/ui/localize'];

// Imported as the file loads: the first import transforms most of the package, which
// takes as long as the machine makes it, and a test's time limit is for its checks.
const imported = await Promise.allSettled(ENTRIES.map((spec) => import(spec) as Promise<Record<string, unknown>>));

describe('importing @contraagent/ui without a DOM', () => {
  it.each(ENTRIES.map((spec, i) => [spec, imported[i]!] as const))('%s', (_spec, result) => {
    if (result.status === 'rejected') throw result.reason;
    expect(Object.keys(result.value).length).toBeGreaterThan(0);
    expect(globalThis.document).toBeUndefined();
  });

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
