import { typedBody, type PanelBody, type TableBody, type TypedPanelBody } from '@contraagent/api';
import '@contraagent/elements/charts/define';
import '@contraagent/elements/data-table/define';
import '@contraagent/elements/json-tree/define';
import '@contraagent/elements/tiles/define';
import { sortRows, type SortState } from '@contraagent/elements/data-table';
import { base, meterStyles } from '@contraagent/elements/styles';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing, type TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { bodyColumns, bodyTiles, rowTone, type BodyRow } from '../../adapters/panel-body.js';
import { chartStrings, numberText } from '../../words/panels.js';
import { tableStrings } from '../../words/table.js';

/** The look of a table body's cells, inside `<cae-data-table>`. */
const CELLS = [
  meterStyles,
  css`
    caption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    /* a narrow screen scrolls the table sideways rather than cutting every cell */
    tr { column-gap: 12px; padding: 6px 12px; border-bottom: 1px solid var(--line); font-size: 12px; min-width: 560px; }
    th, td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    thead tr { color: var(--text-muted); font-size: 11px; }
    tbody [data-align='end'] { font-variant-numeric: tabular-nums; }
    tbody tr[data-tone='failed'], tbody tr[data-tone='attention'] { box-shadow: inset 2px 0 0 var(--tone); }
  `,
];

/**
 * A pipeline's own view drawn from its typed body (`PanelBody`): tiles, a table, charts,
 * and blocks of them one under another, each under its title (folded when the body says
 * `collapsed`). A body of another shape, inside blocks, is shown as a JSON tree.
 */
@customElement('ca-panel-body')
@localized()
export class CaPanelBody extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .block + .block { margin-top: 18px; }
      h4 { margin: 0 0 8px; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-2); }
      details > summary { cursor: pointer; margin-bottom: 8px; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-2); }
      details:not([open]) > summary { margin-bottom: 0; }
    `,
  ];

  @property({ attribute: false }) body: PanelBody | undefined;

  /** The order of each table's rows, by the table's place in the body. */
  @state() private sorts = new Map<string, SortState>();

  override render() {
    const typed = typedBody(this.body);
    return typed ? this.draw(typed, '0') : html`<cae-json-tree .value=${this.body ?? {}}></cae-json-tree>`;
  }

  /** One body, under its title; `at` is its place in the body, which keeps a table's order. */
  private draw(b: TypedPanelBody, at: string): TemplateResult {
    const inner = this.content(b, at);
    if (!b.title) return html`<div class="block">${inner}</div>`;
    return b.collapsed
      ? html`<details class="block"><summary>${b.title}</summary>${inner}</details>`
      : html`<div class="block"><h4>${b.title}</h4>${inner}</div>`;
  }

  private content(b: TypedPanelBody, at: string): TemplateResult {
    const s = chartStrings();
    switch (b.type) {
      case 'blocks':
        return html`${(b).blocks.map((x, i) => {
          const t = typedBody(x);
          return t ? this.draw(t, `${at}.${i}`) : html`<div class="block"><cae-json-tree .value=${x}></cae-json-tree></div>`;
        })}`;
      case 'tiles':
        return html`<cae-stat-tiles .tiles=${bodyTiles(b.tiles)} .bump=${false}></cae-stat-tiles>`;
      case 'table':
        return this.table(b, at);
      case 'columns':
        return html`<cae-column-chart .label=${b.title ?? ''} .x=${b.x} .series=${b.series} ?stacked=${!!b.stacked}
          .format=${numberText(b.unit)} .strings=${s}></cae-column-chart>`;
      case 'lines':
        return html`<cae-line-chart .label=${b.title ?? ''} .x=${b.x} .series=${b.series} .format=${numberText(b.unit)} .strings=${s}></cae-line-chart>`;
      case 'heatmap':
        return html`<cae-heatmap .label=${b.title ?? ''} .x=${b.x} .y=${b.y} .values=${b.values} .format=${numberText(b.unit)} .strings=${s}></cae-heatmap>`;
      case 'hbars':
        return html`<cae-bar-chart .label=${b.title ?? ''} .bars=${b.bars.map((x) => ({ label: x.label, value: x.value, tone: x.tone ?? undefined }))}
          .format=${numberText(b.unit)} .strings=${s}></cae-bar-chart>`;
      default:
        return html`${nothing}`;
    }
  }

  private table(b: TableBody, at: string): TemplateResult {
    const columns = bodyColumns(b);
    const rows = b.rows as BodyRow[];
    const keys = new Map(rows.map((r, i) => [r, String(i)]));
    const sort = this.sorts.get(at) ?? null;
    const shown = sort ? sortRows(rows, columns, sort) : rows;
    return html`<cae-data-table
      .columns=${columns}
      .rows=${shown}
      .rowKey=${(r: BodyRow) => keys.get(r) ?? ''}
      .rowTone=${rowTone}
      .activatable=${false}
      .sort=${sort}
      .cellStyles=${CELLS}
      .caption=${b.title ?? ''}
      .strings=${tableStrings(msg('No rows'))}
      @cae-sort=${(e: CustomEvent<SortState>) => (this.sorts = new Map(this.sorts).set(at, e.detail))}
    ></cae-data-table>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-panel-body': CaPanelBody;
  }
}
