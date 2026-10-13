// Every name a module exports through an `export *` chain from `src/index.ts`
// (the folder `index.ts` files included) is reachable from `@contraagent/ui` as
// that same declaration: an explicit export of the same name shadows a star
// export, and two star exports of one name exclude it as ambiguous. Both drop a
// name without an error, so this test reads the exports with the compiler.
import { join, relative } from 'node:path';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

// Vitest runs from web/.
const WEB = process.cwd();
const UI = join(WEB, 'packages/ui');

function program(): ts.Program {
  const file = join(UI, 'tsconfig.json');
  const config = ts.readConfigFile(file, (f) => ts.sys.readFile(f));
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, UI);
  return ts.createProgram({ rootNames: [join(UI, 'src/index.ts')], options: { ...parsed.options, noEmit: true } });
}

describe('exports of @contraagent/ui', () => {
  const prog = program();
  const checker = prog.getTypeChecker();
  const original = (s: ts.Symbol): ts.Symbol => (s.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(s) : s);
  const moduleOf = (f: ts.SourceFile): ts.Symbol => checker.getSymbolAtLocation(f)!;

  const index = prog.getSourceFile(join(UI, 'src/index.ts'))!;
  const reachable = new Map(checker.getExportsOfModule(moduleOf(index)).map((s) => [s.name, original(s)]));

  /** The modules `file` re-exports with `export * from`, followed through folder index files. */
  function starTargets(file: ts.SourceFile, seen = new Set<string>()): ts.SourceFile[] {
    const out: ts.SourceFile[] = [];
    for (const st of file.statements) {
      if (!ts.isExportDeclaration(st) || st.exportClause || !st.moduleSpecifier) continue;
      const decl = checker.getSymbolAtLocation(st.moduleSpecifier)?.valueDeclaration;
      if (!decl || !ts.isSourceFile(decl) || seen.has(decl.fileName)) continue;
      seen.add(decl.fileName);
      out.push(decl, ...starTargets(decl, seen));
    }
    return out;
  }
  const targets = starTargets(index);

  it('follows the star exports', () => {
    expect(targets.length).toBeGreaterThan(20);
    expect(reachable.size).toBeGreaterThan(50);
  });

  it('every name a star-exported module exports is reachable, and is that declaration', () => {
    const bad = targets.flatMap((f) =>
      checker
        .getExportsOfModule(moduleOf(f))
        .filter((s) => s.name !== 'default')
        .flatMap((s) => {
          const where = `${relative(UI, f.fileName)}: ${s.name}`;
          const got = reachable.get(s.name);
          if (!got) return [`${where} is not exported (ambiguous)`];
          return got === original(s) ? [] : [`${where} is shadowed by another export`];
        }),
    );
    expect(bad).toEqual([]);
  });
});
