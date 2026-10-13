// @ts-check
import { existsSync, readdirSync } from 'node:fs';
import tseslint from 'typescript-eslint';
import lit from 'eslint-plugin-lit';

// The layers (AGENTS.md "Layers"): what each folder must not import. One
// `no-restricted-imports` block per glob, generated from this table; the same
// table, with what ESLint cannot express, is checked by
// packages/ui/src/layers.test.ts. Keep the two in step.
const UI = 'packages/ui/src';
const UI_FOLDERS = readdirSync(new URL(`./${UI}/elements`, import.meta.url), { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name);
/** `elements/<a>` may import only itself and `shared/`; these imports wait for a later phase. */
/** @type {Record<string, string[]>} */
const CROSS_FOLDER_GAPS = {};

/** A relative import into `elements/` from a file outside it. */
const intoElements = { regex: '^\\.{1,2}/(\\.\\./)*elements/', message: 'A lower layer must not import an element.' };
/**
 * A name imported from the folder `b` of `elements/`, from inside another folder
 * of it. A bare `import '../b/ca-x.js'` (it registers a tag the element renders)
 * names nothing, so it passes.
 */
const intoFolder = (/** @type {string} */ b, /** @type {string[]} */ allowed = []) => ({
  regex: `^\\.\\./(\\.\\./)*(elements/)?${b}/${allowed.length ? `(?!(${allowed.map((a) => a.slice(b.length + 1)).join('|')})(\\.js)?$)` : ''}`,
  importNamePattern: '^',
  message: `An element folder imports names only from its own files and shared/: move what it needs from ${b}/ to a lower layer.`,
});

/** @type {{ files: string[], ignores?: string[], patterns: object[] }[]} */
const LAYERS = [
  {
    files: ['packages/api/src/**/*.ts'],
    patterns: [{ group: ['lit', 'lit/*', '@lit/*', '@contraagent/ui', '@contraagent/ui/*', '@contraagent/elements', '@contraagent/elements/*'], message: '@contraagent/api has no UI.' }],
  },
  { files: [`${UI}/{route,router,events,i18n}.ts`, `${UI}/lib/**/*.ts`, `${UI}/styles/**/*.ts`], patterns: [intoElements] },
  ...UI_FOLDERS.flatMap((a) => {
    const others = UI_FOLDERS.filter((b) => b !== a && b !== 'shared');
    const gaps = Object.entries(CROSS_FOLDER_GAPS).filter(([f]) => f.startsWith(`${UI}/elements/${a}/`));
    return [
      { files: [`${UI}/elements/${a}/**/*.ts`], ignores: gaps.map(([f]) => f), patterns: others.map((b) => intoFolder(b)) },
      ...gaps.map(([f, allowed]) => ({ files: [f], patterns: others.map((b) => intoFolder(b, allowed.filter((x) => x.startsWith(`${b}/`)))) })),
    ];
  }),
  // The generic package (from P8): no contraagent code, no localization.
  ...(existsSync(new URL('./packages/elements', import.meta.url))
    ? [{ files: ['packages/elements/src/**/*.ts'], patterns: [{ group: ['@contraagent/*', '@lit/localize', '@lit/localize/*'], message: '@contraagent/elements is generic.' }] }]
    : []),
  // A page imports a package only through its `exports`.
  {
    files: ['apps/*/src/**/*.ts'],
    patterns: [
      { regex: '^\\.{1,2}/(\\.\\./)*packages/', message: 'Import the package by its name.' },
      { regex: '^@contraagent/[^/]+/(src|dist)/', message: 'Import a package through its exports.' },
    ],
  },
];

export default tseslint.config(
  { ignores: ['**/dist/**', '**/node_modules/**', '**/.astro/**', 'packages/ui/src/locales/**', 'packages/api/src/schema.ts', 'packages/ui/custom-elements.json'] },
  ...tseslint.configs.recommendedTypeChecked,
  lit.configs['flat/recommended'],
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  { files: ['**/*.js', '**/*.mjs'], ...tseslint.configs.disableTypeChecked },
  ...LAYERS.map(({ files, ignores, patterns }) => ({
    files,
    ...(ignores?.length ? { ignores } : {}),
    rules: { 'no-restricted-imports': ['error', { patterns }] },
  })),
);
