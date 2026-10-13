import type { JsonObject, PanelInfo } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { base } from '@contraagent/elements/styles';
import '@contraagent/elements/json-tree/define';

/** A view the pipeline added (`monitor.Panel`): its body as a JSON tree, updating live. */
@customElement('ca-panel-view')
@localized()
export class CaPanelView extends LitElement {
  static override styles = [
    base,
    css`
      :host { display: block; }
      .tab-ic { opacity: 1; margin-right: 6px; font-size: 12px; }
      .desc { margin: -4px 0 12px; }
    `,
  ];

  /** The panel's registered name. */
  @property() name = '';
  /** Its title, description and icon from `/api/info`. */
  @property({ attribute: false }) panel: PanelInfo | undefined;
  /** Its body; undefined until the feed has sent it. */
  @property({ attribute: false }) data: JsonObject | undefined;

  override render() {
    if (this.data === undefined) {
      // A panel that /api/info does not list never sends anything: say so instead of loading forever.
      return this.panel
        ? html`<div class="blank"><span class="ic" aria-hidden="true">…</span>${msg('Loading…')}</div>`
        : html`<div class="blank"><span class="ic" aria-hidden="true">▤</span>${msg(str`No custom view named ${this.name}`)}</div>`;
    }
    const info = this.panel;
    return html`<section class="panel">
      <h3><span class="tab-ic" aria-hidden="true">${info?.icon || '▤'}</span>${info?.title || this.name}
        <span class="r">${msg('Custom view')}</span></h3>
      ${info?.description ? html`<div class="meta desc">${info.description}</div>` : nothing}
      <cae-json-tree .value=${this.data}></cae-json-tree>
    </section>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-panel-view': CaPanelView;
  }
}
