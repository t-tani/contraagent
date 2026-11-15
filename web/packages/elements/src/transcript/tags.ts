// Labelled values as chips (who ran a session): facts, not statuses, so they
// are neutral; the label is muted and the value in the text colour. A value
// that says what it is where it stands (`bare`) shows without its label, which
// a screen reader still reads.
import { css, html, nothing, type TemplateResult } from 'lit';
import type { TranscriptTag } from './types.js';

/** `tags` as chips (`tagStyles`). */
export const tagChips = (tags: readonly TranscriptTag[]): TemplateResult =>
  html`${tags.map(
    (t) => html`<span class="tag ${t.look ?? ''}" part="tag" title=${t.tip ?? nothing}><span class=${t.bare ? 'sr' : 'tag-l'}>${t.label}</span>${t.value}</span>`,
  )}`;

export const tagStyles = css`
  .tag { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-size-xs); font-weight: 600; padding: 1px 7px;
    border-radius: var(--radius-sm); white-space: nowrap; color: var(--text); background: var(--raise); }
  .tag-l { font-size: var(--font-size-xs); font-weight: 400; color: var(--text-muted); font-family: var(--sans); }
  .tag.mono, .tag.quiet { font-family: var(--mono); }
  .tag.quiet { color: var(--text-2); font-weight: 500; background: none; box-shadow: inset 0 0 0 1px var(--line); }
`;
