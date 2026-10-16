// Following the end of a growing list: a smooth glide to the end is not the
// reader leaving it; a move up is.
import { describe, expect, it } from 'vitest';
import { FollowScroll } from './follow-scroll.js';

/** A scroller of `height` content in a 200 px box, at `top`. */
function scroller(height: number) {
  const sc = { scrollHeight: height, clientHeight: 200, scrollTop: 0, scrollTo: (o: { top: number }) => void o };
  return sc;
}

describe('FollowScroll', () => {
  it('keeps following while a smooth scroll to the end is under way', () => {
    const sc = scroller(1000);
    const f = new FollowScroll(() => sc as unknown as HTMLElement);
    sc.scrollTop = 800;
    f.read();
    sc.scrollHeight = 1400; // new content below
    f.toBottom(true);
    sc.scrollTop = 900; // a step of the glide
    expect(f.read()?.stick).toBe(true);
    sc.scrollTop = 1200; // at the end: the glide is over
    expect(f.read()?.stick).toBe(true);
  });

  it('stops following when the reader scrolls up during the glide', () => {
    const sc = scroller(1400);
    const f = new FollowScroll(() => sc as unknown as HTMLElement);
    sc.scrollTop = 900;
    f.read();
    f.toBottom(true);
    sc.scrollTop = 1000;
    f.read();
    sc.scrollTop = 600; // the reader's wheel, up
    expect(f.read()?.stick).toBe(false);
    sc.scrollTop = 700;
    expect(f.read()?.stick).toBe(false);
  });

  it('without a glide, follows only within reach of the end', () => {
    const sc = scroller(1400);
    const f = new FollowScroll(() => sc as unknown as HTMLElement);
    sc.scrollTop = 900;
    expect(f.read()?.stick).toBe(false);
    sc.scrollTop = 1180;
    expect(f.read()?.stick).toBe(true);
  });
});
