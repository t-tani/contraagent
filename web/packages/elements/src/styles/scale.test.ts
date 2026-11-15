// The type and radius scale: every step is a token with a default, so an
// element reads it whether or not a page or a theme sets it.
import { describe, expect, it } from 'vitest';
import { TOKENS } from '../themes/tokens-list.js';
import { tokenStyles } from './tokens.js';

const SCALE = /^--ca-(font-size|radius)-/;
const steps = TOKENS.filter((t) => SCALE.test(t.prop));

describe('type and radius scale', () => {
  it('has every step', () => {
    expect(steps.map((t) => t.prop)).toEqual([
      '--ca-font-size-xs',
      '--ca-font-size-sm',
      '--ca-font-size-md',
      '--ca-font-size-lg',
      '--ca-font-size-xl',
      '--ca-font-size-2xl',
      '--ca-radius-sm',
      '--ca-radius-md',
      '--ca-radius-lg',
      '--ca-radius-pill',
    ]);
  });

  it('gives every step a default: a size in rem (it follows the font size a reader set), a corner in pixels', () => {
    for (const t of steps) {
      expect(t.derive, t.prop).toMatch(t.prop.includes('-font-size-') ? /^\d+(\.\d+)?rem$/ : /^\d+px$/);
      expect(tokenStyles.cssText, t.prop).toContain(`--${t.name}: var(${t.prop}, ${t.derive});`);
    }
  });

  it('grows step by step, from 12px of text at the default font size', () => {
    for (const kind of ['font-size', 'radius']) {
      const sizes = steps.filter((t) => t.prop.includes(`-${kind}-`)).map((t) => parseFloat(t.derive!));
      expect(sizes, kind).toEqual([...sizes].sort((a, b) => a - b));
    }
    expect(parseFloat(steps[0]!.derive!) * 16).toBe(12);
  });
});
