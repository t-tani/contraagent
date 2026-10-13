import { localized, msg } from '@lit/localize';
import { LitElement, css, html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { markInstructions, mdFile, splitTelemetry } from '../../lib/markdown.js';
import { base, prose } from '../../styles/index.js';

/**
 * A markdown text with a rendered/source switch. A prompt's leading TELEMETRY
 * line (which run and task it belongs to) is shown apart, so the prose reads as prose.
 */
@customElement('ca-markdown')
@localized()
export class CaMarkdown extends LitElement {
  static override styles = [
    base,
    prose,
    css`
      :host { display: block; }
      .bar { display: flex; justify-content: flex-end; margin-bottom: 4px; }
    `,
  ];

  @property() text = '';
  /** `instructions`: pick out `$variables` and `{{contract}}`. */
  @property() mark: '' | 'instructions' = '';
  @state() private source = false;

  override render() {
    const { telemetry, body } = splitTelemetry(this.text);
    const rendered = mdFile(body, this.mark === 'instructions' ? markInstructions : undefined);
    return html`<div class="bar">
        <button type="button" class="df-tog" @click=${() => (this.source = !this.source)}>
          ${this.source ? msg('Show rendered') : msg('Show source')}</button>
      </div>
      ${this.source
        ? html`<pre class="df-text">${this.text}</pre>`
        : html`${telemetry ? html`<div class="md-tele jmono">${telemetry}</div>` : nothing}${unsafeHTML(rendered)}`}`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-markdown': CaMarkdown;
  }
}
