// The "how it works" scene (HowItWorks.astro, ./how.css): which stage the reader is
// on, from the scroll through the scene's track, read once per frame. It sets the
// figures of the last stage counting up when that stage comes, and, where the
// browser has no scroll-driven animations, data-stage on the track and the rail's
// progress (--how-p), and data-sub (the state within the stage: the check stage has three),
// which ./how.css turns into the same states by transitions.
// Narrow screens and reduced motion: the figures are set when they come into view.

const track = document.querySelector<HTMLElement>('[data-how]');
const counts = [...document.querySelectorAll<HTMLElement & { value: number }>('.how cae-count[data-value]')];
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const wide = matchMedia('(min-width: 64rem)');
/** Each stage's share of the scroll through the track, and where each stage ends (0 to 1). */
const weights = (track?.dataset['weights'] ?? '1').split(',').map(Number);
const ends = weights.map((_, k) => weights.slice(0, k + 1).reduce((a, b) => a + b, 0) / weights.reduce((a, b) => a + b, 0));
const stages = weights.length;

let counted = false;
const count = (): void => {
  if (counted) return;
  counted = true;
  for (const c of counts) c.value = Number(c.dataset['value']);
};

if (track) {
  if (reduced.matches) count();
  else {
    const rail = track.querySelector<HTMLElement>('.how-rail-fill');
    const fallback = !CSS.supports('animation-timeline: view()');
    let top = 0;
    let span = 1;
    const measure = (): void => {
      // Offsets, not boxes: nothing this sets moves the track.
      top = 0;
      for (let el: HTMLElement | null = track; el; el = el.offsetParent as HTMLElement | null) top += el.offsetTop;
      span = Math.max(1, track.offsetHeight - window.innerHeight);
    };
    let queued = false;
    let stage = -1;
    const frame = (): void => {
      queued = false;
      if (!wide.matches) return;
      const p = Math.min(1, Math.max(0, (window.scrollY - top) / span));
      const k = Math.min(stages - 1, ends.findIndex((end) => p < end) < 0 ? stages - 1 : ends.findIndex((end) => p < end));
      if (k >= stages - 1 && p > 0) count();
      if (!fallback) return;
      rail?.style.setProperty('--how-p', p.toFixed(4));
      if (k !== stage) {
        stage = k;
        track.dataset['stage'] = String(k);
      }
      // The check stage goes through three states: which one, by a third of its share.
      const from = k ? ends[k - 1] : 0;
      track.dataset['sub'] = String(Math.min(2, Math.floor(((p - from) / (ends[k] - from)) * 3)));
    };
    const queue = (): void => {
      if (!queued) {
        queued = true;
        requestAnimationFrame(frame);
      }
    };
    measure();
    frame();
    addEventListener('scroll', queue, { passive: true });
    addEventListener('resize', () => {
      measure();
      queue();
    });
    // Narrow screens: the figures count up as they come into view.
    const figs = track.querySelector('.run-figs');
    if (figs)
      new IntersectionObserver(([e]) => {
        if (e?.isIntersecting && !wide.matches) count();
      }).observe(figs);
  }
}

export {};
