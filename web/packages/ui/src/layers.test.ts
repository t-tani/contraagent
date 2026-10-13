// The layers of the web packages (AGENTS.md "Layers"), checked over every import
// and `export … from` in packages/*/src and apps/*/src. eslint.config.js holds
// the same folder rules for the editor; this test also holds the package-level
// rules ESLint cannot express, and lists the whole table in one place.
//
//   package                 may import
//   @contraagent/api        no UI: not lit, @lit/*, @contraagent/ui or @contraagent/elements
//   @contraagent/elements   no contraagent code: not @contraagent/*, @lit/localize; no msg(); no glossary word in a public name
//   @contraagent/ui         api, elements, lit, @lit/localize
//   apps/*                  the packages, only through their `exports`
//
//   inside @contraagent/ui  a folder imports only from the folders before it
//   route, router, events, i18n, lib/, styles/, themes/   never elements/
//   elements/<a>/           names only from elements/<a>/ and elements/shared/;
//                           a bare `import '../b/ca-x.js'` registers a tag it renders
//
//   taskOutcomes, outcomeCounts, taskRows   called only in @contraagent/api (deriveRun)
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, posix } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const WEB = process.cwd();
const UI = 'packages/ui/src';

/** Every .ts (and .astro) file under `dir`, relative to web/, with `/` separators. */
function sources(dir: string, ext = /\.ts$/): string[] {
  const abs = join(WEB, dir);
  if (!existsSync(abs)) return [];
  return readdirSync(abs).flatMap((name) => {
    const rel = `${dir}/${name}`;
    if (name === 'node_modules' || name === 'dist') return [];
    return statSync(join(WEB, rel)).isDirectory() ? sources(rel, ext) : ext.test(name) ? [rel] : [];
  });
}

interface Import {
  file: string;
  line: number;
  spec: string;
  /** False for a bare `import 'x'`, which binds no name. */
  names: boolean;
}

const STATEMENT = /^[ \t]*(?:import|export)\b[^;'"`]*?\bfrom\s*['"]([^'"]+)['"]/gm;
const BARE = /^[ \t]*import\s*['"]([^'"]+)['"]/gm;
const DYNAMIC = /\bimport\(\s*['"]([^'"]+)['"]\s*\)/g;

/** The imports and re-exports of `file`. */
function importsOf(file: string, text: string): Import[] {
  const lineOf = (i: number) => text.slice(0, i).split('\n').length;
  return [
    ...[...text.matchAll(STATEMENT)].map((m) => ({ file, line: lineOf(m.index), spec: m[1]!, names: true })),
    ...[...text.matchAll(DYNAMIC)].map((m) => ({ file, line: lineOf(m.index), spec: m[1]!, names: true })),
    ...[...text.matchAll(BARE)].map((m) => ({ file, line: lineOf(m.index), spec: m[1]!, names: false })),
  ];
}

/** A relative import as a path relative to web/, without its extension; a package name as it is. */
const target = (i: Import): string =>
  i.spec.startsWith('.') ? posix.normalize(posix.join(posix.dirname(i.file), i.spec)).replace(/\.(js|ts)$/, '') : i.spec;
const where = (i: Import): string => `${i.file}:${i.line} imports '${i.spec}'`;

const read = (f: string): string => readFileSync(join(WEB, f), 'utf8');
const packages = readdirSync(join(WEB, 'packages')).filter((d) => existsSync(join(WEB, 'packages', d, 'package.json')));
const manifest = (dir: string) =>
  JSON.parse(read(`${dir}/package.json`)) as {
    name: string;
    exports?: Record<string, unknown>;
    dependencies?: Record<string, string>;
    peerDependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
  };
const packageImports = (dir: string): Import[] => sources(`packages/${dir}/src`).flatMap((f) => importsOf(f, read(f)));
/** The package a bare specifier names (`@scope/name` or `name`). */
const packageOf = (spec: string): string => spec.split('/').slice(0, spec.startsWith('@') ? 2 : 1).join('/');

/** Which packages each package must not import. */
const FORBIDDEN: Record<string, (spec: string) => boolean> = {
  api: (s) => /^(lit|@lit\/|@contraagent\/(ui|elements)(\/|$))/.test(s),
  elements: (s) => /^(@contraagent\/|@lit\/localize(\/|$))/.test(s),
};

/** Imports of names across folders of ui's elements/ that wait for a later phase (the file and the module it imports). */
const CROSS_FOLDER_GAPS = new Set<string>([]);

describe('package layers', () => {
  it.each(packages)('%s imports only what its layer allows', (dir) => {
    const deny = FORBIDDEN[dir];
    const m = manifest(`packages/${dir}`);
    const declared = new Set(Object.keys({ ...m.dependencies, ...m.peerDependencies, ...m.devDependencies }));
    const bad = packageImports(dir).filter((i) => {
      if (i.spec.startsWith('.')) return !target(i).startsWith(`packages/${dir}/`); // a relative path into another package
      if (i.spec.startsWith('node:') || i.spec.startsWith('vitest')) return false;
      if (deny?.(i.spec)) return true;
      // Another workspace package only when this package depends on it.
      return i.spec.startsWith('@contraagent/') && !declared.has(packageOf(i.spec));
    });
    expect(bad.map(where)).toEqual([]);
  });

  it('apps import a package only through its exports', () => {
    const exportsOf = new Map(
      packages.map((d) => {
        const m = manifest(`packages/${d}`);
        return [m.name, new Set(Object.keys(m.exports ?? {}).map((k) => (k === '.' ? m.name : `${m.name}/${k.slice(2)}`)))];
      }),
    );
    const files = readdirSync(join(WEB, 'apps')).flatMap((a) => sources(`apps/${a}/src`, /\.(ts|astro)$/));
    expect(files.length).toBeGreaterThan(0);
    const bad = files
      .flatMap((f) => importsOf(f, read(f)))
      .filter((i) => {
        if (i.spec.startsWith('.')) return target(i).startsWith('packages/');
        const subpaths = exportsOf.get(packageOf(i.spec));
        return subpaths !== undefined && !subpaths.has(i.spec);
      });
    expect(bad.map(where)).toEqual([]);
  });
});

describe('@contraagent/ui folders', () => {
  const imports = packageImports('ui');

  it('reads the sources', () => {
    expect(imports.length).toBeGreaterThan(100);
  });

  it('route, router, events, i18n, lib/, styles/ and themes/ never import elements/', () => {
    const lower = (f: string) => /^packages\/ui\/src\/((route|router|events|i18n)\.ts|lib\/|styles\/|themes\/)/.test(f);
    const bad = imports.filter((i) => lower(i.file) && target(i).startsWith(`${UI}/elements/`));
    expect(bad.map(where)).toEqual([]);
  });

  it('an elements/ folder imports names only from itself and shared/', () => {
    const folder = (p: string) => /^packages\/ui\/src\/elements\/([^/]+)\//.exec(p)?.[1];
    const bad = imports.filter((i) => {
      const a = folder(i.file);
      const b = folder(target(i));
      return a && b && b !== a && b !== 'shared' && i.names && !CROSS_FOLDER_GAPS.has(`${i.file} -> ${target(i)}`);
    });
    expect(bad.map(where)).toEqual([]);
  });
});

// A run's tasks are derived once, by `deriveRun` in @contraagent/api: no other
// package calls the folds it is built from.
const DERIVATIONS = ['taskOutcomes', 'outcomeCounts', 'taskRows'];

describe('single derivation', () => {
  it('only @contraagent/api calls the folds behind deriveRun', () => {
    const call = new RegExp(`\\b(${DERIVATIONS.join('|')})\\(`);
    const files = [
      ...packages.filter((d) => d !== 'api').flatMap((d) => sources(`packages/${d}/src`)),
      ...readdirSync(join(WEB, 'apps')).flatMap((a) => sources(`apps/${a}/src`, /\.(ts|astro)$/)),
    ];
    expect(files.length).toBeGreaterThan(50);
    const bad = files.flatMap((f) =>
      read(f)
        .split('\n')
        .flatMap((l, i) => (call.test(l) ? [`${f}:${i + 1}: ${l.trim()}`] : [])),
    );
    expect(bad).toEqual([]);
  });
});

// From P8 on, @contraagent/elements is the generic package: it names nothing
// after contraagent's glossary (src/contraagent/docs/concepts.md).
const GLOSSARY = ['plan', 'journal', 'kind', 'unit', 'attempt', 'stop', 'outcome', 'task', 'contract', 'round', 'launch', 'hop', 'pass', 'run'];

/** The glossary words in an identifier (`planNode`, `PLAN_NODE`, `plan-node`, plurals too). */
function glossaryWords(name: string): string[] {
  const words = name
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
    .split(/[\s_$-]+/)
    .map((w) => w.toLowerCase());
  return GLOSSARY.filter((g) => words.some((w) => w === g || w === `${g}s` || w === `${g}es`));
}

/** The names a module exports. */
function exportedNames(text: string): string[] {
  const declared = [...text.matchAll(/^[ \t]*export\s+(?:declare\s+)?(?:default\s+)?(?:abstract\s+)?(?:async\s+)?(?:const|let|var|function\*?|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/gm)].map((m) => m[1]!);
  const listed = [...text.matchAll(/^[ \t]*export\s+(?:type\s+)?\{([^}]*)\}/gm)].flatMap((m) =>
    m[1]!
      .split(',')
      .map((s) => s.trim().replace(/^type\s+/, '').split(/\s+as\s+/).pop()!)
      .filter(Boolean),
  );
  return [...declared, ...listed];
}

/** The property names declared in a types module (`name:` or `name?:` at the start of a line). */
function propertyNames(text: string): string[] {
  return [...text.matchAll(/^[ \t]*(?:readonly\s+)?([A-Za-z_$][\w$]*)\??\s*:/gm)].map((m) => m[1]!);
}

describe('generic package purity', () => {
  it('finds glossary words in names', () => {
    expect(glossaryWords('PlanNode')).toEqual(['plan']);
    expect(glossaryWords('TASK_ROWS')).toEqual(['task']);
    expect(glossaryWords('cae-runs-view')).toEqual(['run']);
    expect(glossaryWords('LayeredGraph')).toEqual([]);
    expect(glossaryWords('runtime')).toEqual([]);
    expect(exportedNames("export interface A {}\nexport const b = 1;\nexport { c as D, type E };")).toEqual(['A', 'b', 'D', 'E']);
    expect(propertyNames('interface X {\n  id: string;\n  readonly label?: string;\n}')).toEqual(['id', 'label']);
  });

  const files = sources('packages/elements/src').filter((f) => !f.endsWith('.test.ts'));

  it.runIf(files.length > 0)('@contraagent/elements calls no msg()', () => {
    expect(files.filter((f) => /\bmsg\(/.test(read(f)))).toEqual([]);
  });

  it.runIf(files.length > 0)('@contraagent/elements names nothing after the glossary', () => {
    const bad = files.flatMap((f) => {
      const text = read(f);
      const names = [...exportedNames(text), ...(f.endsWith('/types.ts') ? propertyNames(text) : [])];
      return names.filter((n) => glossaryWords(n).length).map((n) => `${f}: ${n} (${glossaryWords(n).join(', ')})`);
    });
    expect(bad).toEqual([]);
  });
});
