// A Vite plugin for the built bundles (the monitor's `app.js` and `ja.js`, ui's `./bundle`): a
// locale module that lit-localize generates (runtime mode, `src/locales/<locale>.ts`) keys its
// templates by a shorter id. Lit Localize looks a message up as `templates[id]`, where `id` is
// the 17-character hash of the message (or the `id` given to `msg()`); random hex digits do not
// compress, so they were half of the Japanese text's gzip size. Each id is stored as its shortest
// prefix that no other id of the locale starts with, and `templates` answers a lookup by the first
// prefix of the id it has. Every id of the locale finds its own template: an id's key is not a
// prefix of any other id. The locale has every message of the sources (`pnpm check` fails while one
// is missing), so no other id is looked up.

/** Each id's shortest prefix that is not a prefix of any other id. Throws when an id is a prefix of another. */
export function shortKeys(ids) {
  const sorted = [...ids].sort();
  const common = (a, b) => {
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    return i;
  };
  const keys = new Map();
  sorted.forEach((id, i) => {
    // Sorted, an id's longest common prefix with any other id is with a neighbour.
    const n = Math.max(i > 0 ? common(id, sorted[i - 1]) : 0, i + 1 < sorted.length ? common(id, sorted[i + 1]) : 0);
    if (n >= id.length) throw new Error(`locale id ${id} is a prefix of another id`);
    keys.set(id, id.slice(0, n + 1));
  });
  return keys;
}

/**
 * The lookup the compacted module ends with: `templates[id]` is the template stored under the
 * first prefix of `id` that is a key (kept per id after the first lookup), else undefined.
 */
export function lookup(table) {
  const found = new Map();
  return new Proxy(table, {
    get(t, id) {
      if (typeof id !== 'string') return undefined;
      if (!found.has(id)) {
        let v;
        for (let i = 1; i <= id.length && v === undefined; i++) {
          const k = id.slice(0, i);
          if (Object.hasOwn(t, k)) v = t[k];
        }
        found.set(id, v);
      }
      return found.get(id);
    },
  });
}

const ENTRY = /^([ \t]*)'([^'\\]+)': /gm;
const OPEN = 'export const templates = {';

/** The source of a lit-localize locale module with its keys shortened and `templates` the lookup. */
export function compactLocale(code) {
  const start = code.indexOf(OPEN);
  if (start < 0) throw new Error('not a lit-localize locale module: no `export const templates = {`');
  const body = code.slice(start + OPEN.length);
  const ids = [...body.matchAll(ENTRY)].map((m) => m[2]);
  const keys = shortKeys(ids);
  const table = body.replace(ENTRY, (_, indent, id) => `${indent}${JSON.stringify(keys.get(id))}: `);
  return `${code.slice(0, start)}const table = {${table}\nexport const templates = (${lookup.toString()})(table);\n`;
}

const LOAD = /(?<!typeof\s+)\bimport\((['"])(\.{1,2}\/locales\/[\w-]+\.js)\1\)/g;

/**
 * `code` with each `import('…/locales/<locale>.js')` an already loaded module: a static import,
 * resolved at once. For a bundle that is one file, where the locales are inlined anyway.
 */
export function staticLocaleImports(code) {
  const paths = [...new Set([...code.matchAll(LOAD)].map((m) => m[2]))];
  if (!paths.length) return code;
  const name = (p) => `__locale_${p.replace(/^.*\/|\.js$/g, '').replace(/\W/g, '_')}`;
  const imports = paths.map((p) => `import * as ${name(p)} from '${p}';\n`).join('');
  return imports + code.replace(LOAD, (_, __, p) => `Promise.resolve(${name(p)})`);
}

/** @returns {import('vite').Plugin} The locales loaded with the page (`staticLocaleImports`), for a one-file bundle. */
export function staticLocales() {
  return {
    name: 'contraagent-static-locales',
    enforce: 'pre',
    transform(code, id) {
      if (!/\/packages\/ui\/src\/core\/i18n\.ts$/.test(id)) return null;
      return { code: staticLocaleImports(code), map: null };
    },
  };
}

/** @returns {import('vite').Plugin} */
export function compactLocales() {
  return {
    name: 'contraagent-compact-locales',
    enforce: 'pre',
    transform(code, id) {
      if (!/\/packages\/ui\/src\/locales\/(?!codes\.)[^/]+\.ts$/.test(id)) return null;
      return { code: compactLocale(code), map: null };
    },
  };
}
