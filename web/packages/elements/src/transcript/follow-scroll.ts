// Following the end of a growing list: while the reader is at the bottom, new
// content scrolls into view; once they scroll up, it stays where they are.
import type { TranscriptScroll } from './types.js';

/** Within this many pixels of the bottom, the list follows new content. */
const STICK_PX = 60;
/** How long a restored position waits for the content to grow tall enough. */
const RESTORE_GIVE_UP_MS = 4000;

export class FollowScroll {
  /** The reader is at the bottom: new content scrolls into view. */
  stick = true;
  /** The position was restored (or there was none to restore): from now on it is remembered. */
  restored = false;
  /** The last position, kept while the list is hidden. */
  lastTop = 0;

  constructor(private readonly scroller: () => HTMLElement | null | undefined) {}

  toBottom(smooth = false): void {
    const sc = this.scroller();
    if (!sc) return;
    if (smooth) sc.scrollTo({ top: sc.scrollHeight, behavior: 'smooth' });
    else sc.scrollTop = sc.scrollHeight;
  }

  /** Reads the reader's position after a scroll; the position to remember, or null when there is none (hidden). */
  read(): TranscriptScroll | null {
    const sc = this.scroller();
    if (!sc || !sc.clientHeight) return null; // hidden: no position to keep
    this.stick = sc.scrollHeight - sc.scrollTop - sc.clientHeight < STICK_PX;
    this.lastTop = sc.scrollTop;
    return { stick: this.stick, top: Math.round(sc.scrollTop) };
  }

  /** Puts the reader back at `saved` (the end when undefined), waiting while the content is still shorter; `stale` stops it. */
  async restore(saved: TranscriptScroll | undefined, stale: () => boolean): Promise<void> {
    const sc = this.scroller();
    if (!saved || saved.stick || !sc) {
      this.stick = true;
      this.toBottom();
    } else {
      this.stick = false;
      const until = performance.now() + RESTORE_GIVE_UP_MS;
      await new Promise<void>((done) => {
        const step = () => {
          const max = sc.scrollHeight - sc.clientHeight;
          sc.scrollTop = Math.min(saved.top, max);
          if (max >= saved.top || performance.now() > until || stale()) done();
          else requestAnimationFrame(step);
        };
        step();
      });
      this.lastTop = sc.scrollTop;
    }
    this.restored = true;
  }

  /** Shown again after being hidden: back at the end, or where the reader was. */
  reshow(): void {
    const sc = this.scroller();
    if (!sc) return;
    if (this.stick) this.toBottom();
    else sc.scrollTop = this.lastTop;
  }
}
