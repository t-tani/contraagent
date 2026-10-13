// A status shown as a pill or as a word: the word, its tone (`data-tone`) and,
// where a mark belongs, its mark (`data-mark`: ✓ done, ✕ failed, ◌ pending).
// The look of each is in `styles/status.ts`; the mark is drawn by CSS and hidden
// from screen readers, which read the word.
import type { Outcome } from '@contraagent/api';
import { html, nothing, type TemplateResult } from 'lit';
import { outcomeTone, type Tone } from './tone.js';

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

/** The mark of a task's outcome: a waiting task is ◌ too, though muted. */
export const outcomeMark = (o: Outcome): Mark | null => (o === 'waiting' ? 'pending' : markOf(outcomeTone(o)));

export interface StatusOptions {
  title?: string | null;
  /** The mark; `markOf(tone)` when not given, null for none. */
  mark?: Mark | null;
  /** More classes on the element. */
  cls?: string;
}

const attrs = (tone: Tone, o: StatusOptions) => ({
  tone: tone || nothing,
  mark: (o.mark === undefined ? markOf(tone) : o.mark) ?? nothing,
  title: o.title || nothing,
});

/** A status as a pill (`.pill`): tinted by its tone, a done pill quiet with its ✓. */
export function statusPill(text: unknown, tone: Tone, o: StatusOptions = {}): TemplateResult {
  const a = attrs(tone, o);
  return html`<span class="pill ${o.cls ?? ''}" data-tone=${a.tone} data-mark=${a.mark} title=${a.title}>${text}</span>`;
}

/** A status as a word in a row (`.jstop`: History, Problems, Outputs). */
export function statusWord(text: unknown, tone: Tone, o: StatusOptions = {}): TemplateResult {
  const a = attrs(tone, o);
  return html`<span class="jstop ${o.cls ?? ''}" data-tone=${a.tone} data-mark=${a.mark} title=${a.title}>${text}</span>`;
}

/** A checked file's status as a chip (`.ct-chip`); `text` may hold a count after the word. */
export function statusChip(text: unknown, tone: Tone, o: StatusOptions = {}): TemplateResult {
  const a = attrs(tone, o);
  return html`<span class="ct-chip ${o.cls ?? ''}" data-tone=${a.tone} data-mark=${a.mark} title=${a.title}>${text}</span>`;
}

/** A task's outcome as a pill, in the given words. */
export const outcomePill = (o: Outcome, text: string, title?: string | null): TemplateResult =>
  statusPill(text, outcomeTone(o), { title, mark: outcomeMark(o) });
