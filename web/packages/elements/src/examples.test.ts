// @vitest-environment happy-dom
// docs/examples is documentation: the elements it uses exist, each example
// mounts, and the theme sets only properties the elements read.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import './define/all.js';
import { tokenStyles } from './styles/index.js';

// Vitest runs from web/ (under happy-dom, import.meta.url is not a file URL).
const DIR = join(process.cwd(), 'packages', 'elements', 'docs', 'examples');
const read = (f: string) => readFileSync(join(DIR, f), 'utf8');
const files = readdirSync(DIR);
const modules = files.filter((f) => f.endsWith('.ts'));

describe('docs/examples', () => {
  it('uses only elements this package defines', () => {
    const tags = new Set(modules.flatMap((f) => [...read(f).matchAll(/['<](cae-[a-z-]+)/g)].map((m) => m[1]!)));
    const known = [...tags].filter((t) => t !== 'cae-change');
    expect(known.length).toBeGreaterThan(0);
    for (const t of known) expect(customElements.get(t), t).toBeDefined();
  });

  it.each(modules)('%s mounts into a host', async (f) => {
    const mod = (await import(`../docs/examples/${f.slice(0, -3)}.ts`)) as { mount: (host: HTMLElement) => void };
    const host = document.createElement('div');
    document.body.append(host);
    mod.mount(host);
    expect(host.children.length).toBeGreaterThan(0);
    host.remove();
  });

  it('themes only with --ca-* properties the elements read', () => {
    const read_ = new Set([...tokenStyles.cssText.matchAll(/var\((--ca-[a-z0-9-]+)/g)].map((m) => m[1]));
    const set = [...read('theme.css').matchAll(/(--ca-[a-z0-9-]+)\s*:/g)].map((m) => m[1]);
    expect(set.length).toBeGreaterThan(0);
    for (const p of set) expect(read_.has(p), p).toBe(true);
  });
});
