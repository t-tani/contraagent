// The events an element documents (`@fires`, which custom-elements.json and the
// element reference read) are the events it sends, and every event is typed in
// the event map: `CaEventMap` (ui/src/events.ts), and from P8 `CaeEventMap`
// (elements/src/core/events.ts) for `cae-*`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
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

/**
 * Events sent but not yet in an event map. P3 adds them as `ca-close` and
 * `ca-rounds` and removes them from this list; the test fails while an entry
 * here is in a map or no longer sent.
 */
const KNOWN_GAPS: Record<string, string> = {
  close: 'packages/ui/src/elements/shell/ca-run-picker.ts',
  'rounds-changed': 'packages/ui/src/elements/task/ca-transcript.ts',
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

const UI_EVENTS = 'packages/ui/src/events.ts';
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
    expect(sorted(declared(text))).toEqual(sorted(new Set([...sent(text)].filter((n) => !own.has(n)))));
  });

  it('every event sent is in an event map', () => {
    const missing = files.flatMap((f) =>
      [...sent(read(f))].filter((n) => !inMap(n) && KNOWN_GAPS[n] !== f).map((n) => `${f}: ${n}`),
    );
    expect(missing).toEqual([]);
  });

  it('every key of an event map is sent somewhere', () => {
    const all = new Set(files.flatMap((f) => [...sent(read(f))]));
    expect([...CA, ...CAE].filter((k) => !all.has(k))).toEqual([]);
  });

  it('CaEventMap and the HTMLElementEventMap augmentation list the same events', () => {
    expect(sorted(mapKeys(UI_EVENTS, 'HTMLElementEventMap'))).toEqual(sorted(CA));
  });

  it('the known gaps are still gaps', () => {
    for (const [name, file] of Object.entries(KNOWN_GAPS)) {
      expect(inMap(name), `${name} is in the event map: remove it from KNOWN_GAPS`).toBe(false);
      expect(sent(read(file)).has(name), `${file} no longer sends ${name}: remove it from KNOWN_GAPS`).toBe(true);
    }
  });

  it('each helper sends its event', () => {
    for (const { file, event } of Object.values(HELPERS)) expect(sent(read(file)).has(event), file).toBe(true);
  });
});
