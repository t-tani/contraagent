// Bundle size budgets (run by `pnpm check:dist`, after `pnpm build`).
//
// Each `exports` entry of a workspace package is built the way an npm consumer's
// bundler sees it: Vite lib mode, minified, with `lit`, `@lit/*` and the
// workspace packages external. Its gzip size must stay within its budget in
// `size-budgets.json`. Prebuilt files (a package's `./bundle`, the monitor's
// `static/app.js`) are measured as they are. An entry without a budget, and a
// budget without an entry, fail too: a phase that adds or removes an entry sets
// or removes its budget.
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { gzipSync } from 'node:zlib';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(web, '..');
const config = JSON.parse(readFileSync(join(web, 'size-budgets.json'), 'utf8'));
/** @type {Record<string, number>} kB (1000 bytes), gzip */
const budgets = config.budgets;

/** Vite, from the ui package that builds with it. */
const vitePath = createRequire(join(web, 'packages/ui/package.json')).resolve('vite');
const { build } = await import(pathToFileURL(vitePath).href);

const external = (/** @type {string} */ id) => id === 'lit' || id.startsWith('lit/') || id.startsWith('@lit/') || id.startsWith('@contraagent/');

/** gzip bytes of the minified bundle of `entry`, built from `root`. */
async function bundled(root, entry) {
  const out = await build({
    configFile: false,
    root,
    logLevel: 'silent',
    resolve: { conditions: ['source'] },
    build: {
      write: false,
      minify: true,
      target: 'es2022',
      lib: { entry, formats: ['es'], fileName: () => 'entry.js' },
      rolldownOptions: { external, output: { codeSplitting: false } },
    },
  });
  const outputs = (Array.isArray(out) ? out : [out]).flatMap((r) => r.output);
  return outputs.filter((o) => o.type === 'chunk').reduce((n, o) => n + gzipSync(Buffer.from(o.code)).length, 0);
}

/** @type {{ name: string, measure: () => Promise<number> }[]} */
const entries = [];
for (const dir of readdirSync(join(web, 'packages'))) {
  const root = join(web, 'packages', dir);
  const pkgFile = join(root, 'package.json');
  if (!existsSync(pkgFile)) continue;
  const pkg = JSON.parse(readFileSync(pkgFile, 'utf8'));
  for (const [sub, target] of Object.entries(pkg.exports ?? {})) {
    const name = sub === '.' ? pkg.name : `${pkg.name}/${sub.slice(2)}`;
    if (typeof target === 'object' && target.source) {
      entries.push({ name, measure: () => bundled(root, join(root, target.source)) });
    } else if (typeof target === 'string' && target.endsWith('.js')) {
      const file = join(root, target);
      entries.push({ name, measure: async () => gzipSync(readFileSync(file)).length });
    }
  }
}
for (const file of config.files ?? []) {
  entries.push({ name: file, measure: async () => gzipSync(readFileSync(join(repo, file))).length });
}

const kB = (/** @type {number} */ n) => `${(n / 1000).toFixed(1)} kB (${n} B)`;
let failed = false;
for (const { name, measure } of entries) {
  const size = await measure();
  const budget = budgets[name];
  if (budget === undefined) {
    console.log(`✕ ${name}: ${kB(size)} gzip, no budget in size-budgets.json`);
    failed = true;
  } else if (size > budget * 1000) {
    console.log(`✕ ${name}: ${kB(size)} gzip, budget ${budget} kB`);
    failed = true;
  } else {
    console.log(`✓ ${name}: ${kB(size)} gzip, budget ${budget} kB`);
  }
}
const names = new Set(entries.map((e) => e.name));
for (const name of Object.keys(budgets).filter((n) => !names.has(n))) {
  console.log(`✕ ${name}: a budget for an entry that does not exist`);
  failed = true;
}
if (failed) process.exit(1);
