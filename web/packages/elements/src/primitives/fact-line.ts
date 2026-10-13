// A row of facts ("6 tasks", "6 attempts") in a narrow box: each fact is kept
// whole, and the line breaks between facts. Use it inside `.words`.
import { html, nothing, type TemplateResult } from 'lit';
import { toneAttr, type Tone } from '../core/tone.js';

/** A fact in a row of facts; a status fact has a tone. */
export interface Fact {
  text: string;
  tone?: Tone;
}

/**
 * `facts`, each in a `.f` span that does not break inside unless it is wider than
 * the box, separated by `sep`. A fact with a tone is in its status colour
 * (`.tone-text`); an empty fact is left out.
 */
export function factLine(facts: readonly (string | Fact)[], sep = ' | '): TemplateResult | typeof nothing {
  const shown = facts.filter((f) => (typeof f === 'string' ? f : f.text));
  return shown.length
    ? html`${shown.map((f, i) =>
        typeof f === 'string'
          ? html`${i ? sep : ''}<span class="f">${f}</span>`
          : html`${i ? sep : ''}<span class="f tone-text" data-tone=${toneAttr(f.tone)}>${f.text}</span>`,
      )}`
    : nothing;
}
