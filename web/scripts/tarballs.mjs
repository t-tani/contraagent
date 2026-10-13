// `pnpm tarballs`: packs @contraagent/api, @contraagent/elements and
// @contraagent/ui, built, into web/tarballs/, as tarballs that npm and pnpm
// install from this checkout:
//
//   npm install <checkout>/web/tarballs/contraagent-ui-0.1.0.tgz
//
// `pnpm pack` writes each one; its package.json then changes in two ways:
//   - a dependency on another of the three (`workspace:*`) becomes
//     `file:<absolute path of its tarball>`, so the installer finds it here and
//     not in the npm registry;
//   - the `source` export condition and the `./src/` entries of `sideEffects`
//     are dropped. They serve the workspace only (`customConditions` in
//     tsconfig.base.json, `resolve.conditions` in vitest.config.ts and the Vite
//     and Astro configs): there an import of `@contraagent/*` reads the
//     TypeScript sources, with no build first.
// `src` stays in the tarball: the source maps and declaration maps in `dist`
// point into it.
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(web, 'tarballs');
const packages = ['api', 'elements', 'ui'];

const run = (cmd, args, cwd) => {
  const r = spawnSync(cmd, args, { cwd, encoding: 'utf8', shell: process.platform === 'win32' });
  if (r.status !== 0) throw new Error(`${cmd} ${args.join(' ')} (in ${cwd}) failed\n${r.stdout}${r.stderr}`);
  return r.stdout;
};

/** The export map without its `source` conditions. */
const withoutSource = (exports) =>
  Object.fromEntries(
    Object.entries(exports).map(([key, value]) => {
      if (typeof value !== 'object' || value === null) return [key, value];
      return [key, Object.fromEntries(Object.entries(value).filter(([condition]) => condition !== 'source'))];
    }),
  );

const manifests = Object.fromEntries(
  packages.map((dir) => [dir, JSON.parse(readFileSync(join(web, 'packages', dir, 'package.json'), 'utf8'))]),
);
const tarball = (name, version) => join(out, `${name.replace(/^@/, '').replace('/', '-')}-${version}.tgz`);
const local = new Map(Object.values(manifests).map((m) => [m.name, tarball(m.name, m.version)]));

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
const stage = mkdtempSync(join(tmpdir(), 'contraagent-tarballs-'));
try {
  for (const dir of packages) {
    const packed = join(stage, dir);
    mkdirSync(packed);
    run('pnpm', ['pack', '--pack-destination', packed], join(web, 'packages', dir));
    const [file] = readdirSync(packed).filter((f) => f.endsWith('.tgz'));
    run('tar', ['-xzf', file], packed);
    const root = join(packed, 'package');
    const manifestPath = join(root, 'package.json');
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    for (const field of ['dependencies', 'peerDependencies', 'optionalDependencies']) {
      for (const name of Object.keys(manifest[field] ?? {})) {
        if (local.has(name)) manifest[field][name] = `file:${local.get(name)}`;
      }
    }
    if (manifest.exports) manifest.exports = withoutSource(manifest.exports);
    if (Array.isArray(manifest.sideEffects)) manifest.sideEffects = manifest.sideEffects.filter((p) => !p.startsWith('./src/'));
    writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    run('npm', ['pack', '--pack-destination', out, '--silent'], root);
    console.log(tarball(manifest.name, manifest.version));
  }
} finally {
  rmSync(stage, { recursive: true, force: true });
}
