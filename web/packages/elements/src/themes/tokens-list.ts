// The design tokens: every custom property the elements read. The built-in
// themes (data.ts) set a value for each token without `derive`; the elements'
// stylesheet (styles/tokens.ts) is built from this list. What each one means is
// in token-meanings.ts, which the elements do not import.

/**
 * A token: the short name the elements' styles use (`--<name>`) and the `--ca-*`
 * property that sets it (`TOKEN_MEANINGS` has its meaning).
 * A token with `derive` has that value, the same in every theme, unless its
 * property is set: a value computed from the others, or a fixed size. The
 * themes do not list it.
 */
export interface TokenInfo {
  name: string;
  prop: string;
  derive?: string;
}

export const TOKENS: readonly TokenInfo[] = [
  { name: 'backdrop', prop: '--ca-backdrop' },
  { name: 'bg', prop: '--ca-bg' },
  { name: 'card', prop: '--ca-card' },
  { name: 'panel', prop: '--ca-panel' },
  { name: 'panel2', prop: '--ca-panel2' },
  { name: 'raise', prop: '--ca-raise' },
  { name: 'well', prop: '--ca-well' },
  { name: 'track', prop: '--ca-track' },
  { name: 'line', prop: '--ca-line' },
  { name: 'line2', prop: '--ca-line2' },
  { name: 'shadow', prop: '--ca-shadow' },
  { name: 'text', prop: '--ca-text' },
  { name: 'text-2', prop: '--ca-text-secondary' },
  { name: 'text-muted', prop: '--ca-text-muted' },
  { name: 'accent', prop: '--ca-accent' },
  { name: 'accent-bg', prop: '--ca-accent-bg', derive: 'color-mix(in srgb, var(--accent) calc(var(--tint) + 1%), transparent)' },
  { name: 'focus', prop: '--ca-focus' },
  { name: 'focus-width', prop: '--ca-focus-width' },
  { name: 'selection', prop: '--ca-selection' },
  { name: 'status-failed', prop: '--ca-status-failed' },
  { name: 'status-failed-bg', prop: '--ca-status-failed-bg', derive: 'color-mix(in srgb, var(--status-failed) var(--tint), transparent)' },
  { name: 'status-attention', prop: '--ca-status-attention' },
  { name: 'status-attention-bg', prop: '--ca-status-attention-bg', derive: 'color-mix(in srgb, var(--status-attention) var(--tint), transparent)' },
  { name: 'status-done', prop: '--ca-status-done' },
  { name: 'status-done-bg', prop: '--ca-status-done-bg', derive: 'color-mix(in srgb, var(--status-done) var(--tint), transparent)' },
  { name: 'status-running', prop: '--ca-status-running' },
  { name: 'status-running-bg', prop: '--ca-status-running-bg', derive: 'color-mix(in srgb, var(--status-running) var(--tint), transparent)' },
  { name: 'status-muted', prop: '--ca-status-muted' },
  { name: 'status-muted-bg', prop: '--ca-status-muted-bg', derive: 'color-mix(in srgb, var(--status-muted) calc(var(--tint) - 1%), transparent)' },
  { name: 'tint', prop: '--ca-tint' },
  { name: 'agent', prop: '--ca-agent' },
  { name: 'agent-bg', prop: '--ca-agent-bg', derive: 'color-mix(in srgb, var(--agent) calc(var(--tint) + 2%), transparent)' },
  { name: 'meter', prop: '--ca-meter' },
  { name: 'tok-input', prop: '--ca-tok-input' },
  { name: 'tok-cache-read', prop: '--ca-tok-cache-read' },
  { name: 'tok-cache-write', prop: '--ca-tok-cache-write' },
  { name: 'tok-output', prop: '--ca-tok-output' },
  { name: 'code-keyword', prop: '--ca-code-keyword' },
  { name: 'code-string', prop: '--ca-code-string' },
  { name: 'code-number', prop: '--ca-code-number' },
  { name: 'code-constant', prop: '--ca-code-constant' },
  { name: 'code-comment', prop: '--ca-code-comment' },
  { name: 'code-function', prop: '--ca-code-function' },
  { name: 'code-type', prop: '--ca-code-type' },
  { name: 'code-name', prop: '--ca-code-name' },
  // The type and radius scale: the same in every theme, so each has a default and no theme sets it.
  { name: 'font-size-xs', prop: '--ca-font-size-xs', derive: '10px' },
  { name: 'font-size-sm', prop: '--ca-font-size-sm', derive: '11px' },
  { name: 'font-size-md', prop: '--ca-font-size-md', derive: '12px' },
  { name: 'font-size-lg', prop: '--ca-font-size-lg', derive: '13px' },
  { name: 'font-size-xl', prop: '--ca-font-size-xl', derive: '15px' },
  { name: 'font-size-2xl', prop: '--ca-font-size-2xl', derive: '28px' },
  { name: 'radius-sm', prop: '--ca-radius-sm', derive: '4px' },
  { name: 'radius-md', prop: '--ca-radius-md', derive: '8px' },
  { name: 'radius-lg', prop: '--ca-radius-lg', derive: '12px' },
  { name: 'radius-pill', prop: '--ca-radius-pill', derive: '999px' },
];
