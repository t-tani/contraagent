import { runInNewContext } from 'node:vm';
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_THEME,
  THEMES,
  THEME_CHOICES,
  THEME_NAMES,
  THEME_STORE_KEY,
  TOKENS,
  TOKEN_MEANINGS,
  preferredTheme,
  rememberTheme,
  resolveTheme,
  themeBootScript,
  themeRules,
  type ThemeName,
} from './index.js';

/** A storage that holds what it is given; `blocked` throws, as a browser with storage turned off does. */
const store = (init: Record<string, string> = {}, blocked = false) => {
  const m = new Map(Object.entries(init));
  return {
    getItem: (k: string) => {
      if (blocked) throw new Error('blocked');
      return m.get(k) ?? null;
    },
    setItem: (k: string, v: string) => {
      if (blocked) throw new Error('blocked');
      m.set(k, v);
    },
  };
};

describe('theme resolution', () => {
  it('system follows the colour scheme: contraagent Dark or contraagent Light', () => {
    expect(resolveTheme('system', false)).toBe('contraagent-dark');
    expect(resolveTheme('system', true)).toBe('contraagent-light');
  });

  it('a theme is itself, whatever the colour scheme', () => {
    for (const n of THEME_NAMES) {
      expect(resolveTheme(n, true)).toBe(n);
      expect(resolveTheme(n, false)).toBe(n);
    }
  });

  it('anything else is the default, contraagent Dark', () => {
    expect(DEFAULT_THEME).toBe('contraagent-dark');
    for (const x of ['', 'dark', 'solarized', null, undefined, 3]) expect(resolveTheme(x, true)).toBe('contraagent-dark');
  });

  it('reads the stored choice; an unset, invalid or blocked one is the default', () => {
    expect(preferredTheme(store({ [THEME_STORE_KEY]: 'nord' }))).toBe('nord');
    expect(preferredTheme(store({ [THEME_STORE_KEY]: 'system' }))).toBe('system');
    expect(preferredTheme(store())).toBe('contraagent-dark');
    expect(preferredTheme(store({ [THEME_STORE_KEY]: 'neon' }))).toBe('contraagent-dark');
    expect(preferredTheme(store({}, true))).toBe('contraagent-dark');
    expect(preferredTheme(undefined)).toBe('contraagent-dark');
  });

  it('remembers a choice, and a blocked storage is not an error', () => {
    const s = store();
    rememberTheme('one-dark', s);
    expect(preferredTheme(s)).toBe('one-dark');
    expect(() => rememberTheme('nord', store({}, true))).not.toThrow();
  });

  it('the boot script makes the same choice before the first paint', () => {
    const run = (saved: string | null, light: boolean) => {
      const attrs: Record<string, string> = {};
      const matchMedia = () => ({ matches: light });
      runInNewContext(themeBootScript, {
        localStorage: { getItem: () => saved },
        matchMedia,
        window: { matchMedia },
        document: { documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v) } },
      });
      return attrs['data-ca-theme'];
    };
    expect(run(null, true)).toBe('contraagent-dark');
    expect(run('neon', false)).toBe('contraagent-dark');
    expect(run('system', true)).toBe('contraagent-light');
    expect(run('system', false)).toBe('contraagent-dark');
    expect(run('high-contrast', true)).toBe('high-contrast');
  });

  it('lists every theme once in the control, the default first', () => {
    expect(THEME_CHOICES[0]).toBe(DEFAULT_THEME);
    expect(new Set(THEME_CHOICES).size).toBe(THEME_CHOICES.length);
    expect([...THEME_CHOICES].filter((c) => c !== 'system').sort()).toEqual([...THEME_NAMES].sort());
  });
});

// WCAG 2 relative luminance and contrast.
const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];
const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = ([r, g, b]: number[]) => 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
const contrast = (a: number[], b: number[]) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
};
/** `color-mix(in srgb, fg share, transparent)` laid over `bg`. */
const tint = (fg: number[], share: number, bg: number[]) => fg.map((c, i) => c * share + bg[i]! * (1 - share));

describe('theme contrast', () => {
  for (const name of THEME_NAMES) {
    const t = THEMES[name].tokens as Record<string, string>;
    const need = name === 'high-contrast' ? 7 : 4.5;
    const c = (k: string) => rgb(t[k]!);
    const share = parseFloat(t['tint']!) / 100;
    const surfaces = ['bg', 'card', 'panel', 'panel2', 'raise', 'well'].map(c);
    const bases = ['bg', 'card', 'panel', 'panel2'].map(c);
    const statuses = ['status-failed', 'status-attention', 'status-done', 'status-running'];
    const tints = [
      ...[...statuses, 'status-muted'].flatMap((k) => bases.map((b) => tint(c(k), k === 'status-muted' ? share - 0.01 : share, b))),
      ...bases.map((b) => tint(c('accent'), share + 0.01, b)),
      ...bases.map((b) => tint(c('agent'), share + 0.02, b)),
    ];
    const worst = (fg: string, on: number[][]) => Math.min(...on.map((b) => contrast(c(fg), b)));

    it(`${name}: text reads at ${need}:1 on every surface and tint`, () => {
      for (const k of ['text', 'text-2', 'text-muted']) expect(worst(k, [...surfaces, ...tints]), k).toBeGreaterThanOrEqual(need);
    });

    it(`${name}: a status reads on the surfaces and on its own tint`, () => {
      // In high contrast, a status reads at 7:1 where its marks and pills sit, and at 4.5:1 on a raised (hovered) surface.
      for (const k of statuses) {
        expect(worst(k, ['bg', 'card', 'panel', 'well'].map(c)), k).toBeGreaterThanOrEqual(need);
        expect(worst(k, bases.map((b) => tint(c(k), share, b))), `${k} on its tint`).toBeGreaterThanOrEqual(need);
        expect(worst(k, [c('raise')]), `${k} on raise`).toBeGreaterThanOrEqual(4.5);
      }
      expect(worst('accent', surfaces)).toBeGreaterThanOrEqual(4.5);
    });

    it(`${name}: code reads at 4.5:1 where it is shown`, () => {
      for (const k of Object.keys(t).filter((k) => k.startsWith('code-'))) expect(worst(k, ['well', 'card', 'panel'].map(c)), k).toBeGreaterThanOrEqual(4.5);
    });
  }
});

describe('theme data', () => {
  it('gives every token a meaning, in the order of the tokens', () => {
    expect(Object.keys(TOKEN_MEANINGS)).toEqual(TOKENS.map((t) => t.name));
    for (const m of Object.values(TOKEN_MEANINGS)) expect(m.length).toBeGreaterThan(3);
  });

  it('every theme sets every token that is not derived', () => {
    const set = TOKENS.filter((t) => !t.derive).map((t) => t.name).sort();
    for (const n of THEME_NAMES) expect(Object.keys(THEMES[n].tokens).sort(), n).toEqual(set);
  });

  it('writes a rule per theme with its colour scheme', () => {
    const css = themeRules((n: ThemeName) => `[data-ca-theme="${n}"]`);
    for (const n of THEME_NAMES) expect(css).toContain(`[data-ca-theme="${n}"] { color-scheme: ${THEMES[n].scheme};`);
    expect(css).toContain('--ca-theme-bg: #060a11;');
  });
});
