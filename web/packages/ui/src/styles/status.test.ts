// One rule set draws every status: an element names its tone (`data-tone`) and
// its mark (`data-mark`), never a class per stop, outcome or contract status.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { TONES } from '../lib/tone.js';
import { base } from './base.js';

// Vitest runs from web/.
const UI = join(process.cwd(), 'packages/ui/src');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === 'locales' ? [] : sources(p);
    return name.endsWith('.ts') && !name.endsWith('.test.ts') ? [p] : [];
  });
}

/** A status drawn by a class: `.o-done`, `.p-timeout`, `.j-error`, `.t-failed`, `.mk-pending`, `.ct-chip.valid` ... */
const CLASS_STATUS = /\.(?:o|p|j|t|mk)-[a-z_]+\b|\.ct-chip\.[a-z_]+/;
/** The same in markup: `class="pill o-${…}"`, `class="jstop j-error"`. */
const MARKUP_STATUS = /class="[^"]*\b(?:o|p|j|t|mk)-(?:\$\{|[a-z_]+)/;

describe('status styles', () => {
  const text = base.cssText;

  it('have no class per status', () => {
    expect(text).not.toMatch(CLASS_STATUS);
  });

  it('have one rule per tone', () => {
    for (const tone of TONES) {
      const rules = text.match(new RegExp(`(^|\\n)\\s*\\[data-tone='${tone}'\\] \\{`, 'g')) ?? [];
      expect(rules, tone).toHaveLength(1);
    }
  });

  it('are not drawn by a class in any element', () => {
    for (const file of sources(UI)) {
      const src = readFileSync(file, 'utf8');
      expect(src, file).not.toMatch(CLASS_STATUS);
      expect(src, file).not.toMatch(MARKUP_STATUS);
    }
  });
});
