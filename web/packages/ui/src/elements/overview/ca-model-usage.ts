import { modelMeasures, type ModelMeasure, type ModelUsage } from '@contraagent/api';
import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { styleMap } from 'lit/directives/style-map.js';
import '@contraagent/elements/segmented/define';
import { shareBar, shareBarStyles } from '@contraagent/elements/primitives';
import { base } from '@contraagent/elements/styles';
import { modelRows, shareParts } from '../../adapters/model-shares.js';
import { measureLabel, measureText, measureTip } from '../../words/models.js';

const COLUMNS: readonly ModelMeasure[] = ['cost', 'tokens', 'time', 'sessions'];

/**
 * What each model was used for in a run (`Plan.models`): the share of each model in
 * the chosen measure (cost, tokens, time or agent sessions) as one bar, and a table
 * of every model with its share and every measure. A model keeps its colour, and
 * its place, in the order it was first used, whatever the measure; past six models
 * the later ones share one colour as "Other models".
 */
@customElement('ca-model-usage')
@localized()
export class CaModelUsage extends LitElement {
  static override styles = [
    base,
    shareBarStyles,
    css`
      :host { display: block; }
      .head { display: flex; justify-content: flex-end; margin-bottom: 10px; overflow-x: auto; }
      .head cae-segmented { flex: none; }
      .wrap { overflow-x: auto; margin-top: 14px; }
      /* The columns as wide as their contents, so a model's figures sit near its name. */
      table { border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
      th { font-weight: 500; color: var(--text-muted); text-align: right; padding: 0 0 6px 28px; white-space: nowrap; border-bottom: 1px solid var(--line); }
      th:first-child { text-align: left; padding-left: 0; }
      th.on { color: var(--text); font-weight: 600; }
      td { padding: 7px 0 7px 28px; text-align: right; white-space: nowrap; color: var(--text-2); vertical-align: top; }
      tr + tr td { border-top: 1px solid var(--line); }
      td:first-child { text-align: left; padding-left: 0; }
      td.on { color: var(--text); }
      td.share { color: var(--text); font-weight: 600; }
      .model { display: grid; grid-template-columns: 10px max-content; column-gap: 8px; align-items: baseline; }
      .model i { width: 10px; height: 10px; border-radius: 3px; align-self: center; }
      .model b { font-family: var(--mono); font-weight: 500; color: var(--text); }
      .model small { grid-column: 2; font-size: 11px; color: var(--text-muted); }
    `,
  ];

  @property({ attribute: false }) models: readonly ModelUsage[] = [];
  /** The measure the bar and the share column show; the first one with a value when unset or empty. */
  @state() private measure: ModelMeasure | '' = '';

  private chosen(): ModelMeasure {
    const have = modelMeasures(this.models);
    return this.measure && have.includes(this.measure) ? this.measure : (have[0] ?? 'sessions');
  }

  override render() {
    if (!this.models.length) return html`<div class="meta">${msg('No agent sessions')}</div>`;
    const measure = this.chosen();
    const have = modelMeasures(this.models);
    const rows = modelRows(this.models, measure);
    return html`${have.length > 1
        ? html`<div class="head">
            <cae-segmented label=${msg('Measure')} .value=${measure}
              .options=${have.map((m) => ({ value: m, label: measureLabel(m), title: measureTip(m) }))}
              @cae-change=${(e: CustomEvent<{ value: string }>) => (this.measure = e.detail.value as ModelMeasure)}></cae-segmented>
          </div>`
        : nothing}
      ${shareBar(shareParts(this.models, measure), { label: measureLabel(measure) })}
      <div class="wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">${msg('Model')}</th>
              <th scope="col" class="on" title=${measureLabel(measure)}>${msg('Share')}</th>
              ${COLUMNS.map((c) => html`<th scope="col" class=${c === measure ? 'on' : nothing} title=${measureTip(c)}>${measureLabel(c)}</th>`)}
              <th scope="col">${msg('API calls')}</th>
            </tr>
          </thead>
          <tbody>
            ${repeat(
              rows,
              (r) => r.id,
              (r) => html`<tr>
                <td>
                  <span class="model"><i style=${styleMap({ background: r.colour })}></i><b>${r.usage.model}</b><small>${r.usage.agent}</small></span>
                </td>
                <td class="share">${r.share}</td>
                ${COLUMNS.map((c) => html`<td class=${c === measure ? 'on' : nothing}>${measureText(r.usage, c)}</td>`)}
                <td>${r.usage.calls ?? 0}</td>
              </tr>`,
            )}
          </tbody>
        </table>
      </div>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-model-usage': CaModelUsage;
  }
}
