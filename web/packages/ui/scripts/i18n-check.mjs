// Every message has a translation in every target locale. Run after
// `pnpm i18n`, which extracts the messages from the sources into xliff/.
import { readFileSync } from 'node:fs';

const config = JSON.parse(readFileSync(new URL('../lit-localize.json', import.meta.url), 'utf8'));
let missing = 0;
for (const locale of config.targetLocales) {
  const xlf = readFileSync(new URL(`../xliff/${locale}.xlf`, import.meta.url), 'utf8');
  for (const [, id, body] of xlf.matchAll(/<trans-unit id="([^"]+)">([\s\S]*?)<\/trans-unit>/g)) {
    if (/<target>[\s\S]*?\S[\s\S]*?<\/target>/.test(body)) continue;
    const source = (body.match(/<source>([\s\S]*?)<\/source>/) ?? [])[1] ?? '';
    console.error(`${locale}: no translation for ${id}: ${source.slice(0, 80)}`);
    missing++;
  }
}
if (missing) {
  console.error(`${missing} message(s) untranslated: add a <target> in xliff/<locale>.xlf, then \`pnpm i18n\``);
  process.exit(1);
}
