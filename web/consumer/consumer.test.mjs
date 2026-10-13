// One generic component, imported alone, as an npm consumer would (run by
// `pnpm check:dist`, after `pnpm build`). The page in src/main.ts imports only
// `@contraagent/elements/graph/define`. This checks that it:
//   - type-checks against the built packages (dist/, tsconfig.dist.json);
//   - builds, within its gzip budget (`consumer` in size-budgets.json);
//   - holds no contraagent code: nothing of @contraagent/api (openapi-fetch,
//     the /api/runs routes), no Lit Localize, no `ca-*` tag;
//   - run in happy-dom, registers exactly <cae-layered-graph> and the `cae-*`
//     elements it renders, and draws the graph.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { gzipSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..');
const require = createRequire(join(here, 'package.json'));
const failures = [];
const check = (ok, what) => {
  console.log(`${ok ? '✓' : '✕'} consumer: ${what}`);
  if (!ok) failures.push(what);
};

// 1. Types, against dist/.
const tsc = spawnSync(process.execPath, [require.resolve('typescript/bin/tsc'), '-p', join(here, 'tsconfig.dist.json')], { encoding: 'utf8' });
check(tsc.status === 0, `type-checks against dist${tsc.status === 0 ? '' : `\n${tsc.stdout}${tsc.stderr}`}`);

// 2. The build, and its size.
const { build } = await import(pathToFileURL(require.resolve('vite')).href);
const out = await build({ root: here, configFile: join(here, 'vite.config.ts'), logLevel: 'silent', build: { write: false } });
const chunks = (Array.isArray(out) ? out : [out]).flatMap((r) => r.output).filter((o) => o.type === 'chunk');
check(chunks.length === 1, `builds one module (${chunks.map((c) => c.fileName).join(', ')})`);
const code = chunks.map((c) => c.code).join('\n');
const gzip = gzipSync(Buffer.from(code)).length;
const budget = JSON.parse(readFileSync(join(web, 'size-budgets.json'), 'utf8')).consumer;
check(gzip <= budget * 1000, `${(gzip / 1000).toFixed(1)} kB (${gzip} B) gzip, budget ${budget} kB`);

// 3. Nothing of contraagent's own code.
const caTags = [...new Set([...code.matchAll(/(?<![\w-])ca-[a-z][a-z-]*/g)].map((m) => m[0]))];
check(!code.includes('openapi-fetch') && !/\/api\/runs/.test(code), 'holds no @contraagent/api code');
check(!code.includes('lit-localize'), 'holds no Lit Localize');
check(caTags.length === 0, `names no ca-* tag${caTags.length ? `: ${caTags.join(', ')}` : ''}`);

// 4. Run in happy-dom: the tags it registers, and the drawn graph.
const { Window } = await import(pathToFileURL(require.resolve('happy-dom')).href);
const window = new Window({ url: 'http://localhost/' });
for (const key of Object.getOwnPropertyNames(window)) {
  if (!(key in globalThis)) globalThis[key] = window[key];
}
for (const key of ['window', 'document', 'customElements', 'HTMLElement', 'Element', 'Node', 'ShadowRoot', 'CSSStyleSheet', 'Event', 'CustomEvent', 'KeyboardEvent', 'MouseEvent', 'navigator', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'matchMedia', 'ResizeObserver', 'MutationObserver', 'localStorage']) {
  if (key in window) Object.defineProperty(globalThis, key, { value: key === 'window' ? window : window[key], configurable: true, writable: true });
}
const defined = [];
const define = customElements.define.bind(customElements);
customElements.define = (name, ctor, options) => {
  defined.push(name);
  define(name, ctor, options);
};
const dir = mkdtempSync(join(tmpdir(), 'contraagent-consumer-'));
try {
  writeFileSync(join(dir, 'main.js'), code);
  await import(pathToFileURL(join(dir, 'main.js')).href);
} finally {
  rmSync(dir, { recursive: true, force: true });
}
const expected = ['cae-layered-graph', 'cae-mark-matrix', 'cae-segmented'];
check(JSON.stringify([...defined].sort()) === JSON.stringify(expected), `registers ${defined.sort().join(', ')} (expected ${expected.join(', ')})`);
const graph = document.querySelector('cae-layered-graph');
await graph?.updateComplete;
check(!!graph?.shadowRoot?.querySelector('[data-id="test"], .node'), 'draws the graph');
await window.happyDOM.close();

if (failures.length) process.exit(1);
