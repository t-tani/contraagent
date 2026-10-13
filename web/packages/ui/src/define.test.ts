// Each `define/` entry registers every element its elements render: a view
// imported alone (`@contraagent/ui/transcript`) shows no unknown tag. Read from
// the sources: the tags a ui module renders (`<ca-x`, `<cae-x`) are registered
// by the modules it imports, followed through relative imports and the
// entries of @contraagent/elements.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, normalize } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const WEB = process.cwd();
const UI = join(WEB, 'packages/ui/src');

const elementsExports = (JSON.parse(readFileSync(join(WEB, 'packages/elements/package.json'), 'utf8')) as { exports: Record<string, { source?: string }> }).exports;

/** The file an import names, or null for a package outside the workspace. */
function resolve(from: string, spec: string): string | null {
  if (spec.startsWith('.')) {
    const ts = normalize(join(dirname(from), spec.replace(/\.js$/, '.ts')));
    return statSync(ts, { throwIfNoEntry: false })?.isFile() ? ts : null;
  }
  const m = /^@contraagent\/elements(\/.*)?$/.exec(spec);
  const source = m && elementsExports[`.${m[1] ?? ''}`]?.source;
  return source ? join(WEB, 'packages/elements', source) : null;
}

/** The files `file` imports, its own included, transitively. */
function closure(file: string, seen = new Set<string>()): Set<string> {
  if (seen.has(file)) return seen;
  seen.add(file);
  const text = readFileSync(file, 'utf8');
  for (const m of text.matchAll(/^\s*(?:import|export)\b[^'"]*?['"]([^'"]+)['"]/gm)) {
    const f = resolve(file, m[1]!);
    if (f) closure(f, seen);
  }
  return seen;
}

/** The tags a set of files registers and the tags it renders. */
function tags(files: Set<string>): { defined: Set<string>; rendered: Set<string> } {
  const defined = new Set<string>();
  const rendered = new Set<string>();
  for (const f of files) {
    const text = readFileSync(f, 'utf8');
    for (const m of text.matchAll(/(?:@customElement\(|defineElement\()'([a-z-]+)'/g)) defined.add(m[1]!);
    if (!f.startsWith(UI)) continue; // @contraagent/elements: each of its define entries registers what its element renders
    const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    for (const m of code.matchAll(/<(cae?-[a-z-]+)[\s>]/g)) rendered.add(m[1]!);
  }
  return { defined, rendered };
}

const entries = readdirSync(join(UI, 'define')).filter((f) => f.endsWith('.ts') && !f.endsWith('.test.ts'));

describe('define/ entries of @contraagent/ui', () => {
  it('reads the entries', () => {
    expect(entries.length).toBeGreaterThan(10);
  });

  it.each(entries)('%s registers every tag its elements render', (entry) => {
    const { defined, rendered } = tags(closure(join(UI, 'define', entry)));
    expect([...rendered].filter((t) => !defined.has(t))).toEqual([]);
  });
});
