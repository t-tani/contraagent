// A tone: the status colour a value takes. The names are the token names
// (`--ca-status-<tone>`); `neutral` is the text colour, with no `data-tone`.
// An element shows a tone as `data-tone` (styles/status.ts draws it).
import { nothing } from 'lit';

/** A status colour, or `neutral` for the text colour. */
export type Tone = 'failed' | 'attention' | 'done' | 'running' | 'muted' | 'neutral';

/** Every tone with a status colour (a `data-tone` value): each but `neutral`. */
export const TONES: readonly Exclude<Tone, 'neutral'>[] = ['failed', 'attention', 'done', 'running', 'muted'];

/** The `data-tone` attribute of a tone: none for `neutral` (or no tone). */
export const toneAttr = (tone: Tone | null | undefined): Exclude<Tone, 'neutral'> | typeof nothing =>
  tone && tone !== 'neutral' ? tone : nothing;
