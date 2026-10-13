// Every message of the sources is in every target locale, translated, and in
// its generated module (src/locales/<locale>.ts). The built bundles look a
// message up by a prefix of its id (scripts/compact-locale.mjs), which holds
// only while the locale has every message. Fix a failure with `pnpm i18n`
// (it extracts the messages into xliff/ and writes src/locales/) and a
// <target> in xliff/<locale>.xlf.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pkg = fileURLToPath(new URL('..', import.meta.url));
const config = JSON.parse(readFileSync(join(pkg, 'lit-localize.json'), 'utf8'));
const units = (xlf) => [...xlf.matchAll(/<trans-unit id="([^"]+)">([\s\S]*?)<\/trans-unit>/g)];

// The messages the sources have now: extracted into a scratch directory, so xliff/ stays as it is.
const scratch = mkdtempSync(join(tmpdir(), 'i18n-check-'));
const scratchConfig = join(pkg, `.lit-localize.check-${process.pid}.json`);
let current;
try {
  writeFileSync(scratchConfig, JSON.stringify({ ...config, interchange: { ...config.interchange, xliffDir: scratch } }));
  execFileSync(join(pkg, 'node_modules/.bin/lit-localize'), ['extract', '--config', scratchConfig], { cwd: pkg, stdio: 'pipe' });
  current = new Set(units(readFileSync(join(scratch, `${config.targetLocales[0]}.xlf`), 'utf8')).map((u) => u[1]));
} finally {
  rmSync(scratchConfig, { force: true });
  rmSync(scratch, { recursive: true, force: true });
}

let problems = 0;
const fail = (line) => {
  console.error(line);
  problems++;
};
for (const locale of config.targetLocales) {
  const found = units(readFileSync(join(pkg, `xliff/${locale}.xlf`), 'utf8'));
  for (const [, id, body] of found) {
    if (/<target>[\s\S]*?\S[\s\S]*?<\/target>/.test(body)) continue;
    const source = (body.match(/<source>([\s\S]*?)<\/source>/) ?? [])[1] ?? '';
    fail(`${locale}: no translation for ${id}: ${source.slice(0, 80)}`);
  }
  const ids = new Set(found.map((u) => u[1]));
  for (const id of current) if (!ids.has(id)) fail(`${locale}: message ${id} of the sources is not in xliff/${locale}.xlf`);
  const module = readFileSync(join(pkg, `src/locales/${locale}.ts`), 'utf8');
  const generated = new Set([...module.matchAll(/^\s*'([^'\\]+)': /gm)].map((m) => m[1]));
  for (const id of current) if (!generated.has(id)) fail(`${locale}: message ${id} of the sources is not in src/locales/${locale}.ts`);
}
if (problems) {
  console.error(`${problems} problem(s): add a <target> in xliff/<locale>.xlf where one is missing, then \`pnpm i18n\``);
  process.exit(1);
}
