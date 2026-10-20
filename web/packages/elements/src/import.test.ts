// Every entry of the package but the `define` ones imports outside a browser
// (Node, no DOM) without an error and without touching `document`: importing a
// module registers nothing and changes no page.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const pkg = JSON.parse(readFileSync(join(process.cwd(), 'packages/elements/package.json'), 'utf8')) as { exports: Record<string, unknown> };
const entries = Object.entries(pkg.exports)
  .filter(([sub, target]) => typeof target === 'object' && !sub.endsWith('/define'))
  .map(([sub]) => `@contraagent/elements${sub.slice(1)}`);

// Imported as the file loads: the first import transforms the whole package, which
// takes as long as the machine makes it, and a test's time limit is for its checks.
const imported = await Promise.allSettled(entries.map((spec) => import(spec) as Promise<Record<string, unknown>>));

describe('importing @contraagent/elements without a DOM', () => {
  it('reads the entries', () => {
    expect(entries.length).toBeGreaterThan(10);
    expect(globalThis.document).toBeUndefined();
  });

  it.each(entries.map((spec, i) => [spec, imported[i]!] as const))('%s', (_spec, result) => {
    if (result.status === 'rejected') throw result.reason;
    expect(Object.keys(result.value).length).toBeGreaterThan(0);
    expect(globalThis.document).toBeUndefined();
  });
});
