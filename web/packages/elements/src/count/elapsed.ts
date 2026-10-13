import { LitElement } from 'lit';
import { property } from 'lit/decorators.js';
import { ClockController } from '../core/clock.js';
import { fmtDur } from '../core/format.js';

/**
 * Time since `since` (epoch ms), ticking every second: `42s`, `3m 05s`, `1h 02m`.
 *
 * @tagname cae-elapsed
 */
export class CaeElapsed extends LitElement {
  @property({ type: Number }) since = 0;

  constructor() {
    super();
    new ClockController(this);
  }

  // Plain text in the light DOM: it takes the font and colour of where it is put.
  protected override createRenderRoot() {
    return this;
  }

  override render() {
    return this.since ? fmtDur((Date.now() - this.since) / 1000) : '';
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'cae-elapsed': CaeElapsed;
  }
}
