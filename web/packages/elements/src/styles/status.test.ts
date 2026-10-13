// One rule set draws every status: an element names its tone (`data-tone`) and
// its mark (`data-mark`), never a class per status.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { TONES } from '../core/tone.js';
import { base } from './index.js';

// Vitest runs from web/.
const SRC = join(process.cwd(), 'packages/elements/src');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return name.endsWith('.ts') && !name.endsWith('.test.ts') ? [p] : [];
  });
}

/** A status drawn by a class: `.o-done`, `.p-timeout`, `.j-error`, `.t-failed`, `.mk-pending` ... */
const CLASS_STATUS = /\.(?:o|p|j|t|mk)-[a-z_]+\b/;
/** The same in markup: `class="pill o-${…}"`. */
const MARKUP_STATUS = /class="[^"]*\b(?:o|p|j|t|mk)-(?:\$\{|[a-z_]+)/;

describe('status styles', () => {
  const text = base.map((s) => s.cssText).join('\n');

  it('have no class per status', () => {
    expect(text).not.toMatch(CLASS_STATUS);
  });

  it('have one rule per tone', () => {
    for (const tone of TONES) {
      const rules = text.match(new RegExp(`(^|\\n)\\s*\\[data-tone='${tone}'\\] \\{`, 'g')) ?? [];
      expect(rules, tone).toHaveLength(1);
    }
    expect(text).not.toContain("[data-tone='neutral']");
  });

  it('are not drawn by a class in any element', () => {
    for (const file of sources(SRC)) {
      const src = readFileSync(file, 'utf8');
      expect(src, file).not.toMatch(CLASS_STATUS);
      expect(src, file).not.toMatch(MARKUP_STATUS);
    }
  });
});
