// A row of facts (`facts()`: "6 tasks | 6 attempts") in a narrow box: each fact is
// kept whole, and the line breaks between facts. Use it inside `.words`.
import { html, nothing, type TemplateResult } from 'lit';

/** The facts of `line`, each in a `.f` span that does not break inside unless it is wider than the box. */
export function factLine(line: string): TemplateResult | typeof nothing {
  return line ? html`${line.split(' | ').map((f, i) => html`${i ? ' | ' : ''}<span class="f">${f}</span>`)}` : nothing;
}
