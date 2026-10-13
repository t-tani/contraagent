// A status shown as a pill or as a word: the word, its tone (`data-tone`) and,
// where a mark belongs, its mark (`data-mark`: ✓ done, ✕ failed, ◌ pending).
// The look of each is in `styles/status.ts`; the mark is drawn by CSS and hidden
// from screen readers, which read the word.
import { html, nothing, type TemplateResult } from 'lit';
import { toneAttr, type Tone } from '../core/tone.js';

/** The shape before a status word. */
export type Mark = 'done' | 'failed' | 'pending';

/** The mark a tone takes by default: ✓ done, ✕ failed, ◌ attention; none for running, muted or neutral. */
export function markOf(tone: Tone): Mark | null {
  switch (tone) {
    case 'done':
      return 'done';
    case 'failed':
      return 'failed';
    case 'attention':
      return 'pending';
    default:
      return null;
  }
}

export interface PillSpec {
  /** The word (a template may add a count after it). */
  text: unknown;
  tone?: Tone;
  /** The mark: `markOf(tone)` when not given (or true); false or null for none. */
  mark?: Mark | boolean | null;
  title?: string | null;
  /** More classes on the element. */
  cls?: string;
}

/** The `data-mark` of a spec. */
const markAttr = (p: PillSpec): Mark | typeof nothing => {
  const m = p.mark === undefined || p.mark === true ? markOf(p.tone ?? 'neutral') : p.mark || null;
  return m ?? nothing;
};

/** A status as a pill (`.pill`, part `pill tone-<tone>`): tinted by its tone, a done pill quiet with its ✓. */
export function pill(p: PillSpec): TemplateResult {
  const tone = p.tone ?? 'neutral';
  return html`<span class="pill ${p.cls ?? ''}" part="pill tone-${tone}" data-tone=${toneAttr(tone)} data-mark=${markAttr(p)} title=${p.title || nothing}>${p.text}</span>`;
}

/** A status as a word in a row (`.jstop`, part `status tone-<tone>`): coloured for a problem, done quiet with its ✓. */
export function statusWord(p: PillSpec): TemplateResult {
  const tone = p.tone ?? 'neutral';
  return html`<span class="jstop ${p.cls ?? ''}" part="status tone-${tone}" data-tone=${toneAttr(tone)} data-mark=${markAttr(p)} title=${p.title || nothing}>${p.text}</span>`;
}

/** A status as a chip of the class `cls` (an element styles it): the tone and the mark, as on a pill. */
export function statusChip(cls: string, p: PillSpec): TemplateResult {
  const tone = p.tone ?? 'neutral';
  return html`<span class="${cls} ${p.cls ?? ''}" data-tone=${toneAttr(tone)} data-mark=${markAttr(p)} title=${p.title || nothing}>${p.text}</span>`;
}
