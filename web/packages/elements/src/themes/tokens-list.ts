// The design tokens: every custom property the elements read, with its meaning.
// The built-in themes (data.ts) set a value for each token without `derive`;
// the elements' stylesheet (styles/tokens.ts) is built from this list.

/**
 * A token: the short name the elements' styles use (`--<name>`), the `--ca-*`
 * property that sets it, and its meaning (the site's theme reference shows it).
 * A token with `derive` has that value, the same in every theme, unless its
 * property is set: a value computed from the others, or a fixed size. The
 * themes do not list it.
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
  // The type and radius scale: the same in every theme, so each has a default and no theme sets it.
  { name: 'font-size-xs', prop: '--ca-font-size-xs', meaning: 'type: the smallest text, a key or a tag', derive: '10px' },
  { name: 'font-size-sm', prop: '--ca-font-size-sm', meaning: 'type: a chip, a pill, a caption', derive: '11px' },
  { name: 'font-size-md', prop: '--ca-font-size-md', meaning: 'type: a section heading, a row of facts', derive: '12px' },
  { name: 'font-size-lg', prop: '--ca-font-size-lg', meaning: "type: the monitor's text", derive: '13px' },
  { name: 'font-size-xl', prop: '--ca-font-size-xl', meaning: 'type: a title', derive: '15px' },
  { name: 'font-size-2xl', prop: '--ca-font-size-2xl', meaning: "type: a tile's number", derive: '28px' },
  { name: 'radius-sm', prop: '--ca-radius-sm', meaning: 'corners: a key, a code span', derive: '4px' },
  { name: 'radius-md', prop: '--ca-radius-md', meaning: 'corners: a row, a code block', derive: '8px' },
  { name: 'radius-lg', prop: '--ca-radius-lg', meaning: 'corners: a panel', derive: '12px' },
  { name: 'radius-pill', prop: '--ca-radius-pill', meaning: 'corners: a pill or a chip', derive: '999px' },
];
