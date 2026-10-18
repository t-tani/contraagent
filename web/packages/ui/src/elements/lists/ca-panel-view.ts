import { typedBody, type PanelBody, type PanelInfo } from '@contraagent/api';
import { localized, msg, str } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { base } from '@contraagent/elements/styles';
import '@contraagent/elements/json-tree/define';
import './ca-panel-body.js';

/** A view the pipeline added (`monitor.Panel`), updating live: a typed body as tiles, a table and charts, any other as a JSON tree. */
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
  @property({ attribute: false }) data: PanelBody | undefined;
  /** Where the monitor is served: an embedded page's path is relative to it. */
  @property({ attribute: 'base-url' }) baseUrl = '';

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
      ${typedBody(this.data) ? html`<ca-panel-body .body=${this.data} base-url=${this.baseUrl} label=${info?.title || this.name}></ca-panel-body>` : html`<cae-json-tree .value=${this.data}></cae-json-tree>`}
    </section>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-panel-view': CaPanelView;
  }
}
