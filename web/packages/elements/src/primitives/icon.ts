// Small icons: a glyph or a template, registered by name.
import { html, nothing, type TemplateResult } from 'lit';

const icons = new Map<string, TemplateResult | string>();

/** Registers an icon under `name` (a later registration replaces it). */
export function registerIcon(name: string, template: TemplateResult | string): void {
  icons.set(name, template);
}

export interface IconOptions {
  /** Classes on the icon's element. */
  cls?: string;
}

/**
 * The icon `name` (the name itself when nothing is registered under it, so a
 * glyph works as its own name). Without a label it is hidden from screen
 * readers; with one, the label is its tooltip and what a screen reader reads.
 */
export function icon(name: string, label?: string | null, o: IconOptions = {}): TemplateResult {
  const glyph = icons.get(name) ?? name;
  return label
    ? html`<span class=${o.cls || nothing} part="icon" title=${label}><span aria-hidden="true">${glyph}</span><span class="sr">${label}</span></span>`
    : html`<span class=${o.cls || nothing} part="icon" aria-hidden="true">${glyph}</span>`;
}
