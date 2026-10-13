// A row of facts (`factList()`: "6 tasks", "6 attempts") in a narrow box: each fact is
// kept whole, and the line breaks between facts. Use it inside `.words`.
import { html, nothing, type TemplateResult } from 'lit';

/** `facts`, each in a `.f` span that does not break inside unless it is wider than the box, separated by ` | `. */
export function factLine(facts: readonly string[]): TemplateResult | typeof nothing {
  return facts.length ? html`${facts.map((f, i) => html`${i ? ' | ' : ''}<span class="f">${f}</span>`)}` : nothing;
}
