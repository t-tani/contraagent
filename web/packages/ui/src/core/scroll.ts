// A scroller that comes back where the reader left it. The position is
// remembered in a memory (`memory.ts`: the history entry, or an embedded
// monitor's own). It is a position in the whole content, which arrives over the
// network, in parts on a slow connection or machine: restoring holds it until all
// of the content has arrived and is tall enough to scroll there.
import { pageMemory, type Memory } from './memory.js';

/** How long restoring goes on once the content is complete: for what a view draws later (its own fetch), or content now shorter. */
const GIVE_UP_MS = 6000;
const INPUT_EVENTS = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;

export class ScrollMemory {
  private el: HTMLElement | null = null;
  private frame = 0;
  private restoring = false;
  private target = 0;
  /** When restoring ends at the latest: counted from when the content is complete, null before. */
  private until: number | null = null;

  constructor(
    private readonly id: string,
    /** Where the position is remembered: read at each use. */
    private readonly memory: () => Memory = () => pageMemory,
  ) {}

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

  /**
   * Go back to the remembered position, to the top when none is remembered. The
   * position is held until `update` reports the content complete and it is tall
   * enough, or until the reader scrolls.
   */
  restore(): void {
    const el = this.el;
    if (!el) return;
    this.cancel();
    const target = this.memory().recall<number>(this.id) ?? 0;
    if (target <= 0) {
      el.scrollTop = 0;
      return;
    }
    this.target = target;
    this.until = null;
    this.restoring = true;
    // Rows that arrive above the position (a list with the newest first) would move it
    // down by their height (the browser's scroll anchoring); the position is one in the
    // whole list, so it stays.
    el.style.overflowAnchor = 'none';
    for (const t of INPUT_EVENTS) el.addEventListener(t, this.cancel, { passive: true, once: true });
    this.place();
  }

  /** The content changed, `complete` once all of it has arrived: while restoring, the position is set again at the next frame. */
  update(complete: boolean): void {
    if (!this.restoring) return;
    if (complete) this.until ??= performance.now() + GIVE_UP_MS;
    this.frame ||= requestAnimationFrame(this.step);
  }

  /** Start at the top (a new place). */
  reset(): void {
    this.cancel();
    if (this.el) this.el.scrollTop = 0;
  }

  /** Scroll as near the position as the content allows; true once restoring is over. */
  private place(): boolean {
    const el = this.el!;
    const max = el.scrollHeight - el.clientHeight;
    el.scrollTop = Math.min(this.target, max);
    // While the content is still arriving, each update places it again.
    return this.until !== null && (max >= this.target || performance.now() > this.until);
  }

  private readonly step = (): void => {
    this.frame = 0;
    if (!this.restoring || !this.el) return;
    if (this.place()) return this.cancel();
    if (this.until !== null) this.frame = requestAnimationFrame(this.step);
  };

  private readonly cancel = (): void => {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!this.restoring) return;
    this.restoring = false;
    if (this.el) this.el.style.overflowAnchor = '';
    for (const t of INPUT_EVENTS) this.el?.removeEventListener(t, this.cancel);
  };

  private readonly onScroll = (): void => {
    if (!this.restoring && this.el) this.memory().remember(this.id, Math.round(this.el.scrollTop));
  };
}
