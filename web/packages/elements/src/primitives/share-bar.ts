// A share bar: one whole, as a single 100% bar of its parts, side by side.
import { css, html, nothing, type TemplateResult } from 'lit';
import { styleMap } from 'lit/directives/style-map.js';

export interface SharePart {
  /** What tells the part apart (a stable key). */
  id: string;
  /** The part's name, the same as in the legend beside the bar. */
  label: string;
  /** Its amount; a part of 0 draws nothing. */
  value: number;
  /** Its colour: a CSS colour or `var(...)`, the same as its swatch in the legend. */
  color: string;
  /** The amount in words, for the tooltip (`$0.12`, `1.2k`). */
  text?: string;
}

export interface ShareBarOptions {
  /** The bar's accessible name. */
  label?: string;
  /** The smallest share (0..1) whose part is named under the bar; default 0.15. */
  labelAt?: number;
  /** Names the parts under the bar; default true. False when a table beside the bar names each part with its share. */
  names?: boolean;
}

/**
 * Whole percents (0..100) for `values`, summing to exactly 100 when any is above 0
 * (the largest remainders round up); all 0 when none is.
 */
export function wholePercents(values: readonly number[]): number[] {
  const total = values.reduce((a, v) => a + Math.max(v, 0), 0);
  if (!total) return values.map(() => 0);
  const exact = values.map((v) => (100 * Math.max(v, 0)) / total);
  const out = exact.map(Math.floor);
  const order = exact.map((x, i) => [x - Math.floor(x), i] as const).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (let k = 0, left = 100 - out.reduce((a, v) => a + v, 0); k < left; k++) out[order[k]![1]]! += 1;
  return out;
}

/** A share in words: `42%`, `<1%` for a part above 0 that rounds to 0. */
export const sharePercent = (pct: number, value: number): string => (pct === 0 && value > 0 ? '<1%' : `${pct}%`);

/**
 * The parts of a whole as one bar (`.share`, part `share`): each part a segment as
 * wide as its share, 2px apart, in the order given (so a part keeps its place when
 * the amounts change), with its name and share under it when it is wide enough
 * (unless `names` is false).
 * Hovering or focusing a segment shows its name, share and amount; each segment is
 * a tab stop with the same words. Name every part beside the bar too (a legend or a
 * table): a colour alone never says which part is which.
 */
export function shareBar(parts: readonly SharePart[], o: ShareBarOptions = {}): TemplateResult {
  const shown = parts.filter((p) => p.value > 0);
  const pcts = wholePercents(shown.map((p) => p.value));
  const total = shown.reduce((a, p) => a + p.value, 0);
  const labelAt = o.labelAt ?? 0.15;
  const words = (p: SharePart, i: number) => [p.label, sharePercent(pcts[i]!, p.value), p.text].filter(Boolean).join(' | ');
  return html`<div class="share" part="share">
    <div class="share-bar" role="list" aria-label=${o.label || nothing}>
      ${shown.map(
        (p, i) => html`<span class="share-seg" role="listitem" tabindex="0" aria-label=${words(p, i)} data-id=${p.id}
          data-edge=${i === 0 ? 'start' : i === shown.length - 1 ? 'end' : nothing}
          style=${styleMap({ flexGrow: String(p.value / total), background: p.color })}
          ><span class="share-tip" aria-hidden="true">${words(p, i)}</span></span>`,
      )}
    </div>
    ${o.names === false
      ? nothing
      : html`<div class="share-names" aria-hidden="true">
          ${shown.map(
            (p, i) => html`<span style=${styleMap({ flexGrow: String(p.value / total) })}
              >${p.value / total >= labelAt ? html`<b>${p.label}</b> ${sharePercent(pcts[i]!, p.value)}` : nothing}</span>`,
          )}
        </div>`}
  </div>`;
}

export const shareBarStyles = css`
  .share { display: grid; gap: 6px; }
  .share-bar, .share-names { display: flex; gap: 2px; min-width: 0; }
  .share-bar { height: 14px; }
  .share-seg { position: relative; flex: 0 1 0; min-width: 3px; height: 100%; border-radius: 1px; cursor: default; outline-offset: 2px; }
  .share-seg[data-edge='start'] { border-radius: 4px 1px 1px 4px; }
  .share-seg[data-edge='end'] { border-radius: 1px 4px 4px 1px; }
  .share-seg:only-child { border-radius: 4px; }
  /* A hit area taller than the bar. */
  .share-seg::before { content: ''; position: absolute; inset: -6px 0; }
  .share-seg:hover, .share-seg:focus-visible { box-shadow: 0 0 0 2px var(--card); }
  .share-tip { display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); z-index: 2;
    padding: 4px 8px; border-radius: var(--radius-sm); background: var(--raise); border: 1px solid var(--line2); box-shadow: 0 4px 14px var(--shadow);
    color: var(--text); font-size: var(--font-size-sm); white-space: nowrap; pointer-events: none; }
  .share-seg[data-edge='start'] .share-tip, .share-seg:only-child .share-tip { left: 0; transform: none; }
  .share-seg[data-edge='end'] .share-tip { left: auto; right: 0; transform: none; }
  .share-seg:hover .share-tip, .share-seg:focus-visible .share-tip { display: block; }
  .share-names span { flex: 0 1 0; min-width: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: var(--font-size-sm); color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .share-names b { font-weight: 600; color: var(--text-2); }
`;
