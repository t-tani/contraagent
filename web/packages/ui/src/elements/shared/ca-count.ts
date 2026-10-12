import { LitElement, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

const reducedMotion = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** A number that counts up (or down) to its new value when it changes. */
@customElement('ca-count')
export class CaCount extends LitElement {
  @property({ type: Number }) value = 0;
  @state() private shown = 0;
  private frame = 0;

  protected override createRenderRoot() {
    return this;
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (!changed.has('value')) return;
    const from = this.shown;
    const to = this.value;
    cancelAnimationFrame(this.frame);
    if (reducedMotion() || from === to || !Number.isFinite(to) || !this.isConnected) {
      this.shown = to;
      return;
    }
    const t0 = performance.now();
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / 700);
      this.shown = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    cancelAnimationFrame(this.frame);
    this.shown = this.value;
  }

  override render() {
    return String(this.shown);
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'ca-count': CaCount;
  }
}
