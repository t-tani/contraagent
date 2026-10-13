// Labelled values as chips (who ran a session): facts, not statuses, so they
// are neutral; the label is muted and the value in the text colour.
import { css, html, nothing, type TemplateResult } from 'lit';
import type { TranscriptTag } from './types.js';

/** `tags` as chips (`tagStyles`). */
export const tagChips = (tags: readonly TranscriptTag[]): TemplateResult =>
  html`${tags.map(
    (t) => html`<span class="tag ${t.look ?? ''}" part="tag" title=${t.tip ?? nothing}><span class="tag-l">${t.label}</span>${t.value}</span>`,
  )}`;

export const tagStyles = css`
  .tag { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600; padding: 2px 9px;
    border-radius: 7px; border: 1px solid var(--line2); white-space: nowrap; color: var(--text); background: var(--raise); }
  .tag-l { font-size: 10px; font-weight: 400; color: var(--text-muted); font-family: var(--sans); }
  .tag.mono, .tag.quiet { font-family: var(--mono); }
  .tag.quiet { color: var(--text-2); font-weight: 500; background: none; }
`;
