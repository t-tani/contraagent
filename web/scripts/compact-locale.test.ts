import { runInNewContext } from 'node:vm';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compactLocale, lookup, shortKeys, staticLocaleImports } from './compact-locale.mjs';

const ja = readFileSync(new URL('../packages/ui/src/locales/ja.ts', import.meta.url), 'utf8');
const xliffIds = [...readFileSync(new URL('../packages/ui/xliff/ja.xlf', import.meta.url), 'utf8').matchAll(/<trans-unit id="([^"]+)">/g)].map((m) => m[1]!);

/** The `templates` a locale module's source exports, with `html` and `str` as plain tags. */
function templatesOf(code: string): Record<string, unknown> {
  const body = code
    .replace(/^\s*import .*$/gm, '')
    .replace('export const templates =', 'return');
  type Tag = (strings: TemplateStringsArray, ...values: unknown[]) => unknown;
  const tag = (kind: string): Tag => (strings, ...values) => ({ kind, strings: [...strings], values });
  const module = runInNewContext(`(function (html, str) {${body}})`) as (html: Tag, str: Tag) => Record<string, unknown>;
  return module(tag('html'), tag('str'));
}

describe('shortKeys', () => {
  it("gives each id its shortest prefix that no other id starts with", () => {
    const keys = shortKeys(['s0382d7', 's03b454', 's1abc', 'h56', 'none', 'no-runs']);
    expect(Object.fromEntries(keys)).toEqual({ s0382d7: 's038', s03b454: 's03b', s1abc: 's1', h56: 'h', none: 'non', 'no-runs': 'no-' });
  });

  it('throws when an id is a prefix of another', () => {
    expect(() => shortKeys(['tab', 'tab-tasks'])).toThrow(/prefix/);
  });
});

describe('lookup', () => {
  it('finds each id by its key, and nothing else that is not a prefix of a key', () => {
    const ids = ['s0382d7', 's03b454', 's1abc', 'h56'];
    const keys = shortKeys(ids);
    const t = lookup(Object.fromEntries(ids.map((id) => [keys.get(id)!, `v-${id}`])));
    for (const id of ids) expect(t[id]).toBe(`v-${id}`);
    expect(t['x']).toBeUndefined();
    expect(t['constructor']).toBeUndefined();
  });
});

describe('compactLocale', () => {
  const before = templatesOf(ja);
  const after = templatesOf(compactLocale(ja));

  it('reads every message of the locale', () => {
    expect(Object.keys(before).sort()).toEqual([...xliffIds].sort());
  });

  it('answers every id with the same template as the generated module', () => {
    for (const id of xliffIds) expect(after[id], id).toEqual(before[id]);
  });

  it('stores no id in full when a shorter prefix will do', () => {
    const code = compactLocale(ja);
    expect(code).not.toMatch(/'[sh][0-9a-f]{16}'/);
    expect(code.length).toBeLessThan(ja.length);
  });
});

describe('staticLocaleImports', () => {
  it('turns each dynamic import of a locale into a static one, and leaves types alone', () => {
    const code = "type M = typeof import('../locales/ja.js');\nconst L = { ja: () => import('../locales/ja.js') };";
    expect(staticLocaleImports(code)).toBe(
      "import * as __locale_ja from '../locales/ja.js';\ntype M = typeof import('../locales/ja.js');\nconst L = { ja: () => Promise.resolve(__locale_ja) };",
    );
  });
});
