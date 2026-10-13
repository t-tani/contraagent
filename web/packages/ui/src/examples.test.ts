// @vitest-environment happy-dom
// docs/examples is documentation: the elements it uses exist.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import './index.js';

// Vitest runs from web/ (under happy-dom, import.meta.url is not a file URL).
const DIR = join(process.cwd(), 'packages', 'ui', 'docs', 'examples');
const read = (f: string) => readFileSync(join(DIR, f), 'utf8');
const files = readdirSync(DIR);

describe('docs/examples', () => {
  it('uses only elements this package defines', () => {
    const tags = new Set(files.filter((f) => /\.(html|ts)$/.test(f)).flatMap((f) => [...read(f).matchAll(/['<](ca-[a-z-]+)/g)].map((m) => m[1]!)));
    const known = [...tags].filter((t) => !t.startsWith('ca-open') && !t.startsWith('ca-select') && !['ca-filter', 'ca-navigate'].includes(t));
    expect(known.length).toBeGreaterThan(0);
    for (const t of known) expect(customElements.get(t), t).toBeDefined();
  });
});
