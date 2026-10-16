// The "how it works" scene (HowItWorks.astro, ./how.css): which stage the reader is
// on, from the scroll through the scene's track, read once per frame. It sets the
// figures of the last stage counting up when that stage comes, and, where the
// browser has no scroll-driven animations, data-stage on the track and the rail's
// progress (--how-p), and data-sub (the state within the stage: the check stage has three),
// which ./how.css turns into the same states by transitions.
// The scene is pinned only while its words and steps fit the screen: in a wider font,
// or on a short screen, they may not, and then the scene is .how-flat (its stages one
// after another, as with reduced motion). Measured with the scene pinned, on load and
// when the screen changes size.
// Narrow screens, reduced motion and a flat scene: the figures are set when they come into view.

const track = document.querySelector<HTMLElement>('[data-how]');
const counts = [...document.querySelectorAll<HTMLElement & { value: number }>('.how cae-count[data-value]')];
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const wide = matchMedia('(min-width: 64rem)');
/** The least room (px) above and below the pinned scene's words and steps. */
const ROOM = 8;
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
    const scene = track.closest<HTMLElement>('.how');
    const pin = track.querySelector<HTMLElement>('.how-pin');
    const left = track.querySelector<HTMLElement>('.how-left');
    let flat = false;
    /** Pinned, unless the words and steps are taller than the pinned scene (a forced layout, nothing painted between). */
    const fit = (): void => {
      if (!scene || !pin || !left) return;
      scene.classList.remove('how-flat');
      flat = wide.matches && left.offsetHeight + 2 * ROOM > pin.clientHeight;
      scene.classList.toggle('how-flat', flat);
    };
    let top = 0;
    let span = 1;
    const measure = (): void => {
      fit();
      // Offsets, not boxes: nothing this sets moves the track.
      top = 0;
      for (let el: HTMLElement | null = track; el; el = el.offsetParent as HTMLElement | null) top += el.offsetTop;
      span = Math.max(1, track.offsetHeight - window.innerHeight);
    };
    let queued = false;
    let stage = -1;
    const frame = (): void => {
      queued = false;
      if (!wide.matches || flat) return;
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
    const again = (): void => {
      measure();
      queue();
    };
    addEventListener('resize', again);
    // A font that comes late changes the words' height.
    void document.fonts?.ready.then(again);
    // Narrow screens and a flat scene: the figures count up as they come into view.
    const figs = track.querySelector('.run-figs');
    if (figs)
      new IntersectionObserver(([e]) => {
        if (e?.isIntersecting && (!wide.matches || flat)) count();
      }).observe(figs);
  }
}

export {};
