// What each package's registry tarball holds (run by `pnpm check:dist`, after
// `pnpm build`): the tarballs that `pnpm tarballs:registry` writes and the
// release workflow publishes. With tarball paths as arguments it checks those;
// with none, it packs them into a temporary directory first. Each one:
//   - holds no image: the screenshots in a package's docs/images/ are for
//     readers of the repository (`"!docs/images"`), and the documentation site
//     shows each element live;
//   - depends on no `file:` or `workspace:` path, and on the other two packages
//     at exactly its own version (the three versions move together);
//   - has no `source` export condition, which serves the workspace only.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { pack } from './tarballs.mjs';

const IMAGE = /\.(png|webp|jpe?g|gif|svg|avif|ico)$/i;
const FIELDS = ['dependencies', 'peerDependencies', 'optionalDependencies'];

const tar = (args) => {
  const r = spawnSync('tar', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) throw new Error(`tar ${args.join(' ')} failed\n${r.stdout}${r.stderr}`);
  return r.stdout;
};

let stage;
let tarballs = process.argv.slice(2);
if (tarballs.length === 0) {
  stage = mkdtempSync(join(tmpdir(), 'contraagent-packed-'));
  tarballs = pack({ out: stage, registry: true });
}

let failed = false;
try {
  const manifests = tarballs.map((file) => JSON.parse(tar(['-xzOf', file, 'package/package.json'])));
  const names = new Set(manifests.map((m) => m.name));
  tarballs.forEach((file, i) => {
    const manifest = manifests[i];
    const problems = [];
    const files = tar(['-tzf', file]).split('\n').filter((p) => p && !p.endsWith('/'));
    const images = files.filter((p) => IMAGE.test(p));
    if (images.length) problems.push(`${images.length} images: ${images.slice(0, 5).join(', ')}${images.length > 5 ? ', ...' : ''}`);
    for (const field of FIELDS) {
      for (const [name, spec] of Object.entries(manifest[field] ?? {})) {
        if (/^(file|workspace|link):/.test(spec)) problems.push(`${field}.${name} is ${spec}`);
        else if (names.has(name) && spec !== manifest.version) problems.push(`${field}.${name} is ${spec}, not ${manifest.version}`);
      }
    }
    const conditions = Object.values(manifest.exports ?? {}).filter((v) => typeof v === 'object' && v !== null && 'source' in v);
    if (conditions.length) problems.push(`${conditions.length} exports keep the source condition`);
    const kB = `${Math.round(statSync(file).size / 1000)} kB`;
    if (problems.length) {
      console.log(`✕ ${manifest.name} (${basename(file)}): ${problems.join('; ')}`);
      failed = true;
    } else {
      console.log(`✓ ${manifest.name}: ${files.length} files, ${kB} packed, no images, registry dependencies`);
    }
  });
} finally {
  if (stage) rmSync(stage, { recursive: true, force: true });
}
if (failed) process.exit(1);
