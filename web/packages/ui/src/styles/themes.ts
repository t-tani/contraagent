// The built-in themes: one value for every colour token, per theme. Plain data
// and plain functions (no Lit, no DOM at import), so a page, a build script and
// the documentation site can read them too (`@contraagent/ui/themes`).
//
// Two layers of custom properties reach an element:
//   1. `data-ca-theme="<name>"` on any ancestor sets `--ca-theme-*` (the rules below);
//   2. a `--ca-*` property set on any ancestor overrides its token, whatever the theme.
// With neither, an element shows the contraagent theme (the fallbacks in `tokens`).

/**
 * The built-in themes, in the order of the monitor's theme control. Each is a
 * full set of tokens. Sources (all MIT-licensed):
 * - `contraagent-dark`, `contraagent-light`: this package's own palette, MIT.
 * - `github-dark`, `github-light`, `high-contrast`: GitHub Primer primitives
 *   (dark, light and dark high contrast), https://github.com/primer/primitives, MIT, (c) GitHub Inc.
 * - `one-dark`: Atom One Dark, https://github.com/atom/atom/tree/master/packages/one-dark-syntax, MIT, (c) GitHub Inc.
 * - `nord`: Nord, https://www.nordtheme.com, MIT, (c) Arctic Ice Studio and Sven Greb.
 */
export const THEME_NAMES = ['contraagent-dark', 'contraagent-light', 'github-dark', 'github-light', 'one-dark', 'nord', 'high-contrast'] as const;
export type ThemeName = (typeof THEME_NAMES)[number];
/** A reader's choice: a theme, or `system` (contraagent Dark or contraagent Light, as the system's colour scheme). */
export type ThemeChoice = ThemeName | 'system';
/** The choices in the monitor's control, in order. */
export const THEME_CHOICES: readonly ThemeChoice[] = ['contraagent-dark', 'contraagent-light', 'system', 'github-dark', 'github-light', 'one-dark', 'nord', 'high-contrast'];
/** The themes after the first divider of the control: palettes of code editors. */
export const EDITOR_THEMES: readonly ThemeName[] = ['github-dark', 'github-light', 'one-dark', 'nord', 'high-contrast'];
/** The theme for a reader who has not chosen. */
export const DEFAULT_THEME: ThemeName = 'contraagent-dark';
/** What `system` shows, by the system's colour scheme. */
export const SYSTEM_THEMES = { dark: 'contraagent-dark', light: 'contraagent-light' } as const satisfies Record<string, ThemeName>;

/**
 * A token: the short name the elements' styles use (`--<name>`), the `--ca-*`
 * property that sets it, and its meaning (the site's theme reference shows it).
 * A token with `derive` is computed from the others unless its property is set;
 * the themes do not list it.
 */
export interface TokenInfo {
  name: string;
  prop: string;
  meaning: string;
  derive?: string;
}

export const TOKENS: readonly TokenInfo[] = [
  { name: 'backdrop', prop: '--ca-backdrop', meaning: "the monitor's page, behind the panels (a colour or a gradient)" },
  { name: 'bg', prop: '--ca-bg', meaning: 'the page' },
  { name: 'card', prop: '--ca-card', meaning: 'a card or a graph node' },
  { name: 'panel', prop: '--ca-panel', meaning: 'a panel (bottom of its gradient)' },
  { name: 'panel2', prop: '--ca-panel2', meaning: 'a panel (top of its gradient), a sticky header' },
  { name: 'raise', prop: '--ca-raise', meaning: 'a raised surface: a neutral chip, a hovered row' },
  { name: 'well', prop: '--ca-well', meaning: "a sunken surface: code, a graph's frame" },
  { name: 'track', prop: '--ca-track', meaning: 'the empty part of a bar' },
  { name: 'line', prop: '--ca-line', meaning: 'a border' },
  { name: 'line2', prop: '--ca-line2', meaning: "a stronger border, a graph's edge" },
  { name: 'shadow', prop: '--ca-shadow', meaning: 'the colour of a shadow under a panel, a menu or a notice' },
  { name: 'text', prop: '--ca-text', meaning: 'text, and every number that is not a problem count' },
  { name: 'text-2', prop: '--ca-text-secondary', meaning: 'secondary text' },
  { name: 'text-muted', prop: '--ca-text-muted', meaning: 'labels, captions, units' },
  { name: 'accent', prop: '--ca-accent', meaning: 'links, the selected tab or item' },
  { name: 'accent-bg', prop: '--ca-accent-bg', meaning: 'a selected row or item', derive: 'color-mix(in srgb, var(--accent) calc(var(--tint) + 1%), transparent)' },
  { name: 'focus', prop: '--ca-focus', meaning: 'the focus ring' },
  { name: 'focus-width', prop: '--ca-focus-width', meaning: 'the width of the focus ring' },
  { name: 'selection', prop: '--ca-selection', meaning: 'selected text' },
  { name: 'status-failed', prop: '--ca-status-failed', meaning: 'failed: a task, an attempt, a check (with ✕)' },
  { name: 'status-failed-bg', prop: '--ca-status-failed-bg', meaning: 'the tint behind a failed pill or chip', derive: 'color-mix(in srgb, var(--status-failed) var(--tint), transparent)' },
  { name: 'status-attention', prop: '--ca-status-attention', meaning: 'not failed, needs a look: not started (with ◌), a limit near' },
  { name: 'status-attention-bg', prop: '--ca-status-attention-bg', meaning: 'the tint behind an attention pill or chip', derive: 'color-mix(in srgb, var(--status-attention) var(--tint), transparent)' },
  { name: 'status-done', prop: '--ca-status-done', meaning: 'done or passed: marks (✓) and small chips only' },
  { name: 'status-done-bg', prop: '--ca-status-done-bg', meaning: 'the tint behind a done pill or chip', derive: 'color-mix(in srgb, var(--status-done) var(--tint), transparent)' },
  { name: 'status-running', prop: '--ca-status-running', meaning: 'running, live' },
  { name: 'status-running-bg', prop: '--ca-status-running-bg', meaning: 'the tint behind a running pill or chip', derive: 'color-mix(in srgb, var(--status-running) var(--tint), transparent)' },
  { name: 'status-muted', prop: '--ca-status-muted', meaning: 'skipped, waiting, not run' },
  { name: 'status-muted-bg', prop: '--ca-status-muted-bg', meaning: 'the tint behind a muted pill or chip', derive: 'color-mix(in srgb, var(--status-muted) calc(var(--tint) - 1%), transparent)' },
  { name: 'tint', prop: '--ca-tint', meaning: 'how strong a tint is: the share of its colour in a status, agent or selected background' },
  { name: 'agent', prop: '--ca-agent', meaning: "identity: an agent task's icon and edge" },
  { name: 'agent-bg', prop: '--ca-agent-bg', meaning: "the tint behind an agent task's icon", derive: 'color-mix(in srgb, var(--agent) calc(var(--tint) + 2%), transparent)' },
  { name: 'meter', prop: '--ca-meter', meaning: 'a bar that measures, not judges: time, usage, progress' },
  { name: 'tok-input', prop: '--ca-tok-input', meaning: 'tokens: input' },
  { name: 'tok-cache-read', prop: '--ca-tok-cache-read', meaning: 'tokens: cache read' },
  { name: 'tok-cache-write', prop: '--ca-tok-cache-write', meaning: 'tokens: cache write' },
  { name: 'tok-output', prop: '--ca-tok-output', meaning: 'tokens: output' },
  { name: 'code-keyword', prop: '--ca-code-keyword', meaning: 'code: keywords' },
  { name: 'code-string', prop: '--ca-code-string', meaning: 'code and JSON: strings' },
  { name: 'code-number', prop: '--ca-code-number', meaning: 'code and JSON: numbers' },
  { name: 'code-constant', prop: '--ca-code-constant', meaning: 'code: constants, template placeholders' },
  { name: 'code-comment', prop: '--ca-code-comment', meaning: 'code: comments' },
  { name: 'code-function', prop: '--ca-code-function', meaning: 'code: functions, decorators' },
  { name: 'code-type', prop: '--ca-code-type', meaning: 'code: classes and types' },
  { name: 'code-name', prop: '--ca-code-name', meaning: 'code: built-ins; JSON: keys' },
];

/** The name of every token a theme sets (every token without `derive`). */
export type ThemeToken =
  | 'backdrop' | 'bg' | 'card' | 'panel' | 'panel2' | 'raise' | 'well' | 'track' | 'line' | 'line2' | 'shadow'
  | 'text' | 'text-2' | 'text-muted' | 'accent' | 'focus' | 'focus-width' | 'selection'
  | 'status-failed' | 'status-attention' | 'status-done' | 'status-running' | 'status-muted' | 'tint'
  | 'agent' | 'meter' | 'tok-input' | 'tok-cache-read' | 'tok-cache-write' | 'tok-output'
  | 'code-keyword' | 'code-string' | 'code-number' | 'code-constant' | 'code-comment' | 'code-function' | 'code-type' | 'code-name';

export interface Theme {
  /** The name the theme control shows; a theme's own name, the same in every language. */
  label: string;
  /** Light or dark: the `color-scheme` (native controls, scrollbars) and what `system` picks by. */
  scheme: 'dark' | 'light';
  tokens: Record<ThemeToken, string>;
}

// Where a value differs from its source palette, the comment says so and why
// (the contrast rules: text 4.5:1 on every surface and tint, 7:1 in high contrast).
export const THEMES: Record<ThemeName, Theme> = {
  'contraagent-dark': {
    label: 'contraagent Dark',
    scheme: 'dark',
    tokens: {
      backdrop: 'radial-gradient(1100px 520px at 8% -12%, #10203a 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #1b1238 0%, transparent 58%), #060a11',
      bg: '#060a11',
      card: '#0f1724',
      panel: '#0f1724',
      panel2: '#142034',
      raise: '#1a2740',
      well: '#0a111c',
      track: '#1b273b',
      line: '#1d2940',
      line2: '#2b3c58',
      shadow: '#060a11',
      text: '#e7edf5',
      'text-2': '#bcc7d6',
      'text-muted': '#909db2',
      accent: '#7aa2ff',
      focus: '#7aa2ff',
      'focus-width': '2px',
      selection: '#7aa2ff4d',
      'status-failed': '#f87171',
      'status-attention': '#fbbf24',
      'status-done': '#34d399',
      'status-running': '#22d3ee',
      'status-muted': '#94a3b8',
      tint: '13%',
      agent: '#b597fb',
      meter: '#7d8ba3',
      'tok-input': '#7c86f5',
      'tok-cache-read': '#3f4d63',
      'tok-cache-write': '#8796ad',
      'tok-output': '#d6b8ff',
      'code-keyword': '#c4a5ff',
      'code-string': '#7ee2a8',
      'code-number': '#f5c26b',
      'code-constant': '#ff9e64',
      'code-comment': '#74839a',
      'code-function': '#7dd3fc',
      'code-type': '#ffd479',
      'code-name': '#79b8ff',
    },
  },
  // The same hues as contraagent Dark (accent, statuses, identity, code), with
  // the lightness and saturation set for a light page.
  'contraagent-light': {
    label: 'contraagent Light',
    scheme: 'light',
    tokens: {
      backdrop: 'radial-gradient(1100px 520px at 8% -12%, #dde7fb 0%, transparent 62%), radial-gradient(900px 480px at 108% 4%, #ebe3fa 0%, transparent 58%), #eef2f8',
      bg: '#eef2f8',
      card: '#ffffff',
      panel: '#ffffff',
      panel2: '#f7f9fc',
      raise: '#e6ecf5',
      well: '#f3f6fa',
      track: '#e1e7f0',
      line: '#d6dde8',
      line2: '#b6c2d3',
      shadow: '#0f172438',
      text: '#0f1724',
      'text-2': '#34415a',
      'text-muted': '#556279',
      accent: '#2f58d4',
      focus: '#2f58d4',
      'focus-width': '2px',
      selection: '#2f58d42e',
      'status-failed': '#b8132d',
      'status-attention': '#6c4801',
      'status-done': '#026b49',
      'status-running': '#01525f',
      'status-muted': '#56637a',
      tint: '11%',
      agent: '#6f45c0',
      meter: '#8a97ab',
      'tok-input': '#4d4cc8',
      'tok-cache-read': '#cdd6e3',
      'tok-cache-write': '#7d8aa0',
      'tok-output': '#a07ad9',
      'code-keyword': '#6f49a8',
      'code-string': '#076b40',
      'code-number': '#7b5605',
      'code-constant': '#964605',
      'code-comment': '#5d6b80',
      'code-function': '#086586',
      'code-type': '#785902',
      'code-name': '#095ea8',
    },
  },
  'github-dark': {
    label: 'GitHub Dark',
    scheme: 'dark',
    tokens: {
      backdrop: '#010409',
      bg: '#010409',
      card: '#0d1117',
      panel: '#0d1117',
      panel2: '#151b23',
      raise: '#212830',
      well: '#010409',
      track: '#262c36',
      line: '#262c36',
      line2: '#3d444d',
      shadow: '#010409',
      text: '#f0f6fc',
      'text-2': '#d1d7e0',
      'text-muted': '#9299a2',
      accent: '#4796fb',
      focus: '#1f6feb',
      'focus-width': '2px',
      selection: '#388bfd4d',
      'status-failed': '#fc554d',
      'status-attention': '#d29922',
      'status-done': '#3fb950',
      'status-running': '#39c5cf',
      'status-muted': '#9198a1',
      tint: '15%',
      agent: '#ab7df8',
      meter: '#656c76',
      'tok-input': '#58a6ff',
      'tok-cache-read': '#2f3742',
      'tok-cache-write': '#656c76',
      'tok-output': '#d2a8ff',
      'code-keyword': '#ff7b72',
      'code-string': '#a5d6ff',
      'code-number': '#79c0ff',
      'code-constant': '#79c0ff',
      'code-comment': '#9198a1',
      'code-function': '#d2a8ff',
      'code-type': '#ffa657',
      'code-name': '#7ee787',
    },
  },
  'github-light': {
    label: 'GitHub Light',
    scheme: 'light',
    tokens: {
      backdrop: '#f6f8fa',
      bg: '#f6f8fa',
      card: '#ffffff',
      panel: '#ffffff',
      panel2: '#ffffff',
      raise: '#eff2f5',
      well: '#f6f8fa',
      track: '#e6eaef',
      line: '#d1d9e0',
      line2: '#b7c0ca',
      shadow: '#1f232833',
      text: '#1f2328',
      'text-2': '#393f46',
      'text-muted': '#59636e',
      accent: '#0165d6',
      focus: '#0165d6',
      'focus-width': '2px',
      selection: '#0969da33',
      'status-failed': '#cd1e2b',
      'status-attention': '#916103',
      'status-done': '#147b33',
      'status-running': '#10767d',
      'status-muted': '#59636e',
      tint: '8%',
      agent: '#804ddc',
      meter: '#818b98',
      'tok-input': '#54aeff',
      'tok-cache-read': '#d1d9e0',
      'tok-cache-write': '#818b98',
      'tok-output': '#a475f9',
      'code-keyword': '#cf222e',
      'code-string': '#0a3069',
      'code-number': '#0550ae',
      'code-constant': '#0550ae',
      'code-comment': '#59636e',
      'code-function': '#6639ba',
      'code-type': '#953800',
      'code-name': '#116329',
    },
  },
  'one-dark': {
    label: 'One Dark',
    scheme: 'dark',
    tokens: {
      backdrop: '#21252b',
      bg: '#21252b',
      card: '#282c34',
      panel: '#282c34',
      panel2: '#2c313a',
      raise: '#2c313a',
      well: '#21252b',
      track: '#3a3f4b',
      line: '#181a1f',
      line2: '#4b5263',
      shadow: '#0e1013',
      text: '#d7dae0',
      'text-2': '#abb2bf',
      'text-muted': '#a7afbe',
      accent: '#64b2f2',
      focus: '#528bff',
      'focus-width': '2px',
      selection: '#3e4451',
      'status-failed': '#fc858d',
      'status-attention': '#e5c07b',
      'status-done': '#98c379',
      'status-running': '#57b7c3',
      'status-muted': '#a7afbe',
      tint: '12%',
      agent: '#d788ee',
      meter: '#5c6370',
      'tok-input': '#61afef',
      'tok-cache-read': '#3e4451',
      'tok-cache-write': '#5c6370',
      'tok-output': '#c678dd',
      'code-keyword': '#c678dd',
      'code-string': '#98c379',
      'code-number': '#d19a66',
      'code-constant': '#d19a66',
      'code-comment': '#8f949e',
      'code-function': '#61afef',
      'code-type': '#e5c07b',
      'code-name': '#e36e77',
    },
  },
  nord: {
    label: 'Nord',
    scheme: 'dark',
    tokens: {
      backdrop: '#2e3440',
      bg: '#242933',
      card: '#2e3440',
      panel: '#2e3440',
      panel2: '#323946',
      raise: '#3b4252',
      well: '#272c36',
      track: '#3b4252',
      line: '#3b4252',
      line2: '#4c566a',
      shadow: '#1d2129',
      text: '#eceff4',
      'text-2': '#d8dee9',
      'text-muted': '#adbcd9',
      accent: '#9dbedf',
      focus: '#88c0d0',
      'focus-width': '2px',
      selection: '#4c566a',
      'status-failed': '#fe9aa1',
      'status-attention': '#ebcb8b',
      'status-done': '#a5c18e',
      'status-running': '#89c1d1',
      'status-muted': '#adbcd9',
      tint: '13%',
      agent: '#d0a9c9',
      meter: '#7b88a1',
      'tok-input': '#5e81ac',
      'tok-cache-read': '#4c566a',
      'tok-cache-write': '#7b88a1',
      'tok-output': '#b48ead',
      'code-keyword': '#81a1c1',
      'code-string': '#a3be8c',
      'code-number': '#b790b0',
      'code-constant': '#d38972',
      'code-comment': '#8f9db8',
      'code-function': '#88c0d0',
      'code-type': '#8fbcbb',
      'code-name': '#8fbcbb',
    },
  },
  'high-contrast': {
    label: 'High contrast',
    scheme: 'dark',
    tokens: {
      backdrop: '#010409',
      bg: '#010409',
      card: '#0a0c10',
      panel: '#0a0c10',
      panel2: '#0a0c10',
      raise: '#1c2128',
      well: '#010409',
      track: '#272b33',
      line: '#7a828e',
      line2: '#9ea7b3',
      shadow: '#000000',
      text: '#ffffff',
      'text-2': '#f0f3f6',
      'text-muted': '#bdc4cc',
      accent: '#7abbfe',
      focus: '#7abbfe',
      'focus-width': '3px',
      selection: '#409eff66',
      'status-failed': '#ffacb8',
      'status-attention': '#fad209',
      'status-done': '#0ef38e',
      'status-running': '#62ceff',
      'status-muted': '#bdc4cc',
      tint: '12%',
      agent: '#c299fe',
      meter: '#9ea7b3',
      'tok-input': '#409eff',
      'tok-cache-read': '#525964',
      'tok-cache-write': '#9ea7b3',
      'tok-output': '#dbb7ff',
      'code-keyword': '#ff9492',
      'code-string': '#addcff',
      'code-number': '#91cbff',
      'code-constant': '#91cbff',
      'code-comment': '#bdc4cc',
      'code-function': '#dbb7ff',
      'code-type': '#ffb757',
      'code-name': '#72f088',
    },
  },
};

/** The property a theme sets for a token (the layer under `--ca-*`). */
export const themeProp = (token: string): string => `--ca-theme-${token}`;

/**
 * The rules that apply each theme, for a selector per theme name: for a page,
 * `n => `[data-ca-theme="${n}"]``; inside a shadow root, `n => `:host([data-ca-theme="${n}"])``.
 */
export function themeRules(selector: (name: ThemeName) => string): string {
  return THEME_NAMES.map((n) => {
    const t = THEMES[n];
    const decls = Object.entries(t.tokens).map(([k, v]) => `${themeProp(k)}: ${v};`);
    return `${selector(n)} { color-scheme: ${t.scheme}; ${themeProp('color-scheme')}: ${t.scheme}; ${decls.join(' ')} }`;
  }).join('\n');
}

export const isThemeName = (x: unknown): x is ThemeName => (THEME_NAMES as readonly unknown[]).includes(x);
export const isThemeChoice = (x: unknown): x is ThemeChoice => (THEME_CHOICES as readonly unknown[]).includes(x);

/** The theme a choice shows: `system` by the system's colour scheme; anything else not a theme, the default. */
export function resolveTheme(choice: unknown, prefersLight: boolean): ThemeName {
  if (choice === 'system') return prefersLight ? SYSTEM_THEMES.light : SYSTEM_THEMES.dark;
  return isThemeName(choice) ? choice : DEFAULT_THEME;
}

/** Where the reader's choice is kept (this browser only). */
export const THEME_STORE_KEY = 'contraagent:theme';

type Store = Pick<Storage, 'getItem' | 'setItem'>;
const storage = (): Store | undefined => {
  try {
    return globalThis.localStorage;
  } catch {
    return undefined;
  }
};

/** The reader's choice from an earlier visit, else the default theme. */
export function preferredTheme(store: Store | undefined = storage()): ThemeChoice {
  try {
    const saved = store?.getItem(THEME_STORE_KEY);
    if (isThemeChoice(saved)) return saved;
  } catch {
    /* storage blocked: the default */
  }
  return DEFAULT_THEME;
}

/** Remember the reader's choice for the next visit. */
export function rememberTheme(choice: ThemeChoice, store: Store | undefined = storage()): void {
  try {
    store?.setItem(THEME_STORE_KEY, choice);
  } catch {
    /* storage blocked: the choice lasts for this page */
  }
}

/** Whether the system asks for a light colour scheme. */
export const prefersLight = (): boolean => globalThis.matchMedia?.('(prefers-color-scheme: light)').matches ?? false;

/**
 * A script for a page's `<head>`: it sets `data-ca-theme` on `<html>` from the
 * reader's choice before the first paint, as `resolveTheme(preferredTheme(), prefersLight())`
 * does. With `themeRules` in a `<style>` beside it, the page opens in its theme.
 */
export const themeBootScript = `(function(){var c=null;try{c=localStorage.getItem(${JSON.stringify(THEME_STORE_KEY)})}catch(e){}
var names=${JSON.stringify(THEME_NAMES)},choices=${JSON.stringify(THEME_CHOICES)};
if(choices.indexOf(c)<0)c=${JSON.stringify(DEFAULT_THEME)};
if(c==="system")c=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?${JSON.stringify(SYSTEM_THEMES.light)}:${JSON.stringify(SYSTEM_THEMES.dark)};
if(names.indexOf(c)>=0)document.documentElement.setAttribute("data-ca-theme",c);})();`;
