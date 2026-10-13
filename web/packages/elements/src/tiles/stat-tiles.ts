import { LitElement, html, nothing, type PropertyValues, type TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { emit } from '../core/events.js';
import { toneAttr } from '../core/tone.js';
import { factLine } from '../primitives/fact-line.js';
import { markOf } from '../primitives/pill.js';
import { base } from '../styles/index.js';
import { statTilesStyles } from './styles.js';
import type { StatTile } from './types.js';

const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/**
 * Figures as a grid of tiles: each its label, its value (a number counts up in
 * `<cae-count>`), the lines of facts under it and a link. A tile whose number
 * changes bumps, unless `bump` is off or the reader asks for reduced motion.
 *
 * Its look: `columns` (fewer on a narrow screen: 4 below 1150px, 2 below
 * 700px), `--cae-stat-tiles-gap` and the parts.
 *
 * @tagname cae-stat-tiles
 * @fires cae-action - `{id, action}`: a tile's link, by the tile's id and the action's id
 * @csspart tiles - the grid
 * @csspart tile - each tile (`data-id` is its id, `data-tone` its tone)
 * @csspart label - a tile's label
 * @csspart value - a tile's value
 * @csspart sub - each line under the value
 * @csspart action - a tile's link
 */
export class CaeStatTiles extends LitElement {
  static override styles = [base, statTilesStyles];

  @property({ attribute: false }) tiles: readonly StatTile[] = [];
  /** Tiles per row on a wide screen. */
  @property({ type: Number }) columns = 5;
  /** A tile whose number changes bumps. */
  @property({ type: Boolean }) bump = true;

  /** The last number each tile showed. */
  private readonly prev = new Map<string, number>();
  private changed: string[] = [];

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (!changed.has('tiles')) return;
    for (const t of this.tiles) {
      if (typeof t.value !== 'number') continue;
      if ((this.prev.get(t.id) ?? 0) !== t.value) this.changed.push(t.id);
      this.prev.set(t.id, t.value);
    }
  }

  override render() {
    return html`<div class="tiles" part="tiles" style=${this.columns === 5 ? nothing : `--cae-stat-tiles-columns:${this.columns}`}>
      ${repeat(this.tiles, (t) => t.id, (t) => this.tile(t))}
    </div>`;
  }

  private tile(t: StatTile): TemplateResult {
    const tone = t.tone ?? 'neutral';
    return html`<div class="tile" part="tile" data-tone=${toneAttr(tone)} data-id=${t.id} title=${t.tip ?? nothing}>
      <div class="label words" part="label" data-mark=${markOf(tone) ?? nothing}>${t.label}</div>
      <div class="value" part="value">${typeof t.value === 'number' ? html`<cae-count .value=${t.value}></cae-count>` : t.value}</div>
      ${(t.sub ?? []).map((line) => html`<div class="sub words" part="sub">${factLine(line)}</div>`)}
      ${t.action
        ? html`<div class="action words"><a class="lnk" part="action" href="#" @click=${(e: Event) => {
            e.preventDefault();
            if (t.action) emit(this, 'cae-action', { id: t.id, action: t.action.id });
          }}>${t.action.label}</a></div>`
        : nothing}
    </div>`;
  }

  protected override updated(): void {
    const ids = this.changed;
    this.changed = [];
    if (!this.bump || reducedMotion()) return;
    for (const tile of this.renderRoot.querySelectorAll<HTMLElement>('.tile')) {
      if (!ids.includes(tile.dataset['id'] ?? '')) continue;
      tile.animate?.(
        [{ transform: 'scale(1)' }, { transform: 'scale(1.04)', boxShadow: '0 0 0 1px var(--line2)', offset: 0.35 }, { transform: 'scale(1)' }],
        { duration: 700, easing: 'cubic-bezier(.2,.8,.2,1)' },
      );
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-stat-tiles': CaeStatTiles;
  }
}
