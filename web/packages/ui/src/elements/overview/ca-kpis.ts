import { deriveRun, type JournalRow, type Plan } from '@contraagent/api';
import { localized } from '@lit/localize';
import { LitElement, css, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@contraagent/elements/tiles/define';
import { kpiAction, kpiTiles } from '../../adapters/kpi-tiles.js';
import { emit } from '../../core/events.js';

/**
 * The run in numbers, as `<cae-stat-tiles>`: tasks and how they ended (with
 * `plan`; from the journal alone otherwise), attempts, failed attempts, agent
 * time, retries, corrections and model switches (`kpiTiles`). The parts of
 * `<cae-stat-tiles>` are its own: a page styles them as `ca-kpis::part(tile)`.
 *
 * @fires ca-navigate - `{tab: 'journal', stop}`: the history filtered to what a tile counts (`bad`, `invalid_input`, `retried`, `fixup`)
 * @fires ca-open-task - `{key}`: the one task a tile counts
 * @csspart tiles - the grid of tiles
 * @csspart tile - each tile (`data-id` is its id, `data-tone` its tone)
 * @csspart label - a tile's label
 * @csspart value - a tile's value
 * @csspart sub - each line under the value
 * @csspart action - a tile's link
 */
@customElement('ca-kpis')
@localized()
export class CaKpis extends LitElement {
  static override styles = css`
    :host { display: block; }
  `;

  @property({ attribute: false }) journal: JournalRow[] = [];
  /** The scheduled tasks; without it, tasks are counted from the journal. */
  @property({ attribute: false }) plan: Plan = { nodes: [], groups: [] };

  private readonly onAction = (e: CustomEvent<{ action: string }>): void => {
    e.stopPropagation();
    const a = kpiAction(e.detail.action);
    if ('key' in a) emit(this, 'ca-open-task', { key: a.key });
    else emit(this, 'ca-navigate', { tab: 'journal', stop: a.stop });
  };

  override render() {
    return html`<cae-stat-tiles exportparts="tiles, tile, label, value, sub, action" .tiles=${kpiTiles(this.journal, deriveRun(this.journal, this.plan))} @cae-action=${this.onAction}></cae-stat-tiles>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-kpis': CaKpis;
  }
}
