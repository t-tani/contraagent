// A scroller that comes back where the reader left it. The position is
// remembered in the history entry (`memory.ts`); restoring waits until the
// content, which arrives over the network, is tall enough to scroll there.
import { recall, remember } from './memory.js';

const GIVE_UP_MS = 6000;
const INPUT_EVENTS = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;

export class ScrollMemory {
  private el: HTMLElement | null = null;
  private frame = 0;
  private restoring = false;

  constructor(private readonly id: string) {}

  attach(el: HTMLElement): void {
    if (this.el === el) return;
    this.detach();
    this.el = el;
    el.addEventListener('scroll', this.onScroll, { passive: true });
  }

  detach(): void {
    this.cancel();
    this.el?.removeEventListener('scroll', this.onScroll);
    this.el = null;
  }

  /** Go back to the remembered position, as soon as the content allows; to the top when none is remembered. */
  restore(): void {
    const el = this.el;
    if (!el) return;
    this.cancel();
    const target = recall<number>(this.id) ?? 0;
    if (target <= 0) {
      el.scrollTop = 0;
      return;
    }
    const until = performance.now() + GIVE_UP_MS;
    this.restoring = true;
    for (const t of INPUT_EVENTS) el.addEventListener(t, this.cancel, { passive: true, once: true });
    const step = () => {
      const max = el.scrollHeight - el.clientHeight;
      el.scrollTop = Math.min(target, max);
      if (max >= target || performance.now() > until) return this.cancel();
      this.frame = requestAnimationFrame(step);
    };
    step();
  }

  /** Start at the top (a new place). */
  reset(): void {
    this.cancel();
    if (this.el) this.el.scrollTop = 0;
  }

  private readonly cancel = (): void => {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!this.restoring) return;
    this.restoring = false;
    for (const t of INPUT_EVENTS) this.el?.removeEventListener(t, this.cancel);
  };

  private readonly onScroll = (): void => {
    if (!this.restoring && this.el) remember(this.id, Math.round(this.el.scrollTop));
  };
}
