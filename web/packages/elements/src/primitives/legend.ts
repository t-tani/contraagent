// A legend: a swatch and a word per entry.
import { css, html, nothing, type TemplateResult } from 'lit';
import { styleMap } from 'lit/directives/style-map.js';
import { toneAttr, type Tone } from '../core/tone.js';

/** The shape of a status mark: done round, failed square, not started hatched, waiting a ring. */
export type MarkShape = 'round' | 'square' | 'hatched' | 'ring';

export interface LegendItem {
  label: string;
  /** The swatch's colour: a CSS colour or `var(...)`. */
  swatch?: string;
  /** The swatch's status colour (instead of `swatch`). */
  tone?: Tone;
  shape?: MarkShape;
  /** Classes on the swatch (`<i>`), for a swatch the host's styles draw. */
  cls?: string;
  /** What to draw instead of the swatch: an icon, a mark, a line. */
  icon?: unknown;
  /** Hidden from screen readers: the item names what the reader reaches another way. */
  decorative?: boolean;
}

export interface LegendOptions {
  /** The legend's accessible name. */
  label?: string;
  /** More classes on the legend. */
  cls?: string;
}

/** The swatch of an entry; none for an entry that is only a word (a note at the end). */
const swatch = (it: LegendItem): unknown =>
  it.icon ??
  (it.swatch || it.tone || it.shape || it.cls
    ? html`<i class=${it.cls || nothing} data-tone=${toneAttr(it.tone)} data-shape=${it.shape ?? nothing}
        style=${it.swatch ? styleMap({ background: it.swatch }) : nothing}></i>`
    : nothing);

/** A row of entries (`.legend`, part `legend`), each its swatch and its word, as a list. */
export function legend(items: readonly LegendItem[], o: LegendOptions = {}): TemplateResult {
  return html`<div class="legend ${o.cls ?? ''}" part="legend" role="list" aria-label=${o.label || nothing}>
    ${items.map((it) => html`<span role="listitem" aria-hidden=${it.decorative ? 'true' : nothing}>${swatch(it)}${it.label}</span>`)}
  </div>`;
}

export const legendStyles = css`
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--text-muted); }
  .legend > span { white-space: nowrap; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
  .legend i[data-tone] { background: var(--tone); }
  .legend i[data-shape='round'] { border-radius: 50%; }
  .legend i[data-shape='square'] { border-radius: 2px; }
  .legend i[data-shape='ring'] { background: none; border-radius: 50%; box-shadow: inset 0 0 0 1.5px var(--tone, var(--line2)); }
  .legend i[data-shape='hatched'] { border-radius: 2px; background: repeating-linear-gradient(135deg, transparent 0 2px, var(--tone, var(--line2)) 2px 3px); }
`;
