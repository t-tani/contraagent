// The events an element documents (`@fires`, which custom-elements.json and the
// element reference read) are the events it sends, and every event is typed in
// the event map: `CaEventMap` (ui/src/core/events.ts), and from P8 `CaeEventMap`
// (elements/src/core/events.ts) for `cae-*`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, posix } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const WEB = process.cwd();
const read = (f: string): string => readFileSync(join(WEB, f), 'utf8');

function sources(dir: string): string[] {
  if (!existsSync(join(WEB, dir))) return [];
  return readdirSync(join(WEB, dir)).flatMap((name) => {
    const rel = `${dir}/${name}`;
    return statSync(join(WEB, rel)).isDirectory() ? sources(rel) : name.endsWith('.ts') && !name.endsWith('.test.ts') ? [rel] : [];
  });
}

const files = readdirSync(join(WEB, 'packages')).flatMap((p) => sources(`packages/${p}/src`));
/** An element file defines a Lit element class. */
const elementFiles = files.filter((f) => /\bextends\s+LitElement\b/.test(read(f)));

/** Template helpers that send an event from the element that renders them. */
const HELPERS: Record<string, { file: string; event: string }> = {
  taskChip: { file: 'packages/ui/src/elements/shared/task-chip.ts', event: 'ca-open-task' },
};

/** The event names `text` sends itself. */
function sent(text: string): Set<string> {
  const names = [
    ...[...text.matchAll(/\bemit\(\s*[^,()]+,\s*'([^']+)'/g)].map((m) => m[1]!),
    ...[...text.matchAll(/\bnew\s+(?:Custom)?Event\(\s*'([^']+)'/g)].map((m) => m[1]!),
    ...Object.entries(HELPERS)
      .filter(([fn]) => new RegExp(`\\b${fn}\\(`).test(text))
      .map(([, h]) => h.event),
  ];
  return new Set(names);
}

/**
 * The parts of element file `f`: the modules in its folder (or below) that it
 * imports, directly or through another part, and that define no element. An
 * element renders its parts' templates, so it sends the events they send.
 */
function partsOf(f: string, seen = new Set<string>()): Set<string> {
  const folder = posix.dirname(f);
  for (const m of read(f).matchAll(/^\s*import\s+(?!type\b)(?:[^'";]*?\bfrom\s*)?'(\.[^']+)'/gm)) {
    const dep = posix.normalize(posix.join(posix.dirname(f), m[1]!)).replace(/\.js$/, '.ts');
    if (seen.has(dep) || !dep.startsWith(`${folder}/`) || !files.includes(dep) || elementFiles.includes(dep)) continue;
    seen.add(dep);
    partsOf(dep, seen);
  }
  return seen;
}

/** The event names element file `f` sends, itself or through its parts. */
const sentBy = (f: string): Set<string> => new Set([f, ...partsOf(f)].flatMap((x) => [...sent(read(x))]));

/** The event names in the JSDoc `@fires` tags of `text`. */
const declared = (text: string): Set<string> => new Set([...text.matchAll(/@fires\s+([\w-]+)/g)].map((m) => m[1]!));

/** The names an element handles on itself (`this.addEventListener('x'`): it is their host, not their source. */
const handled = (text: string): Set<string> => new Set([...text.matchAll(/\bthis\.addEventListener\(\s*'([^']+)'/g)].map((m) => m[1]!));

/** The keys of `interface <name> { … }` in `file`. */
function mapKeys(file: string, name: string): Set<string> {
  if (!existsSync(join(WEB, file))) return new Set();
  const body = new RegExp(`interface\\s+${name}\\s*\\{([\\s\\S]*?)\\n\\}`).exec(read(file))?.[1] ?? '';
  return new Set([...body.matchAll(/^\s*'([^']+)'\??\s*:/gm)].map((m) => m[1]!));
}

const UI_EVENTS = 'packages/ui/src/core/events.ts';
const CA = mapKeys(UI_EVENTS, 'CaEventMap');
const CAE = mapKeys('packages/elements/src/core/events.ts', 'CaeEventMap');
const inMap = (name: string): boolean => (name.startsWith('cae-') ? CAE : CA).has(name);
const sorted = (s: Set<string>): string[] => [...s].sort();

describe('@fires', () => {
  it('reads the elements and the event map', () => {
    expect(elementFiles.length).toBeGreaterThan(20);
    expect(CA.size).toBeGreaterThan(0);
  });

  it.each(elementFiles)('%s declares exactly the events it sends', (f) => {
    const text = read(f);
    const own = handled(text);
    expect(sorted(declared(text))).toEqual(sorted(new Set([...sentBy(f)].filter((n) => !own.has(n)))));
  });

  it('every event sent is in an event map', () => {
    const missing = files.flatMap((f) => [...sent(read(f))].filter((n) => !inMap(n)).map((n) => `${f}: ${n}`));
    expect(missing).toEqual([]);
  });

  it('every key of an event map is sent somewhere', () => {
    const all = new Set(files.flatMap((f) => [...sent(read(f))]));
    expect([...CA, ...CAE].filter((k) => !all.has(k))).toEqual([]);
  });

  it('CaEventMap and the HTMLElementEventMap augmentation list the same events', () => {
    expect(sorted(mapKeys(UI_EVENTS, 'HTMLElementEventMap'))).toEqual(sorted(CA));
  });

  it('each helper sends its event', () => {
    for (const { file, event } of Object.values(HELPERS)) expect(sent(read(file)).has(event), file).toBe(true);
  });
});
