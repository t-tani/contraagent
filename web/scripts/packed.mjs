// What each package's tarball holds (run by `pnpm check:dist`): `npm pack
// --dry-run` lists the files its `files` field takes. No image goes to npm: the
// screenshots in a package's docs/images/ are for readers of the repository
// (`"!docs/images"`), and the documentation site shows each element live.
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const IMAGE = /\.(png|webp|jpe?g|gif|svg|avif|ico)$/i;

let failed = false;
for (const dir of ['api', 'elements', 'ui']) {
  const cwd = join(web, 'packages', dir);
  const r = spawnSync('npm', ['pack', '--dry-run', '--json', '--ignore-scripts'], { cwd, encoding: 'utf8', shell: process.platform === 'win32' });
  if (r.status !== 0) throw new Error(`npm pack --dry-run (in ${cwd}) failed\n${r.stdout}${r.stderr}`);
  const [pack] = JSON.parse(r.stdout);
  const images = pack.files.map((f) => f.path).filter((p) => IMAGE.test(p));
  const kB = (n) => `${Math.round(n / 1000)} kB`;
  if (images.length) {
    console.log(`✕ ${pack.name}: ${images.length} images in the tarball: ${images.slice(0, 5).join(', ')}${images.length > 5 ? ', ...' : ''}`);
    failed = true;
  } else {
    console.log(`✓ ${pack.name}: ${pack.files.length} files, ${kB(pack.size)} packed, no images`);
  }
}
if (failed) process.exit(1);
