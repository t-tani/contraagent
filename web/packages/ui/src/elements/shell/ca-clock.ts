import { localized } from '@lit/localize';
import { LitElement } from 'lit';
import { customElement } from 'lit/decorators.js';
import { ClockController } from '@contraagent/elements';
import { getLocale } from '../../core/i18n.js';

/** The wall clock in the header: its own element, so the second tick repaints nothing else. */
@customElement('ca-clock')
@localized()
export class CaClock extends LitElement {
  constructor() {
    super();
    new ClockController(this);
  }
  protected override createRenderRoot() {
    return this;
  }
  override render() {
    return new Date().toLocaleTimeString(getLocale(), { hour12: false });
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-clock': CaClock;
  }
}
